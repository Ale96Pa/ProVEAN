/**
 * This file contains the class that renders the topology of the network
 * onto an SVG and keeps it updated both in terms of relative positions, 
 * camera movement and data overlaid on top of it.
 */
import { polygonContains, select } from "d3";

import { get, writable, type Unsubscriber, type Writable } from "svelte/store";

import type {
    AttackGraphModel,
    HostInformation,
    D3Selection,
    RGBColor,
    Point,
} from "@lib/types";
import {
    server,
    type BundledStatistics,
    type StatAGStatistics,
    type SteerAGInstance,
    type SteerAGStatistics,
} from "@lib/server";
import { drawConvexHullIntoGroup } from "@lib/convex_hull";

export enum OverviewMode {
    /** 
     * - Dragging with left click or middle click will move the camera.
     * - Nothing else is possible.
     */
    CameraMovement,
    /**
     * - Dragging with left click from an empty space will create a selection lasso,
     *   and releasing will either select or deselect all hosts inside it based on
     *   whether the shift key is pressed.
     * - Clicking on an host will select or deselect it.
     * - Clicking anywhere else will clear the selection.
     * - Dragging with right click will move the camera.
     * - Nothing else is possible.
     */
    Selection,
    /**
     * Everything from `Selection` plus:
     * - Dragging with middle click will move the selected hosts.
     */
    SelectionAndEditing,
}

export enum LinkStyle {
    /** Thickness of each band is relative to the query. */
    RelativeSum,
    /** Thickness of each band is relative, but the thickness of the total is fixed by StatAG. */
    RelativeStat,
    /** The thickness of each band is relative to the absolute count on that link. */
    Absolute,
    /** The thickness of each band is relative to the absolute count on that link, logarithmic. */
    RelativeMax,
}

interface OverviewHostInformation {
    selection: D3Selection<SVGCircleElement>;
    text: D3Selection<SVGTextElement>;
    group: D3Selection<SVGGElement>,
    model: HostInformation,
    neighbors: number[],
}

interface SteerAGQueryResults {
    /** Id of the query (same as index). */
    id: number;

    /** RGB components of the color of the query */
    rgb: RGBColor;
    /** Color of the query in rgb() format */
    color: string;

    /** Drawn circles for each host */
    circles: D3Selection<SVGCircleElement>[];
    /** Drawn convex hull group */
    convexHull: D3Selection<SVGGElement> | undefined;

    /** Host ratios normalized in the range [0, 2] */
    hostRatios: [number, number][];
    /** Host counts. */
    hostCounts: Record<string, number>;
    /** Number of attack paths in the query. */
    count: number;

    /** Relative link ratios */
    linkTally: Record<string, number>;
    /** The sum of all link tallies */
    linkSum: number;
    /** The maximum of all link tallies */
    linkMax: number;

    /** Whether to show this query on hosts. */
    showHost: boolean;
    /** Whether to show this query on links. */
    showLinks: boolean;
}

interface HostAndLink {
    host: boolean,
    link: boolean,
}

export interface HoveredHost {
    /** Mouse coordinates (x) */
    x: number;
    /** Mouse coordinates (y) */
    y: number;

    /** Host id */
    id: number;
    /** Host name */
    name: string;
    /** Host IP Address */
    ip: string;

    /** Whether the host is selected */
    selected: boolean;

    /** The information per query (including stat) */
    queries: HoveredHostPerQuery[];
}

interface HoveredHostPerQuery {
    /** Query name */
    name: string;
    /** Query color */
    color: RGBColor;
    /** The number of paths passing through the host */
    count: number;
    /** The percentage of paths passing through the host */
    ratio: number;
    /** The ranking of the host in the query */
    rank?: number;
}

enum OverviewState {
    Idle,
    Selecting,
    DraggingCamera,
    DraggingHosts,
}

const HOST_RADIUS = 12;

export class OverviewCanvas {
    /** Entire canvas SVG element */
    svg: SVGSVGElement;
    /** Attack graph model with the network information */
    model: AttackGraphModel;

    /** The *uniform* padding to keep when centering */
    padding: number = 50;

    // There are two types of coordinates: 
    // - topology coordinates: found in the model received by the server
    // - screen coordinates: found in the SVG element
    // These three variables define the transformation matrix between the two.
    /** Scaling factor - a single one to maintain aspect ratio */
    scale: number = 1;
    /** Horizontal translation factor, applied *after* scaling */
    translateX: number = 0;
    /** Vertical translation factor, applied *after* scaling */
    translateY: number = 0;

    /** A map from each host id to its selection element and links */
    private hosts: Record<number, OverviewHostInformation> = {};
    /** A map from each link to the group containing its link ratios */
    private linkRatios: Record<string, D3Selection<SVGGElement>> = {};
    /** A map from each link to the the line element connecting the two hosts. */
    private linkLines: Record<string, D3Selection<SVGLineElement>> = {};

    /** Group containing everything that should be moved by the camera,
     *  as a selection for easier manipulation */
    private cameraGroup: D3Selection<SVGGElement>;
    /** Group for the links ratios */
    private linkRatiosGroup: D3Selection<SVGGElement>;
    /** Group for the link lines */
    private linkLinesGroup: D3Selection<SVGGElement>;
    /** Group for the hosts */
    private hostGroup: D3Selection<SVGGElement>;
    /** Group for host groupings */
    private highlightsGroup: D3Selection<SVGGElement>;

    /** Unsubscriber for the statistics. */
    private unsubscribeFromStats: Unsubscriber;
    /** Unsubscriber for the active queries. */
    private unsubscribeFromQueries: Unsubscriber;

