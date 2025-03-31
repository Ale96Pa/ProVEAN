import itertools
import statistics
import time
from typing import Callable, Generator

import duckdb
import networkx as nx
import pandas as pd
from tqdm import tqdm

from progag.model import AttackGraphModel
from progag.vulnerabilities import PRIV_GUEST, PRIVILEGE_STR, Privilege, Vulnerability

type APEssentials = tuple[str, float, float, float, float, int]


def generate_all_attack_paths(
    model: AttackGraphModel,
    db_path: str,
    cutoff: int = 15,
    print_times: bool = False
):
    """
    Generates all the attack paths for a model (they may be a huge amount)
    and stores them in a duckdb at the given path.
    """
    # Create the duckdb database
    db = duckdb.connect(db_path)
    # Create the table structure
    db.sql(
        """
        DROP TABLE IF EXISTS aps;
        CREATE TABLE aps (
            trace TEXT,
            likelihood FLOAT,
            impact FLOAT,
            score FLOAT,
            risk FLOAT,
            length INTEGER
        )""")

    total, generator = _all_simple_paths(model, cutoff)

    for source, target, rps, rp_time in tqdm(generator, total=total, smoothing=0.01):
        all_aps, ap_time = _attack_paths_from_reachability_paths(model, rps)

        if print_times:
            avg_length = statistics.mean(
                a[5] for a in all_aps) if all_aps else 0

            print(
                f"{source:>3} => {target:>3} "
                f"{len(rps):>7} RPs ({rp_time:>9.4f}s) to "
                f"{len(all_aps):>8} APs ({ap_time:>9.4f}s) "
                f"{len(all_aps) / len(rps):>5.1f}x factor "
                f"w/avg len of {avg_length}"
            )

        db.append("aps", pd.DataFrame(all_aps, columns=[
                  "trace", "likelihood", "impact", "score", "risk", "length"]))

    db.close()


def _all_simple_paths(
    G: nx.DiGraph, cutoff: int = 8
) -> tuple[int, Generator[tuple[int, int, list[list[int]], float], None, None]]:
    """
    Yields all the simple paths in the graph of length up to `cutoff`
    in one batch for each valid (`source`, `target`) pair.
    """
    t = time.time()

    print("Computing the transitive closure of the graph. This might take a while.")
    # Precompute whether there are paths between each pair of hosts
    has_path: dict[tuple[int, int], bool] = {}
    # Compute the transitive closure of the graph
    closure = nx.transitive_closure(G)
    pairs_count = 0
    for i in G.nodes:
        for j in G.nodes:
            if i == j:
                has_path[(i, j)] = False
            else:
                pair_connected = closure.has_edge(i, j)
                has_path[(i, j)] = pair_connected
                if pair_connected:
                    pairs_count += 1

    print("Done. Precomputing the successors of each host.")
    # Precompute the successors to each host
    successors: dict[int, list[int]] = {}
    for i in G.nodes:
        successors[i] = list(G.successors(i))

    t = time.time() - t
    print(f"Performed RP precomputations in {t:.4f}s")

    def _generator():
        for source in G.nodes:
            for target in G.nodes:
                if not has_path[(source, target)]:
                    continue

                t = time.time()
                results = list(_all_simple_paths_source_to_target(
                    G, [source], target, has_path, successors, cutoff))

                # Continue only if in debug mode
                if results:
                    t = time.time() - t
                    yield source, target, results, t
    return pairs_count, _generator()


def _all_simple_paths_source_to_target(
    G: nx.DiGraph, current_path: list[int], target: int,
    has_path: dict[tuple[int, int], bool],
    successors: dict[int, list[int]],
    cutoff: int
) -> Generator[list[int], None, None]:
    """
    Yields all the simple paths to the `target` of length up
    to cutoff where the path starts with `current_path`.

    Requires two extra inputs:
    - `has_path`: a dict from each (s, t) pair
        to whether there is a path between them;
    - `successors`: a dict from a node to its successors;
    """
    if cutoff == 0:
        return

    current_node: int = current_path[-1]

    # Loop through all neighbors of the stack.
    for next_node in successors[current_node]:
        # If the next node is the target, yield the path
        if next_node == target:
            yield [*current_path, next_node]
            # And skip the rest, as we arrived
            continue
        elif next_node in current_path:
            continue

        # If the target is not reachable from there, ignore that.
        if not has_path[(next_node, target)]:
            continue

        # Otherwise restart looking for all paths starting from there
        yield from _all_simple_paths_source_to_target(
            G, [*current_path, next_node], target,
            has_path, successors, cutoff - 1)


def _attack_paths_from_reachability_paths(
    model: AttackGraphModel,
    rps: list[list[int]],
) -> tuple[list[APEssentials], float]:
    all_attack_paths: list[APEssentials] = []
    t = time.time()

    for rp in rps:
        aps = list(_all_attack_paths_from_rp(model, rp[1:], [], [], rp[0]))
        all_attack_paths.extend(aps)

    t = time.time() - t
    return all_attack_paths, t


def _all_attack_paths_from_rp(
    model: AttackGraphModel,
    path: list[int],
    trace: list[str],
    vulns: list[Vulnerability],
    source: int,
    priv_on_source: Privilege = PRIV_GUEST
) -> Generator[APEssentials, None, None]:
    if not path:
        likelihood = sum(v.likelihood for v in vulns) / len(vulns)
        impact = vulns[-1].impact
        score = statistics.median(v.score for v in vulns)
        risk = likelihood * impact / 10.0

        yield (
            "##".join(trace),
            likelihood,
            impact,
            score,
            risk,
            len(vulns),  # length
        )
        return
    target = path[0]

    for cve in model.hosts[target].cves:
        vuln: Vulnerability = model.vulnerabilties[cve]
        # If you don't have the privileges, it's not exploitable.
        if vuln.priv_required > priv_on_source:
            continue

        # If you do have privileges, explore what would happen
        # if you exploited it.
        priv_gained = vuln.priv_gained
        trace_step = f"{PRIVILEGE_STR[priv_on_source]}@{source}"\
            f"#{cve}#{PRIVILEGE_STR[priv_gained]}@{target}"
        yield from _all_attack_paths_from_rp(
            model, path[1:],
            [*trace, trace_step], [*vulns, vuln],
            path[0], priv_gained
        )
