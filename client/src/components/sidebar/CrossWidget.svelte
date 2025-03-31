<script lang="ts">
    import { select } from "d3";

    import { onDestroy, onMount } from "svelte";
    import type { Writable } from "svelte/store";

    import type { APCondition, APMetric, D3Selection } from "@lib/types";
    import { server, type StatAGStatistics } from "@lib/server";
    import { fillHorizontalAxis, plotHistograms } from "@lib/histogram";

    /** Attack Path Metric this histogram is showing. */
    export let metric: APMetric;
    /** The selected filters. */
    export let filter: Writable<APCondition[]>;
    /** The computed joint histograms for all metrics (including this one). */
    export let histograms: Writable<Record<APMetric, number[]> | null>;

    /** The container of both the SVG and the filter selector. */
    let box: HTMLDivElement;
    /** The SVG element that will contain the histogram. */
    let svg: SVGSVGElement;
    /** The width of the SVG in px. */
    let svgWidth: number;
    /** The height of the SVG in px. */
    let svgHeight: number;

    let stats = server.statistics;

    onMount(() => {
        const { width, height } = svg.getBoundingClientRect();
        svgWidth = width;
        svgHeight = height;

        // Create a resize observer
        const observer = new ResizeObserver(() => {
            if (!svg) return;

            const { width, height } = svg.getBoundingClientRect();
            svgWidth = width;
            svgHeight = height;
        });
        observer.observe(box);
    });

    function initHistogram() {
        select(svg).selectAll("*").remove();

        select(svg)
            .insert("text")
            .text(metric)
            .attr("x", svgWidth / 2)
            .attr("y", 16)
            .attr("font-size", 16)
            .attr("text-anchor", "middle");

        let tacks = select(svg)
            .insert("g")
            .attr("transform", `translate(0 ${svgHeight - 3})`);
        fillHorizontalAxis(tacks, svgWidth, metric, 10);

        // Create the group that will be used by the histograms.
        select(svg).insert("g").attr("class", "histograms");
    }

    function drawHistograms(
        stats: StatAGStatistics | undefined,
        jointHistograms: Record<APMetric, number[]> | null,
    ) {
        if (!stats) return;

        // Get the only relevant stat.
        const relevant = stats[metric];
        const g: D3Selection<SVGGElement> = select(svg).select(".histograms");

        const data = [{ data: relevant, fill: "#00b8", stroke: "blue" }];
        if (jointHistograms) {
            data[0].fill = "#00b2";
            data.push({
                data: jointHistograms[metric],
                fill: "#00AA",
                stroke: "black",
            });
        }

        plotHistograms({
            g,
            width: svgWidth,
            height: svgHeight - 16,
            dists: data,
            lineChart: false,
        });
    }

    let selectionDiv: HTMLDivElement;
    let currentSelection: [number, number] | null = null;

    let startX: number | null = null;
    function startSelecting(event: MouseEvent) {
        const { clientX } = event;
        const { left } = box.getBoundingClientRect();
        startX = clientX - left;
    }
    function moveSelection(event: MouseEvent) {
        if (!startX) return;

        const { clientX } = event;
        const { left } = box.getBoundingClientRect();
        const x = clientX - left;

        let sel: [number, number];
        if (x < 0) {
            sel = [0, startX];
        } else if (x > svgWidth) {
            sel = [startX, svgWidth];
        } else {
            sel = [Math.min(startX, x), Math.max(startX, x)];
        }

        if (metric === "length") {
            const scale = svgWidth / 40;
            sel[0] = Math.floor(sel[0] / scale) * scale;
            sel[1] = Math.ceil(sel[1] / scale) * scale;
        } else {
            const scale = svgWidth / 100;
            sel[0] = Math.floor(sel[0] / scale) * scale;
            sel[1] = Math.ceil(sel[1] / scale) * scale;
        }

        if (sel[1] - sel[0] < 8) return;

        currentSelection = sel;
        drawSelection(...currentSelection);
    }

    function drawSelection(start: number, end: number) {
        selectionDiv.style.left = `${start}px`;
        selectionDiv.style.width = `${end - start}px`;
    }

    let selectedRange: [number, number] | null = null;
    function updateSelection() {
        startX = null;
        if (!currentSelection) return;
        const [start, end] = currentSelection;
        currentSelection = null;
        const rs = start / svgWidth;
        const re = end / svgWidth;
        const min = metric === "length" ? Math.round(rs * 40) : rs * 10;
        const max = metric === "length" ? Math.round(re * 40) : re * 10;

        selectedRange = [min, max];

        filter.update((f) => {
            const newFilter = f.filter(([m]) => m !== metric);
            newFilter.push([metric, min, max]);
            return newFilter;
        });
    }
    function removeSelection() {
        if (startX !== null) return;
        currentSelection = null;
        selectionDiv.style.width = "0";
        selectedRange = null;

        filter.update((f) => f.filter(([m]) => m !== metric));
    }

    // When the filter changes, cancel all selections
    const unsubscribe = filter.subscribe((f) => {
        // If this metric is not in the filter, remove the selection.
        if (!f.some(([m]) => m === metric)) {
            currentSelection = null;
            selectedRange = null;
            if (selectionDiv) selectionDiv.style.width = "0";
        }
    });

    onDestroy(() => {
        unsubscribe();
    });

    $: svgWidth * svgHeight && svg && initHistogram();
    $: svgWidth * svgHeight && svg && drawHistograms($stats?.stat, $histograms);
</script>

<svelte:window on:mouseup={updateSelection} on:mousemove={moveSelection} />

<div class="box" bind:this={box}>
    <svg height="10" bind:this={svg} />
    <!-- svelte-ignore a11y-no-static-element-interactions -->
    <div class="handle" on:mousedown={startSelecting}>
        <!-- svelte-ignore a11y-click-events-have-key-events -->
        <div
            class="selection"
            bind:this={selectionDiv}
            on:click|preventDefault={removeSelection}
        ></div>

        <div class="text" class:highlighted={!!selectedRange}>
            {#if selectedRange}
                {@const [a, b] = selectedRange}
                {#if metric === "length"}
                    Selected length range: {a}-{b}
                {:else}
                    Selected {metric} range: {a.toFixed(1)}-{b.toFixed(2)}
                {/if}
            {:else}
                No selected {metric} range
            {/if}
        </div>
    </div>
</div>

<style lang="scss">
    .box {
        flex: 1;
        border: 1px solid black;
        background: white;
        display: flex;
        flex-direction: column;

        svg {
            flex: 10;
        }
        .handle {
            height: 24px;
            background: grey;
            position: relative;

            .selection {
                position: absolute;
                top: 0;
                height: 24px;
                background: #00b8;
                cursor: crosshair;
                &:hover {
                    border: 1px solid black;
                }
            }

            .text {
                pointer-events: none;
                user-select: none;

                position: absolute;
                top: 2px;
                left: 0;
                width: 100%;
                display: flex;
                justify-content: center;
                align-items: center;
                color: black;

                &.highlighted {
                    color: white;
                }
            }
        }
    }
</style>
