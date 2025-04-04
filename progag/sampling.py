from abc import ABC, ABCMeta, abstractmethod
import random
from typing import Optional

import networkx as nx


from progag.model import AttackGraphModel

type Edge = tuple[int, int]

ABSOLUTE_MAX_LENGTH = 40


def generate_weight_pattern(N: int) -> list[int]:
    if N <= 0:
        return []
    N -= 1
    peak = N // 2
    first_half = list(range(peak + 1))
    second_half = first_half[:-1] if N % 2 == 0 else first_half
    return first_half + second_half[::-1]


WEIGHT_PATTERN = [
    [0, *generate_weight_pattern(i - 3), 0, 0] for i in range(ABSOLUTE_MAX_LENGTH + 1)
]


class PathSampler:
    # The attack graph model.
    model: AttackGraphModel
    # Minimum length of path the sampler tries to generate,
    # setting this won't guarantee it is actually generated.
    min_length: int
    # Maximum length of any path generated by the sampler.
    max_length: int
    # The sampling strategy.
    strategy: 'SamplingStrategy'

    # The hosts that can be sampled for starting paths
    # (e.g. the ones that have some outgoing edge).
    valid_hosts: list[int]
    # Number of generated paths.
    sampled: int

    # Whether to use the edge weights to determine the next host.
    use_dynamic_weights: bool

    # Weights assigned to each edge according to a specific
    # algorithm. Choosing an edge with a higher weight should
    # result in a higher probability of the path continuing.
    edge_weights: dict[Edge, int]

    def __init__(
        self, model: AttackGraphModel, *,
        min_length: Optional[int] = None,
        max_length: Optional[int] = None,
        hosts: Optional[set[int]] = None,
        strategy: Optional['SamplingStrategy'] = None,
        use_dynamic_weights: bool = True,
    ):
        if max_length is not None:
            assert max_length <= ABSOLUTE_MAX_LENGTH, \
                f"Max length must be less than {ABSOLUTE_MAX_LENGTH}"
        else:
            max_length = ABSOLUTE_MAX_LENGTH

        if min_length is not None:
            self.min_length = max(1, min_length)
            if min_length > max_length:
                raise ValueError(
                    "Min length must be less than or equal to max length")
        else:
            min_length = 1

        if strategy is None:
            strategy = Uniform()
        self.strategy = strategy

        self.model = model
        self.mode = type
        self.sampled = 0
        self.use_dynamic_weights = use_dynamic_weights

        self.valid_hosts = []
        for host in model.hosts.values():
            if not model.out_degree(host.id) and not model.in_degree(host.id):
                continue
            # If the hosts are set, remove from valid hosts
            # everything that is not in hosts.
            if hosts is not None and host.id not in hosts:
                continue

            self.valid_hosts.append(host.id)

        self.edge_weights = {}
        if self.use_dynamic_weights:
            for source, target in model.edges:
                self.edge_weights[source, target] = 4

        self.min_length = min_length
        self.max_length = min(max_length, len(
            self.valid_hosts), ABSOLUTE_MAX_LENGTH)

        # Initialize the strategy only after the sampler is fully initialized
        self.strategy.init(self)

    def sample_path(self) -> list[Edge]:
        """ Samples a path with the sampler's parameters. """
        path = self.strategy.sample(self)

        if self.use_dynamic_weights:
            self._update_weights(path)

        return path

    def _sample_one_end(
        self, start_host: int, max_length: int,
        forward: bool = True,
        visited: Optional[set[int]] = None
    ) -> list[Edge]:
        """
        Samples a path starting at `start_host` with length up to
        `max_length`, avoiding hosts in `visited`, if provided.

        If `forward` is set to False, the path is sampled backwards,
        and it ends at `start_host`.
        """
        if visited is None:
            visited = set()
        visited.add(start_host)

        path: list[Edge] = []
        current_host = start_host

        for _ in range(max_length):
            # Find the next host to visit, if possible
            next_host = self._sample_next_host(
                current_host, visited, forward=True)
            if not next_host:
                break

            visited.add(next_host)
            if forward:
                path.append((current_host, next_host))
            else:
                # When going backwards, you prepend the new edge
                # so that the target as the same as last edge's source.
                path.insert(0, (next_host, current_host))
            current_host = next_host

        return path

    def _sample_next_host(
        self, current_host: int, visited: set[int], forward: bool
    ) -> Optional[int]:
        """
        Samples the next host from `current_host`,
        avoiding hosts in `visited`.

        If `forward` is set, it looks at successors,
        otherwise it looks at predecessors.
        """
        # Get all candidates, already excluding those in visited.
        if forward:
            neighbors: list[int] = [
                host
                for host in self.model.neighbors(current_host)
                if host not in visited]
        else:
            neighbors: list[int] = [
                host
                for host in self.model.predecessors(current_host)
                if host not in visited]

        if not neighbors:
            return None
        elif len(neighbors) == 1:
            # Bypass random selection when there is only one choice.
            return neighbors[0]
        elif len(neighbors) == 2:
            if self.use_dynamic_weights:
                # Re-implementing random.sample here because
                # it is way faster.
                a, b = neighbors
                if forward:
                    wa = self.edge_weights[current_host, a]
                    wb = self.edge_weights[current_host, b]
                else:
                    wa = self.edge_weights[a, current_host]
                    wb = self.edge_weights[b, current_host]
                r = random.random()
                return a if r < wa / (wa + wb) else b
            else:
                r = random.random()
                return neighbors[0] if r < 0.5 else neighbors[1]
        else:
            if self.use_dynamic_weights:
                # Sample the next host from the neighbors
                # with a weight proportional to the number of paths
                # that have already passed through that host.
                if forward:
                    weights = [self.edge_weights[current_host, host]
                               for host in neighbors]
                else:
                    weights = [self.edge_weights[host, current_host]
                               for host in neighbors]
                return random.sample(neighbors, 1, counts=weights)[0]
            else:
                return random.choice(neighbors)

    def _sample_length(self) -> int:
        """ Get the maximum length of the next path. """
        mean = (self.max_length - self.min_length + 1) / 2
        # 99.7% of values will be within [mean - 3*stddev, mean + 3*stddev]
        stddev = mean / 3

        length = int(random.gauss(mean, stddev)) + self.min_length - 1

        # Ensure the length is within the valid range
        if length < self.min_length or length > self.max_length:
            return random.randint(self.min_length, self.max_length)
        return length

    def _update_weights(self, path: list[Edge]):
        """
        Updates the edge weights based on the paths that were
        traversed in this edge, following the pattern defined
        in `WEIGHT_PATTERN`.

        Every 200 paths, the weights are trimmed to avoid
        neglecting paths that were unlucky in the beginning.
        """
        final_length = len(path)

        # If this length is within the valid range, use it to update the weights
        if final_length in range(self.min_length, self.max_length + 1):
            # Increase the weight of each edge based on this logic:
            for weight, edge in zip(WEIGHT_PATTERN[final_length], path):
                self.edge_weights[edge] += weight

        self.sampled += 1
        if self.sampled % 200 == 0:
            for edge, score in self.edge_weights.items():
                if score >= 100:
                    self.edge_weights[edge] = score // 100


