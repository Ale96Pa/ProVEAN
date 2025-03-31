import { AP_METRICS, type APCondition, type APMetric, type AttackGraphModel, type AttackPath, type RGBColor } from "./types";

import { writable, type Writable } from "svelte/store";
import { io, Socket } from "socket.io-client";

export interface BundledStatistics {
    stat: StatAGStatistics;
    steer: SteerAGStatistics[];
}

class ServerConnection {
    private socket: Socket | null = null;

    public model: AttackGraphModel | null = null;
    public otherModelPaths: string[] = [];

    /** Whether the web socket is connected to the backend */
    public isConnected: Writable<boolean> = writable(false);
    /** Whether the briefing information has been received */
    public isBriefed: Writable<boolean> = writable(false);
    /** Whether the server is stopped. */
    public isStopped: Writable<boolean> = writable(false);

    /** Whether generation is paused. */
    public paused: Writable<boolean> = writable(false);
    /** Last downloaded statistics for StatAG and each SteerAG query. */
    public statistics: Writable<BundledStatistics> = writable();
    /** Downloaded SteerAG instances */
    public steeringQueries: Writable<SteerAGInstance[]> = writable([]);
    /** Last downloaded generation statistics for each query. */
    public generationStats: Writable<QueryGenerationStatistics>[] = [];


    public connect() {
        if (this.socket) {
            this.socket.close();
            this.socket = null;
            this.isConnected.set(false);
        }

        // The backend and frontend are running on different ports
        const socket = this.socket = io();

        socket.on("connect_error", (err) => {
            console.error("Detected error during connection.", err);
        });
        socket.on("connect", () => this.isConnected.set(true));

        // The on-connect briefing
        socket.on("briefing", (json: {
            paused: boolean,
            others: string[],
            model: AttackGraphModel,
        }) => {
            this.model = json.model;
            this.otherModelPaths = json.others;
            this.paused.set(json.paused);
            this.isBriefed.set(true);
        });

        // When the active SteerAG instances are updated
        socket.on("all_steerags", (query: SteerAGInstance[]) => {
            this.steeringQueries.set(query);
            // Initialize the generationStats store
            for (const q of query)
                if (!this.generationStats[q.id])
                    this.generationStats[q.id] = writable();
        });
        // When the next iteration of statistics arrives.
        socket.on("bundled_stats", (stats) => {
            // Wait for the active_steerags to be received
            this.statistics.update((prev?: BundledStatistics) => {
                if (!prev)
                    prev = { stat: stats.stat, steer: [] };
                else
                    // Update the StatAG statistics
                    prev.stat = stats.stat;

                // Update the SteerAG statistics
                for (const steer in stats.steer) {
                    const id = stats.steer[steer].id;
                    prev.steer[id] = stats.steer[steer];
                }

                return prev;
            });
        });
        // When the generation statistics are updated
        socket.on("query_generation_statistics", (stats: QueryGenerationStatistics) => {
            this.generationStats[stats.id].set(stats);
        });

        // NOTE - debug logging
        socket.onAny((name, ...args) => {
            console.debug(`EVENT[${name}]:`, ...args);
        });
    }

    private requestInternal<T>(event: string, data: any): Promise<T> {
        return new Promise((resolve, reject) => {
            if (!this.socket) {
                reject("Socket not connected");
            } else {
                if (data === undefined) {
                    this.socket.emit(event, (response: T) => {
                        resolve(response);
                    });
                } else {
                    this.socket.emit(event, data, (response: T) => {
                        resolve(response);
                    });
                }
            }
        });
    }

    public request<T extends keyof ServerCommands>(
        event: T, data?: ServerCommands[T]["inputs"]
    ): Promise<ServerCommands[T]["output"]> {
        return this.requestInternal(event, data);
    }

    public async changeModel(path: string) {
        this.isStopped.set(true);
        this.request("change_model", path);
        // Wait to reconnect
        await new Promise((resolve) => setTimeout(resolve, 2000));

        window.location.reload();
    }


