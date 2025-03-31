<script lang="ts">
    import { select } from "d3";
    import { onMount } from "svelte";

    import {
        server,
        type BundledStatistics,
        type SteerAGInstance,
    } from "@lib/server";
    import {
        fillHorizontalAxis,
        plotHistograms,
        type HistogramScale,
    } from "@lib/histogram";
    import type { APMetric, D3Selection } from "@lib/types";

    /** Label of the histogram (usually metric name) */
    export let label: string;
    /** Metric to plot */
    export let metric: APMetric;
    /** Query instances to plot (contains the colors and ids) */
    export let queries: SteerAGInstance[];
    /**
     * Plotting scale:
     * - "lin" for linear scale (where the y axis represents the PDF
     *         of each metric, normalized to the maximum value);
     * - "log" for logarithmic scale (where the y axis represents the
     *        absolute count of paths in each bin).
     */
    export let scale: HistogramScale = "lin";

    const X_AXIS_HEIGHT = 10;
    const Y_AXIS_WIDTH = 50;

    /** SVG element. */
    let svg: SVGSVGElement;
    /** Width of the SVG element. */
    let svgWidth = 0;
    /** Height of the SVG element. */
    let svgHeight = 0;

    /** The histogram group. */
    let histogram: D3Selection<SVGGElement>;
    /** The plot overlay group. */
    let overlay: D3Selection<SVGGElement>;

    /** Initializes groups and things in the SVG element. */
    function initSvg(svg: SVGSVGElement) {
        if (!svg) return;
        svgWidth = svg.clientWidth;
        svgHeight = svg.clientHeight;

        // Clear the SVG
        select(svg).selectAll("*").remove();

        histogram = select(svg).insert("g").attr("class", "histogram");
        overlay = select(svg).insert("g").attr("class", "overlay");

        // Draw the title.
        select(svg)
            .insert("text")
            .text(label)
            .attr("x", svgWidth / 2)
            .attr("y", 16)
            .attr("font-size", 16)
            .attr("text-anchor", "middle");

        let tacks = select(svg)
            .insert("g")
            .attr("transform", `translate(0 ${svgHeight - 2.5})`);
        fillHorizontalAxis(
            tacks,
            svgWidth - Y_AXIS_WIDTH,
            metric,
            X_AXIS_HEIGHT,
        );

        drawHistogram(svg, $stats, scale);
    }

    let histogramResults: ReturnType<typeof plotHistograms>;
    function drawHistogram(
        svg: SVGSVGElement,
        stats: BundledStatistics,
        scale: HistogramScale,
    ) {
        if (!stats) return;
        const statData = stats.stat[metric];
        if (!statData) return;

        const dists = [{ data: statData, fill: "#00b2", stroke: "blue" }];
        for (const query of queries) {
            const fill = `rgba(${query.color}, 0.25)`;
            const stroke = `rgb(${query.color})`;
            const steerData = stats.steer[query.id]?.[metric];
            if (!steerData) continue;

            dists.push({
                data: steerData,
                fill: fill,
                stroke: stroke,
            });
        }

        histogramResults = plotHistograms({
            g: histogram,
            width: svgWidth,
            height: svgHeight - X_AXIS_HEIGHT,
            dists,
            lineChart: metric !== "impact",
            scale,
            yAxis: {
                width: Y_AXIS_WIDTH,
                position: "right",
            },
        });
    }

    // Reactive declarations
    const stats = server.statistics;

    onMount(() => {
        // Add a resize observer to the SVG
        const resizeObserver = new ResizeObserver(() => {
            initSvg(svg);
        });
        resizeObserver.observe(svg);
    });

    let hidden = true;

    interface TooltipQueryData {
        query: string;
        color: string;
        absolute: number;
        relative: number;
    }

    let tooltipData = {
        bucket: 0,
        x: 0,
        y: 0,
        values: [] as TooltipQueryData[],
    };

    function onMouseMove(evt: MouseEvent) {
        const steerData = $stats.steer;
        if (!steerData) return;

        // Get the coordinates on the plot
        let pageY = evt.pageY;
        if (pageY > window.innerHeight - svgHeight)
            pageY = window.innerHeight - svgHeight;
        let pageX = svgWidth;

        const x = evt.offsetX;
        const bucket = histogramResults.xScale.invert(x) | 0;
        if (bucket < 0 || bucket >= 100) return;
        if (bucket >= 40 && metric === "length") return;

        // Create a vertical bar
        overlay.selectAll("*").remove();
        overlay
            .append("rect")
            .attr("x", x)
            .attr("y", 0)
            .attr("width", 1)
            .attr("height", svgHeight - X_AXIS_HEIGHT)
            .attr("fill", "none")
            .attr("stroke", "#0004")
            .attr("stroke-width", 1);

        const values: TooltipQueryData[] = [];
        const stat = $stats.stat[metric][bucket];
        values.push({
            query: "Statistic",
            color: "rgb(0,0,176)",
            absolute: stat,
            relative: stat / histogramResults.pmfTotals[0],
        });

        let index = 1;
        for (const { id, name, color } of queries) {
            const data = steerData[id]?.[metric];
            if (!data) continue;

            values.push({
                query: name,
                color: `rgb(${color})`,
                absolute: data[bucket],
                relative: data[bucket] / histogramResults.pmfTotals[index++],
            });
        }

        tooltipData = {
            x: pageX,
            y: pageY,
            bucket,
            values,
        };

        hidden = false;
    }
    function onMouseLeave(evt: MouseEvent) {
        hidden = true;
        overlay.selectAll("*").remove();
    }

    $: svgWidth * svgHeight && queries && drawHistogram(svg, $stats, scale);
</script>

<!-- svelte-ignore a11y-no-static-element-interactions -->
<svg
    height="0"
    bind:this={svg}
    on:mousemove={onMouseMove}
    on:mouseleave={onMouseLeave}
/>

<div
    class="tooltip"
    class:hidden
    style:top={`${tooltipData.y}px`}
    style:right={`${tooltipData.x + 10}px`}
>
    {#if metric === "length"}
        {@const b = tooltipData.bucket}

        {#if b === 39}
            Attack paths of <b>length</b> 40 or higher
        {:else}
            Attack paths of <b>length</b> {b + 1}
        {/if}
    {:else}
        {@const b = tooltipData.bucket}
        Attack paths with <b>{metric}</b> in [{b / 10}, {(b + 1) / 10}]
    {/if}

    <table>
        <thead>
            <td>Query</td>
            <td>Path Count</td>
            <td>Relative %</td>
        </thead>
        <tbody>
            {#each tooltipData.values as { query, color, absolute, relative }}
                <tr>
                    <td>
                        <span class="square" style:background-color={color}>
                            &nbsp;
                        </span>
                        {query}
                    </td>
                    <td>{absolute}</td>
                    <td>{(relative * 100).toFixed(2)}%</td>
                </tr>
            {/each}
        </tbody>
    </table>
</div>

<style lang="scss">
    svg {
        flex: 1;

        // height: 100%;
        border: 1px solid #ccc;
        background-color: white;
    }

    .tooltip {
        position: fixed;
        background-color: white;
        border: 1px solid #ccc;
        padding: 0.5em;
        z-index: 1000;

        &.hidden {
            display: none;
        }

        .square {
            display: inline-block;
            margin-right: 0.25em;
        }

        thead {
            border-bottom: 1px solid #ccc;
            font-weight: bold;
        }
    }
</style>
