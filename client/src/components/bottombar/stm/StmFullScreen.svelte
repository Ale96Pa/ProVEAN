<script lang="ts">
    import {
        Filter,
        Metric,
        Sorting,
        SourceTargetMatrix,
        type MatrixSelection,
    } from "./stm";
    import { fade } from "svelte/transition";
    import MetricSelect from "./MetricSelect.svelte";
    import MatrixCanvas from "./MatrixCanvas.svelte";

    export let stm: SourceTargetMatrix;
    export let close: () => void;

    let metric: Metric = stm.metric;
    let filter: Filter = stm.filter;
    let filterAmount: number = stm.filterAmount;
    let sorting: Sorting = stm.sorting;

    $: stm && (stm.metric = metric);
    $: stm && stm.setFilter(filter, filterAmount);
    $: stm && (stm.sorting = sorting);

    function selectAndClose() {
        if (stm.selection !== null) stm.selectHosts();
        close();
    }

    let invisible = false;
    let selectionInfo: MatrixSelection | null = null;
</script>

<!-- svelte-ignore a11y-no-static-element-interactions -->
<div
    class="fullscreen"
    in:fade={{ duration: 75 }}
    class:invisible
    on:mouseup={() => (invisible = false)}
>
    <!-- svelte-ignore a11y-no-static-element-interactions -->
    <div class="actions">
        <div class="action">
            <div class="title">Choose Metric</div>
            <div class="content full-size-select">
                Select which data to show in the matrix.
                <MetricSelect bind:metric description />
            </div>
        </div>
        <div class="action">
            <div class="title">Filter</div>
            <div class="content">
                <div>Choose the filter to apply to the matrix.</div>

                <select bind:value={filter}>
                    <option value={Filter.None}>Do not apply any filter</option>
                    <option value={Filter.Cols}>Filter Columns</option>
                    <option value={Filter.Rows}>Filter Rows</option>
                    <option value={Filter.Both}>
                        Filter Both Rows and Columns
                    </option>
                </select>
                {#if filter}
                    for top
                    <input
                        type="range"
                        bind:value={filterAmount}
                        min={0}
                        max={0.99}
                        step={0.01}
                    />
                    {(filterAmount * 100) | 0}%.
                {/if}
            </div>
        </div>
        <div class="action">
            <div class="title">Sort</div>
            <div class="content">
                <div>Choose how to sort the displayed matrix.</div>
                <select bind:value={sorting}>
                    <option value={Sorting.None}>Do not sort</option>
                    <option value={Sorting.PCA}>
                        Principal Component Analysis (PCA) Sorting
                    </option>
                    <option value={Sorting.Rows}>Sort by Rows</option>
                    <option value={Sorting.Cols}>Sort by Columns</option>
                    <option value={Sorting.RowsAndCols}>
                        Sort by Rows and Columns
                    </option>
                </select>
            </div>
        </div>

        <!-- svelte-ignore a11y-click-events-have-key-events -->
        <div
            class="action button"
            on:click={() => (
                (stm.selection = null),
                stm.updateStore.set({}),
                (selectionInfo = null)
            )}
        >
            <div class="title">Clear Selection</div>
        </div>
        <!-- svelte-ignore a11y-click-events-have-key-events -->
        <div
            class="action button"
            on:mousedown={() => (invisible = true) && stm.selectHosts()}
            on:mouseup={() => (invisible = false)}
        >
            <div class="title">Peek</div>
            <div class="content">
                <small>
                    Click and hold this button to highlight the hosts in the
                    selection on the topology view and temporarily disable this
                    overlay.
                </small>
            </div>
        </div>
        <!-- svelte-ignore a11y-click-events-have-key-events -->
        <div class="action button" on:click={selectAndClose}>
            <div class="title">Select and Close</div>
            <div class="content">
                <small>
                    Click this button to highlight the selected hosts (if any)
                    and close this overlay.
                </small>
            </div>
        </div>

        <div class="info">
            {#if selectionInfo === null}
                No selection
            {:else}
                {@const info = stm.computeSelectionSummary(selectionInfo)}

                Selected {info.sources} sources and {info.targets} targets<br />
                <b>Query</b>: selected {info.selSteer} out of {info.totalSteer} attack
                paths ({((info.selSteer / info.totalSteer) * 100).toFixed(
                    2,
                )}%)<br />
                <b>StatAG</b>: selected
                {info.selStat} out of {info.totalStat} attack paths ({(
                    (info.selStat / info.totalStat) *
                    100
                ).toFixed(2)}%)<br />
            {/if}
        </div>
    </div>

    <div class="canvas-container">
        Source-Target Count Matrix<br />
        <MatrixCanvas {stm} bind:selectionInfo />
    </div>

    <button class="close" on:click={close}>Close</button>
</div>

<style lang="scss">
    .fullscreen {
        position: fixed;
        top: 0;
        left: 0;
        width: 100%;
        height: 100%;
        background: rgba(0, 0, 0, 0.75);
        color: white;
        z-index: 1000;

        display: grid;
        place-items: center;

        grid-template-columns: 1fr 1fr;
        grid-template-rows: 1fr;
        gap: 10px;

        transition: opacity 0.2s;

        &.invisible {
            opacity: 0;
        }

        .close {
            position: absolute;
            top: 10px;
            right: 10px;
            padding: 5px;
            border-radius: 5px;
            cursor: pointer;
        }

        .actions {
            width: 80%;

            display: flex;
            flex-direction: column;
            gap: 10px;

            .action {
                background: #fff3;
                border-radius: 16px;
                padding: 10px;

                &.button {
                    background: #fffb;
                    color: #000;
                    cursor: pointer;
                }

                .title {
                    font-size: 1.25em;
                    font-weight: 400;
                }
                .content {
                    font-size: 1em;

                    :global(select),
                    :global(input) {
                        font-size: 1rem;
                        padding: 5px;
                        border-radius: 5px;
                    }

                    input[type="range"] {
                        height: 0px;
                    }

                    &.full-size-select :global(select) {
                        width: 100%;
                        padding: 5px;
                        border-radius: 5px;
                    }
                }
            }
        }

        .canvas-container {
            padding: 20px;
            :global(canvas) {
                width: min(50vw, 800px);
                aspect-ratio: 1;
                image-rendering: pixelated;
            }
        }

        .info {
            bottom: 10px;
            right: 10px;
            background: rgba(0, 0, 0, 0.5);
            padding: 5px;
            font-size: 1.5em;
        }
    }
</style>
