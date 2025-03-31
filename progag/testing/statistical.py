from dataclasses import dataclass
import json
import math
from typing import Any

import duckdb
import numpy as np
import pandas as pd
from tqdm import tqdm

from progag.generation import SCORE_BINS, statistical_difference
from server.joint import APMetric


@dataclass
class AGStatistics:
    bins: int

    likelihood: np.ndarray
    impact: np.ndarray
    score: np.ndarray
    risk: np.ndarray

    def compare(self, other: 'AGStatistics') -> dict[APMetric, float]:
        """
        Compares the distributions of the four metrics
        between this object and the other one.
        """
        if self.bins != other.bins:
            raise ValueError("Cannot compare CDFs if the bin sizes differ.")

        return {
            "likelihood": statistical_difference(
                self.likelihood, other.likelihood),
            "impact": statistical_difference(
                self.impact, other.impact),
            "score": statistical_difference(
                self.score, other.score),
            "risk": statistical_difference(
                self.risk, other.risk),
        }

    def write_to(self, path: str):
        """ Writes the statistics to a JSON file. """
        with open(path, 'w+') as o:
            json.dump(self.to_json(), o)

    def to_json(self) -> dict[str, Any]:
        """ Returns the statistics as a JSON object. """
        return {
            "bins": self.bins,
            "likelihood": self.likelihood.tolist(),
            "impact": self.impact.tolist(),
            "score": self.score.tolist(),
            "risk": self.risk.tolist(),
        }

    @staticmethod
    def read_from(path: str) -> 'AGStatistics':
        """ Reads the statistics from a JSON file. """
        with open(path, 'r') as o:
            d = json.load(o)
            return AGStatistics.from_json(d)

    @staticmethod
    def from_json(d: dict[str, Any]) -> 'AGStatistics':
        bins: int = d["bins"]

        likelihood = np.array(d["likelihood"])
        impact = np.array(d["impact"])
        score = np.array(d["score"])
        risk = np.array(d["risk"])

        return AGStatistics(bins, likelihood, impact, score, risk)

    @staticmethod
    def from_gt_db(gt_db_path: str, bin_count: int = SCORE_BINS) -> 'AGStatistics':
        """
        Computes the distributions of the main four metrics,
        likelihood, impact, score and risk from the given
        ground-truth database.

        ## Explanation
        Suppose we have 100 score bins.
        We know our range goes from 0.0 to 10.0.
        Creating a bin that ends at 0.0 makes no sense, so
        every i-th bin will end at i/100 (excluded).

        e.g. Our bins will end at 0.1, 0.2, ..., 9.9, 10.0.
        Since we don't want to overcount, each bin should
        be open on the right, e.g. [1.0, 1.1).

        Since our samples may take the value 10.0, we
        simply put them in the last bin (aka, we count as
        if there were 101 bins, and then merge the last two).
        """
        chunk_size = 1_000_000

        likelihood_tot = np.zeros(bin_count, dtype=np.uint64)
        impact_tot = np.zeros(bin_count, dtype=np.uint64)
        score_tot = np.zeros(bin_count, dtype=np.uint64)
        risk_tot = np.zeros(bin_count, dtype=np.uint64)

        with duckdb.connect(gt_db_path, read_only=True) as db:
            size = (db.query("SELECT COUNT(*) FROM aps").fetchone() or [0])[0]
            print(f"[TEST] Aggregating dataset with {size} APs")
            chunks = int(math.ceil(size / chunk_size))

            # Divide into 1 million chunks.
            for i in tqdm(range(chunks)):
                df = db.query(
                    "SELECT likelihood, impact, score, risk FROM aps "
                    f"OFFSET {i * chunk_size} LIMIT {chunk_size}""").to_df()

                _count_and_accumulate(
                    df, bin_count,
                    likelihood_tot, impact_tot, score_tot, risk_tot
                )

        # Compute the cumulative sum of each PDF.
        likelihood_cum = np.cumsum(likelihood_tot)
        impact_cum = np.cumsum(impact_tot)
        score_cum = np.cumsum(score_tot)
        risk_cum = np.cumsum(risk_tot)

        # Produce the CDF as a list of floats.
        return AGStatistics(
            bin_count,
            likelihood_cum / likelihood_cum[-1],
            impact_cum / impact_cum[-1],
            score_cum / score_cum[-1],
            risk_cum / risk_cum[-1],
        )