class SamplingStrategy(ABC, metaclass=ABCMeta):
    @abstractmethod
    def sample(self, sampler: PathSampler) -> list[Edge]:
        """ Sample a path from `sampler` with the given sampling strategy. """
        ...

    def init(self, sampler: PathSampler) -> None:
        """ Function run after the sampler is initialized. """
        ...


class Uniform(SamplingStrategy):
    """
    Samples paths uniformly, starting from a random host and moving
    forward for a random length.
    """

    def sample(self, sampler: PathSampler) -> list[Edge]:
        max_length = sampler._sample_length()
        start_host = random.choice(sampler.valid_hosts)
        path = sampler._sample_one_end(start_host, max_length)
        return path


class StartingAt(SamplingStrategy):
    """
    Samples paths starting from a random host and moving
    forward for a random length.
    """
    hosts: list[int]

    def __init__(self, hosts: list[int]):
        self.hosts = hosts

    def init(self, sampler: PathSampler) -> None:
        # Remove any hosts that are not valid
        self.hosts = [
            host for host in self.hosts if host in sampler.valid_hosts]

    def sample(self, sampler: PathSampler) -> list[Edge]:
        max_length = sampler._sample_length()
        start_host = random.choice(self.hosts)
        path = sampler._sample_one_end(start_host, max_length, forward=True)
        return path


