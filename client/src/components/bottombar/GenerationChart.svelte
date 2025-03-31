<script lang="ts">
    import { onMount } from "svelte";
    import type { Writable } from "svelte/store";
    import { line, scaleLinear, select } from "d3";

    import { type QueryGenerationStatistics } from "@lib/server";

    // Get the generation statistics
    export let genStats: Writable<QueryGenerationStatistics>;

    let svg: SVGSVGElement;
    let svgWidth: number;
    let svgHeight: number;

    onMount(() => {
        // Create a resize observer to resize the chart
        const resizeObserver = new ResizeObserver(() => {
            initChart(svg);
        });
        resizeObserver.observe(svg);
    });

    const MARGIN = 4;
    const STABILITY_COLOR = "orange";
    const PRECISION_COLOR = "steelblue";

    function initChart(svg: SVGSVGElement) {
        if (!svg) return;

        select(svg).selectAll("*").remove();
        svgWidth = svg.clientWidth;
        svgHeight = svg.clientHeight;

        // Background rectangle
        select(svg)
            .insert("rect")
            .attr("width", svgWidth)
            .attr("height", svgHeight)
            .attr("fill", "white");

        // Groups for the two charts
        const precisionG = select(svg).insert("g").attr("class", "precision");
        select(svg)
            .insert("g")
            .attr("class", "stability")
            .attr("transform", `translate(0, ${svgHeight / 2})`);

        // Insert a title for the two charts
        select(svg)
            .insert("text")
            .attr("x", svgWidth / 2)
            .attr("y", 16)
            .attr("text-anchor", "middle")
            .attr("font-size", 16)
            .attr("fill", PRECISION_COLOR)
            .text("Precision");

        select(svg)
            .insert("text")
            .attr("x", svgWidth / 2)
            .attr("y", svgHeight - 8)
            .attr("text-anchor", "middle")
            .attr("font-size", 16)
            .attr("fill", STABILITY_COLOR)
            .text("Stability");

        // Draw a line separating the two graphs
        const y = svgHeight / 2;
        select(svg)
            .insert("line")
            .attr("x1", 0)
            .attr("y1", y)
            .attr("x2", svgWidth)
            .attr("y2", y)
            .attr("stroke", "gray")
            .attr("stroke-width", 1);

        drawChart(svg, "precision", $genStats);
        drawChart(svg, "stability", $genStats);
    }

    function drawChart(
        svg: SVGSVGElement,
        name: "precision" | "stability",
        data: QueryGenerationStatistics | null,
    ) {
        if (!data) return;

        const ifp = name === "precision";
        let stats = data?.[name];
        if (!stats) return;
        if (!ifp) stats = stats.filter((s) => s !== null);

        const g = select(svg).select<SVGGElement>(`g.${name}`);

        // Clear the group
        g.selectAll("*").remove();

        // Draw the chart
        const width = svgWidth;
        const height = svgHeight / 2;
        const margin = {
            top: Number(!ifp) * MARGIN,
            right: 40,
            bottom: Number(ifp) * MARGIN,
            left: 0,
        };

        const x = scaleLinear()
            .domain([0, stats.length - 1])
            .range([margin.left, width - margin.right]);

        const y = scaleLinear()
            .domain(
                ifp
                    ? [0, 1]
                    : [data.min_stability! ?? 0, data.max_stability! ?? 1],
            )
            .range([height - margin.bottom, margin.top]); // Inverted

        const l = line<number>()
            .x((_, i) => x(i))
            .y((d) => y(d));

        const color = ifp ? PRECISION_COLOR : STABILITY_COLOR;

        g.insert("path")
            .datum(stats)
            .attr("fill", "none")
            .attr("stroke", color)
            .attr("stroke-width", 1.5)
            // @ts-ignore
            .attr("d", l);

        // Draw the value at the right end of the chart
        const value = stats[stats.length - 1]! ?? 0;
        const yValue = y(value);
        const xValue = x(stats.length - 1);

        g.insert("text")
            .attr("x", xValue + 2)
            .attr("y", Math.max(yValue, 8))
            .attr("dy", 2)
            .attr("font-size", 12)
            .attr("fill", color)
            .text(ifp ? (value * 100).toFixed(1) + "%" : value.toFixed(4));
    }

    $: svg && drawChart(svg, "precision", $genStats);
    $: svg && drawChart(svg, "stability", $genStats);
</script>

<svg bind:this={svg}></svg>

<style>
    svg {
        width: 100%;
        height: 100%;
    }
</style>
