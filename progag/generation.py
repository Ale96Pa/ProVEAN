import os
import time
from typing import Generator, Optional

import duckdb
import numpy as np
import pandas as pd

from progag.model import AttackGraphModel
from progag.attack_paths import AttackPathStatistics
from progag.sampling import Edge, PathSampler
from progag.vulnerabilities import PRIV_GUEST, PRIVILEGE_STR, Vulnerability
from progag.attack_paths import AttackPath

type FiveCDFs = tuple[np.ndarray, np.ndarray,
                      np.ndarray, np.ndarray, np.ndarray]

SCORE_BINS = 200
LENGTH_BINS = 40

DF_COLUMNS = [
    "hash", "trace", "likelihood", "impact",
    "score", "risk", "damage", "length", "source", "target",
    "iteration"]


class PathGenerator:
    # The AG model for sampling hosts and vulnerabilities.
    model: AttackGraphModel

    # The object which produces the reachability paths.
    path_sampler: PathSampler
    # The number of reachability paths to sample at each step.
    sample_size: int

    # Path to store the CSV file with the generation information.
    csv_path: Optional[str] = None
    # Connection to the database for storing paths.
    db: Optional[duckdb.DuckDBPyConnection]

    # The current iteration.
    iteration: int = 0
    # The hashes of all generated paths.
    unique_hashes: set[str]
    # Collision rate at each iteration.
    collision: list[float]
    # Generation times at each iteration.
    times: list[float]
    # Number of unique paths that were generated.
    generated: list[int]

    # Whether to compute the statistics
    compute_statistics: bool = True
    # Statistics to be generated with the paths
    statistics: Optional[AttackPathStatistics] = None

    # The metrics of all generated paths to compute the stability value.
    count_lik: np.ndarray
    count_imp: np.ndarray
    count_sco: np.ndarray
    count_ris: np.ndarray
    count_len: np.ndarray
    # The last generated CDF for each metric.
    prev_cdf_lik: np.ndarray
    prev_cdf_imp: np.ndarray
    prev_cdf_sco: np.ndarray
    prev_cdf_ris: np.ndarray
    prev_cdf_len: np.ndarray

    # Information about the stability at each iteration
    # In order: likelihood, impact, score, risk, length
    stability: list[tuple[float, float, float, float, float]] = []

    def __init__(
        self, model: AttackGraphModel, *,
        sample_size: int = 100,
        max_length: Optional[int] = None,
        db: Optional[duckdb.DuckDBPyConnection] = None,
        db_path: Optional[str] = None,
        csv_path: Optional[str] = None,
        compute_statistics: bool = True,
    ):
        self.model = model
        self.sample_size = sample_size
        self.path_sampler = PathSampler(
            model, max_length=max_length)
        self.compute_statistics = compute_statistics
        if self.compute_statistics:
            self.statistics = AttackPathStatistics()
        self.csv_path = csv_path
        if self.csv_path:
            self._init_csv_file()

        if db is None and db_path is not None:
            self._init_database(db_path)
        else:
            self.db = db

        self.unique_hashes = set()
        self.collision = []
        self.times = []
        self.generated = []
        self.count_lik = np.zeros(SCORE_BINS, dtype=np.uint64)
        self.count_imp = np.zeros(SCORE_BINS, dtype=np.uint64)
        self.count_sco = np.zeros(SCORE_BINS, dtype=np.uint64)
        self.count_ris = np.zeros(SCORE_BINS, dtype=np.uint64)
        self.count_len = np.zeros(LENGTH_BINS, dtype=np.uint64)
        self.prev_cdf_lik = np.zeros(SCORE_BINS, dtype=np.float64)
        self.prev_cdf_imp = np.zeros(SCORE_BINS, dtype=np.float64)
        self.prev_cdf_sco = np.zeros(SCORE_BINS, dtype=np.float64)
        self.prev_cdf_ris = np.zeros(SCORE_BINS, dtype=np.float64)
        self.prev_cdf_len = np.zeros(LENGTH_BINS, dtype=np.float64)

    def step(self) -> list[AttackPath]:
        start_time = time.time()
        attack_paths = self.sample_attack_paths()
        elapsed_time = time.time() - start_time

        self.update_stability(attack_paths)
        if self.statistics is not None:
            self.statistics.update(attack_paths)

        self.times.append(elapsed_time)

        # Before the iteration increases, save the paths
        self.save_paths(attack_paths)

        self.iteration += 1
        # self.log_iteration()
        self.save_stats_to_csv()
        return attack_paths

    # |--------------------|
    # | Persistent Storage |
    # |--------------------|
    def save_paths(self, new_paths: list[AttackPath]):
        """ Saves the paths to the database, if provided. """
        if self.db is None:
            return

        # Convert the new paths to a DataFrame
        df = pd.DataFrame(
            map(
                lambda ap: [ap.hash, ap.trace, ap.likelihood, ap.impact,
                            ap.score, ap.risk, ap.damage, ap.length,
                            ap.source_host, ap.target_host,
                            self.iteration],
                new_paths
            ),
            columns=DF_COLUMNS)
        self.db.append("aps", df)

    def _init_database(self, path: str):
        # Delete the database if it already exists
        if os.path.exists(path):
            os.remove(path)
            print("Removed old database")

        # Initialize the database
        self.db = duckdb.connect(path)
        # Create the table structure
        self.db.sql("DROP TABLE IF EXISTS aps")
        self.db.sql(
            """
            CREATE TABLE aps (
                hash TEXT PRIMARY KEY,
                trace TEXT,
                likelihood FLOAT,
                impact FLOAT,
                score FLOAT,
                risk FLOAT,
                damage FLOAT,
                length INTEGER,
                source INTEGER,
                target INTEGER,
                iteration INTEGER,
            )""")

    def save_stats_to_csv(self):
        if not self.csv_path:
            return

        s = self.iteration_summary()
        DATA = ",".join(map(str, [
            s["iteration"],
            s["generated"],
            s["collision"],
            s["st_likelihood"],
            s["st_impact"],
            s["st_risk"],
            s["st_score"],
            s["st_length"],
            s["time"],
        ]))

        with open(self.csv_path, "a") as f:
            f.write("\n")
            f.write(DATA)

    def _init_csv_file(self):
        if self.csv_path is None:
            return

        HEADER = ",".join([
            "iteration", "generated",
            "collision", "st_likelihood",
            "st_impact", "st_risk",
            "st_score", "st_length", "time"
        ])
        with open(self.csv_path, "w+t") as f:
            f.write(HEADER)

    # |-----------------------|
    # | Stability Computation |
    # |-----------------------|
    def update_stability(self, new_paths: list[AttackPath]):
        """
        Performs a Kolmogorov-Smirnov test on the main metrics of the
        given attack paths by comparing it to the last iteration.

        Updates the stability value once done.
        """
        # Save the steps to the new distribution
        for path in new_paths:
            self.count_lik[_score_to_bin(path.likelihood)] += 1
            self.count_imp[_score_to_bin(path.impact)] += 1
            self.count_sco[_score_to_bin(path.score)] += 1
            self.count_ris[_score_to_bin(path.risk)] += 1
            if path.length > LENGTH_BINS:
                self.count_len[LENGTH_BINS - 1] += 1
            elif path.length >= 1:
                self.count_len[path.length - 1] += 1

        cdf_lik = _measurements_to_cdf(self.count_lik)
        cdf_imp = _measurements_to_cdf(self.count_imp)
        cdf_sco = _measurements_to_cdf(self.count_sco)
        cdf_ris = _measurements_to_cdf(self.count_ris)
        cdf_len = _measurements_to_cdf(self.count_len)

        if self.iteration > 0:
            lik = statistical_difference(self.prev_cdf_lik, cdf_lik)
            imp = statistical_difference(self.prev_cdf_imp, cdf_imp)
            sco = statistical_difference(self.prev_cdf_sco, cdf_sco)
            ris = statistical_difference(self.prev_cdf_ris, cdf_ris)
            len = statistical_difference(self.prev_cdf_len, cdf_len)
            # print(f"KS: lik={lik:>0.8f} imp={imp:>0.8f} sco={
            #       sco:>0.8f} ris={ris:>0.8f} len={len:>0.8f}")

            # Update the stability
            self.stability.append(
                (1.0-lik, 1.0-imp, 1.0-sco, 1.0-ris, 1.0-len))

        # Replace the previous CDF with the current one.
        self.prev_cdf_lik = cdf_lik
        self.prev_cdf_imp = cdf_imp
        self.prev_cdf_sco = cdf_sco
        self.prev_cdf_ris = cdf_ris
        self.prev_cdf_len = cdf_len

    # |----------------------|
    # | Attack Path Sampling |
    # |----------------------|
    def sample_attack_paths(
        self, preferred_cves: Optional[set[str]] = None
    ) -> list[AttackPath]:
        """
        Samples the `sample_size` number of reachability paths from the model,
        then converts them to attack paths (with the preferred vulnerabilities
        if specified).

        Once that is done, it returns only the attack paths that were not
        generated previously and updates the collision rate.
        """
        # Attack paths that do not collide with the previous ones
        attack_paths: list[AttackPath] = []
        sampled_aps: int = 0
        collisions: int = 0

        # Generate attack paths and count collisions
        for path in self.sample_reachability_paths():
            # Stop when you have enough APs.
            if sampled_aps == self.sample_size:
                break
            # Ignore empty paths.
            if not path:
                continue

            # Generate the attack path.
            ap = self.convert_reachability_to_ap(path, preferred_cves)
            if ap is None:
                continue

            sampled_aps += 1
            # Check for collisions.
            if ap.hash in self.unique_hashes:
                collisions += 1
            else:
                self.unique_hashes.add(ap.hash)
                attack_paths.append(ap)

        # Store the new generated value.
        self.generated.append(sampled_aps - collisions)
        # Store the new collision value.
        self.collision.append(
            collisions / sampled_aps if sampled_aps > 0 else 0.0)

        return attack_paths

    def sample_reachability_paths(self) -> Generator[list[Edge], None, None]:
        """
        Creates a generator that samples non-empty paths.
        """
        for i in range(self.sample_size):
            path = self.path_sampler.sample_path()
            if not path:
                continue
            yield path

    def convert_reachability_to_ap(
        self, path: list[Edge], preferred_cves: Optional[set[str]] = None
    ) -> Optional[AttackPath]:
        """
        Converts a reachability path to an attack path using the
        vulnerabilities on the target host at each step, making sure
        it respects the gained privileges.

        May return None if it can't match privileges at the first step,
        but otherwise will always return a path, even if shorter than
        the reachability path.

        If preferred CVEs is set, it will try to use those first.
        """
        priv_on_source = PRIV_GUEST

        exploited_vulns: list[Vulnerability] = []
        trace_steps: list[str] = []

        for source_host, target_host in path:
            # Get the vulnerabilities on the target host
            cve = self.model.sample_cve_on_host(
                target_host,
                current_priv=priv_on_source,
                preferred_cves=preferred_cves)
            # If you couldn't find the requested vulnerability
            if cve is None:
                # Just cut the path short, it'll be fine
                break

            vuln = self.model.vulnerabilties[cve]

            priv_required = vuln.priv_required
            priv_gained = vuln.priv_gained

            # print(cve, "on", target_host, "needs",
            #       f"{priv_required.name}@{source_host}", "you have"
            #       f"({priv_on_source.name}@{source_host})",
            #       "and gives", f"{priv_gained.name}@{target_host}")

            # If the privilege required is already gained on the source host
            priv_on_source = priv_gained
            exploited_vulns.append(vuln)

            trace_steps.append(f"{PRIVILEGE_STR[priv_on_source]}@{source_host}#"
                               f"{cve}#{PRIVILEGE_STR[priv_gained]}@{target_host}")

        if not exploited_vulns:
            return None

        # Join the steps to build the final trace
        trace: str = "##".join(trace_steps)

        ap_length = len(exploited_vulns)
        return AttackPath(trace, exploited_vulns, path[0:ap_length])

    # |-------|
    # | Utils |
    # |-------|
    def iteration_summary(self, i: Optional[int] = None) -> dict:
        if i is None:
            i = self.iteration - 1

        return {
            "iteration": i,
            "generated": self.generated[i],
            "collision": self.collision[i],
            "st_likelihood": None if i == 0 else self.stability[i-1][0],
            "st_impact": None if i == 0 else self.stability[i-1][1],
            "st_risk": None if i == 0 else self.stability[i-1][2],
            "st_score": None if i == 0 else self.stability[i-1][3],
            "st_length": None if i == 0 else self.stability[i-1][4],
            "time": self.times[i],
        }

    def iteration_history(self) -> pd.DataFrame:
        summaries = []
        for i in range(self.iteration):
            summaries.append(self.iteration_summary(i))
        return pd.DataFrame(summaries)

    def log_iteration(self):
        i = self.iteration - 1
        i = f"iter {i:>3}"
        g = self.generated[-1]
        g = f"generated {g:>6}"
        c = self.collision[-1]
        c = f"collision_rate {c:7.2%}"
        t = self.times[-1]
        t = f"time {t:>.2f}s"

        if not self.stability:
            s = ""
        else:
            s = self.stability[-1]
            s = sum(s) / 5.0
            s = f" | stability: {s:>9.8f}"

        print(f"{i} | {g} | {c} | {t}{s}")
        pass

    def compare_cdfs(self, cdfs: FiveCDFs) -> tuple[float, float, float, float, float]:
        cdf_lik, cdf_imp, cdf_sco, cdf_ris, cdf_len = cdfs
        lik = statistical_difference(self.prev_cdf_lik, cdf_lik)
        imp = statistical_difference(self.prev_cdf_imp, cdf_imp)
        sco = statistical_difference(self.prev_cdf_sco, cdf_sco)
        ris = statistical_difference(self.prev_cdf_ris, cdf_ris)
        len = statistical_difference(self.prev_cdf_len, cdf_len)
        return 1.0-lik, 1.0-imp, 1.0-sco, 1.0-ris, 1.0-len


