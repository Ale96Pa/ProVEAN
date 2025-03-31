<script lang="ts">
    import { scaleLinear, select } from "d3";
    import { onDestroy, onMount } from "svelte";
    import type { D3Selection } from "@lib/types";

    /** The list of values to plot. */
    export let values: number[] | undefined;
    export let selectionUpdated: (source: number, target: number) => void;

    export function clearSelection() {
        selection.attr("x", 0).attr("y", 0).attr("width", 0).attr("height", 0);
    }

    const X_AXIS_HEIGHT = 10;
    const Y_AXIS_WIDTH = 30;

    /** SVG element. */
    let svg: SVGSVGElement;
    /** Width of the SVG element. */
    let svgWidth = 0;
    /** Height of the SVG element. */
    let svgHeight = 0;

    /** The tacks group. */
    let tacks: D3Selection<SVGGElement>;
    /** The histogram group. */
    let histogram: D3Selection<SVGGElement>;
    /** The selection rectangle.*/
    let selection: D3Selection<SVGRectElement>;

    /** Initializes groups and things in the SVG element. */
    function initSvg(svg: SVGSVGElement) {
        if (!svg) return;
        svgWidth = svg.clientWidth;
        svgHeight = svg.clientHeight;

        // Clear the SVG
        select(svg).selectAll("*").remove();

        tacks = select(svg).insert("g");

        histogram = select(svg)
            .insert("g")
            .attr("class", "histogram")
            .attr("transform", `translate(0 ${X_AXIS_HEIGHT})`);

        selection = select(svg)
            .insert("rect")
            .attr("fill", "none")
            .attr("stroke", "black")
            .attr("stroke-width", 1)
            .attr("pointer-events", "none");

        drawHistogram(svg, values);
    }

    function drawHistogram(svg: SVGSVGElement, values?: number[]) {
        if (!svg) return;
        if (!values) return;
        // Draw the histogram.
        histogram.selectAll("*").remove();

        // Get the minimum and maximum values
        const min = values[values.length - 1];
        const max = values[0];

        const yScale = scaleLinear()
            .domain([min, max])
            .range([0, svgHeight - 2 * X_AXIS_HEIGHT]);
        const xScale = scaleLinear()
            .domain([values.length - 1, 0])
            .range([0, svgWidth - Y_AXIS_WIDTH]);

        plotLinearYAxis(
            histogram
                .append("g")
                .attr(
                    "transform",
                    `translate(${svgWidth - Y_AXIS_WIDTH + 2.5} 0)`,
                ),
            histogram.append("g"),
            svgWidth - Y_AXIS_WIDTH,
            svgHeight,
            yScale.invert,
        );

        const points = values.map((v, i) => `${xScale(i)},${yScale(v)}`);
        points.push(`${xScale(values.length)},${yScale(max)}`);
        histogram
            .insert("polyline")
            .attr("fill", "#03b4")
            .attr("stroke", "blue")
            .attr("points", points.join(" "));
    }

    const FONT_SIZE = 10;
    function plotLinearYAxis(
        textG: D3Selection<SVGGElement>,
        linesG: D3Selection<SVGGElement>,
        plotWidth: number,
        plotHeight: number,
        scale: (x: number) => number,
    ) {
        const PADDING = 10;

        const text = (y: number) => {
            const value = scale(plotHeight - y - PADDING);

            textG
                .append("text")
                .attr("x", 2)
                .attr("y", y)
                .attr("font-size", FONT_SIZE)
                .text(value.toFixed(2));

            linesG
                .insert("line")
                .attr("x1", 0)
                .attr("x2", plotWidth)
                .attr("y1", y)
                .attr("y2", y)
                .attr("stroke", "#e8e8e8");
        };

        const N = Math.ceil(plotHeight / (FONT_SIZE + PADDING));
        for (let i = 0; i <= N; i++) {
            // If the value is discrete, round it to the nearest integer
            text((plotHeight / N) * i);
        }
    }

    let startX: number | null = null;
    function mouseDown(event: MouseEvent) {
        const x = event.clientX;
        const left = svg.getBoundingClientRect().left;
        window.addEventListener("mousemove", mouseMove);
        window.addEventListener("mouseup", mouseUp);

        startX = x - left;
    }
    function mouseMove(event: MouseEvent) {
        if (startX === null) return;

        const x = event.clientX;
        const left = svg.getBoundingClientRect().left;

        let start = Math.min(startX, x - left);
        let end = Math.max(startX, x - left);
        start = Math.max(0, Math.min(start, svgWidth - Y_AXIS_WIDTH));
        end = Math.max(0, Math.min(end, svgWidth - Y_AXIS_WIDTH));

        drawSelection(start, end);

        const WIDTH = svgWidth - Y_AXIS_WIDTH;
        const sliceStart = Math.floor(start / (WIDTH / values!.length));
        const sliceEnd = Math.ceil(end / (WIDTH / values!.length));
        selectionUpdated(sliceStart, sliceEnd);
    }
    function mouseUp() {
        startX = null;

        window.removeEventListener("mousemove", mouseMove);
        window.removeEventListener("mouseup", mouseUp);
    }

    function drawSelection(start: number, end: number) {
        selection
            .attr("x", start)
            .attr("y", X_AXIS_HEIGHT)
            .attr("width", end - start)
            .attr("height", svgHeight - 2 * X_AXIS_HEIGHT);
    }

    onMount(() => {
        // Add a resize observer to the SVG
        const resizeObserver = new ResizeObserver(() => {
            initSvg(svg);
        });
        resizeObserver.observe(svg);
    });

    onDestroy(() => {
        window.removeEventListener("mousemove", mouseMove);
        window.removeEventListener("mouseup", mouseUp);
    });

    $: svgWidth * svgHeight && drawHistogram(svg, values);
</script>

<div class="container">
    <slot></slot>

    <!-- svelte-ignore a11y-no-static-element-interactions -->
    <svg
        bind:this={svg}
        on:mousedown={mouseDown}
        on:mousemove={mouseMove}
        on:mouseup={mouseUp}
    />
</div>

<style>
    .container {
        flex: 1;
        display: flex;
    }

    svg {
        flex: 1;
        border: 1px solid #ccc;
        background-color: white;
        user-select: none;
    }
</style>
