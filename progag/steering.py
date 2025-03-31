import time
from typing import Optional

import duckdb
import pandas as pd
from sklearn.tree import DecisionTreeClassifier

from progag.attack_paths import AttackPath
from progag.generation import PathGenerator
from progag.model import AttackGraphModel
from progag.sampling import EndingAt, PathSampler, SamplingStrategy, SourceTarget, StartingAt, Uniform

type Range[T] = tuple[T, T]


class AttackPathQuery:
    """
    Query on the attack path metrics that can be used
    to filter the attack paths.
    """
    # Metric ranges - affects paths that are passed to the DT.
    likelihood_range: Optional[Range[float]]
    impact_range: Optional[Range[float]]
    score_range: Optional[Range[float]]
    risk_range: Optional[Range[float]]

    # Topological ranges - affects how paths are generated.
    length_range: Optional[Range[int]]
    sources: Optional[list[int]]
    targets: Optional[list[int]]

    # Impacted metrics
    metrics: set[str]

    def __init__(
        self,
        # Topological constraints
        length: Optional[Range[int]] = None,
        sources: Optional[list[int]] = None,
        targets: Optional[list[int]] = None,
        # Metric constraints
        likelihood: Optional[Range[float]] = None,
        impact: Optional[Range[float]] = None,
        score: Optional[Range[float]] = None,
        risk: Optional[Range[float]] = None,
    ):
        self.metrics = set()

        self.length_range = length
        if length is not None:
            self.metrics.add("length")
        self.likelihood_range = likelihood
        if likelihood is not None:
            self.metrics.add("likelihood")
        self.impact_range = impact
        if impact is not None:
            self.metrics.add("impact")
        self.risk_range = risk
        if risk is not None:
            self.metrics.add("risk")
        self.score_range = score
        if score is not None:
            self.metrics.add("score")

        self.sources = sources
        self.targets = targets

    def check_bounds(self, attack_path: AttackPath) -> bool:
        """
        Returns True if the query's bounds are satisfied
        by the given attack path, but does not check the
        topological constraint.
        """
        if self.likelihood_range is not None:
            a, b = self.likelihood_range
            if not a <= attack_path.likelihood <= b:
                return False
        if self.impact_range is not None:
            a, b = self.impact_range
            if not a <= attack_path.impact <= b:
                return False
        if self.score_range is not None:
            a, b = self.score_range
            if not a <= attack_path.score <= b:
                return False
        if self.risk_range is not None:
            a, b = self.risk_range
            if not a <= attack_path.risk <= b:
                return False
        if self.length_range is not None:
            a, b = self.length_range
            if not a <= attack_path.length <= b:
                return False
        return True

    def to_dict(self) -> dict:
        return {
            "likelihood_range": self.likelihood_range,
            "impact_range": self.impact_range,
            "score_range": self.score_range,
            "risk_range": self.risk_range,

            "length_range": self.length_range,
            "sources": self.sources,
            "targets": self.targets
        }

    def get_sampler(self, model: AttackGraphModel) -> PathSampler:
        """
        Initializes the correct path sampler to generate reachability
        paths that will allow generating attack paths that satisfy the
        given query.
        """
        match self.sources, self.targets:
            case None, None:
                strategy = Uniform()
            case sources, None:
                strategy = StartingAt(sources)
            case None, targets:
                strategy = EndingAt(targets)
            case sources, targets:
                strategy = SourceTarget(sources, targets)

        match self.length_range:
            case None:
                return PathSampler(model, strategy=strategy)
            case (m, M):
                return PathSampler(model, strategy=strategy,
                                   min_length=m, max_length=M)


