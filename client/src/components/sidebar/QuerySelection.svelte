<script lang="ts">
    import { writable, type Writable } from "svelte/store";

    import { server } from "@lib/server";
    import { AP_METRICS, type APCondition, type APMetric } from "@lib/types";

    import CrossWidget from "./CrossWidget.svelte";
    import type { OverviewCanvas } from "@components/topology/topology";
    import SelectHosts from "./SelectHosts.svelte";

    export let topology: OverviewCanvas;

    /** The currently selected filter for the next query. */
    let filter: Writable<APCondition[]> = writable([]);
    /** The data for the histograms for each metric, if present. */
    let histograms: Writable<Record<APMetric, number[]> | null> =
        writable(null);

    let sources: number[] | null = null;
    let targets: number[] | null = null;

    function canonicizeFilter(filter: APCondition[]): APCondition[] {
        // Remove the queries that span their entire range.
        const result = filter.filter(([type, min, max]) => {
            if (type === "length" && min === 0 && max === 40) return false;
            if (type !== "length" && min === 0.0 && max === 10.0) return false;
            return true;
        });

        // Sort the result by the metric name.
        result.sort(([a], [b]) => a.localeCompare(b));

        return result;
    }

    function filtersEqual(a: APCondition[], b: APCondition[]): boolean {
        if (a.length !== b.length) return false;
        for (let i = 0; i < a.length; i++) {
            if (a[i][0] !== b[i][0]) return false;
            if (a[i][1] !== b[i][1]) return false;
            if (a[i][2] !== b[i][2]) return false;
        }
        return true;
    }

    /** Ask the server to compute the joint distributions. */
    async function computeJointHistograms(
        filter: APCondition[],
        sources: number[] | null,
        targets: number[] | null,
    ) {
        // Remove the queries that span their entire range.
        filter = canonicizeFilter(filter);

        if (filter.length === 0 && sources === null && targets === null) {
            $histograms = null;
            return;
        }

        const data = await server.request("compute_joint_histograms", {
            metrics: filter,
            sources,
            targets,
        });

        // If the filter stayed the same
        if (filtersEqual(canonicizeFilter($filter), filter)) {
            $histograms = data;
        }
    }

    let queryName: string = "New query";
    let enableSteering: boolean = true;
    /** Launch a new query. */
    async function launchQuery() {
        const query = $filter;
        if (query.length === 0 && sources === null && targets === null) return;

        server.request("start_new_query", {
            name: queryName,
            enableSteering,
            query,
            sources,
            targets,
        });

        $filter = [];
        queryName = "Query Name";
        sources = null;
        targets = null;
    }

    $: computeJointHistograms($filter, sources, targets);
</script>

<div class="container">
    <div class="start">
        <input
            type="text"
            placeholder="Insert Query Name"
            bind:value={queryName}
        />
        <button on:click={launchQuery}>Launch Query</button>
    </div>

    <div class="hosts">
        <SelectHosts {topology} name="source" bind:selected={sources} />
        <SelectHosts {topology} name="target" bind:selected={targets} />
    </div>

    <div class="widgets">
        {#each AP_METRICS as metric}
            {#if metric !== "damage"}
                <CrossWidget {metric} {filter} {histograms} />
            {/if}
        {/each}
    </div>

    <div class="steering">
        <label for="steering">Enable Steering for query</label>
        <input
            type="checkbox"
            name="steering"
            bind:checked={enableSteering}
            id="steering"
        />
    </div>
</div>

<style lang="scss">
    .container {
        flex: 1;
        display: flex;
        flex-direction: column;
        padding-top: 4px;
        gap: 2px;

        user-select: none;
        -webkit-user-select: none;
    }

    .start {
        display: flex;
        gap: 4px;
        font-size: 0.8em;

        input {
            flex: 1;
            padding: 4px;
        }
        button {
            padding: 4px;
            background-color: #f0f0f0;
            border: 1px solid #ccc;
            cursor: pointer;
        }
    }

    .hosts {
        display: flex;
    }

    .widgets {
        flex: 1;
        display: flex;
        flex-direction: column;
        gap: 4px;
        padding-bottom: 4px;
        padding-right: 4px;
    }

    .steering {
        // Style a label and checkbox combo to look decent.
        display: flex;
        align-items: center;
        justify-content: center;
        gap: 4px;
        font-size: 1em;
    }
</style>
