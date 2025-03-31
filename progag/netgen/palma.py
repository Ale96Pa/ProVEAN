import json
import os

import networkx as nx
from networkx.drawing.nx_agraph import graphviz_layout

from progag.model import AttackGraphModel, NetworkHost
from progag.netgen.topology import Coordinate
from progag.vulnerabilities import VulnerabilityPool


def convert_palma(path: str) -> AttackGraphModel:
    """
    Converts a model from Palma's (AttackGraphProgressive) format
    to the `AttackGraphModel` format.
    """
    # Read the JSON file.
    data = json.load(open(path))

    devices: list = data["devices"]
    vulns: list = data["vulnerabilities"]
    edges: list = data["edges"]

    # Create a DiGraph for the model.
    graph = nx.DiGraph()
    for d in devices:
        graph.add_node(d["hostname"])
    for e in edges:
        a, b = e["host_link"]
        graph.add_edge(a, b)

    # Plot the graph to obtain the node coordinates
    coords: dict[int, Coordinate] = graphviz_layout(graph, prog="neato")

    model = AttackGraphModel()

    # Load the vulnerabilities
    vuln_pool: set[str] = set()
    for v in vulns:
        vuln_pool.add(v["id"])
    with open(os.path.join(os.path.dirname(__file__), "inventory", "vulnerabilities.json")) as f:
        model.vulnerabilties = VulnerabilityPool.load_from_list_object(
            json.load(f), filter=vuln_pool)

    for d in devices:
        id: int = d["hostname"]
        netint = d["network_interfaces"][0]
        ip: str = netint["ipaddress"]
        service = netint["ports"][0]["services"][0]
        name = service["name"]
        cpe = service["cpe_list"][0]
        cve_list = service["cve_list"]

        x, y = coords[id]
        host = NetworkHost(id, name, ip, cve_list, {cpe: cve_list}, 0, x, y)
        model.add_host(host)

    for e in edges:
        a, b = e["host_link"]
        model.add_edge(a, b)

    return model
