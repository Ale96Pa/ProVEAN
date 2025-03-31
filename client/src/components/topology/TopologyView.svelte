<script lang="ts">
    import { onDestroy, onMount } from "svelte";

    import type { AttackGraphModel } from "@lib/types";
    import { type HoveredHost, OverviewCanvas } from "./topology";
    import { writable } from "svelte/store";

    export let model: AttackGraphModel;
    export let canvas: OverviewCanvas;
    let svg: SVGSVGElement;

    let selection = writable<number[] | null>(null);
    let attackPathsView = writable(false);
    let hoveredHost = writable<HoveredHost | null>(null);

    onMount(() => {
        canvas = new OverviewCanvas(svg, model);
        selection = canvas.selection;
        attackPathsView = canvas.attackPathsView;
        hoveredHost = canvas.hoveredHost;
    });

    function computeLegendData(selection: number[] | null) {
        const all = selection?.length ?? 0;
        const specific = canvas.selectedHosts;

        const source = specific.sourceHosts.size;
        const target = specific.targetHosts.size;
        const sourceAndTarget = specific.sourceHosts.intersection(
            specific.targetHosts,
        ).size;
        const justSelected = all - source - target + sourceAndTarget;

        return {
            source: source - sourceAndTarget,
            target: target - sourceAndTarget,
            sourceAndTarget,
            justSelected,
        };
    }

    function hideAttackPaths() {
        attackPathsView.set(false);
        canvas.linksRatiosOrLines = "ratios";
    }

    onDestroy(() => {
        canvas.destroy();
    });
</script>

<div class="container">
    <svg bind:this={svg} class:selection={$selection !== null} />

    {#if $attackPathsView}
        <div class="attack-paths">
            <button on:click={hideAttackPaths}>
                Click to hide attack paths
            </button>
        </div>
    {/if}

    {#if $selection?.length}
        {@const { justSelected, source, target, sourceAndTarget } =
            computeLegendData($selection)}

        <div class="legend">
            Legend
            {#if justSelected}
                <div class="legend-item">
                    <div
                        class="legend-circle"
                        style="background-color: #12af12;"
                    ></div>
                    <div class="legend-text">Selected ({justSelected})</div>
                </div>
            {/if}
            {#if source}
                <div class="legend-item">
                    <div
                        class="legend-circle"
                        style="background-color: #1101ff;"
                    ></div>
                    <div class="legend-text">Source ({source})</div>
                </div>
            {/if}
            {#if target}
                <div class="legend-item">
                    <div
                        class="legend-circle"
                        style="background-color: #ff0111;"
                    ></div>
                    <div class="legend-text">Target ({target})</div>
                </div>
            {/if}
            {#if sourceAndTarget}
                <div class="legend-item">
                    <div
                        class="legend-circle"
                        style="background-color: #ff01ff;"
                    ></div>
                    <div class="legend-text">
                        Source & Target ({sourceAndTarget})
                    </div>
                </div>
            {/if}

            <div class="legend-item">
                <small>
                    Drag with middle mouse button<br /> to drag hosts around.
                </small>
            </div>
        </div>
    {/if}

    {#if $hoveredHost}
        {@const { x, y, ...host } = $hoveredHost}

        <div class="tooltip" style="top: {y}px; left: {x + 32}px">
            {#if host.selected}
                <i>
                    Selected. Click on the
                    <img src="icons/host.svg" alt="hosts" />
                    icon to view details
                </i>
                <br />
            {/if}
            <b>Host Name</b>: {host.name}
            <br />
            <b>IP Address</b>: {host.ip}

            <table>
                <thead>
                    <th>Query</th>
                    <th>Path Count</th>
                    <th>Relative %</th>
                    <th>Rank</th>
                </thead>
                <tbody>
                    {#each host.queries as { name, color, count, ratio, rank }}
                        <tr
                            style="background-color: rgba({color.join(
                                ',',
                            )},0.1)"
                        >
                            <td>
                                <span
                                    class="square"
                                    style:background-color="rgb({color.join(
                                        ',',
                                    )}">&nbsp;</span
                                >
                                {name}
                            </td>
                            <td>{count}</td>
                            <td>{(ratio * 100).toFixed(2)}</td>
                            <td>{rank ?? "N/A"}</td>
                        </tr>
                    {/each}
                </tbody>
            </table>
        </div>
    {/if}
</div>

<style lang="scss">
    .container {
        position: relative;
        display: flex;
        flex: 1;

        grid-template-columns: 1fr;
        grid-template-rows: 1fr;

        user-select: none;
    }
    svg {
        flex: 1;

        &.selection {
            :global(g.host[selected="false"] circle.host-circle) {
                transition: fill 0.5s;
                fill: white;
            }
            :global(g.host[selected="false"] text) {
                fill: black;
            }
            :global(.halo) {
                opacity: 0.5;
            }
        }

        :global(g.host[selected="true"]) {
            --host-color: #12af12;
            --text-color: white;
        }
        :global(g.host[selected="s"]) {
            --host-color: #1101ff;
            --text-color: white;
        }
        :global(g.host[selected="t"]) {
            --host-color: #ff0111;
            --text-color: white;
        }
        :global(g.host[selected="st"]) {
            --host-color: #ff01ff;
            --text-color: black;
        }

        :global(g.host:not([selected="false"])) {
            :global(circle.host-circle) {
                animation: animate-stroke 1s ease-in-out;
                stroke-width: 24;
                stroke: var(--host-color);
                fill: var(--host-color);
            }

            :global(text) {
                fill: var(--text-color);
            }
        }

        // Hide halos.
        :global(g.hosts.hideHalos .halo) {
            display: none;
        }
    }

    @keyframes animate-stroke {
        0%,
        50% {
            stroke-width: 8;
        }
        25%,
        100% {
            stroke-width: 24;
        }
    }

    .legend {
        position: absolute;
        top: 0;
        left: 0;
        display: flex;
        flex-direction: column;
        padding: 0.5rem;
        background-color: rgba(255, 255, 255, 0.5);
        border-radius: 0.5rem;
        margin: 0.5rem;

        .legend-item {
            display: flex;
            align-items: center;
        }
        .legend-circle {
            width: 1rem;
            height: 1rem;
            border-radius: 50%;
            margin-right: 0.5rem;
        }
    }

    .attack-paths {
        position: absolute;
        top: 0;
        right: 1em;
        display: flex;
        flex-direction: column;
        border-radius: 0.5rem;

        button {
            all: unset;
            cursor: pointer;
            margin: 0.5rem 0;

            border-radius: 0.5rem;
            padding: 0.5rem;
            background-color: #fff;
            box-shadow: 0 0 0.5rem rgba(0, 0, 0, 0.1);
            transition: box-shadow 0.2s ease-in-out;
        }
    }

    .tooltip {
        user-select: none;
        pointer-events: none;

        position: fixed;
        z-index: 1000;
        padding: 0.5rem;
        background-color: rgba(255, 255, 255, 0.875);
        border-radius: 0.5rem;

        i {
            line-height: 32px;
            img {
                height: 12px;
            }
        }

        .square {
            display: inline-block;
            margin-right: 0.25em;
        }
    }
</style>