    constructor(svg: SVGSVGElement, model: AttackGraphModel) {
        this.svg = svg;
        this.model = model;

        this.cameraGroup = select(svg)
            .insert("g")
            .attr("id", "camera-group");
        this.centerCamera();

        // Draw all the nodes and links
        this.linkRatiosGroup = this.cameraGroup.append("g")
            .attr("class", "link-ratios");
        this.highlightsGroup = this.cameraGroup.append("g")
            .attr("class", "groupings")
            .attr("style", "pointer-events: none;")
        this.linkLinesGroup = this.cameraGroup.append("g")
            .attr("class", "link-lines");
        this.hostGroup = this.cameraGroup.append("g")
            .attr("class", "hosts");
        this.initHostsAndLinks();
        this.linksRatiosOrLines = "ratios";

        // Add listeners to the svg
        svg.addEventListener("mousedown", this.onMouseDown.bind(this));
        window.addEventListener("mousemove", this.onMouseMove.bind(this));
        window.addEventListener("mouseup", this.onMouseUp.bind(this));
        svg.addEventListener("wheel", this.onWheel.bind(this));
        svg.addEventListener("contextmenu", (event) => event.preventDefault());

        // Subscribe to the server's events
        this.unsubscribeFromQueries = server.steeringQueries.subscribe(this.updateSteerAGQQueries.bind(this));
        this.unsubscribeFromStats = server.statistics.subscribe(this.updateStatistics.bind(this));
    }

    public destroy() {
        window.removeEventListener("mouseup", this.onMouseUp);
        window.removeEventListener("mousemove", this.onMouseMove);

        this.unsubscribeFromStats();
        this.unsubscribeFromQueries();
    }

    /** Positions the camera so that all nodes in the network are in view. */
    public centerCamera() {
        let minx = Infinity;
        let maxx = -Infinity;
        let miny = Infinity;
        let maxy = -Infinity;

        for (const p of this.model.hosts) {
            if (p.x < minx) minx = p.x;
            else if (p.x > maxx) maxx = p.x;
            if (p.y < miny) miny = p.y;
            else if (p.y > maxy) maxy = p.y;
        }

        const { width, height } = this.svg.getBoundingClientRect();

        const difW = maxx - minx + 2 * this.padding;
        const difH = maxy - miny + 2 * this.padding;

        const scale = Math.min(width / difW, height / difH);
        const centerX = minx - this.padding - (width - difW * scale) / 2 / scale;
        const centerY = miny - this.padding - (height - difH * scale) / 2 / scale;

        this.updateTransformMatrix(scale, centerX, centerY);
    }
    /** Updates the global camera transformation matrix.  */
    private updateTransformMatrix(scale: number, translateX: number, translateY: number) {
        this.scale = scale;
        this.translateX = translateX;
        this.translateY = translateY;

        this.cameraGroup.attr("transform",
            `scale(${scale} ${scale}) translate(${-translateX} ${-translateY})`);
    }
    /** Converts the given screen coordinates to host coordinates
     *  by inverting the canvas' camera transformation matrix */
    private screenToHostCoordinates(x: number, y: number): Point {
        return {
            x: x / this.scale + this.translateX,
            y: y / this.scale + this.translateY
        };
    }

    private initHostsAndLinks() {
        for (const host of this.model.hosts)
            this.insertHost(host);
        for (const [source, target] of this.model.edges)
            this.insertLink(source, target);
    }

    /** Inserts everything needed to handle a new host. */
    private insertHost(host: HostInformation) {
        const group = this.hostGroup.append("g")
            .attr("class", "host")
            .attr("selected", "false")
            .attr("n", host.id)
            .attr("transform", `translate(${host.x} ${host.y})`);
        const circle = group.append("circle")
            .attr("class", "host-circle")
            .attr("r", HOST_RADIUS)
            .attr("fill", "white")
            .attr("stroke", "black");

        const text = group.append("text")
            .attr("fill", "white")
            .attr("text-anchor", "middle")
            .attr("font-size", HOST_RADIUS)
            .attr("y", HOST_RADIUS / 2 - 1)
            .text(host.id);

        this.hosts[host.id] = {
            selection: circle,
            group,
            text,
            neighbors: [],
            model: host,
        };
    }
    /** Inserts everything needed to handle a new link. */
    private insertLink(sourceId: number, targetId: number) {
        // Ensure each (undirected) link is only drawn once
        if (targetId < sourceId)
            [sourceId, targetId] = [targetId, sourceId];
        if (this.linkRatios[`${sourceId}-${targetId}`] !== undefined)
            return;

        const linkId = `${sourceId}-${targetId}`;

        // Add a group to contain both the rects.
        const g = this.linkRatiosGroup.insert("g");
        this.linkRatios[linkId] = g;

        // Create the line
        const line = this.linkLinesGroup.append("line").attr("stroke", "black");
        this.linkLines[linkId] = line;

        this.hosts[sourceId].neighbors.push(targetId);
        this.hosts[targetId].neighbors.push(sourceId);

        // Update the positions for the group
        this.updateLinkPosition(sourceId, targetId);
    }
    /** Obtain the host model object given a target object */
    private getHostFromTarget(target: EventTarget): HostInformation | null {
        // Make sure the target is not the SVG itself
        if (!(target instanceof SVGElement))
            return null;

        // Go up one class and look until you find an element with class .host
        let element: Element | null = target;
        while (element !== null && !element.classList.contains("host"))
            element = element.parentElement;

        if (element === null)
            return null;

        const id = parseInt(element.getAttribute("n") ?? "");
        return this.model.hosts[id] ?? null;
    }
    /** Move a host to another coordinate */
    private updateHostPosition(id: number, x: number, y: number) {
        // Get the host model object
        const host = this.model.hosts[id];
        host.x = x;
        host.y = y;

        // Update the circle's position
        this.hosts[id].group.attr("transform", `translate(${x} ${y})`);

        // Update all neighboring links
        for (const other of this.hosts[id].neighbors) {
            this.updateLinkPosition(host.id, other)
        }
    }
    /** Move a link (and all the internal rectangles) to the new position. */
    private updateLinkPosition(sourceId: number, targetId: number) {
        if (targetId < sourceId)
            [sourceId, targetId] = [targetId, sourceId];
        const g = this.linkRatios[`${sourceId}-${targetId}`];
        if (!g) return;

        const { x: ax, y: ay } = this.model.hosts[sourceId];
        const { x: bx, y: by } = this.model.hosts[targetId];

        const d = Math.hypot(ax - bx, ay - by);

        const u = (ax + bx) / 2;
        const v = (ay + by) / 2;
        const b = bx - ax;
        const a = by - ay;
        const alpha = -Math.atan2(b, a) / Math.PI * 180;

        const s = Math.max(d - 2 * HOST_RADIUS, 1);
        g.selectAll("rect")?.attr("y", -s / 2).attr("height", s);

        g.attr("transform", `translate(${u} ${v}) rotate(${alpha})`);

        // Update the position of the line
        this.linkLines[`${sourceId}-${targetId}`]
            .attr("x1", ax)
            .attr("y1", ay)
            .attr("x2", bx)
            .attr("y2", by);
    }

