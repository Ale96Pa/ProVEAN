import time
from queue import Queue
from threading import Thread
from typing import Any, Callable, Literal, Optional

import eventlet
from flask import Flask
from flask_socketio import SocketIO
import numpy as np

from progag import AttackGraphModel, AttackPathQuery, PathGenerator
from server.logging import Logger
from server.analysis import AnalysisType, AttackSourceTargetMatrix
from server.coordinator import Coordinator
from server.joint import APCondition,  filter_to_where_clause, get_joint_histograms, topological_where_clause
from server.steerag import SteerAGPool


class VisProgAGServer:
    # SocketIO server to communicate with the client.
    io: SocketIO
    # Path to retrieve the model from, and save it to.
    model_path: str
    # Function to call a new model.
    load_new_model: Callable[[str], None]
    # The paths to all other networks
    other_models: list[str]

    # Loaded model.
    model: AttackGraphModel

    # The StatAG path generator.
    statag: PathGenerator
    # The path to the StatAG DB.
    statag_db_path: str
    # The path to the StatAG DB.
    statag_csv_path: str = "network/statag.csv"
    # The path to the "queries" folder, which contains
    # the results of each launched query.
    steerags_path: str

    # The SteerAG processes pool.
    pool: SteerAGPool
    # Number of generations sent to the client.
    iterations_sent: int = 0
    # Number of generated iterations.
    iterations_generated: int = 0
    # The source-target matrix for the StatAG.
    stm: AttackSourceTargetMatrix

    # The queue of messages to emit.
    queue: Queue
    # Whether the generation has been paused.
    paused: bool = False
    # Whether the generator is about to quit.
    quit: bool = False

    def __init__(self, app: Flask, model_path: str, load_new_model: Callable[[str], None], networks: list[str]):
        self.io = SocketIO(app, cors_allowed_origins='*', force_new=True)
        self.model_path = model_path
        self._load_model()
        self.load_new_model = load_new_model
        self.other_models = networks

        # Get the current date
        date = time.strftime("%Y-%m-%d-%H-%M-%S")
        self.statag_db_path = f"network/statag_{date}.db"
        self.steerags_path = f"network/queries_{date}"

        # Initialize the source-target matrix for the StatAG.
        self.stm = AttackSourceTargetMatrix(self.model)

        # Initialize the queue
        self.queue = Queue()
        self.run(self.task_flush_queue)

        # Initialize the SteerAG process pool.
        self.pool = SteerAGPool(
            self.model, path=self.steerags_path)

        # Create the StatAG path generator with sensible defaults.
        self.statag = PathGenerator(
            self.model, sample_size=500,
            db_path=self.statag_db_path,
            csv_path=self.statag_csv_path)
        # Do one iteration so you have something to send
        self.statag.step()

        # Initialize the SocketIO events
        self._init_events()

        self.run(self.task_handle_pool_response)
        self.run(self.task_advance_generation)

    def close(self):
        """ Shut down the server and all connected processes. """
        self.pool.close()
        self.io.stop()

    def run(self, fn: Callable, *args, **kwargs) -> Thread:
        return self.io.start_background_task(fn, *args, **kwargs)

    def _load_model(self):
        start_time = time.time()

        try:
            self.model = AttackGraphModel.read_from_file(self.model_path)
        except IOError as e:
            Logger.error(f"Could not load the model at {self.model_path}")
            print(e)

        elapsed = time.time() - start_time
        Logger.debug(f"Model `{self.model_path}` loaded in {elapsed:.2f}s")

    def _set(self, event_name: str, handler):
        self.io.on_event(event_name, handler)

    def task_flush_queue(self):
        while not self.quit:
            name, data = self.queue.get()
            self.io.emit(name, data)

    def task_handle_pool_response(self):
        while True:
            match self.pool.get_response():
                case Coordinator.QueryStarted(id):
                    self.send_bundled_stats([id])
                case Coordinator.QueryStopped(id):
                    self.send_steer_queries()
                case Coordinator.QueriesAdvanced(which):
                    self.send_bundled_stats(which)
                    if which:
                        for id in which:
                            self.send_query_generation_statistics(id)
                    self.iterations_sent += 1
                case Coordinator.AnalysisCompleted(id, uuid, result):
                    self.emit("analysis_response_"+uuid, result)
                # Stop the task
                case Coordinator.Terminated():
                    break
        Logger.info("Terminated listener for pool responses.")

    # -------------------------
    # | Advancing generations |
    # -------------------------
    def task_advance_generation(self):
        while not self.quit:
            while self.paused or self.iterations_generated != self.iterations_sent:
                if self.quit:
                    Logger.info(
                        "Stopped advancing old tasks because of quit signal.")
                    return
                time.sleep(0.2)

            # Advance StatAG
            sg = eventlet.spawn(self.advance_statag)
            # Advance the queries
            if self.pool.advance_all_queries():
                self.iterations_generated += 1

            if self.quit:
                sg.kill()
                Logger.info("Killed StatAG task because of quit signal.")
                return

            sg.wait()

        Logger.info("Stopped advancing old tasks because of quit signal.")

    def advance_statag(self):
        """
        Advance the StatAG path generator by one step.

        Update the source-target matrix with the new paths.
        """
        try:
            paths = self.statag.step()
            self.stm.update(paths, self.statag)
        except KeyboardInterrupt:
            Logger.error(
                "Server terminated with SIGINT while advancing StatAG.")
            exit(2)
        except Exception as e:
            Logger.error(f"Error while advancing `{
                         self.model_path}` StatAG: {e}")

    # -------------------
    # | Received Events |
    # -------------------
    def _init_events(self):
        self._set("connect", self.brief_client)
        self._set("request_hosts_positions", self.get_host_coords)
        self._set("update_hosts_positions", self.update_hosts_positions)
        self._set("compute_joint_histograms", self.compute_joint_histograms)
        self._set("set_steerag_paused", self.set_steerag_paused)
        self._set("start_new_query", self.start_new_query)
        self._set("set_paused", self.set_paused)
        self._set("request_analysis", self.request_analysis)
        self._set("get_statag_stm", self.get_statag_stm)
        self._set("stop_query", self.stop_query)
        self._set("rename_query", self.rename_query)
        self._set("recolor_query", self.recolor_query)
        self._set("change_model", self.load_new_model)

    def brief_client(self):
        """
        Send everything the client might want when first connecting,
        considering the fact that something may already have happened
        before it connected, so it might want to catch up.
        """
        Logger.info("Preparing briefing for new client.")
        self.emit('briefing', {
            "model": self.model.to_json(),
            "others": self.other_models,
            "paused": self.paused,
        })

        # Send the names and ids of the active steerags.
        self.send_steer_queries()
        # Send all the combined statistics.
        self.send_bundled_stats(None)
        # Send the current query precision and stability.
        for query in self.pool.queries:
            if query.active:
                self.send_query_generation_statistics(query.id)

    def send_steer_queries(self):
        self.emit("all_steerags", self.pool.all_queries())

    def get_host_coords(self):
        """ Returns the coordinates of all hosts in the network. """
        Logger.info("Sending host coordinates to client.")

        coordinates: dict[int, tuple[float, float]] = {}
        for host in self.model.hosts.values():
            coordinates[host.id] = (host.x, host.y)
        return coordinates

    type LongCoord = dict[Literal['x', 'y'], int]

    def update_hosts_positions(self, data: dict[str, LongCoord]):
        """ Update the coordinates of the hosts. """
        Logger.info("Updating host coordinates from client.")

        for id, node_data in data.items():
            node = self.model.hosts[int(id)]
            node.x = node_data["x"]
            node.y = node_data["y"]
        # Save the model to a file
        self.model.save_to_file(self.model_path)

    def compute_joint_histograms(self, data):
        """
        Computes the joint distribution given the conditions.
        """
        Logger.info("Computing joint distributions histograms.")

        metrics: list[APCondition] = data["metrics"]
        sources: Optional[list[int]] = data["sources"]
        targets: Optional[list[int]] = data["targets"]

        if self.statag.db is None:
            return None

        t = time.time()
        hist = get_joint_histograms(self.statag.db, metrics, sources, targets)
        Logger.debug(f"Computed joint histograms in {time.time() - t:.2f}s")
        return hist

    def set_steerag_paused(self, data):
        """ Pause/unpause a SteerAG query generation. """
        id: int = data["id"]
        paused: bool = data["paused"]

        Logger.info(f"Setting SteerAG {id} to {
                    'paused' if paused else 'unpaused'}.")

        self.pool.set_paused(id, paused)

    def start_new_query(self, data):
        """ Start a new SteerAG query. """
        query_name: str = data["name"]
        query_data: list[APCondition] = data["query"]
        query_sources: Optional[list[int]] = data["sources"]
        query_targets: Optional[list[int]] = data["targets"]
        query_steering: bool = data["enableSteering"]

        if query_steering:
            Logger.info(f"Starting a new SteerAG query: {query_name}")
        else:
            Logger.info(f"Starting a new StatAG filter: {query_name}")

        # Convert the list of APConditions to an array
        dictionary: dict = {}
        for metric, a, b in query_data:
            dictionary[metric] = (a, b)
        dictionary["sources"] = query_sources
        dictionary["targets"] = query_targets

        query = AttackPathQuery(**dictionary)

        bootstrap = self._get_starting_paths(
            query_data, query_sources, query_targets)
        if not bootstrap:
            Logger.info(
                "No bootstrapping paths found for query `{query_name}`")
        else:
            Logger.info(
                f"Found {len(bootstrap)} bootstrapping paths for query `{query_name}`")

        self.pool.add_query(query, query_name, bootstrap, query_steering)
        # Send the new active steerags to the client
        self.send_steer_queries()

    def set_paused(self, data: bool):
        """ Pause/unpause the generation of the paths. """
        self.paused = data

    def request_analysis(self, data):
        """ Requests a new analysis. """
        # Type of analysis.
        ty: AnalysisType = data["type"]
        # The query ID to run the analysis on.
        id = data["id"]
        # Arguments to the analysis.
        args = data.get("args", None)
        # The UUID of the analysis to send it back to the client
        uuid = data["uuid"]

        Logger.debug(f"Starting analysis {uuid}")

        self.pool.start_analysis(ty, id, uuid, args)

    def get_statag_stm(self):
        """ Returns the source-target matrix of the StatAG. """
        Logger.info("Sending StatAG source-target matrix to client.")
        return self.stm.result()

    def stop_query(self, id: int):
        """ Stops a SteerAG query. """
        Logger.info(f"Stopping SteerAG {id}")
        self.pool.stop_query(id)

    def rename_query(self, data):
        """ Renames a SteerAG query. """
        id = data["id"]
        name = data["name"]

        Logger.info(f"Renaming SteerAG {id} to {name}")

        self.pool.rename_query(id, name)
        self.send_steer_queries()

    def recolor_query(self, data):
        """ Recolors a SteerAG query. """
        id = data["id"]
        color = data["color"]

        Logger.info(f"Recoloring SteerAG {id} to {color}")

        self.pool.recolor_query(id, color)
        self.send_steer_queries()

    def _get_starting_paths(
        self, condition: list[APCondition],
        sources: Optional[list[int]], targets: Optional[list[int]]
    ) -> Optional[list[str]]:
        """ Get a list of paths to start a query from. """
        if not self.statag.db:
            return None

        # Get the first paths that match the condition
        where_clause = filter_to_where_clause(condition)
        topo = topological_where_clause(sources, targets)
        query = f"SELECT trace FROM aps WHERE {
            where_clause} AND {topo} LIMIT 1000"
        results = self.statag.db.execute(query).fetchall()
        if not results:
            return None

        return [result[0] for result in results]

    # -----------------
    # | Stuff to emit |
    # -----------------
    def emit(self, name: str, data: Any):
        """ Emit an event via the emit queue. """
        self.queue.put((name, data))
        # self.io.emit(name, data)

    def send_bundled_stats(self, steerag_ids: Optional[list[int]]):
        bundled_stats = {
            "stat": create_statag_summary(self.statag),
            "steer": {}
        }

        if steerag_ids is None:
            steerag_ids = [
                query.id for query in self.pool.queries if query.active]
        else:
            steerag_ids = [
                id for id in steerag_ids if self.pool.queries[id].active]

        # Send the statistics of each SteerAG individually.
        for id in steerag_ids:
            try:
                summary = self.pool.shared_memory[id].summary
                if summary:
                    bundled_stats["steer"][id] = summary
            except KeyError:
                # This solves a problem where sometimes the first step of a query
                # is not completed yet at this point.
                Logger.warn(f"Query {id} not yet generated, skipping")
                pass

        self.emit("bundled_stats", bundled_stats)

    def send_query_generation_statistics(self, id: int):
        query = self.pool.shared_memory[id]
        self.emit("query_generation_statistics", {
            "id": id,
            "precision": query.precision,
            "min_stability": query.min_stability,
            "max_stability": query.max_stability,
            "stability": query.stability,
        })


def create_statag_summary(gen: PathGenerator):
    stats = gen.statistics
    return {
        "iteration": gen.iteration,
        "generated": gen.generated[-1],
        "unique": len(gen.unique_hashes),
        "collision": gen.collision[-1],
        "stability": gen.stability[-1] if gen.stability else None,
        ** ({
            "likelihood": stats.likelihoods,
            "impact": stats.impacts,
            "damage": stats.damages,
            "score": stats.scores,
            "risk": stats.risks,
            "length": stats.lengths,
            "edges": stats.edges_count,
            "hosts": stats.hosts_count,
            "edge_sum": stats.edges_sum,
            "host_sum": stats.hosts_sum,
        } if stats is not None else {})
    }
