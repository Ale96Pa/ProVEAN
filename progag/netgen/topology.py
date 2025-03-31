import enum
import math
import random
from typing import Optional

import numpy as np
import networkx as nx
from networkx.drawing.nx_agraph import graphviz_layout


type Coordinate = tuple[float, float]


class TopologyType(enum.Enum):
    RING = enum.auto()
    STAR = enum.auto()
    COMPLETE = enum.auto()
    RANDOM = enum.auto()

    COMPLEX = enum.auto()


class Topology:
    num_nodes: int
    type: TopologyType

    index_offset: int = 0
    protection_domain: int = 0

    graph: nx.Graph
    host_positions: dict[int, Coordinate]

    offset: Coordinate
    radius: float

    def __init__(self, num_nodes: int, type: TopologyType):
        self.num_nodes = num_nodes
        self.host_positions = {}
        self.type = type

    @staticmethod
    def create_standard(
        num_nodes: int, topology_type: TopologyType
    ) -> 'Topology':
        """
        Creates a simple network topology of the given type.

        It also computes the host position and the network radius.
        """
        net = Topology(num_nodes, topology_type)

        match topology_type:
            case TopologyType.RING:
                net.graph = nx.cycle_graph(num_nodes)
            case TopologyType.STAR:
                net.graph = nx.star_graph(num_nodes - 1)
            case TopologyType.COMPLETE:
                net.graph = nx.complete_graph(num_nodes)
            case TopologyType.RANDOM:
                # TODO - Check if this causes an error when n=2 and m=2
                net.graph = nx.gnm_random_graph(
                    num_nodes, random.randint(num_nodes, num_nodes + 10))
            case _:
                raise ValueError(f"Cannot generate: {topology_type}")

        # Compute the drawing position
        net.host_positions = graphviz_layout(net.graph, prog="neato")
        center, radius = find_center_and_radius(
            list(net.host_positions.values()))

        net.offset = (-center[0], -center[1])
        net.add_offset_to_all_hosts()
        net.offset = (0, 0)

        net.radius = radius

        return net

    def does_overlap(self, other: 'Topology') -> bool:
        """
        Check if the current network overlaps with another network.
        """
        # Compute the distance between the two centers
        x1, y1 = self.offset
        x2, y2 = other.offset

        distance2 = (x1 - x2) ** 2 + (y1 - y2) ** 2
        return distance2 < (self.radius + other.radius) ** 2

    def __repr__(self) -> str:
        type = f"of type {self.type.name}"
        nums = f"with {self.num_nodes} nodes and {len(self.graph.edges)} edges"

        return f"ComputerNetwork {type} {nums}"

    def add_offset_to_all_hosts(self):
        """
        Adds the offset to all host positions.
        """
        (x0, y0) = self.offset

        # Remove the center from every host's position, so that they are
        # relative to the center.
        for host_id, (x, y) in self.host_positions.items():
            # Round to the nearest 0.01
            xn = (x + x0) // 0.01 * 0.01
            yn = (y + y0) // 0.01 * 0.01
            self.host_positions[host_id] = (xn, yn)

    def to_json(self) -> dict:
        return {
            "hosts": self.host_positions,
            "edges": [list(edge) for edge in self.graph.edges],
        }


def create_network(
    num_nodes: int,
    *,
    min_subnet_size: int = 3,
    max_subnet_size: int = 15,

    min_neigh_conn: int = 1,
    max_neigh_conn: int = 3,

    min_link_per_conn: int = 1,
    max_link_per_conn: int = 4,
) -> tuple[Topology, dict[int, int], int]:
    """
    Creates a network with a rather convoluted process. 

    Here is the explanation:
    - We take the `num_nodes` nodes and partition them into parts of
      random sizes.
    - Based on each partition's size we choose a type (e.g. ring, star,
      complete, etc.) and create the network.
    - For each subnetwork, we get the position of each node relative to
      the subnetwork's center using `graphviz_layout` and we compute the
      radius of the network.
    - We treat each subnet as big circles and use an algorithm to spread
      them out so that they do not overlap, obtaining a new offset for
      each subnet.
    - We reposition all host's subnets based on their offsets to get their
      final position and merge all subnets.
    - Based on a nearest-neighbor algorithm, we choose which other subnets
      each subnet should be connected to and create random links between the
      two between the two nodes that are closest to each other based on the
      final layout, to avoid clutter.


    Returns:
    - A Topology object representing the composed network.
    - A map from each host to the protection domain it belongs to.
    - The number of protection domains in the network.
    """
    # Divide the hosts in smaller partitions
    subnet_plans = plan_subnets(num_nodes, min_subnet_size, max_subnet_size)

    # Create a network for each partition
    networks: list[Topology] = []

    current_offset: int = 0
    for i, (net_size, net_type) in enumerate(subnet_plans):
        net = Topology.create_standard(net_size, net_type)
        net.protection_domain = i
        # Update the network offset for when we will do the merging
        net.index_offset = current_offset
        current_offset += net_size
        networks.append(net)

    # Reposition the networks so that they do not overlap
    spread_networks(networks)
    for net in networks:
        net.add_offset_to_all_hosts()

    # Create the composed graph and merge all subgraphs
    complex = Topology(num_nodes, TopologyType.COMPLEX)
    complex.graph = nx.Graph()
    host_domains: dict[int, int] = {}

    for net in networks:
        o = net.index_offset

        for host_id, pos in net.host_positions.items():
            complex.host_positions[host_id + o] = pos
            complex.graph.add_node(host_id + o)
            host_domains[host_id + o] = net.protection_domain
        for edge in net.graph.edges:
            complex.graph.add_edge(edge[0] + o, edge[1] + o)

    for net in networks:
        # Get the networks this should be connected to
        k = random.randint(
            min(len(networks) - 1, min_neigh_conn),
            min(len(networks) - 1, max_neigh_conn))
        nearest_neighbors = k_nn_of(net, networks, k)

        for neigh in nearest_neighbors:
            # Get the number of links there should be between
            # these two subnetworks.
            num_links = random.randint(min_link_per_conn, max_link_per_conn)
            nearest_pairs = find_k_nearest_pairs(net, neigh, k=num_links)

            for (a, b) in nearest_pairs:
                complex.graph.add_edge(a, b)

    return complex, host_domains, len(subnet_plans)