@dataclass
class StatAGStatistics:
    iterations: list[AGStatistics]

    def compare(self, gt_distro: AGStatistics) -> list[dict[APMetric, float]]:
        """
        Compares each distribution with the ground truth.
        """
        result: list[dict[APMetric, float]] = []

        # Returns the comparison of each metric over each iteration.
        for it in self.iterations:
            result.append(it.compare(gt_distro))

        return result

    def write_to(self, path: str):
        """ Writes the statistics to a JSON file. """
        with open(path, 'w+') as o:
            json.dump([x.to_json() for x in self.iterations], o)

    @staticmethod
    def read_from(path: str) -> 'StatAGStatistics':
        """ Reads the statistics from a JSON file. """
        with open(path, 'r') as o:
            d = json.load(o)
            stats = [AGStatistics.from_json(x) for x in d]
            return StatAGStatistics(stats)

    @staticmethod
    def from_statag_db(
        db_path: str, bin_count: int = SCORE_BINS
    ) -> 'StatAGStatistics':
        """
        Computes the CDFs of each metric, one per iteration, of
        all paths generated up until that generation.
        """
        stats: list[AGStatistics] = []

        with duckdb.connect(db_path, read_only=True) as db:
            size = (db.query("SELECT COUNT(*) FROM aps").fetchone() or [0])[0]
            last_iter = (
                db.query("SELECT MAX(iteration) FROM aps").fetchone() or [0])[0]
            print("[TEST] Aggregating dataset with "
                  f"{size} paths until iteration {last_iter}")

            likelihood_tot = np.zeros(bin_count, dtype=np.uint64)
            impact_tot = np.zeros(bin_count, dtype=np.uint64)
            score_tot = np.zeros(bin_count, dtype=np.uint64)
            risk_tot = np.zeros(bin_count, dtype=np.uint64)

            for i in tqdm(range(1, last_iter + 1)):
                df = db.query(
                    "SELECT likelihood, impact, score, risk FROM aps "
                    f"WHERE iteration = {i}").to_df()

                _count_and_accumulate(
                    df, bin_count,
                    likelihood_tot, impact_tot, score_tot, risk_tot
                )

                # Compute the cumulative sum of each PDF.
                likelihood_cum = np.cumsum(likelihood_tot)
                impact_cum = np.cumsum(impact_tot)
                score_cum = np.cumsum(score_tot)
                risk_cum = np.cumsum(risk_tot)

                # Add the AGStatistics object to the list
                stats.append(AGStatistics(
                    bin_count,
                    likelihood_cum / likelihood_cum[-1],
                    impact_cum / impact_cum[-1],
                    score_cum / score_cum[-1],
                    risk_cum / risk_cum[-1],
                ))

        return StatAGStatistics(stats)


def _count_and_accumulate(
    df: pd.DataFrame,
    bin_count: int,
    likelihood_tot: np.ndarray,
    impact_tot: np.ndarray,
    score_tot: np.ndarray,
    risk_tot: np.ndarray
):
    """
    Counts the number of elements in the given DataFrame and
    accumulates them in the given arrays.
    """
    # Normalize between [0, bin_count] and then round down.
    scale = bin_count / 10.0
    df["likelihood"] = (df["likelihood"] * scale).round(0)
    df["impact"] = (df["impact"] * scale).round(0)
    df["score"] = (df["score"] * scale).round(0)
    df["risk"] = (df["risk"] * scale).round(0)

    # Count the values of each row.
    likelihood_cnt = df["likelihood"].value_counts().to_dict()
    impact_cnt = df["impact"].value_counts().to_dict()
    score_cnt = df["score"].value_counts().to_dict()
    risk_cnt = df["risk"].value_counts().to_dict()

    for v in range(0, bin_count):
        likelihood_tot[v] += likelihood_cnt.get(v, 0)
        impact_tot[v] += impact_cnt.get(v, 0)
        score_tot[v] += score_cnt.get(v, 0)
        risk_tot[v] += risk_cnt.get(v, 0)

    # Merge the last two
    likelihood_tot[bin_count-1] += likelihood_cnt.get(bin_count, 0)
    impact_tot[bin_count-1] += impact_cnt.get(bin_count, 0)
    score_tot[bin_count-1] += score_cnt.get(bin_count, 0)
    risk_tot[bin_count-1] += risk_cnt.get(bin_count, 0)
