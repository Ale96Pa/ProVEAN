import json
import os
import random
from typing import Optional

from tqdm import tqdm

from .services import services_pool
from .topology import create_network
from .palma import convert_palma
from .mesh import create_mesh_model

from ..model import AttackGraphModel, NetworkHost
from ..vulnerabilities import VulnerabilityPool


def generate_model(
    num_hosts: int = 100,
    *,
    min_subnet_size: int = 3,
    max_subnet_size: int = 15,

    different_oses: int = 5,
    min_services_per_host: int = 1,
    max_services_per_host: int = 3,
    min_vulns_per_service: int = 1,
    max_vulns_per_service: int = 2,

    os_has_vulns=True,
    output_topology: Optional[str] = None,
    log: bool = False,
) -> AttackGraphModel:
    """
    Generates a good-looking network (plane-wise) with a somewhat realistic
    distribution of vulnerabilities: if a host has a CVE, it must affect at
    least one of the services running on the host.
    """
    if log:
        print("Creating network topology...")
    net, host_domains, domains_count = create_network(
        num_hosts, min_subnet_size=min_subnet_size, max_subnet_size=max_subnet_size)

    # Output the topology only if requested
    if output_topology is not None:
        data = net.to_json()
        with open(output_topology, "w+") as file:
            json.dump(data, file, indent=2)
    if log:
        print("Network topology created")

    # All machines within a domain share the same OS.
    base_oses = services_pool.choose_oses(different_oses)
    domain_os_cpe: dict[int, str] = {}
    for domain in range(domains_count):
        domain_os_cpe[domain] = random.choice(base_oses)
    if log:
        print(f"Chosen OS pool for each domain")

    # All machines within a domain will get services from the same pool
    domain_services: dict[int, list[str]] = {}
    for domain in range(domains_count):
        # TODO - Find a better distribution
        domain_services[domain] = services_pool.choose_services(
            max_services_per_host * 2)
    if log:
        print("Chosen service pool for each domain")

    # We want to also keep track of all vulnerabilities in the system
    vuln_pool: set[str] = set()

    # Create the host.
    model = AttackGraphModel()
    for edge in net.graph.edges:
        model.add_link(edge[0], edge[1])

    # Add the hosts to the model
    if log:
        print("Creating hosts...")
    iter = tqdm(range(num_hosts)) if log else range(num_hosts)
    for host_id in iter:
        # The domain this host belongs to
        domain = host_domains[host_id]

        # Find an IP address for the host
        ipv4 = f"192.168.{domain}.{host_id + 1}"
        # Find an hostname for the host
        hostname = f"server{host_id + 1}_domain{domain}"

        domain_os = domain_os_cpe[domain]
        domain_cpes = domain_services[domain]

        total_vulns = 0

        while True:
            # Choose the services for this host
            # - the OS, obviously
            host_services: list[str] = [domain_os] if os_has_vulns else []
            # - the services
            num_services = random.randint(
                min_services_per_host, max_services_per_host)
            host_services.extend(random.sample(domain_cpes, num_services))

            # For each service, choose the vulnerabilities
            host_vulns: set[str] = set()
            host_cves_per_cpe: dict[str, list[str]] = {}
            for cpe in host_services:
                num_vulns = random.randint(
                    min_vulns_per_service, max_vulns_per_service)
                vulns = services_pool.get_vulns(cpe, num_vulns)

                host_vulns.update(vulns)
                host_cves_per_cpe[cpe] = vulns

            total_vulns = len(host_vulns)
            if total_vulns >= num_services * min_vulns_per_service:
                break

        # Add the vulnerabilities to the pool
        vuln_pool.update(host_vulns)

        # Create the host
        host = NetworkHost(
            id=host_id,
            hostname=hostname,
            ipv4=ipv4,
            cves=list(host_vulns),
            services=host_cves_per_cpe,
            domain=domain,
            x=net.host_positions[host_id][0],
            y=net.host_positions[host_id][1],
        )

        model.add_host(host, ignore_vulns=True)

    # Read the vulnerabilities JSON file
    with open(os.path.join(os.path.dirname(__file__), "inventory", "vulnerabilities.json"), encoding="utf8") as f:
        model.vulnerabilties = VulnerabilityPool.load_from_list_object(
            json.load(f), filter=vuln_pool)

    return model
