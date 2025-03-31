<script lang="ts">
    import type { OverviewCanvas } from "@components/topology/topology";
    import { server, type AttackPathHistogramOutput } from "@lib/server";
    import { AP_METRICS, type APCondition, type APMetric } from "@lib/types";
    import { onMount, tick } from "svelte";
    import Histogram from "./Histogram.svelte";
    import Hint from "svelte-hint";
    import IconButton from "@components/IconButton.svelte";
    import ApConditionsSelect from "../aps/ApConditionsSelect.svelte";

    export let id: number;
    export let topology: OverviewCanvas;

    let conditions: APCondition[] = [];
    let metric: APMetric = "risk";
    let redraw: (v?: number[]) => void;
    let histogram: Histogram;

    let loading = false;
    let data: AttackPathHistogramOutput | null = null;

    async function loadData(query: APCondition[], sort: APMetric) {
        loading = true;
        data = await server.requestAnalysis("attack_path_histogram", id, {
            sort,
            query,
        });
        loading = false;

        if (data.paths.length === 0) return;

        await tick();
        // Make sure the redraw function exists;
        if (!redraw) return;
    }

    let lastSelection: [number, number] | null = null;
    function selectionUpdated(source: number, target: number) {
        if (!data) return;
        const sourceAndTarget = data.paths.slice(source, target);
        topology.selectAttackPaths(id, sourceAndTarget);
        lastSelection = [source, target];
    }

    function highlightSelection() {
        if (!lastSelection || !data) return;
        const [source, target] = lastSelection;
        const sourceAndTarget = data.paths.slice(source, target);
        topology.selectAttackPaths(id, sourceAndTarget);
    }

    function clearAndDeselectSelection() {
        histogram.clearSelection();
        topology.attackPathsView.set(false);
        topology.linksRatiosOrLines = "ratios";
        lastSelection = null;
    }

    $: loadData(conditions, metric);
</script>

<div class="top">
    <div class="header">
        <div class="left">
            <div class="queries">
                <ApConditionsSelect bind:conditions />
            </div>

            Top
            {#if data}
                {data?.paths.length}
            {/if}
            highest
            <select bind:value={metric}>
                {#each AP_METRICS as m}
                    <option value={m}>{m}</option>
                {/each}
            </select>
            attack paths.
        </div>

        <div class="right">
            <button on:click={() => loadData(conditions, metric)}
                >Refresh</button
            >
        </div>
    </div>
    <div class="container">
        {#if loading}
            Loading...
        {:else if !data?.paths?.length}
            No paths found. Change the conditions if they conflict with the
            query definition.
        {:else}
            <Histogram
                bind:this={histogram}
                values={data?.paths.map(([_, value]) => value)}
                {selectionUpdated}
            >
                <div class="commands">
                    <Hint text="Clear selection.">
                        <IconButton
                            icon="close"
                            on:click={clearAndDeselectSelection}
                        />
                    </Hint>
                    <Hint text="Highlight selection again.">
                        <IconButton
                            icon="highlight"
                            on:click={highlightSelection}
                        />
                    </Hint>
                </div>
            </Histogram>
        {/if}
    </div>
</div>

<style lang="scss">
    .top {
        display: flex;
        flex-direction: column;
    }

    .header {
        display: flex;
        justify-content: space-between;
        align-items: center;

        padding: 2px 8px;
        background-color: #fff;
        font-size: 0.8em;

        select,
        button {
            all: unset;
            font-size: 1.15em;
            cursor: pointer;
            border-bottom: 1px solid black;
            user-select: none;

            &:hover {
                color: #f00;
                border-bottom: 1px solid #f00;
            }
        }
    }

    .commands {
        display: flex;
        gap: 4px;
        flex-direction: column;

        :global(.icon-button-text) {
            display: none;
        }
    }

    .container {
        flex: 1;
        display: flex;
        flex-direction: column;
        gap: 4px;
        overflow-y: auto;
    }
</style>