    public async requestAnalysis<T extends keyof AnalysisCommands>(
        type: T, id: number,
        args?: AnalysisCommands[T]["args"],
    ): Promise<AnalysisCommands[T]["output"]> {
        // Generate a unique query identifier.
        const rando = (Math.random() * Number.MAX_SAFE_INTEGER).toFixed(0);
        const uuid = `${type}@${id}@@${rando}`;

        // Request the analysis from the server
        await server.requestInternal("request_analysis",
            { type, id, uuid, args });

        // Wait for the response
        const event_name = "analysis_response_" + uuid;

        return await new Promise((resolve) => {
            server.socket?.on(event_name, (data) => {
                resolve(data);
                server.socket?.off(event_name);
            });
        });
    }
}

type ServerCommands = {
    "update_hosts_positions": {
        inputs: Record<number, { x: number, y: number }>
        output: void;
    };
    "request_hosts_positions": {
        inputs: void;
        output: Record<number, [number, number]>;
    };
    "request_statistics": {
        inputs: number;
        output: void;
    };
    "advance_steerag_job": {
        inputs: number;
        output: void;
    };
    "compute_joint_histograms": {
        inputs: {
            metrics: APCondition[];
            sources: number[] | null;
            targets: number[] | null;
        };
        output: Record<APMetric, number[]>;
    };
    "set_steerag_paused": {
        inputs: { id: number, paused: boolean };
        output: void;
    };
    "start_new_query": {
        inputs: {
            query: APCondition[],
            enableSteering: boolean,
            sources: number[] | null,
            targets: number[] | null,
            name: string
        };
        output: void;
    };
    "set_paused": {
        inputs: boolean;
        output: void;
    };
    "get_statag_stm": {
        inputs: void;
        output: AttackPathStmOutput;
    };
    "stop_query": {
        inputs: number;
        output: void;
    };
    "rename_query": {
        inputs: { id: number, name: string };
        output: void;
    };
    "recolor_query": {
        inputs: { id: number, color: number[] };
        output: void;
    };
    "change_model": {
        inputs: string;
        output: void;
    };
};

type AnalysisCommands = {
    "attack_source_target_matrix": {
        args: undefined;
        output: AttackPathStmOutput;
    };
    "top_vulnerabilities": {
        args: undefined;
        output: TopVulnerabilitiesOutput;
    };
    "attack_path_histogram": {
        args: {
            query: APCondition[],
            sort: APMetric,
        };
        output: AttackPathHistogramOutput;
    };
    "select_attack_paths": {
        args: APCondition[];
        output: AttackPath[];
    };
};

interface AttackPathStmOutput {
    iteration: number;
    counts: number[][];
};

export interface AttackPathHistogramOutput {
    iteration: number;
    paths: [string, number][];
    metric: APMetric;
}

export interface TopVulnerabilitiesOutput {
    iteration: number;
    cves: [string, number][];
}

export interface QueryGenerationStatistics {
    id: number,
    stability: (number | null)[];
    min_stability: number | null;
    max_stability: number | null;
    precision: number[];
}

export interface StatAGStatistics {
    iteration: number,
    generated: number,
    collision: number,
    unique: number;
    edge_sum: number;
    host_sum: number;
    stability: [
        likelihood: number, impact: number,
        risk: number, score: number, length: number
    ] | null;
    likelihood: number[],
    impact: number[],
    score: number[],
    risk: number[],
    damage: number[],
    length: number[],
    edges: Record<string, Record<string, number>>,
    hosts: Record<string, number>
}

export interface SteerAGStatistics extends StatAGStatistics {
    id: number,
    precision: number,
    uniqueQuery: number;
    generatedQuery: number;
}

export interface SteerAGInstance {
    id: number,
    name: string,
    color: RGBColor,
    paused: boolean,
    active: boolean,
    steering: boolean,
    query: {
        likelihood_range?: [number, number],
        impact_range?: [number, number],
        score_range?: [number, number],
        risk_range?: [number, number],
        length_range?: [number, number],
        sources?: number[],
        targets?: number[]
    }
}

export const server = new ServerConnection();
