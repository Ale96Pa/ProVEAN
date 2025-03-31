import time
from typing import Literal, Optional

import duckdb

from progag.attack_paths import METRIC_STEPS, MAX_LENGTH, get_metric_index

AP_ATTRIBUTES = ["likelihood", "impact", "risk", "score", "length"]

type APMetric = Literal["likelihood", "impact", "risk", "score", "length"]
type APCondition = tuple[APMetric, int | float, int | float]


def get_joint_histograms(
    db: duckdb.DuckDBPyConnection,
    metrics: list[APCondition],
    sources: Optional[list[int]] = None,
    targets: Optional[list[int]] = None
) -> dict[str, list[int]]:
    """
    Here is a very quick explanation of what this function does.

    - The client makes a selection on the attributes.
      Let's say they select the likelihood interval [0, 5].
    - Now, paths whose likelihood is between [0, 5] cannot,
      by definition, have a risk higher than 5. However if
      the user selected the risk interval [5, 7], he would
      get no results while the current histogram supposedly
      shows their selection should not be empty.
    - What we want to do is computing the *joint* histograms
      of each attribute after applying the filtering.

    We want the new joint histograms to show the user what
    happens when they change their selection on that attribute.

    This means that if we selected a likelihood interval, the
    histogram for likelihood should not reflect that selection,
    otherwise the user would lose information on what happens
    when they expand their selection.
    """
    # Get the attributes that were not in the selection.
    # These have the characteristic that they all compute
    # their histograms on the full joint distribution.
    filtered_attrs: list[str] = [f[0] for f in metrics]
    unfiltered_attrs: list[str] = [
        a for a in AP_ATTRIBUTES if a not in filtered_attrs]

    topological_where = topological_where_clause(sources, targets)

    if unfiltered_attrs:
        # If there are still unfiltered attributes,
        # compute the query on all of them.
        histograms = _compute_histograms(
            db, unfiltered_attrs, metrics, topological_where)
    else:
        histograms: dict[str, list[int]] = {}

    for attr in filtered_attrs:
        # Compute the query on each individual attribute
        result = _compute_histograms(
            db, [attr], metrics, topological_where, exclude=attr)
        histograms[attr] = result[attr]

    end_time = time.time()

    return histograms


def filter_to_where_clause(
    filter: list[APCondition],
    exclude: Optional[str] = None
) -> str:
    clauses: list[str] = []

    for attr, min, max in filter:
        if attr == exclude:
            continue

        clauses.append(f"{attr} >= {min} AND {attr} <= {max}")

    if not clauses:
        return "1 = 1"
    return " AND ".join(clauses)


def _compute_histograms(
    db: duckdb.DuckDBPyConnection,
    select_attrs: list[str],
    filter: list[APCondition],
    topological_where: str,
    *,
    exclude: Optional[str] = None
) -> dict[str, list[int]]:
    """
    Computes an histogram for each selected attribute
    where all the filters (except the excluded ones)
    have been applied.
    """
    select_clause = ", ".join(select_attrs)
    where_clause = filter_to_where_clause(filter, exclude)
    if not where_clause:
        where_clause = "1 = 1"

    sql: str = (
        f"""SELECT {select_clause}
            FROM aps
            WHERE {where_clause} AND {topological_where}
            """)
    query_res = db.query(sql).df()

    histograms: dict[str, list[int]] = {}
    for attr in select_attrs:
        attr_data = query_res.get(attr, None)
        # Make sure the result contains this
        assert attr_data is not None

        if attr == "length":
            histogram: list[int] = [0] * MAX_LENGTH
            # Perform the counting in-pandas for higher performance
            len_counts: list[tuple[int, int]] = attr_data\
                .value_counts().items()  # type: ignore

            for le, count in len_counts:
                if le >= MAX_LENGTH:
                    histogram[MAX_LENGTH - 1] = count
                else:
                    histogram[le] = count
        else:
            histogram: list[int] = [0] * METRIC_STEPS

            # Perform the counting in-pandas just like before
            oth_counts: list[tuple[float, int]] = attr_data\
                .value_counts().items()  # type: ignore

            for val, count in oth_counts:
                idx = get_metric_index(val)
                histogram[idx] += count

        histograms[attr] = histogram

    return histograms


def topological_where_clause(sources: Optional[list[int]], targets: Optional[list[int]]) -> str:
    source_list = list(map(str, sources)) if sources else []
    target_list = list(map(str, targets)) if targets else []
    source_cond = "(" + " OR ".join(
        [f"source = {source}" for source in source_list]) + ")" if source_list else "1 = 1"
    target_cond = "(" + " OR ".join(
        [f"target = {target}" for target in target_list]) + ")" if target_list else "1 = 1"

    return f"{source_cond} AND {target_cond}"
