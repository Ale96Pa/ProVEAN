from typing import Any, Callable, Literal, Optional
from dataclasses import dataclass

import numpy as np

type JsonDict = dict[str, Any]


PRIV_GUEST = 0
PRIV_USER = 1
PRIV_ROOT = 2

type Privilege = Literal[0, 1, 2]
PRIVILEGE_STR = ["guest", "user", "root"]


# Maps the v2 or v3 authentication or privilegesRequired
# string into a single privilege.
RPSTR2PRIV: dict[str, Privilege] = {
    "NONE": PRIV_GUEST,
    "LOW": PRIV_GUEST,
    "SINGLE": PRIV_USER,
    "MEDIUM": PRIV_USER,
    "MULTIPLE": PRIV_USER,  # FIXME - Find the actual mapping for MULTIPLE
    "HIGH": PRIV_ROOT,
    "CRITICAL": PRIV_ROOT,
}


class Vulnerability:
    """ A vulnerability as read from the CVSS's JSON file. """
    _raw: JsonDict

    cve_id: str
    base_features: 'SteeringBaseFeatures'
    priv_required: Privilege
    priv_gained: Privilege

    def __init__(self, vuln: JsonDict):
        self._raw = vuln
        self.cve_id = vuln["id"]

        # Obtain the metrics
        metrics: JsonDict = vuln["metrics"]
        # Obtain the first v2 metric if it exists
        metricsv2: list[JsonDict] = metrics.get("cvssMetricV2", None)
        metric2: Optional[JsonDict] = metricsv2[0] if metricsv2 else None
        # Obtain the first v3.0 or v3.1 metric if they exist
        metricsv30: list[JsonDict] = metrics.get("cvssMetricV30", None)
        metric30: Optional[JsonDict] = metricsv30[0] if metricsv30 else None
        metricsv31: list[JsonDict] = metrics.get("cvssMetricV31", None)
        metric31: Optional[JsonDict] = metricsv31[0] if metricsv31 else None
        metric3 = metric30 or metric31
        self.base_features = SteeringBaseFeatures.parse(metric2, metric3)

        # Obtain the privileges
        self.priv_required, self.priv_gained = self._get_privileges(
            metric2, metric3)

    def __repr__(self) -> str:
        return f"<Vulnerability {self.cve_id}>"

    # Derivative features
    @property
    def impact(self) -> float:
        return self.base_features.impact_score

    @property
    def likelihood(self) -> float:
        return self.base_features.exploitability_score

    @property
    def score(self) -> float:
        return self.base_features.base_score

    def _get_privileges(
        self, v2: Optional[JsonDict], v3: Optional[JsonDict]
    ) -> tuple[Privilege, Privilege]:
        """
        Computes an estimate (very rough) of the required privilege
        level needed to exploit this vulnerability and the privilege
        level gained after exploiting it.
        """
        if v2:
            authentication: str = v2["cvssData"]["authentication"]
            req_priv: Privilege = RPSTR2PRIV[authentication]

            oap: bool = v2["obtainAllPrivilege"]
            oup: bool = v2["obtainUserPrivilege"]
            if oap:
                gain_priv: Privilege = PRIV_ROOT
            elif oup:
                gain_priv: Privilege = PRIV_USER
            else:
                # REVIEW - Why does this not return GUEST? Is it an error or a deliberate choice
                gain_priv: Privilege = PRIV_USER
        elif v3:
            pr: str = v3["cvssData"]["privilegesRequired"]
            scope: str = v3["cvssData"]["scope"]

            req_priv: Privilege = RPSTR2PRIV[pr]
            if scope == "UNCHANGED":
                gain_priv: Privilege = req_priv
            else:
                # REVIEW - This choice seems arbitrary, even though it is consistent
                # with the above one.
                gain_priv: Privilege = PRIV_USER
        else:
            req_priv = PRIV_GUEST
            gain_priv = PRIV_GUEST

        return req_priv, gain_priv

    def summary(self) -> str:
        """
        Returns a string that pretty-prints all relevant information
        about this vulnerability.
        """
        rp = PRIVILEGE_STR[self.priv_required]
        gp = PRIVILEGE_STR[self.priv_gained]

        s = color_string(self.base_features.base_severity,
                         0, 4, lambda x: f"sev:{x}")

        c = color_string(self.base_features.confidentiality_impact,
                         0, 3, lambda x: f"C:{x}")
        i = color_string(self.base_features.integrity_impact,
                         0, 3, lambda x: f"I:{x}")
        a = color_string(self.base_features.availability_impact,
                         0, 3, lambda x: f"A:{x}")

        # Short float with decimal point
        def sfwdp(x: float) -> str:
            if x == 10.0:
                return "MAX"
            else:
                return f"{x:>3.1f}"

        bas = color_string(self.base_features.base_score,
                           0.0, 10.0, lambda x: f"bs:{sfwdp(x)}")
        exp = color_string(self.base_features.exploitability_score,
                           0.0, 10.0, lambda x: f"es:{sfwdp(x)}")
        imp = color_string(self.base_features.impact_score,
                           0.0, 10.0, lambda x: f"is:{sfwdp(x)}")

        scores = f"{bas} {exp} {imp} {c}/{i}/{a}"
        return f"{self.cve_id:<16} {s} {scores} ({rp} -> {gp})"