class SteeringPathGenerator(PathGenerator):
    # Query used by the steering algorithm.
    query: AttackPathQuery
    # Whether steering is disabled (for debug purposes).
    disable_steering: bool

    # Number of queries of each type needed to
    # start training the DT.
    min_dataset_size: int
    # Cutoff to avoid the DT dataset growing out
    # of control.
    max_dataset_size: int

    # Training APs that satisfy the query.
    query_aps: list[AttackPath]
    # Training APs that do not satisfy the query.
    nonquery_aps: list[AttackPath]

    # Unique hashes of the query APs
    query_hashes: set[str]
    # Generated query paths
    query_generated: list[int]

    # History of the precision at each generation.
    precision: list[float]
    # History of steering at each iteration.
    steering: list[bool]
    # Vulnerabilities that have been deemed to be
    # steering-compliant by the decision tree.
    steering_compliant_vulns: set[str]

    def __init__(
        self, model: AttackGraphModel, query: AttackPathQuery, *,
        db: Optional[duckdb.DuckDBPyConnection] = None,
        db_path: Optional[str] = None,
        min_training_size: int = 20,
        max_training_size: int = 200,
        sample_size: int = 500,
        compute_statistics: bool = True,
        csv_path: Optional[str] = None,
        disable_steering: bool = False
    ):
        super().__init__(
            model, sample_size=sample_size, db=db, db_path=db_path,
            compute_statistics=compute_statistics, csv_path=csv_path)

        self.query = query
        self.disable_steering = disable_steering
        self.min_dataset_size = min_training_size
        self.max_dataset_size = max_training_size

        self.path_sampler = query.get_sampler(model)
        self.query_hashes = set()
        self.query_generated = []
        self.steering_compliant_vulns = set()

        self.query_aps = []
        self.nonquery_aps = []
        self.precision = []
        self.steering = []

    def _init_csv_file(self):
        if self.csv_path is None:
            return

        HEADER = ",".join([
            "iteration", "generated",
            "collision", "precision",
            "st_likelihood", "st_impact",
            "st_risk", "st_score",
            "st_length", "time"
        ])
        with open(self.csv_path, "w+t") as f:
            f.write(HEADER)

    def step(self):
        start_time = time.time()

        if self._can_steer():
            steering = True

            # Only update the steering-compliant vulnerabilities if
            # other conditions are met. One such condition is whether
            # the precision of the last 5 iterations is on average higher
            # than the current precision.
            last_five = self.precision[-5:]
            avg = sum(last_five) / 5.0
            update_steering_vulns = avg <= self.precision[-1]

            if update_steering_vulns or len(self.steering_compliant_vulns) == 0:
                # Train the decision tree to get the steering compliant
                # vulnerabilities from the model.
                self.update_steering_compliant_vulns()

            # Generate the paths with the steering compliant vulnerabilities.
            attack_paths = self.sample_attack_paths(
                preferred_cves=self.steering_compliant_vulns)
        else:
            steering = False
            # Get the new paths without any extra help.
            attack_paths = self.sample_attack_paths()

        result = self._advance_iteration(attack_paths)
        elapsed_time = time.time() - start_time
        self.times.append(elapsed_time)
        self.steering.append(steering)

        self.iteration += 1
        self.save_stats_to_csv()
        return result

    def add_bootstrap(self, paths: list[str]):
        """ Adds the bootstrap paths to the dataset. """
        start_time = time.time()
        attack_paths = [AttackPath.from_trace(p, self.model) for p in paths]

        # Pretend these were sampled.
        self.generated.append(len(attack_paths))
        self.collision.append(0)
        self.unique_hashes.update([p.hash for p in attack_paths])

        result = self._advance_iteration(attack_paths)
        elapsed_time = time.time() - start_time
        self.times.append(elapsed_time)
        self.steering.append(False)

        if self.path_sampler.use_dynamic_weights:
            # Update the weights to favor the bootstrap paths.
            for ap in attack_paths:
                self.path_sampler._update_weights(ap.edges)

        self.iteration += 1
        self.save_stats_to_csv()
        return result

    def _advance_iteration(self, attack_paths: list[AttackPath]) -> tuple[list[AttackPath], list[AttackPath]]:
        # Update the training dataset with the new paths and filter them.
        query_aps, nonquery_aps = self.update_paths(attack_paths)

        self.update_stability(query_aps)
        if self.statistics is not None:
            self.statistics.update(query_aps)

        for ap in query_aps:
            self.query_hashes.add(ap.hash)
        self.query_generated.append(len(query_aps))

        # Before the iteration increases, save the paths.
        self.save_paths(query_aps)

        return query_aps, nonquery_aps

    # |----------|
    # | Steering |
    # |----------|
    def _can_steer(self) -> bool:
        """ Returns True if there are the correct conditions to start steering. """
        # Steering is disabled for this query.
        if self.disable_steering:
            return False

        # Not enough data to steer.
        return (len(self.query_aps) >= self.min_dataset_size and
                len(self.nonquery_aps) >= self.min_dataset_size)

    def update_paths(
        self, new_paths: list[AttackPath]
    ) -> tuple[list[AttackPath], list[AttackPath]]:
        """
        Filters the paths that satisfy the query.

        Little note: when filtering the paths, this method does
        not check for the topological constraint of the query,
        since all paths generated by this generator's sampler
        will already satisfy it.

        Returns both query paths and non-query paths.
        """
        query_aps: list[AttackPath] = []
        nonquery_aps: list[AttackPath] = []

        for path in new_paths:
            if self.query.check_bounds(path):
                query_aps.append(path)
            else:
                nonquery_aps.append(path)
        total = len(query_aps) + len(nonquery_aps)

        # Compute the new precision value
        precision = 0.0 if total == 0 else len(query_aps) / total
        self.precision.append(precision)

        # Extend the training set
        self.query_aps.extend(query_aps)
        self.nonquery_aps.extend(nonquery_aps)

        # Trim the excess
        MAX = self.max_dataset_size
        if len(self.query_aps) > MAX:
            self.query_aps = self.query_aps[-MAX:]
        if len(self.nonquery_aps) > MAX:
            self.nonquery_aps = self.nonquery_aps[-MAX:]

        # Return the new query and non-query paths
        return query_aps, nonquery_aps

    def update_steering_compliant_vulns(self):
        """
        Builds the training set with both query and non-query paths
        and trains a decision tree classifier to predict whether an
        embedding will result in a query path or not.

        Then updates the steering_compliant_vulns attribute with the
        vulnerabilities that are compliant with the steering.
        """
        # Convert each path into a feature vector
        # and then train a decision tree on them
        q_features = [ap.to_features_vector().to_dict()
                      for ap in self.query_aps]
        n_features = [ap.to_features_vector().to_dict()
                      for ap in self.nonquery_aps]

        # Convert each feature to a pandas DataFrame
        for qf in q_features:
            qf["query"] = True
        for nf in n_features:
            nf["query"] = False
        df = pd.DataFrame(q_features + n_features)

        # Create the tree
        dtree = DecisionTreeClassifier(class_weight="balanced")
        # Prepare the training data
        X = df.drop(columns=["query"])
        Y = df["query"]

        # Train the tree
        dtree.fit(X, Y)

        # Convert all the vulnerabilities in the model
        # to objects and predict their steering compliance
        self.steering_compliant_vulns = set()

        for cve, vuln in self.model.vulnerabilties.items():
            features = vuln.base_features.to_dict()
            df = pd.DataFrame([features])
            query = dtree.predict(df)[0]
            if query:
                self.steering_compliant_vulns.add(cve)

    # |-------|
    # | Utils |
    # |-------|
    def iteration_summary(self, i: Optional[int] = None) -> dict:
        if i is None:
            i = self.iteration - 1
        prev_summary = super().iteration_summary(i)

        return {
            **prev_summary,

            "steering": self.steering[i],
            "precision": self.precision[i],
        }

    def log_iteration(self):
        i = self.iteration - 1
        i = f"iter {i:>3}"
        g = self.generated[-1]
        g = f"generated {g:>6}"
        c = self.collision[-1]
        c = f"collision_rate {c:7.2%}"
        t = self.times[-1]
        t = f"time {t:>.2f}s"
        p = self.precision[-1]
        p = f"precision {p:7.2%}"

        if not self.stability:
            s = ""
        else:
            s = self.stability[-1]
            s = sum(s) / 5.0
            s = f" | stability: {s:>9.8f}"

        print(f"STEERAG: {i} | {g} | {c} | {p} | {t}{s}")
        pass

    def save_stats_to_csv(self):
        if not self.csv_path:
            return

        s = self.iteration_summary()
        DATA = ",".join(map(str, [
            s["iteration"],
            s["generated"],
            s["collision"],
            s["precision"],
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
