import json
import os
import random

from networkx.drawing.nx_agraph import graphviz_layout

from progag.model import AttackGraphModel, NetworkHost
from progag.netgen.services import services_pool
from progag.vulnerabilities import VulnerabilityPool


def create_mesh_model(
    num_hosts: int, link_probability: float = 1.0,
    vulns_per_host: int = 3
) -> AttackGraphModel:
    """
    Generates a mesh network with the given number of hosts and
    link probability between them. Assigns the same number of
    vulnerabilities to each host.
    """
    model = AttackGraphModel()

    per_host_cves: list[set[str]] = []
    per_host_cpes: list[dict[str, list[str]]] = []
    cve_pool: set[str] = set()

    # Get the list of all vulnerabilities
    for i in range(num_hosts):
        # Select random services
        usable_services = set(services_pool.choose_services(16))

        remaining_vulns = vulns_per_host
        chosen_cpes: dict[str, list[str]] = {}
        chosen_cves: set[str] = set()
        for service in usable_services:
            if remaining_vulns == 0:
                break

            # Select a random number of vulnerabilities for the service
            vulns = services_pool.get_vulns(service, remaining_vulns)
            remaining_vulns -= len(vulns)
            chosen_cpes[service] = vulns
            chosen_cves.update(vulns)

        per_host_cves.append(chosen_cves)
        per_host_cpes.append(chosen_cpes)
        cve_pool.update(chosen_cves)

    with open(os.path.join(os.path.dirname(__file__), "inventory", "vulnerabilities.json")) as f:
        model.vulnerabilties = VulnerabilityPool.load_from_list_object(
            json.load(f), filter=cve_pool)

    # Create the hosts
    for i, chosen_cves, chosen_cpes in zip(range(num_hosts), per_host_cves, per_host_cpes):
        sn = i // 256
        ip = i % 254
        host = NetworkHost(i, f"Host-{i}", f"10.0.{sn}.{ip}",
                           list(chosen_cves), chosen_cpes, 0, 0.0, 0.0)
        model.add_host(host, drop_vuln=True)

    # Create the links
    for i in range(num_hosts):
        for j in range(num_hosts):
            if i == j:
                continue

            if random.random() <= link_probability:
                model.add_link(i, j)

    # Spread the hosts in a 2D grid
    positions: dict[int, tuple[float, float]
                    ] = graphviz_layout(model, prog="neato")
    for host_id, host in model.hosts.items():
        host.x, host.y = positions[host_id]

    return model