def get_cdf_from_database(db_path: str):
    """
    Obtains the CDFs of the likelihood, impact, risk, score and length
    of the paths in the given database.
    """
    count_lik = np.zeros(SCORE_BINS, dtype=np.uint64)
    count_imp = np.zeros(SCORE_BINS, dtype=np.uint64)
    count_sco = np.zeros(SCORE_BINS, dtype=np.uint64)
    count_ris = np.zeros(SCORE_BINS, dtype=np.uint64)
    count_len = np.zeros(LENGTH_BINS, dtype=np.uint64)

    with duckdb.connect(db_path, read_only=True) as db:
        sc = (("likelihood", count_lik),
              ("impact", count_imp),
              ("score", count_sco),
              ("risk", count_ris),)

        for score, count in sc:
            for i in range(SCORE_BINS):
                lower_limit = i * 10.0 / SCORE_BINS

                if i < SCORE_BINS - 1:
                    upper_limit = (i+1) * 10.0 / SCORE_BINS
                    count[i] = db.query(
                        f"SELECT COUNT(*) as c FROM aps WHERE {score} < {
                            upper_limit} AND {score} >= {lower_limit}"
                    ).to_df()["c"][0]
                else:
                    count[i] = db.query(
                        f"SELECT COUNT(*) as c FROM aps WHERE {
                            score} >= {lower_limit}"
                    ).to_df()["c"][0]

        for l in range(LENGTH_BINS - 1):
            count_len[l] = db.query(
                f"SELECT COUNT(*) as c FROM aps WHERE length = {l + 1}"
            ).to_df()["c"][0]
        count_len[LENGTH_BINS - 1] = db.query(
            f"SELECT COUNT(*) as c FROM aps WHERE length >= {LENGTH_BINS}"
        ).to_df()["c"][0]

    return (
        _measurements_to_cdf(count_lik),
        _measurements_to_cdf(count_imp),
        _measurements_to_cdf(count_sco),
        _measurements_to_cdf(count_ris),
        _measurements_to_cdf(count_len),
    )


def _measurements_to_cdf(metrics: np.ndarray) -> np.ndarray:
    """
    Takes the measurements for each index, computes the cumulative
    sum, and then normalizes it.
    """
    cdf = np.cumsum(metrics, dtype=np.float64)
    if cdf[-1] > 0:
        cdf /= cdf[-1]
    else:
        cdf = np.zeros(cdf.shape, dtype=np.float64)
    return cdf


def _score_to_bin(score: float) -> int:
    """
    Returns the bin index of a score, based on the constant `SCORE_BINS`.
    """
    if score == 10.0:
        return SCORE_BINS - 1

    return int(score / 10 * SCORE_BINS)


def statistical_difference(cdf1: np.ndarray, cdf2: np.ndarray) -> float:
    """
    Returns the maximum difference between the two distributions.
    """
    return float(np.max(np.abs(cdf1 - cdf2)))
