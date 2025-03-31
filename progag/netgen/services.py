import json
from os.path import dirname, abspath, join
import random
import time


PATH = abspath(join(dirname(__file__), "inventory", "cpe_cves.json"))


class ServicesPool:
    cves_per_cpe: dict[str, list[str]]

    valid_os_cpes: list[str]
    app_cpes: list[str]

    path: str
    _loaded: bool = False

    def __init__(self, json_path: str):
        self.path = json_path

    def _ensure_loaded(self):
        if self._loaded:
            return

        self.app_cpes = []
        self.valid_os_cpes = []
        # Time it
        start_time: float = time.time()
        with open(self.path) as f:
            self.cves_per_cpe = json.load(f)
            for key in self.cves_per_cpe.keys():

                if key.startswith("o:linux") or key.startswith("o:microsoft:windows") or key.startswith("o:apple:mac_os_x"):
                    self.valid_os_cpes.append(key)
                elif key[0] != 'o':
                    self.app_cpes.append(key)

        end_time: float = time.time()

        print(f"Loaded {len(self.cves_per_cpe)} CPEs with CVEs in {
              end_time - start_time:.2f}s")
        self._loaded = True

    def choose_oses(self, os_count: int) -> list[str]:
        """
        Choose the given amount of CPEs from the pool
        that qualify as OSes (see `is_valid_os`).
        """
        self._ensure_loaded()

        os_count = min(os_count, len(self.valid_os_cpes))
        return random.sample(self.valid_os_cpes, os_count)

    def choose_services(self, app_count: int) -> list[str]:
        """
        Choose the given amount of CPEs from the pool.
        """
        self._ensure_loaded()

        app_count = min(app_count, len(self.app_cpes))
        return random.sample(self.app_cpes, app_count)

    def get_vulns(self, cpe: str, num: int) -> list[str]:
        """
        Returns the given number of CVEs for the given CPE,
        if possible. If not enough CVEs are available, returns
        all of them.
        """
        self._ensure_loaded()

        if cpe not in self.cves_per_cpe:
            return []

        actual_count = min(num, len(self.cves_per_cpe[cpe]))
        return random.sample(self.cves_per_cpe[cpe], actual_count)


services_pool = ServicesPool(PATH)


def is_valid_os(cpe: str) -> bool:
    return cpe.startswith("o:linux") or\
        cpe.startswith("o:microsoft:windows") or\
        cpe.startswith("o:apple:mac_os_x")