    public set linksRatiosOrLines(what: "ratios" | "lines") {
        if (what === "ratios") {
            this.linkRatiosGroup.attr("visibility", "visible");
            this.linkLinesGroup.attr("visibility", "hidden");
        } else {
            this.linkRatiosGroup.attr("visibility", "hidden");
            this.linkLinesGroup.attr("visibility", "visible");
        }
    }


    // Query host highlighting and query updates.
    /** Whether to compute and show convex hulls. */
    #showConvexHulls: boolean = true;
    /** Whether to compute and show circles. */
    #showCircles: boolean = true;
    /** The threshold for convex hull separation. */
    #convexHullThreshold: number = 100;
    /** Whether to show the StatAG ratios on the links. */
    #showStatAGRatios: boolean = true;
    /** How to draw ratios on links */
    #linkStyle: LinkStyle = LinkStyle.RelativeSum;

    /** All data about each query */
    private queries: SteerAGQueryResults[] = [];
    /** All data about what is shown of each query and what is not, for external reading. */
    public queryShows: Writable<HostAndLink[]> = writable([]);
    /** Tally of paths passing through each link in StatAG. */
    private baseLinkTally: Record<string, number> = {}
    /** Max links passing through a link in StatAG, for relative normalization. */
    private baseLinkMax: number = 0;
    /** Total number of computed links in StatAG, for absolute normalization. */
    private baseLinkCount: number = 0;

