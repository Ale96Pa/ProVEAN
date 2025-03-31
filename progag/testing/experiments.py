import os
from typing import Optional

from tqdm import tqdm

from progag.generation import PathGenerator
from progag.model import AttackGraphModel
from progag.testing.statistical import AGStatistics, StatAGStatistics

EXPERIMENTS_PATH = "./experiments/"


class Experiment:
    model: AttackGraphModel
    name: str
    folder: str

    expcnt: int

    def __init__(self, name: str):
        self.name = name

        if name.startswith("../") or name.startswith("./"):
            self.folder = name + "/"
        else:
            self.folder = EXPERIMENTS_PATH + name + "/"
        self.model = AttackGraphModel.read_from_file(
            self.folder + "model.json")

        self.expcnt = 0
        # Count the number of exp *folders* inside the main folder
        for _, folders, _ in os.walk(self.folder):
            for f in folders:
                if f.startswith("exp"):
                    self.expcnt += 1

    # ------------------------
    # | StatAG (experiments) |
    # ------------------------
    def run_statag(
        self, times: int, iterations: int = 1000,
        samples_per_iter: int = 100,
        max_length: Optional[int] = None,
    ):
        """
        Runs a StatAG path generator the given number of times,
        each with the given number of iterations.
        """
        # Create the directories that will contain the generated paths
        statag_dir = self.folder + "/statag/"
        for i in range(self.expcnt, self.expcnt+times):
            _mkdir(statag_dir + f"exp{i}/")

        # Run the StatAG path generator
        for i in range(self.expcnt, self.expcnt+times):
            print("[TEST] Running StatAG experiment "
                  f"{i + 1}/{self.expcnt + times}")

            try:
                gen = PathGenerator(
                    self.model,
                    db_path=statag_dir + f"exp{i}/aps.db",
                    csv_path=statag_dir + f"exp{i}/log.csv",
                    sample_size=samples_per_iter,
                    compute_statistics=False,
                    max_length=max_length)

                for i in tqdm(range(iterations)):
                    gen.step()
            except KeyboardInterrupt:
                print("[TEST] StatAG generation interrupted by CTRL+C")
                exit(1)

        self.expcnt += times

    def compute_exp_statistics(self):
        """
        For each experiment, computes the statistics of the generated paths
        at each iteration.
        """
        for i in range(self.expcnt):
            db_path = self.exp_folder(i) + "aps.db"
            stats_path = self.exp_folder(i) + "stats.json"

            # Make sure they are not already computed
            if os.path.exists(stats_path):
                continue
            # Make sure the db exists
            if not os.path.exists(db_path):
                raise FileNotFoundError(
                    f"Database for experiment {i} not found")

            print("[TEST] Computing statistics for experiment "
                  f"{i + 1}/{self.expcnt}")
            stats = StatAGStatistics.from_statag_db(db_path)
            stats.write_to(stats_path)

    def exp_folder(self, i: int) -> str:
        return self.folder + f"statag/exp{i}/"

    def exp_distro(self, i: int) -> StatAGStatistics:
        """
        Returns the metric distributions for the given experiment.
        """
        path = self.exp_folder(i) + "stats.json"
        return StatAGStatistics.read_from(path)

    # ----------------
    # | Ground Truth |
    # ----------------
    def compute_gt_statistics(self):
        gt_path = self.folder + "gt/"
        db_path = gt_path + "aps.db"
        out_path = gt_path + "stats.json"

        if os.path.exists(out_path):
            return
        if not os.path.exists(db_path):
            raise FileNotFoundError("Could not find GT database")

        stats = AGStatistics.from_gt_db(db_path)
        stats.write_to(out_path)

    def gt_distro(self) -> AGStatistics:
        """
        Returns the metric distributions for the ground truth.
        """
        path = self.folder + "gt/stats.json"
        return AGStatistics.read_from(path)

    @staticmethod
    def init_directory_structure(
        model_path: str, name: Optional[str] = None
    ):
        # Try to open the model
        model = AttackGraphModel.read_from_file(model_path)
        print("[TEST] Loaded model from", model_path)

        if name is None:
            name = os.path.basename(model_path).split(".")[0]
        model_dir = EXPERIMENTS_PATH + name + "/"

        _mkdir(EXPERIMENTS_PATH)
        _mkdir(model_dir)
        _mkdir(model_dir + "gt/")
        _mkdir(model_dir + "statag/")

        # Save the model to the experiment directory
        model.save_to_file(model_dir + "model.json")


def _mkdir(path):
    if not os.path.exists(path):
        os.makedirs(path)


if __name__ == "__main__":
    # Experiment.init_directory_structure(
    #     "network/model_30h_-2v.json")

    exp = Experiment("model_30h_-2v")
    # exp.run_statag(1, 1000, samples_per_iter=1000)
    # exp.compute_exp_statistics()
