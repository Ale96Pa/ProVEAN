from abc import ABC
from dataclasses import dataclass
from faulthandler import enable
from multiprocessing import Process, Queue, Manager
from multiprocessing.managers import DictProxy
import statistics
from typing import Any, Literal, Optional

from progag import AttackGraphModel, AttackPathQuery
from progag.steering import SteeringPathGenerator

from server.analysis import AnalysisType, AttackSourceTargetMatrix, TopVulnerabilities, get_ap_histogram, select_attack_paths
from server.logging import Logger

type QuerySummary = dict[str, Any]
type StepComplete = Literal["STEP"]


METRIC_TO_INDEX = {
    "likelihood": 0,
    "impact": 1,
    "score": 2,
    "risk": 3,
    "length": 4,
}


@dataclass
class SharedMemoryQueryData:
    # The ID of the query.
    id: int
    # The relevant metrics for the query.
    metrics: set[str]

    # The summary of the last iteration of the query to be sent to the client.
    summary: Optional[QuerySummary]
    # The query stability values.
    stability: list[float | None]
    # The minimum and maximum stability values.
    min_stability: Optional[float]
    max_stability: Optional[float]
    # The query precision values.
    precision: list[float]

    def __init__(self, id: int, metrics: set[str]):
        self.id = id
        self.metrics = metrics

        self.stability = []
        self.precision = []
        self.summary = None
        self.min_stability = None
        self.max_stability = None

    def update(self, gen: SteeringPathGenerator):
        """ Updates the statistics in the shared dictionary. """
        self.summary = get_steerag_statistics_summary(self.id, gen)
        self.precision.append(gen.precision[-1])

        stability = gen.stability[-1] if gen.stability else None
        if stability is not None:
            # Compute the new stability based only on the metrics
            # that are relevant to the query.
            relevant = [stability[METRIC_TO_INDEX[i]]
                        for i in self.metrics]

            if relevant:
                s: float = statistics.median(relevant)
            else:
                s: float = sum(stability[i] for i in range(5)) / 5
            if self.min_stability is None or s < self.min_stability:
                self.min_stability = s
            if self.max_stability is None or s > self.max_stability:
                self.max_stability = s

            self.stability.append(s)
        else:
            self.stability.append(None)

        return self


type SharedDict = DictProxy[int, SharedMemoryQueryData]