# FIXME Move to utils or something.
def color_string[T: int | float](
        value: T, minimum: T, maximum: T,
        formatter: Callable[[T], str]) -> str:
    """
    Takes a value between min and max and colors the result of the formatter
    function applied to that value based on where it falls in the range.
    """
    string: str = formatter(value)

    min = float(minimum)
    max = float(maximum)
    val = float(value)
    dif = max - min

    # There are five color steps, from green to red
    # written with ANSI color codes
    LIME = "\x1b[92m"
    GREEN = "\x1b[33m"
    YELLOW = "\x1b[93m"
    ORANGE = "\x1b[91m"
    RED = "\x1b[31m"

    color: str = ""
    if val <= min + dif * 0.1:
        color = LIME
    elif val <= min + dif * 0.35:
        color = GREEN
    elif val <= min + dif * 0.65:
        color = YELLOW
    elif val <= min + dif * 0.9:
        color = ORANGE
    elif val <= max:
        color = RED

    return f"{color}{string}\x1b[0m"


# Maps most of the v2 or v3 categories into a single number.
CAT2NUM: dict[str, int] = {
    "NONE": 0,
    "NETWORK": 1,
    "LOW": 1,
    "SINGLE": 1,
    "PARTIAL": 1,
    "ADJACENT_NETWORK": 2,
    "MEDIUM": 2,
    "MULTIPLE": 2,
    "COMPLETE": 2,
    "LOCAL": 3,
    "HIGH": 3,
    "PHYSICAL": 4,
    "CRITICAL": 4,
}


@dataclass
class SteeringBaseFeatures:
    base_score: float
    impact_score: float
    exploitability_score: float

    access_vector: int
    access_complexity: int
    authentication: int
    confidentiality_impact: int
    integrity_impact: int
    availability_impact: int

    base_severity: int

    @staticmethod
    def parse(v2: Optional[JsonDict], v3: Optional[JsonDict]):
        """
        Parse the base features from the CVSS JSON object, either from
        the cvssv2Metric or from the cvssv30Metric (or cvssv31Metric).
        """
        if v2:
            metrics: JsonDict = v2
            cvss: JsonDict = metrics["cvssData"]

            access_vector = CAT2NUM[cvss["accessVector"]]
            access_complexity = CAT2NUM[cvss["accessComplexity"]]
            authentication = CAT2NUM[cvss["authentication"]]

            base_severity = CAT2NUM[metrics["baseSeverity"]]
        elif v3:
            metrics: JsonDict = v3
            cvss: JsonDict = metrics["cvssData"]

            access_vector = CAT2NUM[cvss["attackVector"]]
            access_complexity = CAT2NUM[cvss["attackComplexity"]]
            authentication = CAT2NUM[cvss["privilegesRequired"]]

            base_severity = CAT2NUM[cvss["baseSeverity"]]
        else:
            return SteeringBaseFeatures.default()

        base_score = cvss["baseScore"]
        impact_score = metrics["impactScore"]
        exploitability_score = metrics["exploitabilityScore"]

        confidentiality_impact = CAT2NUM[cvss["confidentialityImpact"]]
        integrity_impact = CAT2NUM[cvss["integrityImpact"]]
        availability_impact = CAT2NUM[cvss["availabilityImpact"]]

        return SteeringBaseFeatures(
            base_score, impact_score, exploitability_score,
            access_vector, access_complexity, authentication,
            confidentiality_impact, integrity_impact, availability_impact,
            base_severity)

    @staticmethod
    def default() -> 'SteeringBaseFeatures':
        return SteeringBaseFeatures(5.0, 5.0, 5.0, 0, 0, 0, 0, 0, 0, 0)

    @staticmethod
    def median(features: list['SteeringBaseFeatures']) -> 'SteeringBaseFeatures':
        """
        Computes the median of each feature given a list of base feature vectors.
        """
        return SteeringBaseFeatures(
            float(np.median([f.base_score for f in features])),
            float(np.median([f.impact_score for f in features])),
            float(np.median([f.exploitability_score for f in features])),
            int(np.median([f.access_vector for f in features])),
            int(np.median([f.access_complexity for f in features])),
            int(np.median([f.authentication for f in features])),
            int(np.median([f.confidentiality_impact for f in features])),
            int(np.median([f.integrity_impact for f in features])),
            int(np.median([f.availability_impact for f in features])),
            int(np.median([f.base_severity for f in features]))
        )

    def to_dict(self) -> dict[str, int | float]:
        """
        Converts this object into a dictionary.
        """
        return {
            "base_score": self.base_score,
            "impact_score": self.impact_score,
            "exploitability_score": self.exploitability_score,
            "access_vector": self.access_vector,
            "access_complexity": self.access_complexity,
            "authentication": self.authentication,
            "confidentiality_impact": self.confidentiality_impact,
            "integrity_impact": self.integrity_impact,
            "availability_impact": self.availability_impact,
            "base_severity": self.base_severity
        }


class VulnerabilityPool(dict[str, Vulnerability]):
    @staticmethod
    def load_from_list_object(
        data: list[JsonDict], filter: Optional[set[str]] = None
    ) -> 'VulnerabilityPool':
        """
        Load the list of vulnerabilities from a list of vulnerabilities
        as formatted in the CVSS's JSON dump.
        """
        pool = VulnerabilityPool()

        if filter is None:
            for raw_vuln in data:
                cve_id: str = raw_vuln["id"]
                vulnerability = Vulnerability(raw_vuln)

                pool[cve_id] = vulnerability
        else:
            for raw_vuln in data:
                cve_id: str = raw_vuln["id"]
                if cve_id not in filter:
                    continue
                vulnerability = Vulnerability(raw_vuln)
                pool[cve_id] = vulnerability

        return pool

    def __init__(self):
        super().__init__()

    def __repr__(self) -> str:
        return f"<VulnerabilityPool {len(self)} vulnerabilities>"

    def get_from(self, *, year: int, id: int) -> Optional[Vulnerability]:
        cve_id = f"CVE-{year}-{id:0>4}"
        return self.get(cve_id, None)

    def print_summary(self):
        for vuln in self.values():
            print(vuln.summary())
