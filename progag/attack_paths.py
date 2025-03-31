from dataclasses import dataclass
import hashlib
import statistics

from progag.model import AttackGraphModel
from progag.vulnerabilities import SteeringBaseFeatures, Vulnerability
from progag.sampling import Edge


@dataclass
class AttackPath:
    trace: str
    length: int

    likelihood: float
    impact: float
    score: float
    risk: float
    # New metric, average of impacts.
    damage: float

    hash: str
    vulns: list[Vulnerability]
    edges: list[Edge]

    def __init__(self, trace: str,
                 vulns: list[Vulnerability],
                 edges: list[Edge]):
        self.trace = trace

        # The length is the number of exploited vulnerabilities
        self.length = len(vulns)

        # The likelihood is the average
        self.likelihood = statistics.mean(v.likelihood for v in vulns)
        # The impact is the impact on the last
        self.impact = vulns[-1].impact
        # The score is the median of the scores
        self.score = statistics.median(v.score for v in vulns)
        # The risk is the product of likelihood and impact
        self.risk = self.likelihood * self.impact / 10.0
        # Compute the damage
        self.damage = statistics.mean(v.impact for v in vulns)

        self.hash = hashlib.sha256(trace.encode()).hexdigest()
        self.vulns = vulns
        self.edges = edges

    def to_dict(self) -> dict:
        return {
            "trace": self.trace,
            "length": self.length,
            "likelihood": self.likelihood,
            "impact": self.impact,
            "score": self.score,
            "risk": self.risk,
            "damage": self.damage,
            "hash": self.hash
        }

    @property
    def hosts(self) -> set[int]:
        hosts = set()
        for source, target in self.edges:
            hosts.add(source)
            hosts.add(target)
        return hosts

    @property
    def source_host(self) -> int:
        return self.edges[0][0]

    @property
    def target_host(self) -> int:
        return self.edges[-1][1]

    def to_features_vector(self) -> SteeringBaseFeatures:
        """
        Converts the attack path to a feature vector for
        training the decision tree.
        """
        return SteeringBaseFeatures.median(
            [v.base_features for v in self.vulns])

    @staticmethod
    def from_trace(trace: str, model: AttackGraphModel) -> 'AttackPath':
        """ Obtains the attack path from a trace and the AG model. """
        # Split the AP into steps
        edges = []
        vulns = []
        for step in trace.split("##"):
            priv_source, cve, priv_target = step.split("#")

            source = int(priv_source.split("@")[1])
            target = int(priv_target.split("@")[1])
            edges.append((source, target))
            vulns.append(model.vulnerabilties[cve])

        return AttackPath(trace, vulns, edges)


STEPS = 8
METRIC_STEPS = 100
MAX_LENGTH = 40


class AttackPathStatistics:
    num_paths = 0

    # Maps the index of the likelihood, impact and score arrays
    # to the highest value that falls in there
    scale: list[float]

    likelihoods: list[int]
    impacts: list[int]
    damages: list[int]
    scores: list[int]
    lengths: list[int]
    risks: list[int]

    # Maps one host to the amount of times it appears in an AP.
    hosts_count: dict[int, int]
    # Maps a source host to a map from the destination host to
    # the number that edge is traversed in an AP.
    edges_count: dict[int, dict[int, int]]

    # Sum of all values in hosts_count.
    hosts_sum: int
    # Sum of all values in edges_count.
    edges_sum: int

    def __init__(self):
        self.scale = []
        for i in range(METRIC_STEPS):
            self.scale.append((i + 1) / METRIC_STEPS * 10)

        self.likelihoods = [0] * METRIC_STEPS
        self.impacts = [0] * METRIC_STEPS
        self.damages = [0] * METRIC_STEPS
        self.scores = [0] * METRIC_STEPS
        self.risks = [0] * METRIC_STEPS

        self.lengths = [0] * MAX_LENGTH

        self.hosts_count = {}
        self.edges_count = {}
        self.hosts_sum = 0
        self.edges_sum = 0

    def update(self, new_paths: list[AttackPath]):
        self.num_paths += len(new_paths)

        for ap in new_paths:
            self._update_hosts_and_edges(ap)

            li = ap.likelihood
            im = ap.impact
            sc = ap.score
            ri = ap.risk
            le = ap.length
            dg = ap.damage

            self.likelihoods[get_metric_index(li)] += 1
            self.impacts[get_metric_index(im)] += 1
            self.scores[get_metric_index(sc)] += 1
            self.risks[get_metric_index(ri)] += 1
            self.damages[get_metric_index(dg)] += 1

            if le >= MAX_LENGTH:
                self.lengths[MAX_LENGTH - 1] += 1
            else:
                self.lengths[le] += 1

    def _update_hosts_and_edges(self, ap: AttackPath):
        for source, target in ap.edges:
            # Create the source dict if absent
            if source not in self.edges_count:
                self.edges_count[source] = {}

            # Create the key entry if not present
            if target not in self.edges_count[source]:
                self.edges_count[source][target] = 1
            else:
                self.edges_count[source][target] += 1

            self.edges_sum += 1

        for host in ap.hosts:
            if host not in self.hosts_count:
                self.hosts_count[host] = 1
            else:
                self.hosts_count[host] += 1

            self.hosts_sum += 1

    def format(self, *, metric_steps: int = 5, plot_height: int = 3) -> str:
        assert METRIC_STEPS % metric_steps == 0
        plot_width = METRIC_STEPS // metric_steps

        li_rows = self.format_metric(
            metric_steps, self.likelihoods, plot_height)
        im_rows = self.format_metric(
            metric_steps, self.impacts, plot_height)
        sc_rows = self.format_metric(
            metric_steps, self.scores, plot_height)

        le_rows = self.format_metric(
            1, self.lengths[1:], plot_height)

        border_width = plot_width * 3 + 7 + MAX_LENGTH

        # First row, border
        result = f"┌{"─" * border_width}┐\n"
        # Other rows, bar charts
        for li, im, sc, le in zip(li_rows, im_rows, sc_rows, le_rows):
            result += f"│ {li}  {im}  {sc}  {le} │\n"
        # Penultimate row: labels
        result += "│ "
        for string in ["Likelihood", "Impact", "Score"]:
            if plot_width < len(string):
                result += f"{string[:plot_width-3]}...  "
            else:
                result += f"{string}{" " * (plot_width - len(string))}  "
        result += f"Length{" " * (MAX_LENGTH - 6)}│\n"
        # Last row: border
        result += f"└{"─" * border_width}┘"

        return result

    def format_metric(self, metric_steps: int, data: list[int], plot_height: int):
        """
        Formats a single metric in an ASCII bar chart.
        """
        plot_width = len(data) // metric_steps

        y_data = [sum(data[i*metric_steps:(i+1)*metric_steps])
                  for i in range(plot_width)]
        y_max = max(y_data)
        y_axis = [y / y_max for y in y_data]

        rows: list[list[str]] = [
            [' '] * plot_width for _ in range(plot_height)]

        for x, height in enumerate(y_axis):
            actual_height = int(height * plot_height * 2) / 2

            if actual_height == 0.0:
                rows[-1][x] = "_"
            else:
                y = plot_height - 1
                while actual_height >= 1:
                    # ASCII full block
                    rows[y][x] = "█"
                    actual_height -= 1.0
                    y -= 1
                if actual_height == 0.5:
                    rows[y][x] = "▄"

        # Reduce each row accordingly
        return ["".join(row) for row in rows]


def get_metric_index(value: float) -> int:
    if value == 10.0:
        return METRIC_STEPS - 1
    else:
        return int(value / 10 * METRIC_STEPS)