class EndingAt(SamplingStrategy):
    """
    Samples paths ending at a random host and moving
    backwards for a random length.
    """
    hosts: list[int]

    def __init__(self, hosts: list[int]):
        self.hosts = hosts

    def init(self, sampler: PathSampler) -> None:
        # Remove any hosts that are not valid
        self.hosts = [
            host for host in self.hosts if host in sampler.valid_hosts]

    def sample(self, sampler: PathSampler) -> list[Edge]:
        max_length = sampler._sample_length()
        start_host = random.choice(self.hosts)
        path = sampler._sample_one_end(start_host, max_length, forward=False)
        return path


class PassingThrough(SamplingStrategy):
    """
    Samples paths that are guaranteed to pass through a set of hosts.
    """
    hosts: list[int]

    def __init__(self, hosts: list[int]):
        self.hosts = hosts

    def init(self, sampler: PathSampler):
        # Remove any hosts that are not valid
        self.hosts = [
            host for host in self.hosts if host in sampler.valid_hosts]

    def sample(self, sampler: PathSampler) -> list[Edge]:
        max_length = sampler._sample_length()
        start_host = random.choice(self.hosts)

        # Divide the length in two randomized parts
        first_half = random.randint(0, max_length)
        second_half = max_length - first_half

        visited: set[int] = set()
        first_path = sampler._sample_one_end(
            start_host, first_half, True, visited)
        second_path = sampler._sample_one_end(
            start_host, second_half, False, visited)

        return first_path + second_path


class SourceTarget(SamplingStrategy):
    """
    Samples paths that are guaranteed to start from a set of sources
    and end at a set of targets.
    """
    model: AttackGraphModel
    sources: list[int]
    targets: list[int]

    dfs_results: dict[Edge, int]

    def __init__(self, sources: list[int], targets: list[int]):
        self.sources = sources
        self.targets = targets

    def init(self, sampler: PathSampler):
        self.model = sampler.model

        # Remove any hosts that are not valid from the sources or targets
        self.sources = [
            host for host in self.sources if host in sampler.valid_hosts]
        self.targets = [
            host for host in self.targets if host in sampler.valid_hosts]

        # Force the use of dynamic weights for this strategy
        sampler.use_dynamic_weights = True

        self.dfs_results = {}
        for source in self.sources:
            for target in self.targets:
                res = self.dfs(source, target)
                if res:
                    self.dfs_results[(source, target)] = res

        # Make sure the results are not empty
        if self.dfs_results == {}:
            for source in self.sources:
                for target in self.targets:
                    self.dfs_results[(source, target)] = 40
            print("ERROR! No paths found between sources and targets")

    def sample(self, sampler: PathSampler) -> list[Edge]:
        # Sample a source and target
        source = random.choice(self.sources)
        target = random.choice(self.targets)
        # Re-sample the target until it is different from the source
        while target == source:
            target = random.choice(self.targets)

        # Sample a path from the source to the target
        path = sampler._sample_one_end(
            source, self.dfs_results[(source, target)] * 2, True)

        if not path:
            return []

        reached = path[-1][1]
        if reached in self.targets:
            return path

        return []

    def dfs(self, source: int, target: int) -> Optional[int]:
        """
        Runs a depth-first search from `source` to `target`,
        returning the minimum distance to each target.
        """
        graph = self.model

        visited: set[int] = set()
        visited.add(source)
        queue: list[tuple[int, int]] = [(source, 0)]

        while queue:
            node, distance = queue.pop(0)

            if node == target:
                return distance

            for neighbor in graph.successors(node):
                if neighbor in visited:
                    continue
                visited.add(neighbor)
                queue.append((neighbor, distance + 1))

        return None
