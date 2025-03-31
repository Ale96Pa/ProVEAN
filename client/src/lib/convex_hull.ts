import * as d3 from "d3";

import type { D3Selection, Point } from "./types";


interface ConvexHullParameters {
    /** Group where to put all the convex hull polygons. */
    g: D3Selection<SVGGElement>,
    /** The points to inscribe in convex hulls. */
    points: number[],
    /** The mapping from a point to its coordinates. */
    coordinates: Record<number, Point>,
    /** Threshold value for dividing the given points into partitions. */
    threshold: number;
    /** The radius of a point, so that the hulls circle it. */
    pointRadius: number;
    /** The convex hull thickness. */
    thickness: number;
    /** Border color of the convex hull polygons. */
    borderColor: string;
    /** Background color of the convex hull polygons. */
    backgroundColor: string;
}

type Tuple = [number, number];


export function drawConvexHullIntoGroup({
    g, points, coordinates, borderColor, backgroundColor,
    pointRadius, thickness, threshold
}: ConvexHullParameters) {
    // Partition the hosts with the given threshold.
    const partitions = partitionPoints(points, coordinates, threshold);

    for (const points of partitions) {
        // Update the coordinates that need to be included
        const allCoords: Tuple[] = [];
        for (const point of points) {
            const { x, y } = coordinates[point];
            allCoords.push(...circleAround(x, y, pointRadius + thickness))
        }

        // Compute the convex hull of said point.
        const convexHull = d3.polygonHull(allCoords);
        if (!convexHull) continue;

        const polygon = convexHull.map(([x, y]) => `${x},${y}`).join(" ");

        g.insert("polygon")
            .attr("points", polygon)
            .attr("stroke", borderColor)
            .attr("stroke-width", 2)
            .attr("fill", backgroundColor);

    }
}

/** Partitions the hosts into multiple convex hulls. */
function partitionPoints(
    points: number[], coordinates: Record<number, Point>, threshold: number
): number[][] {
    const distance = (p1: Point, p2: Point): number =>
        Math.hypot(p1.x - p2.x, p1.y - p2.y);

    // Check out a starting host.
    const remaining = new Set(points);
    const meshes: Set<number>[] = [];

    const expand = (startHost: number, mesh: Set<number>) => {
        const startPoint = coordinates[startHost];

        for (const host of remaining) {
            const hostPoint = coordinates[host];
            if (distance(startPoint, hostPoint) < threshold) {
                // Add the host point to the mesh and remove it from the remaining ones
                remaining.delete(host);
                mesh.add(host);
                // Expand starting from here
                expand(host, mesh);
            }
        }
    }

    while (remaining.size) {
        // Get the next host from the remaining hosts
        const startHost: number = remaining.values().next().value;
        remaining.delete(startHost);
        // Create a new mesh
        const mesh = new Set([startHost]);
        meshes.push(mesh);

        // Expand it using the rules.
        expand(startHost, mesh);
    }

    return meshes.map(mesh => [...mesh]);
}

/** Returns the points circling the given point */
function* circleAround(x: number, y: number, radius: number, precision: number = 32): Generator<Tuple> {
    for (let i = 0; i < precision; i++) {
        const alpha = i / precision * Math.PI * 2;
        const dx = radius * Math.cos(alpha);
        const dy = radius * Math.sin(alpha);
        yield [x + dx, y + dy];
    }
}