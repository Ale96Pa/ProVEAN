import type { BaseType, Selection } from "d3";

export interface AttackGraphModel {
    hosts: HostInformation[],
    edges: [number, number][],
    vulnerabilities: VulnerabilityDetails[]
}

export interface VulnerabilityDetails {
    id: string;
    score: ["V2" | "V30" | "V31", number, "LOW" | "MEDIUM" | "HIGH"];
    v2vector?: string;
    metrics: {
        cvssMetricV2?: {
            exploitabilityScore: number;
            impactScore: number;
            cvssData: { baseScore: number };
        }[];
        cvssMetricV31?: {
            exploitabilityScore: number;
            impactScore: number;
            cvssData: { baseScore: number };
        }[];
    }
}

export interface HostInformation {
    id: number;
    hostname: string;
    ipv4: string;
    domain: number;
    cves: string[];
    services: Record<string, string[]>
    x: number;
    y: number;
}

/** Result of calling `d3.select` on an element without anything else. */
export type D3Selection<T extends BaseType> = Selection<T, unknown, null, undefined>;

export type RGBColor = [r: number, g: number, b: number];

export interface Point {
    x: number;
    y: number;
}

/** Metrics for which an histogram is shown. */
export const AP_METRICS = [
    "likelihood",
    "impact",
    "score",
    "risk",
    "length",
    "damage",
] as const;

/** A single metric. */
export type APMetric = (typeof AP_METRICS)[number];
/** A single metric and its range. */
export type APCondition = [APMetric, number, number];


export interface AttackPath {
    trace: string;
    length: number;
    likelihood: number;
    impact: number;
    score: number;
    risk: number;
    damage: number;
    hash: string;
}