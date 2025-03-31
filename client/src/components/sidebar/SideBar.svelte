<script lang="ts">
    import { server } from "@lib/server";
    import QueryHistogram from "./QueryHistogram.svelte";
    import QuerySelection from "./QuerySelection.svelte";
    import type { RGBColor } from "@lib/types";
    import type { HistogramScale } from "@lib/histogram";
    import type { OverviewCanvas } from "@components/topology/topology";

    export let topology: OverviewCanvas;

    // Writable store for the active queries
    const queries = server.steeringQueries;

    let allQueries: number[] = [];
    $: allQueries = $queries.filter((q) => q.active).map((q) => q.id);

    /**
     * Selected tab:
     * - "new" for the new query selection screen;
     * - "all" for all queries;
     * - number for a specific query.
     */
    let tab: "new" | "all" | number = "new";

    /** The color of the select*/
    let color: RGBColor;
    $: color = typeof tab !== "number" ? [255, 255, 255] : $queries[tab].color;

    /** Histogram scale (for coordinating it among tabs) */
    let scale: HistogramScale = "lin";
</script>

<div class="container">
    <select
        bind:value={tab}
        style="background: linear-gradient(to right, white, rgb({color}));"
    >
        <option value="new">Start a New Query</option>
        <option value="all">All Queries ({allQueries.length})</option>

        {#each $queries as query (query.id)}
            {#if query.active}
                <option value={query.id}>[{query.id}] {query.name}</option>
            {/if}
        {/each}
    </select>

    {#if tab === "new"}
        <QuerySelection {topology} />
    {:else if tab === "all"}
        <QueryHistogram ids={allQueries} bind:scale />
    {:else}
        <QueryHistogram ids={[tab]} bind:scale />
    {/if}
</div>

<style>
    .container {
        display: flex;
        flex-direction: column;
        width: 100%;
        background-color: #f0f0f0;
    }

    select {
        padding: 4px;
        font-size: 1em;
        background-color: #f0f0f0;
        border: none;
        border-bottom: 1px solid #ccc;
        outline: none;
    }
</style>