    public set showConvexHulls(value: boolean) {
        this.#showConvexHulls = value;
        for (let id = 0; id < this.queries.length; id++)
            this.showHostsForQuery(id);
    }
    public get showConvexHulls() { return this.#showConvexHulls; }

    public set showCircles(value: boolean) {
        this.#showCircles = value;
        for (let id = 0; id < this.queries.length; id++)
            this.showHostsForQuery(id);
    }
    public get showCircles() { return this.#showCircles; }

    public set convexHullThreshold(value: number) {
        this.#convexHullThreshold = value;

        if (!this.#showConvexHulls) return;

        for (let id = 0; id < this.queries.length; id++)
            if (this.queries[id]?.showHost)
                this.convexHullQuery(id);
    }
    public get convexHullThreshold() { return this.#convexHullThreshold; }

    public set showStatAGRatios(value: boolean) {
        this.#showStatAGRatios = value;
        this.redrawLinkRatios();
    }
    public get showStatAGRatios() { return this.#showStatAGRatios; }

    public set linkStyle(value: LinkStyle) {
        this.#linkStyle = value;
        this.redrawLinkRatios();
    }
    public get linkStyle() { return this.#linkStyle; }


    /** Perform the SVG updates to show the updated query, if necessary. */
    private showHostsForQuery(id: number) {
        const query = this.queries[id];
        if (query === undefined)
            return;

        if (this.#showConvexHulls && query.showHost)
            this.convexHullQuery(id);
        else {
            // Destroy all convex hulls
            query.convexHull?.remove();
        }

        if (this.#showCircles && query.showHost)
            this.drawCirclesForQuery(id);
        else {
            // Hide all circles
            for (const circle of query.circles)
                circle.style("display", "none");
        }
    }

    /** Draws circles above the hosts for the query. */
    private drawCirclesForQuery(id: number) {
        // Create the query circles if not already present.
        if (this.queries[id].circles.length === 0)
            this.initializeCirclesForQuery(id);

        const { hostRatios, rgb, circles } = this.queries[id];
        const color = rgb.join(",");

        for (const [ratio, host] of hostRatios) {
            circles[host].style("display", null);

            if (Number.isNaN(ratio)) {
                circles[host].attr("fill", "transparent");
                continue;
            }

            // Transform the ratio so that values below are very close to 0
            // and values above one are scaled up to 0.5.
            let value = ratioEasing(ratio);
            circles[host].attr("fill", `rgba(${color}, ${value})`)
        }
    }
    /** Initialize the circles for the hosts for the query. */
    private initializeCirclesForQuery(id: number) {
        const circles: D3Selection<SVGCircleElement>[] = [];
        this.queries[id].circles = circles;

        for (const hostId in this.hosts) {
            const { group } = this.hosts[hostId];
            circles[hostId] = group
                .insert("circle")
                .attr("r", HOST_RADIUS * 3.5 + id * 3.5)
                .attr("class", "halo")
                .style("pointer-events", "none");
        }
    }

    /** Highlights the given hosts with convex hulls of the given color,
     * making sure to use multiple ones every time it grows too big. */
    private convexHullQuery(id: number) {
        const { rgb, hostRatios, convexHull } = this.queries[id];

        const borderColor = `rgb(${rgb.join(",")})`;
        const backgroundColor = `rgba(${rgb.join(",")}, 0.15)`;

        // Filter the hosts.
        const hosts = hostRatios
            // Sort the results by ratio
            .sort(([ra, ha], [rb, hb]) => rb - ra)
            // Keep only those with ratio >1
            .filter(([ra, ha]) => ra > 1)
            // Ignore the ratio data.
            .map(([ra, ha]) => ha);

        // Delete the last group if any
        convexHull?.remove();

        // Create a new group
        const g = this.highlightsGroup.insert("g");

        drawConvexHullIntoGroup({
            g,
            borderColor,
            backgroundColor,
            pointRadius: HOST_RADIUS,
            thickness: 10 + id,
            coordinates: this.model.hosts,
            points: hosts,
            threshold: this.#convexHullThreshold,
        })

        this.queries[id].convexHull = g;
    }


    /** Update the query data whenever new queries are created */
    private updateSteerAGQQueries(data?: SteerAGInstance[]) {
        // Do not update if the data is undefined
        if (data === undefined) return;

        let changeForLinks = false;
        // For each query
        for (const query of data) {
            const id = query.id;
            const registered = this.queries[id];

            // If the query is not active, but it is already registered here.
            if (!query.active && registered !== undefined) {
                delete this.queries[id];
                this.queryShows.update((s) => {
                    delete s[id];
                    return s;
                });
                // Destroy all convex hulls
                registered.convexHull?.remove();
                // Destroy all circles
                for (const circle of registered.circles)
                    circle.remove();

                changeForLinks = true;
            }
            // If the query is active, but it is not registered here.
            else if (query.active && registered === undefined) {
                this.queries[id] = {
                    id,
                    rgb: query.color,
                    color: `rgb(${query.color})`,
                    circles: [],
                    convexHull: undefined,
                    hostRatios: [],
                    hostCounts: {},
                    count: 0,
                    linkTally: {},
                    linkSum: 0,
                    linkMax: 0,
                    showHost: true,
                    showLinks: true,
                };

                this.queryShows.update((s) => {
                    if (s[id] === undefined)
                        s[id] = {
                            host: true,
                            link: true,
                        };
                    return s;
                });
            }
            // If the query is registered, and it is active.
            else if (query.active && registered !== undefined) {
                // If the color changed
                if (query.color.join(",") !== registered.rgb.join(",")) {
                    this.queries[id].rgb = query.color;
                    this.queries[id].color = `rgb(${query.color.join(",")})`;

                    // Redraw everything for this query
                    if (this.#showConvexHulls)
                        this.convexHullQuery(id);
                    if (this.#showCircles)
                        this.drawCirclesForQuery(id);

                    changeForLinks = true;
                }
            }
        }

        if (changeForLinks) {
            this.redrawLinkRatios();
        }
    }


    private async updateStatistics(stats?: BundledStatistics) {
        if (stats === undefined) return;
        const { stat, steer } = stats;

        // Find the maximum host color
        let maxAPsPerHost = 0;
        for (const host in stat.hosts)
            maxAPsPerHost = Math.max(stat.hosts[host], maxAPsPerHost);

        // Update the color of each host
        for (const host of this.model.hosts) {
            const { selection: circle, text } = this.hosts[host.id];
            const aps = stat.hosts[host.id] ?? 0;
            const t = aps / maxAPsPerHost;

            const color = `rgb(${255 - 255 * t}, ${255 - 255 * t}, 255)`;
            circle.attr("fill", color);
            text.attr("fill", t < 0.5 ? "black" : "white");
        }

        const [linkSums, sum, max] = computeLinkRelativityStat(stat);
        this.baseLinkTally = linkSums;
        this.baseLinkCount = sum;
        this.baseLinkMax = max;

        // Update the query results
        for (let id = 0; id < steer.length; id++) {
            if (steer[id] === undefined) continue;
            if (get(server.steeringQueries)[id].active === false) continue;

            await this.updateQueryResult(id, steer[id]);
        }

        this.redrawLinkRatios();
    }
    /** Tell the overview that the query with the given id has new results and color. */
    public async updateQueryResult(id: number, stats: SteerAGStatistics) {
        while (this.queries[id] === undefined)
            await new Promise((resolve) => setTimeout(resolve, 100));
        if (stats === undefined)
            return;

        const hostRatios = computeHostRatios(stats);
        const [linkTallies, linkSum, linkMax] = computeLinkRelativityStat(stats);

        this.queries[id].hostRatios = hostRatios;
        this.queries[id].linkTally = linkTallies;
        this.queries[id].linkSum = linkSum;
        this.queries[id].linkMax = linkMax;
        this.queries[id].hostCounts = stats.hosts;
        this.queries[id].count = stats.uniqueQuery;

        this.showHostsForQuery(id);
    }

    /** Draws the rectangles to represent the ratios of query paths on each link. */
    private redrawLinkRatios() {
        // For each link, find the size of the rectangles.
        const sizes: Record<string, number> = {};
        let maxSize: number = 0;

        // Only the fast one skips this step, as it uses StatAG for thickness.
        if (this.#linkStyle !== LinkStyle.RelativeStat) {
            for (const link in this.baseLinkTally) {
                let sum = 0;

                if (this.#showStatAGRatios) {
                    let ratio = this.getRatio(this.baseLinkTally, link, this.baseLinkMax, this.baseLinkCount);
                    if (Number.isNaN(ratio)) continue;
                    sum += ratio;
                }

                for (const query of this.queries) {
                    if (query === undefined) continue;
                    if (query.showLinks === false) continue;
                    if (query.linkTally[link] === undefined) continue;

                    let ratio = this.getRatio(query.linkTally, link, query.linkMax, query.linkSum);
                    if (Number.isNaN(ratio)) continue;
                    sum += ratio;
                }
                sizes[link] = sum;
                maxSize = Math.max(maxSize, sum);
            }

            for (const link in sizes) {
                sizes[link] /= maxSize;
            }
        }

        for (const link in this.baseLinkTally) {
            const rectangles: { ratio: number, color: string }[] = [];

            if (this.#showStatAGRatios) {
                let ratio = this.getRatio(this.baseLinkTally, link, this.baseLinkMax, this.baseLinkCount);
                if (Number.isNaN(ratio)) continue;

                const color = "blue";
                rectangles.push({ ratio, color });
            }

            for (const query of this.queries) {
                if (query === undefined) continue;
                if (query.showLinks === false) continue;
                if (query.linkTally[link] === undefined) continue;

                let ratio = this.getRatio(query.linkTally, link, query.linkMax, query.linkSum);
                if (Number.isNaN(ratio)) continue;

                const color = query.color;
                rectangles.push({ ratio, color });
            }

            if (this.#linkStyle === LinkStyle.RelativeStat) {
                // The thickness depends only on StatAG.
                const thickness = this.baseLinkTally[link] / this.baseLinkMax;
                this.drawLinkRectangles(link, thickness, rectangles);
            }
            else {
                const thickness = sizes[link];
                this.drawLinkRectangles(link, thickness, rectangles);
            }

            this.updateLinkRectanglesHeights(link);
        }
    }

    private getRatio(tallies: Record<string, number>, link: string, max: number, sum: number): number {
        if (this.#linkStyle === LinkStyle.RelativeSum || this.#linkStyle === LinkStyle.RelativeStat)
            return tallies[link] / sum;
        else if (this.#linkStyle === LinkStyle.RelativeMax)
            return tallies[link] / max;
        else
            return tallies[link];
    }

    /** Draws a set of rectangles with the given properties:
     * 
     * @param link The id of the link.
     * @param thickness The thickness of the link in the range [0, 1].
     * @param rectangles The set of rectangles to draw, 
     * each with a relative ratio of the width and a color.
     */
    private drawLinkRectangles(link: string, thickness: number, rectangles: { ratio: number, color: string }[]) {
        // Remove all rectangles from the group
        const g = this.linkRatios[link];
        g.selectAll("rect").remove();

        if (Number.isNaN(thickness) || thickness === 0) {
            g.insert("rect")
                .attr("x", -0.5)
                .attr("width", 1)
                .attr("fill", "blue");

            this.updateLinkRectanglesHeights(link);
        }
        thickness = Math.max(1, thickness * 1.5 * HOST_RADIUS);

        let sum = 0;
        let offset = 0;
        for (const { ratio } of rectangles) sum += ratio;

        const scaling = thickness / sum;
        for (const { ratio, color } of rectangles) {
            const rw = ratio * scaling;
            g.insert("rect")
                .attr("x", offset * scaling - thickness / 2)
                .attr("width", rw)
                .attr("fill", color);
            offset += ratio;
        }

        if (rectangles.length === 0) {
            g.insert("rect")
                .attr("x", -0.25)
                .attr("width", 0.5)
                .attr("fill", "black");
        }

        this.updateLinkRectanglesHeights(link);
    }

    /** Updates the heights of the link's rectangles based
     *  on the same logic used in updateLinkPosition */
    private updateLinkRectanglesHeights(link: string) {
        const [sourceId, targetId] = link.split("-");
        const source = this.model.hosts[parseInt(sourceId)];
        const target = this.model.hosts[parseInt(targetId)];

        const d = Math.hypot(source.x - target.x, source.y - target.y);
        const s = Math.max(d - 1.5 * HOST_RADIUS, 1);

        this.linkRatios[link]
            .selectAll("rect")
            .attr("y", -s / 2)
            .attr("height", s);
    }

    // Toggling visualization
    /** Set whether the given query results should be shown on links. */
    public setLinksView(id: number, value?: boolean) {
        if (!this.queries[id]) return;
        if (value === undefined)
            value = !this.queries[id].showLinks;

        this.queries[id].showLinks = value;
        this.redrawLinkRatios();
        this.queryShows.update(s => { s[id].link = value; return s });
    }
    /** Set whether the given query results should be shown on hosts. */
    public setHostsView(id: number, value?: boolean) {
        if (!this.queries[id]) return;
        if (value === undefined)
            value = !this.queries[id].showHost;

        this.queries[id].showHost = value;
        this.showHostsForQuery(id);
        this.queryShows.update(s => { s[id].host = value; return s });
    }
    /** Highlight a single query */
    public highlightQuery(id: number) {
        const queryShows = get(this.queryShows).map((value, i) => {
            if (value === undefined) return undefined;
            return { host: value.host, link: value.link, index: i };
        }).filter(value => value !== undefined);

        const allFalseButId = queryShows
            .every(({ host, link, index: i }) =>
                i === id ? host && link : !host && !link);

        // Hide all queries except the given one
        for (const query of this.queries) {
            if (!query) continue;

            this.setLinksView(query.id, allFalseButId || query.id === id);
            this.setHostsView(query.id, allFalseButId || query.id === id);
        }
    }

    // Interaction
    /** What actions are allowed and with which controls, see enum for descriptions. */
    mode: OverviewMode = OverviewMode.SelectionAndEditing;
    /** Which state of the interaction we are currently in. */
    private state: OverviewState = OverviewState.Idle;
    /** `event.offset`{`X`|`Y`} when the mouse is pressed down */
    private mouseStart: Point = { x: 0, y: 0 };

    /** **For camera movement** - the starting translation. */
    private cameraStart: Point = { x: 0, y: 0 };
    /** **For selection** - lasso representing the selection */
    private selectionLasso: D3Selection<SVGPolygonElement> | null = null;
    /** **For selection** - points to compose the lasso polyline. */
    private selectionLassoPoints: [number, number][] = [];

    /** **For selection** - The IDs of the selected host as a store. */
    public selection: Writable<number[] | null> = writable(null);
    /** **For selection** - The set of selected hosts */
    public selectedHosts = new HostSelection(this.hosts);
    /** **For editing** - Stored initial coordinates for selected hosts if dragging them */
    private selectedHostsStart: Record<number, Point> = {};
    /** Undo stack (no redo necessary) */
    private moveUndoStack: Record<number, Point>[] = [];
    public undoStackLength = writable(0);

    private onMouseDown(event: MouseEvent) {
        // If the state is not idle, ignore the event
        if (this.state !== OverviewState.Idle)
            return;

        const left = this.svg.getBoundingClientRect().left;
        this.mouseStart = { x: event.clientX - left, y: event.clientY };

        // If you are right clicking in any mode, or left clicking in camera mode,
        // you have to start dragging the camera
        if (event.button === 2 || this.mode === OverviewMode.CameraMovement) {
            this.cameraStart = { x: this.translateX, y: this.translateY };
            this.state = OverviewState.DraggingCamera;
        }
        // If you are left clicking in selection mode or editing, you have to start selecting
        else if ((this.mode === OverviewMode.Selection || this.mode == OverviewMode.SelectionAndEditing) && event.button === 0) {
            this.state = OverviewState.Selecting;
            this.selectionLasso = this.cameraGroup.append("polygon")
                .attr("stroke", "black")
                .attr("stroke-dasharray", "5,5")
                .attr("fill", "rgba(0, 0, 0, 0.1)");
            this.selectionLassoPoints = [];
        }
        // If you are middle clicking in editing mode, you have to start dragging the selected hosts (if any)
        else if (this.mode === OverviewMode.SelectionAndEditing && event.button === 1 && this.selectedHosts.size > 0) {
            // Save the initial coordinates of the selected hosts
            this.selectedHostsStart = {};
            for (const hostId of this.selectedHosts) {
                const host = this.model.hosts[hostId];
                this.selectedHostsStart[hostId] = { x: host.x, y: host.y };
            }
            // Save it in the undo stack (no need to copy as this reference is never modified)
            this.moveUndoStack.push(this.selectedHostsStart);
            this.undoStackLength.set(this.moveUndoStack.length);

            this.state = OverviewState.DraggingHosts;
        }
        // In any other case, ignore the event
        else {
            this.state = OverviewState.Idle;
        }
    }
    private onMouseMove(event: MouseEvent) {
        const left = this.svg.getBoundingClientRect().left;
        const mouse = { x: event.clientX - left, y: event.clientY };

        switch (this.state) {
            // If on idle, look for an host to show an infobox on
            case OverviewState.Idle:
                this.prepareInfoBox(event);
                break;

            // Move the camera
            case OverviewState.DraggingCamera: {
                const dx = (this.mouseStart.x - mouse.x) / this.scale;
                const dy = (this.mouseStart.y - mouse.y) / this.scale;
                const nx = this.cameraStart.x + dx;
                const ny = this.cameraStart.y + dy;
                this.updateTransformMatrix(this.scale, nx, ny);
                break
            }
            // Update the selection lasso
            case OverviewState.Selecting: {
                if (this.selectionLasso === null)
                    return;
                const point = this.screenToHostCoordinates(mouse.x, mouse.y);
                this.selectionLassoPoints.push([point.x, point.y]);
                this.selectionLasso.attr("points",
                    this.selectionLassoPoints.map(([x, y]) => `${x},${y}`).join(" "))
                break;
            }
            // Update all the selected hosts' positions with the difference
            case OverviewState.DraggingHosts: {
                const dx = (this.mouseStart.x - mouse.x) / this.scale;
                const dy = (this.mouseStart.y - mouse.y) / this.scale;

                for (const hostId of this.selectedHosts) {
                    const start = this.selectedHostsStart[hostId];
                    this.updateHostPosition(hostId, start.x - dx, start.y - dy);
                }

                break;
            }
        }
    }
    private onMouseUp(event: MouseEvent) {
        const left = this.svg.getBoundingClientRect().left;
        const mouse = { x: event.clientX - left, y: event.clientY };

        switch (this.state) {
            case OverviewState.Selecting:
                if (this.selectionLasso !== null) {
                    this.selectionLasso.remove();
                    this.selectionLasso = null;
                }

                const rw = Math.abs(this.mouseStart.x - mouse.x);
                const rh = Math.abs(this.mouseStart.y - mouse.y);

                // Random click, call click
                if (Math.hypot(rw, rh) <= HOST_RADIUS) {
                    this.onClick(event);
                    break;
                }

                const shift = event.shiftKey;

                for (const host of this.model.hosts) {
                    if (polygonContains(this.selectionLassoPoints, [host.x, host.y])) {
                        if (shift)
                            this.selectedHosts.delete(host.id);
                        else
                            this.selectedHosts.add(host.id);
                    }
                }

                this.onHostSelectionChanged();

                break;
            case OverviewState.DraggingHosts:
                // Re-highlight all queries.
                for (let id = 0; id < this.queries.length; id++)
                    this.showHostsForQuery(id);
                break
        }
        this.state = OverviewState.Idle;
    }
    private onClick(event: MouseEvent) {
        const target = event.target as SVGElement;

        // If you can select hosts
        if (this.mode === OverviewMode.Selection || this.mode === OverviewMode.SelectionAndEditing) {
            // If you are clicking on one
            const host = this.getHostFromTarget(target);
            // Toggle its selection status
            if (host !== null) {
                if (this.selectedHosts.has(host.id))
                    this.selectedHosts.delete(host.id);
                else
                    this.selectedHosts.add(host.id);

                this.onHostSelectionChanged();
            }
            // Otherwise, clear all selection, unless you are pressing on shift
            else if (!event.shiftKey) {
                this.selectedHosts.clear();
                this.onHostSelectionChanged();
            }
        }

        this.state = OverviewState.Idle;
    }
    private onWheel(event: WheelEvent) {
        const left = this.svg.getBoundingClientRect().left;
        const mouse = { x: event.clientX - left, y: event.clientY };
        const factor = (1 + event.deltaY / 1000);
        this.zoom(factor, mouse);
    }

    /**
     * Actions to take when the host selection changes.
     */
    private onHostSelectionChanged() {
        // Collect the selected hosts
        const selectedHosts = Array.from(this.selectedHosts);
        this.selection.set(selectedHosts.length === 0 ? null : selectedHosts);

        // // You can do everything only if the AM is loaded.
        // const am = AMOverview.singleton;
        // if (am === null) return;

        // if (selectedHosts.length === 0)
        //     am.hosts = null;
        // else {
        //     // Update the AM with the new selection
        //     selectedHosts.sort((a, b) => a - b);
        //     am.hosts = selectedHosts;
        // }
    }


    // Data higlighting
    public attackPathsView = writable(false);
    // THe hovered host information
    public hoveredHost = writable<HoveredHost | null>(null);

    /** Clear the selection and add the given hosts to the selection, 
     * divided between sources and targets. */
    public selectHosts(hosts: { sources: number[], targets: number[] }) {
        let sources = new Set(hosts.sources);
        let targets = new Set(hosts.targets);

        const intersection = sources.intersection(targets);
        sources = sources.difference(intersection);
        targets = targets.difference(intersection);

        this.selectedHosts.clear();
        for (const host of hosts.sources)
            this.selectedHosts.addWithRole(host, "s");
        for (const host of hosts.targets)
            this.selectedHosts.addWithRole(host, "t");
        for (const host of intersection)
            this.selectedHosts.addWithRole(host, "st");

        this.onHostSelectionChanged();
    }

    /** Selects the top hosts for the given query. */
    public selectTopHosts(queryId: number, count: number) {
        // The record is in "id" => count form, turn it into a sortable array
        const hosts = this.queries[queryId].hostRatios
            // Sort the results by ratio
            .sort(([ra, ha], [rb, hb]) => rb - ra)
            // Select only the top hosts
            .slice(0, count)
            // Ignore the ratio data.
            .map(([ra, ha]) => ha);

        // Select them (without using the selectHosts method)
        this.selectedHosts.clear();
        for (const host of hosts)
            this.selectedHosts.add(host);
        this.onHostSelectionChanged();
    }

    public selectAttackPaths(queryId: number, attackPaths: [string, number][]) {
        const queryColor = this.queries[queryId].color;

        const stats: Record<string, [number, number]> = {};
        let maxValue = 0;

        for (const path of attackPaths) {
            // const score = path[1];
            const score = 1;

            for (const step of path[0].split("##")) {
                const [source, _, target] = step.split("#");
                const sourceId = parseInt(source.split("@")[1]);
                const targetId = parseInt(target.split("@")[1]);

                const min = Math.min(sourceId, targetId);
                const max = Math.max(sourceId, targetId);
                const linkId = `${min}-${max}`;

                if (stats[linkId] === undefined)
                    stats[linkId] = [0, 0];

                const prevAvg = stats[linkId][0];
                const prevN = stats[linkId][1];
                // Progressive average
                stats[linkId][0] = prevAvg + (score - prevAvg) / (prevN + 1);
                stats[linkId][1] = prevN + 1;

                maxValue = Math.max(maxValue, stats[linkId][0] * stats[linkId][1]);
            }
        }

        for (const linkId in this.linkLines) {
            const stat = stats[linkId];
            const link = this.linkLines[linkId];

            if (stat === undefined)
                link.attr("stroke-width", 0.1)
                    .attr("stroke", "black");
            else {
                const ratio = stat[0] * stat[1] / maxValue * HOST_RADIUS;

                link.attr("stroke-width", ratio)
                    .attr("stroke", queryColor);
            }
        }

        this.linksRatiosOrLines = "lines";
        this.attackPathsView.set(true);
    }

    public zoom(factor: number, mouse: Point | null = null) {
        if (mouse === null) {
            const { width, height } = this.svg.getBoundingClientRect();
            mouse = { x: width / 2, y: height / 2 };
        }

        // Zoom into the mouse position
        const scale = Math.max(0.1, this.scale / factor);
        const tx = mouse.x * (1 / this.scale - 1 / scale) + this.translateX;
        const ty = mouse.y * (1 / this.scale - 1 / scale) + this.translateY;

        this.updateTransformMatrix(scale, tx, ty);
    }

    /** Undo a host movement in case you mess up. */
    public undoMovement() {
        const lastMove = this.moveUndoStack.pop();
        this.undoStackLength.set(this.moveUndoStack.length);
        if (lastMove === undefined)
            return;

        for (const hostId in lastMove) {
            const { x, y } = lastMove[hostId];
            this.updateHostPosition(parseInt(hostId), x, y);
        }
    }

    // Saving/loading
    /** Update the positions on the server so that they are permanent */
    public async sendPositions() {
        const positions: Record<number, Point> = {};
        for (const host of this.model.hosts) {
            positions[host.id] = { x: host.x, y: host.y };
        }

        await server.request("update_hosts_positions", positions);
    }
    /** Reset the positions of hosts as given by the server */
    public async resetPositions() {
        const positions = await server.request("request_hosts_positions");
        for (const hostId in positions) {
            const host = this.model.hosts[parseInt(hostId)];
            const [x, y] = positions[hostId];
            this.updateHostPosition(host.id, x, y);
        }
        // Clear the undo stack
        this.moveUndoStack = [];
        this.undoStackLength.set(0);
    }

    private prepareInfoBox(event: MouseEvent) {
        if (!event.target) return this.hoveredHost.set(null);
        const host = this.getHostFromTarget(event.target);
        if (host === null) return this.hoveredHost.set(null);
        const statData = get(server.statistics).stat;

        const id = host.id;
        const modelHost = this.model.hosts[id];
        const statCount = statData.hosts[id] ?? 0;
        const statRatio = statCount / statData.unique;

        const queries: HoveredHostPerQuery[] = [];
        queries.push({
            name: "Statistical",
            count: statCount,
            ratio: statRatio,
            color: [0, 0, 156],
        });

        for (const query of this.queries) {
            if (!query) continue;

            const queryInfo = get(server.steeringQueries)[query.id];
            if (queryInfo.active === false) continue;

            const count = query.hostCounts[id] ?? 0;
            const ratio = count / query.count;

            const rank = query.hostRatios.findIndex(([r, h]) => h === id);

            queries.push({
                name: queryInfo.name,
                color: queryInfo.color,
                count,
                ratio,
                rank: rank === -1 ? undefined : rank + 1,
            });
        }

        this.hoveredHost.set({
            x: event.pageX,
            y: event.pageY,

            id,
            name: modelHost.hostname,
            ip: modelHost.ipv4,

            selected: this.selectedHosts.has(host.id),
            queries,
        });
    }
}

class HostSelection extends Set<number> {
    constructor(private hostData: Record<number, OverviewHostInformation>) {
        super();
    }

    public sourceHosts = new Set<number>();
    public targetHosts = new Set<number>();

    hostSelection(id: number): D3Selection<SVGGElement> {
        return this.hostData[id].group;
    }

    add(id: number) {
        if (this.has(id)) return this;

        this.hostSelection(id).attr("selected", "true");
        return super.add(id);
    }
    delete(id: number) {
        this.hostSelection(id).attr("selected", "false");
        this.sourceHosts.delete(id);
        this.targetHosts.delete(id);
        return super.delete(id);
    }
    addWithRole(id: number, role: "s" | "t" | "st") {
        this.hostSelection(id).attr("selected", role);
        if (role === "s" || role === "st")
            this.sourceHosts.add(id);
        if (role === "t" || role === "st")
            this.targetHosts.add(id);
        return super.add(id);
    }

    clear() {
        for (const id of this) {
            this.hostSelection(id).attr("selected", "false");
        }
        this.sourceHosts.clear();
        this.targetHosts.clear();
        super.clear();
    }
}

function computeHostRatios(stats: SteerAGStatistics): [number, number][] {
    // Get the stats for this server
    const steer = stats.hosts;
    // const stat = get(server.statistics).stat.hosts;

    let maxSteer = 0;

    let ratios: [number, number][] = [];
    for (const id in server.model!.hosts) {
        const steerValue = steer[id] || 0;
        // const statValue = stat[id] || 0;

        if (steerValue > maxSteer) maxSteer = steerValue;

        // let ratio = statValue === 0 ? 0 : steerValue;
        let ratio = steerValue;
        ratios.push([ratio, parseInt(id)]);
    }

    const RATIO = 2 / maxSteer;

    const pairs = ratios
        // Sort them so that the highest ratios are first
        .sort(([r1, _h1], [r2, _h2]) => r2 - r1)
        // Map them so that when SteerAG is better than StatAG the value is >1
        .map(([r, h]) => [r * RATIO, h] as [number, number]);

    return pairs;
}
/** Computes the relative percentage of paths passing through each link. */
function computeLinkRelativityStat(stats: StatAGStatistics):
    [stats: Record<string, number>, sum: number, max: number] {
    const result: Record<string, number> = {};
    let sum = 0;
    let max = 0;

    for (const source in stats.edges) {
        const sourceInt = parseInt(source);
        for (const target in stats.edges[source]) {
            const targetInt = parseInt(target);

            let [a, b] = [sourceInt, targetInt];
            if (targetInt < sourceInt) [a, b] = [b, a];

            const link = `${a}-${b}`;
            result[link] ??= 0;
            result[link] += stats.edges[source][target];

            sum += result[link];
            max = Math.max(max, result[link]);
        }
    }

    return [result, sum, max];
}

/** At which height the parabolic easing starts. */
const PAR_H = 0.25;
/** The global dampening factor */
const DAMPING = 0.3333;

function ratioEasing(x: number): number {
    if (x < 1) return x * PAR_H * DAMPING;

    return DAMPING * ((1 - PAR_H) * (x - 1) ** 2 + PAR_H);
}