@dataclass
class Coordinator:
    """ The coordinator process. Initialize with `Coordinator.spawn()`. """

    # ------------------------------
    #  COMMANDS
    # ------------------------------
    class Command(ABC):
        name: str

    @dataclass
    class NewQuery(Command):
        name = "new_query"
        id: int
        query: AttackPathQuery
        path_prefix: str
        # Already generated paths that may help start the query faster.
        bootstrap: Optional[list[str]]
        # Whether steering is enabled
        enable_steering: bool

    @dataclass
    class SetPaused(Command):
        name = "set_paused"
        id: int
        paused: bool

    @dataclass
    class StopQuery(Command):
        name = "stop_query"
        id: int

    @dataclass
    class AdvanceQueries(Command):
        name = "advance_queries"

    @dataclass
    class StartAnalysis(Command):
        name = "start_analysis"
        id: int
        ty: AnalysisType
        uuid: str
        args: Any

    @dataclass
    class Terminate(Command):
        name = "terminate"

    # ------------------------------
    #  RESULTS
    # ------------------------------
    class Result(ABC):
        name: str

    @dataclass
    class QueryStarted(Result):
        name = "query_started"
        id: int

    @dataclass
    class QueriesAdvanced(Result):
        name = "queries_advanced"
        which: Optional[list[int]]

    @dataclass
    class AnalysisCompleted(Result):
        name = "analysis_completed"
        id: int
        uuid: str
        data: Any

    @dataclass
    class QueryStopped(Result):
        name = "query_stopped"
        id: int

    @dataclass
    class Terminated(Result):
        name = "terminated"

    # ------------------------------
    #  FIELDS
    # ------------------------------
    # Single shared memory for data sharing.
    shared_memory: SharedDict
    # Queue to receive commands from the main thread.
    request_queue: 'Queue[Command]'
    # Queue to send results to the main thread.
    results_queue: 'Queue[Result]'

    # The attack graph model.
    model: AttackGraphModel

    @dataclass
    class QueryProcess:
        id: int
        process: Process
        request_queue: 'Queue[ProcessCommand]'
        response_queue: 'Queue[StepComplete]'
        paused: bool
    # Process for each query.
    processes: dict[int, QueryProcess]

    # ------------------------------
    #  SPAWN
    # ------------------------------
    @staticmethod
    def spawn(
        shared_memory: SharedDict,
        request_queue: 'Queue[Command]',
        results_queue: 'Queue[Result]',
        model: AttackGraphModel
    ) -> Process:
        """ Method called by the main thread to spawn this process. """
        proc = Process(
            target=Coordinator.child_start,
            args=(shared_memory, request_queue, results_queue, model))
        proc.start()
        return proc

    @staticmethod
    def child_start(
        shared_memory: SharedDict,
        request_queue: 'Queue[Command]',
        results_queue: 'Queue[Result]',
        model: AttackGraphModel,
    ):
        """ Main function of the process coordinator. """
        ctx = Coordinator(
            shared_memory=shared_memory,
            request_queue=request_queue,
            results_queue=results_queue,
            model=model,
            processes={},
        )

        Logger.set_process("coordinator")

        try:
            Logger.info(f"Coordinator process started!")

            # Wait for values in the queue.
            while True:
                cmd = ctx.request_queue.get()
                # Break on terminate command
                if isinstance(cmd, Coordinator.Terminate):
                    break
                ctx.run_command(cmd)
        except KeyboardInterrupt:
            Logger.error("Coordinator process terminated with SIGINT")
            exit(0)

        # Once you have been asked to break, close all sub-processes.
        ctx.close()

    # ------------------------------
    #  COMMAND HANDLING
    # ------------------------------
    def run_command(self, cmd: Command):
        match cmd:
            case Coordinator.NewQuery(id, query, path_prefix, bootstrap, enable_steering):
                manager = Manager()
                req_q = manager.Queue(maxsize=2)
                res_q = manager.Queue(maxsize=2)

                process = Process(
                    target=run_query,
                    args=(id, self.shared_memory, req_q, res_q,
                          self.results_queue,
                          self.model, query, path_prefix, bootstrap, enable_steering),
                    name=f"Query {id}"
                )
                process.start()
                Logger.info(f"Started generator process for query {id}")

                self.processes[id] = Coordinator.QueryProcess(
                    id=id,
                    process=process,
                    request_queue=req_q,  # type:ignore
                    response_queue=res_q,  # type:ignore
                    paused=True
                )

                # Wait for the process to complete its task.
                r = self.processes[id].response_queue.get()
                assert r == "STEP", "Expected a step completion"
                # Send a message to the main thread that the query has started.
                self.results_queue.put(Coordinator.QueryStarted(id))
                # Allow the new query to advance.
                self.processes[id].paused = False

            case Coordinator.SetPaused(id, p):
                Logger.info(f"Set query {id} to {
                            'paused' if p else 'unpaused'}.")
                if id not in self.processes:
                    Logger.warn(f"Query {id} not found")
                    return
                self.processes[id].paused = p

            case Coordinator.StopQuery(id):
                Logger.info(f"Stopping query {id}...")
                if id not in self.processes:
                    Logger.warn(f"Query {id} not found")
                    self.results_queue.put(Coordinator.QueryStopped(id))
                    return

                self.processes[id].request_queue.put(StopCommand())
                self.processes[id].process.join()
                del self.processes[id]
                self.results_queue.put(Coordinator.QueryStopped(id))
                Logger.info(f"Query {id} stopped")

            case Coordinator.AdvanceQueries():
                # Get the list of queries that are not paused.
                queries = [q for q in self.processes.values() if not q.paused]
                if not queries:
                    self.results_queue.put(Coordinator.QueriesAdvanced(None))
                    return

                # Send the step command to all the queries.
                for q in queries:
                    q.request_queue.put(StepCommand())

                # Wait for all the queries to complete their step.
                which: list[int] = []
                for q in queries:
                    try:
                        r = q.response_queue.get()
                        assert r == "STEP", "Expected a step completion"
                        which.append(q.id)
                    except EOFError:
                        Logger.error(
                            f"Query {q.id} terminated while advancing")
                        continue

                # Notify the main thread which queries have advanced.
                self.results_queue.put(Coordinator.QueriesAdvanced(which))

            case Coordinator.StartAnalysis(id, ty, uuid, args):
                Logger.info(f"Starting analysis for query {id} with type {ty}")
                if id not in self.processes:
                    Logger.warn(f"Query {id} does not exist (anymore|yet)")
                    return

                process = self.processes[id]
                process.request_queue.put(StartAnalysisCommand(ty, uuid, args))
                # Does not wait for the result.

            case msg:
                Logger.warn("Unknown message {msg.name}")

    def close(self):
        # Ask each process to terminate
        for q in self.processes.values():
            q.request_queue.put(StopCommand())
            q.process.join()

        Logger.info("Joined all sub-processes.")

        self.results_queue.put(Coordinator.Terminated())


