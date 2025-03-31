from typing import Literal
import duckdb
import numpy as np

from progag.attack_paths import AttackPath
from progag.generation import PathGenerator
from progag.model import AttackGraphModel
from progag.steering import SteeringPathGenerator
from server.joint import APCondition, filter_to_where_clause


type AnalysisType = Literal[
    "attack_source_target_matrix",
    "top_vulnerabilities",
    "attack_path_histogram",
    "select_attack_paths",
]


def get_ap_histogram(
    db_conn: duckdb.DuckDBPyConnection,
    condition: list[APCondition],
    metric: str,
    n: int = 10000
) -> list[tuple[str, float]]:
    """
    Finds the `n` top paths in the given `metric` from the database.
    """
    paths = []

    query = f"""
        SELECT trace, {metric} FROM aps
        WHERE {filter_to_where_clause(condition)}
        ORDER BY {metric} DESC
    """
    result = db_conn.sql(query).df()

    if len(result) < n:
        for trace, value in zip(result["trace"], result[metric]):
            paths.append((trace, value))
    else:
        # Limit the number of results
        step = len(result) // n
        for trace, value in zip(result["trace"][0:-1:step], result[metric][0:-1:step]):
            paths.append((trace, value))

    return paths


def select_attack_paths(
    db_conn: duckdb.DuckDBPyConnection,
    model: AttackGraphModel,
    condition: list[APCondition],
    n: int = 100
):
    query = f"""
        SELECT trace FROM aps
        WHERE {filter_to_where_clause(condition)}
        LIMIT {n}
    """
    result = db_conn.sql(query).df()

    aps: list[AttackPath] = []

    for trace in result["trace"]:
        ap = AttackPath.from_trace(trace, model)
        aps.append(ap)

    return aps


class AttackSourceTargetMatrix:
    def __init__(self, model: AttackGraphModel):
        n = model.number_of_nodes()
        self.matrix = np.zeros((n, n), dtype=int)
        self.iteration = 0

    def update(self, paths: list[AttackPath], gen: PathGenerator):
        for path in paths:
            source = path.source_host
            target = path.target_host
            self.matrix[source, target] += 1

        self.iteration = gen.iteration

    def result(self):
        return {
            "iteration": self.iteration,
            "counts": self.matrix.tolist(),
        }


class TopVulnerabilities:
    def __init__(self):
        self.iteration = 0
        self.vulns: dict[str, int] = {}

    def update(self, paths: list[AttackPath], gen: SteeringPathGenerator):
        self.iteration = gen.iteration

        for path in paths:
            for vuln in path.vulns:
                cve = vuln.cve_id
                self.vulns[cve] = self.vulns.get(cve, 0) + 1

    def result(self):
        return {
            "iteration": self.iteration,
            "cves": sorted(self.vulns.items(), key=lambda x: x[1], reverse=True),
        }
