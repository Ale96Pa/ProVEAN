<script lang="ts">
    import { server } from "@lib/server";
    import { onDestroy, onMount } from "svelte";

    import { Filter, Sorting, SourceTargetMatrix } from "./stm";
    import StmFullScreen from "./StmFullScreen.svelte";
    import type { OverviewCanvas } from "@components/topology/topology";
    import MatrixCanvas from "./MatrixCanvas.svelte";
    import IconButton from "@components/IconButton.svelte";
    import Hint from "svelte-hint";
    import { get } from "svelte/store";

    export let id: number;
    export let topology: OverviewCanvas;

    let stm: SourceTargetMatrix;
    let lastIteration: number = 0;

    async function loadMatrices(first: boolean) {
        const steerData = await server.requestAnalysis(
            "attack_source_target_matrix",
            id,
        );
        const statData = await server.request("get_statag_stm");

        // The first time you load, create the class too.
        if (first) {
            stm = new SourceTargetMatrix(
                topology,
                statData.counts,
                steerData.counts,
            );
            lastIteration = steerData.iteration;
        }
        stm.update(statData.counts, steerData.counts);
        lastIteration = steerData.iteration;
    }

    let windowOpen: boolean = false;

    function openWindow() {
        if (windowOpen) return;
        windowOpen = true;
        window.addEventListener("keydown", closeWindow);
    }
    function closeWindow(event: KeyboardEvent | null) {
        if (event && event.key !== "Escape") return;

        windowOpen = false;
        window.removeEventListener("keydown", closeWindow);
        stm.updateStore.set({});
    }

    let updateStore: SourceTargetMatrix["updateStore"];

    function getMessage(_: any) {
        if (!stm) return "Loading...";

        // Applied filtering
        const filters = stm.filter !== Filter.None;
        const sortings = stm.sorting !== Sorting.None;

        if (filters && sortings) {
            return "Applied filtering and sorting";
        } else if (filters) {
            return "Applied filtering";
        } else if (sortings) {
            return "Applied sorting";
        } else {
            return "No filters or sorting applied";
        }
    }
    function hasFilters(_: any) {
        if (!stm) return false;

        // Applied filtering
        const filters = stm.filter !== Filter.None;
        const sortings = stm.sorting !== Sorting.None;

        return filters || sortings;
    }
    function clearFilters() {
        if (!stm) return;

        stm.setFilter(Filter.None, 0.5);
        stm.sorting = Sorting.None;
        stm.updateStore.set({});
    }

    function clearSelection() {
        stm.selection = null;
        stm.updateStore.set({});
    }
    function highlightSelection() {
        if (!stm.selection) return;
        stm.selectHosts();
    }

    let refreshInterval = setInterval(() => {
        if (!stm) return;
        if (windowOpen) return;

        // Get the current query iteration.
        const query = get(server.statistics)?.steer[id];
        if (!query) return;

        if (query.iteration >= lastIteration + 10) {
            loadMatrices(false);
        }
    }, 5000);

    onMount(async () => {
        await loadMatrices(true);
        updateStore = stm.updateStore;
    });
    onDestroy(() => {
        closeWindow(null);
        clearInterval(refreshInterval);
    });
</script>

<div class="container">
    <div class="toolbar">
        <b>Data</b>
        <div>
            Last: iteration {lastIteration}<br />
            <Hint text="Recompute attack path count data.">
                <IconButton icon="reload" on:click={() => loadMatrices(false)}>
                    Refresh
                </IconButton>
            </Hint>
        </div>
        <Hint text={getMessage($updateStore)}>
            <IconButton
                icon="glass"
                on:click={openWindow}
                active={hasFilters($updateStore)}
            >
                Zoom and Filter
            </IconButton>
        </Hint>
        {#if updateStore && hasFilters($updateStore)}
            <Hint text="Clear filters.">
                <IconButton icon="close" on:click={clearFilters}>
                    Remove Filters
                </IconButton>
            </Hint>
        {/if}

        <b>Selection</b>
        <IconButton icon="clear-selection" on:click={clearSelection}>
            Clear Selection
        </IconButton>
        <IconButton icon="show" on:click={highlightSelection}>
            Show Selection
        </IconButton>
    </div>

    <div class="canvas-container">
        {#if stm}
            <MatrixCanvas {stm} highlightDuringSelection />
        {/if}
    </div>
</div>

{#if windowOpen && stm}
    <StmFullScreen {stm} close={() => closeWindow(null)} />
{/if}

<style lang="scss">
    .container {
        display: grid;
        grid-template-columns: auto 1fr;
        grid-template-rows: 1fr;

        .toolbar {
            display: flex;
            flex-direction: column;
            justify-content: center;
            align-items: start;

            padding-left: 8px;
            font-size: 0.8em;
        }

        .canvas-container {
            display: flex;
            justify-content: center;
            align-items: center;

            :global(canvas) {
                height: 224px;
                aspect-ratio: 1;
                image-rendering: pixelated;
            }
        }
    }
</style>