def plan_subnets(
    num_nodes: int, min_size: int = 3, max_size: int = 15
) -> list[tuple[int, TopologyType]]:
    """
    Partition the given hosts into smaller subnets, such
    that the sizes are, if possible, within the given range.

    For each subnet, define the desired type it will have
    based on the relative size.
    """
    partition: list[int] = []

    # Divide the total in a random amount of parts
    # such that no part is smaller than 2.
    selected: int = 0

    while selected < num_nodes - 2:
        max_next_size: int = min(max_size, num_nodes - selected)
        next_part: int = random.randint(min_size, max_next_size)

        partition.append(next_part)
        selected += next_part

    # Add the difference to the smallest partition
    difference = num_nodes - selected
    if difference != 0:
        smallest_index = np.argmin(partition)
        partition[smallest_index] += difference
    assert sum(partition) == num_nodes

    types: list[TopologyType] = []
    for num_hosts in partition:
        part_type: TopologyType = _select_partition_type(num_hosts)
        types.append(part_type)

    return list(zip(partition, types))


def _select_partition_type(num_hosts: int) -> TopologyType:
    avail = [TopologyType.STAR, TopologyType.RANDOM,
             TopologyType.COMPLETE, TopologyType.RING]

    if num_hosts >= 8:
        avail.remove(TopologyType.RING)
    if num_hosts >= 6:
        avail.remove(TopologyType.COMPLETE)

    return random.choice(avail)


def find_center_and_radius(
    coordinates: list[Coordinate]
) -> tuple[Coordinate, float]:
    """
    Find the center point of a graph and the radius of the graph.
    """
    x_coords, y_coords = zip(*coordinates)
    x_center, y_center = np.mean(x_coords), np.mean(y_coords)

    distances = np.sqrt((x_coords - x_center) ** 2 +
                        (y_coords - y_center) ** 2)
    radius = np.max(distances) * 1.1

    return (float(x_center), float(y_center)), radius


def spread_networks(networks: list[Topology]):
    """
    Spread the networks in the plane so that they do not overlap.

    Mutates the networks in place.
    """
    overlap = _find_overlap(networks)

    while overlap is not None:
        (a, b) = overlap
        step = min(a.radius, b.radius) / 3
        angle = random.uniform(0, 2 * math.pi)

        while a.does_overlap(b):
            a.offset = (a.offset[0] + step * math.cos(angle),
                        a.offset[1] + step * math.sin(angle))

        ax = float(a.offset[0]) // 0.01 * 0.01
        ay = float(a.offset[1]) // 0.01 * 0.01

        a.offset = (ax, ay)

        overlap = _find_overlap(networks)


def _find_overlap(
    networks: list[Topology]
) -> Optional[tuple[Topology, Topology]]:
    """
    Find the first pair of networks that overlap.
    """
    for i, net1 in enumerate(networks):
        for j, net2 in enumerate(networks):
            if i != j and net1.does_overlap(net2):
                return (net1, net2)
    return None


def k_nn_of(
    net: Topology, networks: list[Topology], k: int = 2
) -> list[Topology]:
    """
    Updates `net.nearest_neighbors` with the `k` networks that are
    closest to `net` from the given list except `net`.
    """
    neighbors: list[tuple[float, Topology]] = []

    for neigh in networks:
        # You are not your nearest neighbor
        if net == neigh:
            continue

        distance = np.sqrt((net.offset[0] - neigh.offset[0]) ** 2 +
                           (net.offset[1] - neigh.offset[1]) ** 2)
        neighbors.append((distance, neigh))

    neighbors.sort(key=lambda x: x[0])
    return [nb for _, nb in neighbors[:k]]


def find_k_nearest_pairs(
    a: Topology, b: Topology, k: int = 2
) -> list[tuple[int, int]]:
    """
    Find the k nearest pairs of nodes from a and b.
    """
    pairs: list[tuple[float, int, int]] = []

    for na, (pax, pay) in a.host_positions.items():
        for nb, (pbx, pby) in b.host_positions.items():
            dist = math.sqrt((pax - pbx) ** 2 + (pay - pby) ** 2)
            pairs.append((dist, na, nb))

    pairs.sort()
    return [(na + a.index_offset, nb + b.index_offset) for (_, na, nb) in pairs[:k]]