class ProcessCommand(ABC):
    """ A command from the coordinator to the query process. """
    name: str


@dataclass
class StepCommand(ProcessCommand):
    name = "step"


@dataclass
class StopCommand(ProcessCommand):
    name = "stop"


@dataclass
class StartAnalysisCommand(ProcessCommand):
    name = "start_analysis"
    ty: AnalysisType
    uuid: str
    args: Any


def run_query(
    id: int,
    shared_memory: SharedDict,
    input_command: 'Queue[ProcessCommand]',
    step_complete: 'Queue[StepComplete]',
    output_queue: 'Queue[Coordinator.Result]',
    model: AttackGraphModel,
    query: AttackPathQuery,
    path_prefix: str,
    bootstrap: Optional[list[str]],
    enable_steering: bool
):
    Logger.set_process(f"Query {id}")
    stm = AttackSourceTargetMatrix(model)
    cve = TopVulnerabilities()

    try:
        # Create the generator
        generator = SteeringPathGenerator(
            model, query,
            db_path=path_prefix+"_aps.db",
            csv_path=path_prefix+"_stats.csv",
            disable_steering=not enable_steering)

        if bootstrap is not None:
            query_paths, _ = generator.add_bootstrap(bootstrap)
            stm.update(query_paths, generator)
            cve.update(query_paths, generator)

        # Generate the first step.
        query_paths, _ = generator.step()
        shared_memory[id] = shared_memory[id].update(generator)
        step_complete.put("STEP")
        stm.update(query_paths, generator)
        cve.update(query_paths, generator)

        # Wait for commands.
        while True:
            match input_command.get():
                case StepCommand():
                    # Generate the next step.
                    query_paths, _ = generator.step()
                    stm.update(query_paths, generator)
                    cve.update(query_paths, generator)
                    shared_memory[id] = shared_memory[id].update(generator)
                    step_complete.put("STEP")
                case StopCommand():
                    Logger.info(f"Stopping generator...")
                    # FIXME Maybe this helps with the memory leak?
                    step_complete.put("STEP")
                    exit(0)
                case StartAnalysisCommand(ty, uuid, args):
                    match ty:
                        case"attack_source_target_matrix":
                            output_queue.put(Coordinator.AnalysisCompleted(
                                id, uuid, stm.result()))
                            Logger.info("Sent attack source target matrix")
                        case "select_attack_paths":
                            if generator.db is not None:
                                paths = select_attack_paths(
                                    generator.db, model, args)
                                output_queue.put(
                                    Coordinator.AnalysisCompleted(
                                        id, uuid, [ap.to_dict() for ap in paths])
                                )
                            else:
                                Logger.error("No database connection")
                        case "top_vulnerabilities":
                            output_queue.put(Coordinator.AnalysisCompleted(
                                id, uuid, cve.result()))
                            Logger.info("Sent top vulnerabilities")
                        case "attack_path_histogram":
                            if generator.db is not None:
                                paths = get_ap_histogram(
                                    generator.db, args["query"], args["sort"])
                                output_queue.put(
                                    Coordinator.AnalysisCompleted(id, uuid, {
                                        "iteration": generator.iteration,
                                        "metric": args["sort"],
                                        "paths": paths,
                                    }))
                                Logger.info(f"Sent top {args['sort']} paths")
                            else:
                                Logger.error("No database connection")
                        case ty:
                            Logger.warn(f"Unknown analysis type {ty}")

                case other:
                    Logger.warn(f"Unknown process command {other}")
    except KeyboardInterrupt:
        Logger.error(f"Terminated SteerAG generator for query {id}")
        exit(1)


def get_steerag_statistics_summary(id: int, gen: SteeringPathGenerator) -> QuerySummary:
    """ Updates the statistics in the shared dictionary. """
    stats = gen.statistics

    return {
        "id": id,
        "iteration": gen.iteration,
        "generated": gen.generated[-1],
        "uniqueQuery": len(gen.query_hashes),
        "generatedQuery": gen.query_generated[-1],
        "unique": len(gen.unique_hashes),
        "collision": gen.collision[-1],
        "stability": gen.stability[-1] if gen.stability else None,
        "precision": gen.precision[-1],
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
