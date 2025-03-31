import { scaleLinear, scaleLog } from "d3";
import type { D3Selection } from "./types";

export type HistogramScale = "lin" | "log";

interface PlotHistogramArguments {
    /** The group element to plot the histograms into, as a d3 selection. */
    g: D3Selection<SVGGElement>;
    /** The width of the histogram area (including the space
     *  that will be reserved for the y axis) */
    width: number;
    /** The height of the histogram. */
    height: number;
    /** The distributions to plot, each with its fill and stroke colors. */
    dists: DistributionData[];
    /** Whether to plot the histogram a line chart or a bar chart. */
    lineChart: boolean;

    scale?: HistogramScale;
    /** Information about the y axis to print. */
    yAxis?: {
        width: number;
        position: "left" | "right";
    };
}

interface DistributionData {
    data: number[];
    fill: string;
    stroke: string;
}

const FONT_SIZE = 10;


/** Plots the histograms of one or more distribution. */
export function plotHistograms(o: PlotHistogramArguments) {
    // Unpack the arguments
    const { g, width, height, dists, lineChart, yAxis } = o;
    const linearScale = (o.scale ?? "lin") === "lin";

    // Clear the group element first
    g.selectAll("*").remove();

    const linesG = g.append("g").attr("class", "lines");

    // Create the plot group.
    const plot = g.insert("g").attr("class", "plot");
    let plotWidth = width;
    let plotHeight = height;
    if (yAxis) {
        plotWidth -= yAxis.width;
        plotHeight -= FONT_SIZE / 2;

        let x = yAxis.position === "left" ? yAxis.width : 0;
        let y = FONT_SIZE / 2;

        plot.attr("transform", `translate(${x} ${y})`);
        linesG.attr("transform", `translate(${x} ${y})`);
    }


    const { pmfMaximum, pmfTotals, absMaxExponent } = prepareData(dists);

    /** The linear scale for the x axis. */
    const xScale = scaleLinear()
        .domain([0, dists[0].data.length])
        .range([0, plotWidth]);
    /** The linear scale for the y axis. */
    const yScale = linearScale ?
        scaleLinear()
            .domain([0, pmfMaximum])
            .range([plotHeight, 0])
        : scaleLog()
            .domain([1, 10 ** absMaxExponent])
            .range([plotHeight, 0]);

    // For each point, find where it stands in the grand scheme of things
    for (let d = 0; d < dists.length; d++) {
        const { data, stroke, fill } = dists[d];

        const points: string[] = [];
        points.push(`-1,${plotHeight}`);

        for (let i = 0; i < data.length; i++) {
            if (pmfTotals[d] === 0) continue;

            const y = linearScale ?
                yScale(data[i] / pmfTotals[d])
                : yScale(data[i] || 1);

            points.push(`${xScale(i)},${y}`);
            if (!lineChart) points.push(`${xScale(i + 1)},${y}`);
        }
        points.push(`${plotWidth + 1},${plotHeight}`);


        plot.insert("polyline")
            .attr("points", points.join(" "))
            .attr("stroke", stroke)
            .attr("fill", fill);
    }

    if (yAxis) {
        const axisG = g.insert("g").attr("class", "y-axis");
        if (yAxis.position === "right")
            axisG.attr("transform", `translate(${plotWidth} ${FONT_SIZE})`)

        if (linearScale)
            plotLinearYAxis(axisG, linesG, plotWidth, plotHeight, yScale.invert);
        else
            plotLogYAxis(axisG, linesG, plotWidth, plotHeight, yScale, absMaxExponent);
    }

    return {
        xScale,
        pmfTotals
    }
}

/** Prepares the data to be returned, mutably coercing values to avoid NaNs
 *  and returning the final domain over all distributions. */
function prepareData(distributions: DistributionData[]) {
    let maxExponent: number = 0;

    let pmfMaximum: number = 0;
    let pmfTotals: number[] = [];

    for (const { data } of distributions) {
        let maximum = 0;
        let total = 0;

        for (let i = 0; i < data.length; i++) {
            const point = data[i];
            if (Number.isNaN(point)) data[i] = 0;
            maximum = Math.max(maximum, point);
            total += point;
        }

        pmfTotals.push(total);
        pmfMaximum = Math.max(pmfMaximum, total ? maximum / total : 0);
        maxExponent = Math.max(maxExponent, maximum);
    }

    let absMaxExponent = Math.max(5, Math.ceil(Math.log10(maxExponent)));
    return { pmfTotals, pmfMaximum, absMaxExponent };
}

/** Plot the linear y axis */
function plotLinearYAxis(textG: D3Selection<SVGGElement>,
    linesG: D3Selection<SVGGElement>,
    plotWidth: number, plotHeight: number,
    scale: (x: number) => number,
) {
    const PADDING = 10;

    const text = (y: number) => {
        const value = scale(y);

        textG.append("text")
            .attr("x", 2)
            .attr("y", y)
            .attr("font-size", FONT_SIZE)
            .text((value * 100).toFixed(2) + "%");

        linesG.insert("line")
            .attr("x1", 0)
            .attr("x2", plotWidth)
            .attr("y1", y)
            .attr("y2", y)
            .attr("stroke", "#e8e8e8")
    }

    const N = Math.ceil(plotHeight / (FONT_SIZE + PADDING));
    for (let i = 0; i <= N; i++)
        text(plotHeight / N * i)
}

/** Plot the log y axis */
function plotLogYAxis(textG: D3Selection<SVGGElement>,
    linesG: D3Selection<SVGGElement>,
    plotWidth: number, height: number,
    scale: (x: number) => number,
    absMaxExponent: number,
) {
    // Place one line every 10^i
    for (let i = 0; i <= absMaxExponent; i++) {
        const y = scale(10 ** i);
        textG.insert("text")
            .attr("x", 2)
            .attr("y", y)
            .attr("font-size", FONT_SIZE)
            .text(`10^${i}`);

        linesG.insert("line")
            .attr("x1", 0)
            .attr("x2", plotWidth)
            .attr("y1", y)
            .attr("y2", y)
            .attr("stroke", "#e8e8e8")
    }
}

/**
 * Draws the text for the horizontal axis of the histogram.
 * @param g The group element to plot the histograms into, as a D3 selection.
 * @param w The width of the histogram.
 * @param metric The metric to plot the axis for.
 * @param fontSize The font size of the text.
*/
export function fillHorizontalAxis(
    g: D3Selection<SVGGElement>,
    w: number,
    metric: string,
    fontSize: number = 10,
) {
    // Get how many tacks you can fit
    const tackCount = Math.floor(w / (3 * fontSize)) - 2;

    // Insert the first and the last
    const lastVal = metric === "length" ? "40+" : "10.0";
    const firstVal = metric === "length" ? "0" : "0.0";

    g.insert("text")
        .attr("x", 1)
        .attr("font-size", fontSize)
        .attr("fill", "black")
        .attr("text-anchor", "start")
        .text(firstVal);
    g.insert("text")
        .attr("x", w - 3)
        .attr("font-size", fontSize)
        .attr("fill", "black")
        .attr("text-anchor", "end")
        .text(lastVal);

    const MARGIN = w / (tackCount + 1);
    for (let i = 0; i < tackCount; i++) {
        const x = (i + 1) * MARGIN;
        const r = x / w;

        g.insert("text")
            .attr("x", x)
            .attr("font-size", fontSize)
            .attr("fill", "black")
            .attr("text-anchor", "middle")
            .text(
                metric === "length"
                    ? Math.round(r * 40)
                    : (r * 10.0).toFixed(1),
            );
    }
}