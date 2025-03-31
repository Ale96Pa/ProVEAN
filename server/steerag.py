from dataclasses import dataclass
from multiprocessing import Process, Queue, Manager
import os
from typing import Any, Optional

from progag import AttackGraphModel, AttackPathQuery

from server.analysis import AnalysisType
from server.coordinator import Coordinator, SharedMemoryQueryData, SharedDict
from server.logging import Logger

COLOR_POOL = [
    (231, 76, 60),
    (46, 204, 113),
    (241, 196, 15),
    (155, 89, 182),
    (128, 128, 0),
    (241, 149, 72),
    (142, 68, 173)
]


@dataclass
class SteerAG:
    # The ID of the SteerAG.
    id: int
    # The user-assigned name of the query.
    name: str
    # The current query value.
    query: AttackPathQuery
    # The color assigned to the query
    color: tuple[int, int, int]
    # Whether the query is paused.
    paused: bool
    # Whether the query is active.
    active: bool
    # Whether steering has been enabled for this query.
    enable_steering: bool


class SteerAGPool:
    """
    A pool of SteerAG queries and the process pools enabling them.
    """
    # Model to pass to the generation step.
    model: AttackGraphModel
    # The processes with all related information
    queries: list[SteerAG]
    # The identifier to be assigned to the next query.
    next_id: int = 0
    # The path to save everything about the queries.
    path: str
    # The color pool.
    color_pool: list[tuple[int, int, int]]

    # The process coordinating all query processes under itself.
    coordinator: Process
    # The process coordinator command queue.
    commands_queue: 'Queue[Coordinator.Command]'
    # The queue that gets filled when new results are available.
    results_queue: 'Queue[Coordinator.Result]'
    # The shared memory with the coordinator.
    shared_memory: SharedDict

    def __init__(self, model: AttackGraphModel, path: str):
        self.model = model
        self.queries = []
        self.path = path
        self.color_pool = COLOR_POOL.copy()

        self._create_or_clear_target_path()

        # Initialize the coordinator.
        manager = Manager()
        self.commands_queue = manager.Queue(maxsize=128)  # type:ignore
        self.results_queue = manager.Queue(maxsize=128)  # type:ignore
        self.shared_memory = manager.dict()

        self.coordinator = Coordinator.spawn(
            self.shared_memory,
            self.commands_queue,
            self.results_queue,
            model)

    def close(self):
        """ Stop the pool and the coordinator process. """
        # Send a command to the terminator to ask it to stop.
        self.commands_queue.put(Coordinator.Terminate())
        # Wait for the coordinator to terminate.
        self.coordinator.join()

    def _create_or_clear_target_path(self):
        if not os.path.exists(self.path):
            os.makedirs(self.path)
        else:
            # Remove everything from the folder
            for file in os.listdir(self.path):
                os.remove(os.path.join(self.path, file))

    def add_query(
        self,
        query: AttackPathQuery,
        name: Optional[str] = None,
        bootstrap: Optional[list[str]] = None,
        enable_steering: bool = True
    ) -> SteerAG:
        """
        Add a query to the pool.
        """
        id = self.next_id

        color = self.color_pool.pop(0)
        if color is None:
            color = (255, 0, 0)

        sag = SteerAG(
            id=id,
            name=f"Query {id}" if name is None else name,
            color=color,
            query=query,
            paused=False,
            active=True,
            enable_steering=enable_steering
        )
        self.queries.append(sag)

        # Create the query in the shared memory, passing to it the
        # relevant metrics, so that it can compute the stability.
        self.shared_memory[id] = SharedMemoryQueryData(id, query.metrics)

        # Get the path where to save the csv and db file.
        path_prefix = self.path + f"/query_{id}"
        self.commands_queue.put(
            Coordinator.NewQuery(id, query, path_prefix, bootstrap, enable_steering))

        self._write_to_json()

        self.next_id += 1
        return sag

    def stop_query(self, id: int):
        """ Stop a query. """
        self.queries[id].active = False
        self.commands_queue.put(Coordinator.StopQuery(id))

        # Claim back the color
        self.color_pool.append(self.queries[id].color)
        self._write_to_json()

    def rename_query(self, id: int, name: str):
        """ Rename a query. """
        self.queries[id].name = name
        self._write_to_json()

    def recolor_query(self, id: int, color: tuple[int, int, int]):
        """ Recolor a query. """
        self.queries[id].color = color
        self._write_to_json()

    def all_queries(self) -> list[dict]:
        """ Returns a summary of all active queries. """
        result: list[dict] = []
        for query in self.queries:
            result.append({
                "id": query.id,
                "name": query.name,
                "color": query.color,
                "paused": query.paused,
                "active": query.active,
                "query": query.query.to_dict(),
                "steering": query.enable_steering
            })
        return result

    def _write_to_json(self):
        # Save the queries information to a file
        self.save_info_to_file(self.path+"/info.json")

    def save_info_to_file(self, path: str):
        """ Saves the information about the queries to a JSON file. """
        import json
        data = []
        for query in self.queries:
            data.append({
                "id": query.id,
                "name": query.name,
                "color": query.color,
                # We don't care about paused or active status
                "query": query.query.to_dict()
            })
        with open(path, "w") as f:
            json.dump(data, f, indent=2)

    # --------------
    # | Processing |
    # --------------
    def advance_all_queries(self):
        """ Request the next step for all queries """
        try:
            self.commands_queue.put(Coordinator.AdvanceQueries())
            return True
        except EOFError:
            Logger.error("Terminated (while advancing queries).")
            return False

    def get_response(self) -> Optional[Coordinator.Result]:
        """ Get the next response from the coordinator. """
        try:
            return self.results_queue.get()
        except EOFError:
            Logger.error("Terminated (while getting response).")

    def start_analysis(self, ty: AnalysisType, id: int, uuid: str, args: Any):
        """
        Start a new analysis with the type `ty` for the query `id`.
        Keep track of it with the `uuid`.
        """
        self.commands_queue.put(Coordinator.StartAnalysis(id, ty, uuid, args))

    # ---------
    # | Utils |
    # ---------
    def set_paused(self, id: int, paused: bool = True):
        self.queries[id].paused = paused
        self.commands_queue.put(Coordinator.SetPaused(id, paused))
