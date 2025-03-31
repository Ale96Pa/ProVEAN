import { select } from "d3";

import { server, type BundledStatistics } from "@lib/server";
import type { D3Selection } from "@lib/types";

const GLOBAL_MARGIN = 4;
const LABEL_SIZE = 12;

export class AMOverview {
    static singleton: AMOverview | null = null;

    svg: D3Selection<SVGSVGElement>;

    visible: boolean = false;

    #hosts: number[] | null = null;
    private N: number = 0;
    private map: Record<number, number> = {};
    private edges: [number, number][] = [];
    private edgeGroups: D3Selection<SVGGElement>[] = [];
    private colors: string[] | null = null;

    private stats: BundledStatistics | null = null;
    private rowWidth: number = 0;

    constructor(canvas: SVGSVGElement) {
        this.svg = select(canvas);

        // Subscribe to the stats changes.
        server.statistics.subscribe((stats) => {
            this.stats = stats;
            this.update();
        });

        server.steeringQueries.subscribe((ags) => {
            this.colors = ["blue"];
            for (const ag of ags)
                this.colors.push(`rgb(${ag.color.join(",")})`);
            this.update();
        });

        this.hosts = null;

        AMOverview.singleton = this;
    }

    public set hosts(hosts: number[] | null) {
        if (hosts === null) {
            this.#hosts = null;
            this.map = {};
            this.edges = [];

            this.svg.style("display", "none");
            return;
        }

        this.svg.style("display", null);

        this.N = hosts.length;
        // Get the visible edges.
        const set = new Set<number>(hosts);
        this.edges = [];
        for (const [s, t] of server.model!.edges)
            if (set.has(s) && set.has(t))
                this.edges.push([s, t]);

        // Get the reverse mapping for the host numbers.
        this.#hosts = hosts;
        this.map = {};
        for (let i = 0; i < hosts.length; i++)
            this.map[hosts[i]] = i;

        this.draw();
    }

    private draw() {
        // Update the CSS size of the SVG.
        const v = this.N * 16 + LABEL_SIZE + 2 * GLOBAL_MARGIN;
        this.svg.style("width", `${v}px`);
        this.svg.style("height", `${v}px`);

        // Clear the SVG.
        this.svg.selectAll("*").remove();

        // Draw the labels.
        const labels = this.svg.append("g")
            .attr("class", "labels")
            .attr("transform", `translate(${GLOBAL_MARGIN + LABEL_SIZE} ${GLOBAL_MARGIN + LABEL_SIZE})`);

        const rowWidth = (v - LABEL_SIZE - 2 * GLOBAL_MARGIN) / (this.N);
        const fontSize = Math.min(8, rowWidth / 2) + "px";

        for (let i = 0; i < this.N; i++) {
            const host = this.#hosts![i];
            const z = (i + 0.5) * rowWidth;
            labels.append("text")
                .attr("x", -2)
                .attr("y", z + 4)
                .text(host)
                .attr("text-anchor", "end")
                .attr("font-size", fontSize)
                .attr("fill", "red")
                .attr("alignment-baseline", "middle");
            labels.append("text")
                .attr("x", z)
                .attr("y", -2)
                .text(host)
                .attr("text-anchor", "middle")
                .attr("font-size", fontSize)
                .attr("alignment-baseline", "end");
        }

        // Draw the edges.
        const edges = this.svg.append("g")
            .attr("class", "edges")
            .attr("transform", `translate(${GLOBAL_MARGIN + LABEL_SIZE}, ${GLOBAL_MARGIN + LABEL_SIZE})`);

        // Draw the grid.
        const grid = this.svg.append("g")
            .attr("class", "grid")
            .attr("transform", `translate(${GLOBAL_MARGIN + LABEL_SIZE}, ${GLOBAL_MARGIN + LABEL_SIZE})`);


        for (let i = 0; i <= this.N; i++) {
            const x = i * rowWidth;

            grid.append("line")
                .attr("x1", x)
                .attr("y1", 0)
                .attr("x2", x)
                .attr("y2", v - LABEL_SIZE - 2 * GLOBAL_MARGIN)
                .attr("stroke", "black")
                .attr("stroke-width", 0.5);

            grid.append("line")
                .attr("x1", 0)
                .attr("y1", x)
                .attr("x2", v - LABEL_SIZE - 2 * GLOBAL_MARGIN)
                .attr("y2", x)
                .attr("stroke", "black")
                .attr("stroke-width", 0.5);
        }

        this.edgeGroups = [];
        for (const [s, t] of this.edges) {
            const x1 = this.map[s] * rowWidth;
            const y1 = this.map[t] * rowWidth;

            this.edgeGroups.push(edges.append("g")
                .attr("class", "edge")
                .attr("transform", `translate(${x1} ${y1})`)
            );
        }

        this.rowWidth = rowWidth;
        this.update();
    }

    private update() {
        if (!this.colors) return;
        if (!this.stats) return;
        const { stat, steer } = this.stats;

        for (let i = 0; i < this.edges.length; i++) {
            const [source, target] = this.edges[i];
            const group = this.edgeGroups[i];

            let statValue = stat.edges[source]?.[target] ?? 0;
            if (stat.edge_sum) statValue /= stat.edge_sum;

            const values = [statValue];
            for (const stat of steer) {
                let value = stat.edges[source]?.[target] ?? 0;
                if (stat.edge_sum) value /= stat.edge_sum;
                values.push(value);
            }

            group.selectAll("*").remove();
            drawStatistics(group, values, this.colors, this.rowWidth);
        }
    }
}

function drawStatistics(
    container: D3Selection<SVGGElement>,
    values: number[],
    colors: string[],
    size: number,
) {
    let total = values.reduce((a, b) => a + b, 0);

    let usedX = 0;
    let usedY = 0;

    let fromLeft = true;
    for (let i = 0; i < values.length; i++) {
        const color = colors[i];
        const value = values[i];

        fromLeft = !fromLeft;
        const perc = value / total;
        total -= value;
        if (value == 0) continue;

        const sizeX = fromLeft ? (size - usedX) * perc : size - usedX;
        const sizeY = fromLeft ? size - usedY : (size - usedY) * perc;

        container
            .insert("rect")
            .attr("x", usedX)
            .attr("y", usedY)
            .attr("width", sizeX)
            .attr("height", sizeY)
            .attr("fill", color);

        if (fromLeft) usedX += sizeX;
        else usedY += sizeY;
    }
}
