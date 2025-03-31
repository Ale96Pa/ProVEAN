"""
Provides the structures needed to represent the attack graph model,
including the reachability graph and the node's vulnerabilities and
services.
"""
from dataclasses import dataclass
import json
import random
from typing import Any, Optional

import networkx as nx

from progag.vulnerabilities import PRIV_ROOT, Privilege, VulnerabilityPool


@dataclass
class NetworkHost:
    # An integer uniquely identifying the host in the network
    id: int
    # The name of the host
    hostname: str
    # The IPv4 address of the host
    ipv4: str

    # The list of all CVEs on the host
    cves: list[str]
    # Map between service CPE and CVE.
    services: dict[str, list[str]]
    # The host protection domain, if anyone cares
    domain: int = 0

    # The host coordinates in the plot
    x: float = 0.0
    y: float = 0.0

    # Method for JSON serialization
    def to_json(self):
        return {
            "id": self.id,
            "hostname": self.hostname,
            "ipv4": self.ipv4,
            "services": self.services,
            "cves": self.cves,
            "domain": self.domain,
            "x": self.x,
            "y": self.y
        }

    @staticmethod
    def from_json(o: dict[str, Any]) -> 'NetworkHost':
        return NetworkHost(
            id=o["id"],
            hostname=o["hostname"],
            ipv4=o["ipv4"],
            cves=o["cves"],
            services=o["services"],
            domain=o.get("domain", 0),
            x=o.get("x", 0),
            y=o.get("y", 0))


class AttackGraphModel(nx.DiGraph):
    """
    Represents the entirety of the attack graph model: nodes, the edges
    between them and vulnerabilities and services for each host.
    """
    # Map from host ID (in nx.DiGraph) to the host attributes
    hosts: dict[int, NetworkHost]
    # List of vulnerabilities
    vulnerabilties: VulnerabilityPool

    # Host ids for fast random selection
    host_keys: list[int]

    def __init__(self):
        super().__init__()
        self.hosts = {}
        self.host_keys = []
        self.vulnerabilties = VulnerabilityPool()

    def __str__(self) -> str:
        n = self.number_of_nodes()
        m = self.number_of_edges()
        v = len(self.vulnerabilties.items())
        return f"AttackGraphModel(n={n}, m={m}, v={v})"

    def __repr__(self) -> str:
        return str(self)

    @staticmethod
    def read_from_file(filename: str) -> 'AttackGraphModel':
        """ Read the attack graph model from a JSON file. """
        model = AttackGraphModel()

        with open(filename, 'r') as file:
            data = json.load(file)
            model.vulnerabilties = VulnerabilityPool.load_from_list_object(
                data["vulnerabilities"])
            for host in data["hosts"]:
                model.add_host(NetworkHost.from_json(host))
            for edge in data["edges"]:
                model.add_edge(edge[0], edge[1])

        return model

    def save_to_file(self, filename: str):
        """ Save all the attack graph model data to a JSON file. """
        data = self.to_json()
        with open(filename, 'w') as file:
            json.dump(data, file, indent=2)

    def to_json(self) -> object:
        return {
            "hosts": [h.to_json() for h in self.hosts.values()],
            "edges": [e for e in self.edges],
            "vulnerabilities": [v._raw for v in self.vulnerabilties.values()]
        }

    def add_host(self, host: NetworkHost, ignore_vulns: bool = False, drop_vuln=False):
        """ 
        Add the given host to the model.

        If `ignore_vulns` is True, do not check whether the vulnerabilities
        are present in the pool.

        If `drop_vuln` is True, ignores the specified vulnerabilities
        if they are not present in the pool.
        """
        if host.id not in self.hosts:
            self.host_keys.append(host.id)
        self.add_node(host.id)
        self.hosts[host.id] = host

        # Make sure all vulnerabilities in the new host
        # are present in the pool.
        if not ignore_vulns:
            for cve in host.cves:
                if cve not in self.vulnerabilties:
                    if not drop_vuln:
                        raise ValueError(f"Vulnerability {
                            cve} not found in the pool")
                    else:
                        host.cves.remove(cve)

            for cpe, cves in host.services.items():
                for cve in cves:
                    if cve not in self.vulnerabilties:
                        if not drop_vuln:
                            raise ValueError(f"Vulnerability {
                                cve} not found in the pool")
                        else:
                            host.services[cpe].remove(cve)

    def add_link(self, source: int, target: int):
        """ Add a bidirectional link between two hosts. """
        self.add_edge(source, target)
        self.add_edge(target, source)

    def get_random_host(self) -> int:
        """ Get a random host in the network. """
        return random.choice(self.host_keys)

    def sample_cve_on_host(
        self, host_id: int,
        current_priv: Privilege = PRIV_ROOT,
        preferred_cves: Optional[set[str]] = None
    ) -> Optional[str]:
        """
        Samples a CVE on the host such that the required privilege
        of the CVE is already possessed by the attacker.

        If `preferred_cves` is set, it will try to use those first.
        """
        # Get the vulnerabilities on the target host
        host = self.hosts[host_id]
        cves = host.cves

        if preferred_cves is not None:
            # Remove all the non-preferred cves from the list of cves
            cves = [cve for cve in cves if cve in preferred_cves]
            # If there are no preferred cves, retry without them
            if not cves:
                return self.sample_cve_on_host(host_id, current_priv)

        # If you have root, you can exploit anything
        if current_priv == PRIV_ROOT:
            # Just return any vulnerability
            return random.choice(cves)

        # Filter the vulnerabilities with a lower or equal
        # requested privilege
        filtered = []
        for cve in cves:
            requested = self.vulnerabilties[cve].priv_required
            if requested <= current_priv:
                filtered.append(cve)

        # If after filtering you found nothing, and you were trying
        # to use preferred CVEs, first try without them
        if not filtered and preferred_cves is not None:
            return self.sample_cve_on_host(host_id, current_priv)

        if not filtered:
            return None

        return random.choice(filtered)
