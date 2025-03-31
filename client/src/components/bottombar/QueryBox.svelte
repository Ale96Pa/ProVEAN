<script lang="ts">
    import { server } from "@lib/server";
    import type { RGBColor } from "@lib/types";

    import { OverviewCanvas } from "@components/topology/topology";
    import GenerationChart from "./GenerationChart.svelte";
    import ToggleableButton from "./ToggleableButton.svelte";
    import StmBottomBar from "./stm/StmBottomBar.svelte";
    import TopBottomBar from "./top/TopBottomBar.svelte";
    import CveBottomBar from "./cve/CveBottomBar.svelte";
    import QueryInfo from "./QueryInfo.svelte";
    import AttackPathList from "./aps/AttackPathList.svelte";

    /** The ID of this query. */
    export let id: number;
    /** The color of this query. */
    export let color: RGBColor;
    /** The name of this query. */
    export let name: string;
    /** Whether SteerAG is enabled for this query. */
    export let steering: boolean;
    /** The topology object. */
    export let topology: OverviewCanvas;

    const COLORS: RGBColor[] = [
        [231, 76, 60],
        [46, 204, 113],
        [241, 196, 15],
        [155, 89, 182],
        [128, 128, 0],
        [241, 149, 72],
        [142, 68, 173],
    ];

    // Stores
    const steerAGs = server.steeringQueries;
    const stats = server.statistics;
    const isGloballyPaused = server.paused;
    const queryShows = topology.queryShows;
    const genStats = server.generationStats[id];

    let bg: string, fg: string;
    $: {
        bg = `rgb(${color.join(",")})`;
        fg =
            color[0] * 0.299 + color[1] * 0.587 + color[2] * 0.114 > 186
                ? "black"
                : "white";
    }

    let isPaused = false;
    $: isPaused = $steerAGs[id].paused;

    type Tab = "gen" | "inf" | "stm" | "aps" | "top" | "cve";

    let tab: Tab = "gen";
    let stmLoaded = false;
    let topLoaded = false;

    /** Whether you are in color changing mode. */
    let changingColor = false;

    $: {
        if (tab === "stm" && !stmLoaded) {
            stmLoaded = true;
        }
        if (tab === "top" && !topLoaded) {
            topLoaded = true;
        }
    }

    async function changePause() {
        await server.request("set_steerag_paused", {
            id,
            paused: !isPaused,
        });

        steerAGs.update((steerAGs) => {
            steerAGs[id].paused = !isPaused;
            return steerAGs;
        });
    }

    function toggleHostView() {
        topology.setHostsView(id);
    }
    function toggleLinkView() {
        topology.setLinksView(id);
    }
    function highlightQuery() {
        topology.highlightQuery(id);
    }
    function stopQuery() {
        const ok = confirm(
            "Are you sure you want to stop this query? This cannot be undone.",
        );
        if (!ok) return;

        server.request("stop_query", id);
    }
    function renameQuery() {
        server.request("rename_query", { id, name });
    }
    function changeColor(color: RGBColor) {
        server.request("recolor_query", { id, color });
        changingColor = false;
        randomColor = newRandomColor();
    }

    let randomColor: RGBColor = newRandomColor();

    function newRandomColor(): RGBColor {
        const r = Math.floor(Math.random() * 255);
        const g = Math.floor(Math.random() * 255);
        const b = Math.floor(Math.random() * 255);

        return [r, g, b];
    }

    function selectTopHosts() {
        // Select a number of hosts with a prompt
        const num = prompt(
            "How many hosts would you like to select?",
            "5",
        ) as string;
        if (num === null) return;

        // Convert it to a number
        const n = parseInt(num);
        if (isNaN(n)) return;

        // Select the hosts
        topology.selectTopHosts(id, n);
    }
</script>

<div
    class="steerag-view"
    style="--background-color: {bg}; --foreground-color: {fg};"
>
    <div class="title-bar">
        <div class="tb-title">
            <div class="iter">
                {#if $stats?.steer[id]}
                    Iteration {$stats.steer[id].iteration}
                {:else}
                    Loading...
                {/if}
            </div>
            <div class="name">
                <input
                    type="text"
                    bind:value={name}
                    on:change={renameQuery}
                    on:keydown={(e) => {
                        if (e.key === "Enter")
                            // @ts-ignore
                            e.target.blur();
                    }}
                />
            </div>
        </div>
        <div class="tb-controls">
            <div class="tb-buttons">
                <div class="group">
                    <ToggleableButton
                        on:click={() => (changingColor = !changingColor)}
                        value={changingColor}
                        tooltip="Select a new color."
                        falseIcon="palette"
                        trueIcon="palette"
                    />
                </div>

                <div class="contents" class:hidden={changingColor}>
                    <div class="group">
                        <ToggleableButton
                            on:click={selectTopHosts}
                            value={true}
                            tooltip="Select top N hosts based on rank."
                            falseIcon="host"
                            trueIcon="host"
                        />
                    </div>
                    <div class="group">
                        <ToggleableButton
                            on:click={changePause}
                            value={!$steerAGs[id].paused}
                            disabled={$isGloballyPaused}
                            tooltip="Pause/Play generation."
                            falseIcon="play"
                            trueIcon="pause"
                        />
                    </div>

                    <div class="group">
                        <ToggleableButton
                            on:click={stopQuery}
                            value={false}
                            tooltip="Stop generation."
                            falseIcon="stop"
                            trueIcon=""
                        />
                    </div>

                    <div class="group">
                        <ToggleableButton
                            on:click={toggleHostView}
                            value={$queryShows[id]?.host}
                            tooltip="Show/Hide the host results of this query from topology view."
                            falseIcon="circle-empty"
                            trueIcon="circle-full"
                        />
                        <ToggleableButton
                            on:click={toggleLinkView}
                            value={$queryShows[id]?.link}
                            tooltip="Show/Hide the link results of this query from topology view."
                            falseIcon="link-empty"
                            trueIcon="link-full"
                        />
                        <ToggleableButton
                            on:click={highlightQuery}
                            value={false}
                            tooltip="Highlight the results of this query on the topology view."
                            falseIcon="glass"
                            trueIcon=""
                        />
                    </div>
                </div>

                <div class="colors-container" class:hidden={!changingColor}>
                    {#each COLORS as color}
                        <button
                            class="color-button"
                            style="background-color: rgb({color})"
                            on:click={() => changeColor(color)}>&nbsp</button
                        >
                    {/each}

                    <button
                        class="color-button"
                        style="background-color: rgb({randomColor})"
                        on:click={() => changeColor(randomColor)}>&nbsp</button
                    >
                </div>
            </div>

            <div class="tb-tab" class:hidden={changingColor}>
                <!-- Radio Buttons -->
                <select bind:value={tab}>
                    <option value="gen">Generation Statistics</option>
                    <option value="inf">Query Information</option>
                    <option value="stm">Source-Target Matrix</option>
                    <option value="aps">Filter Attack Paths</option>
                    <option value="top">Detailed Histograms</option>
                    <option value="cve">Top Vulnerabilities</option>
                </select>
            </div>
        </div>
    </div>

    {#if tab === "gen"}
        {#if $genStats}
            {#if $genStats.min_stability === 1 && $genStats.max_stability === 1 && $genStats.precision.at(-1) === 0}
                <div class="no-paths">
                    <div class="title">No Paths Found Yet</div>
                    <div class="description">
                        Either no paths exist or they are very unlikely (e.g.
                        too long).<br />
                        The search will still still continue.<br />
                        If you wish to stop the search, click on the stop button.
                    </div>
                </div>
            {:else}
                <GenerationChart {genStats} />
            {/if}
        {:else}
            <div class="no-paths">
                <div class="title">Loading...</div>
                <div class="description">
                    If you paused the generation, unpause it for this query to
                    continue.
                </div>
            </div>
        {/if}

        <div class="footer">
            {#if $stats?.steer[id]}
                {@const {
                    generated,
                    generatedQuery,
                    collision,
                    unique,
                    uniqueQuery,
                } = $stats.steer[id]}

                New Query Paths: {generatedQuery}
                &middot; Collisions: {(collision * 100).toFixed(2)}%
                <br />
                Total Query Paths: <b>{uniqueQuery}</b>
                ({((uniqueQuery / unique) * 100).toFixed(2)}% of total)
            {:else}
                Loading...
            {/if}
        </div>
    {:else if tab === "aps"}
        <AttackPathList {id} {topology} />
    {:else if tab === "inf"}
        <QueryInfo {id} {steering} {topology} />
    {:else if tab === "cve"}
        <CveBottomBar {id} {topology} />
    {/if}

    {#if stmLoaded}
        <div class="contents" class:hidden={tab !== "stm"}>
            <StmBottomBar {id} {topology} />
        </div>
    {/if}
    {#if topLoaded}
        <div class="contents" class:hidden={tab !== "top"}>
            <TopBottomBar {id} {topology} />
        </div>
    {/if}
</div>

<style lang="scss">
    .steerag-view {
        display: inline-grid;

        overflow: hidden;
        width: 380px;
        height: 298px;

        border-top: 2px solid #777;
        border-right: 2px solid #777;
        border-left: none;

        grid-template-rows: max-content 1fr;
    }

    .title-bar {
        background: var(--background-color);
        color: var(--foreground-color);
        padding: 4px;
        padding-top: 0;

        .tb-title {
            display: flex;
            gap: 4px;

            padding-bottom: 2px;

            .name {
                flex: 1;
                display: flex;
                input {
                    flex: 1;
                    font-size: 0.8em;
                    font-weight: bold;
                    height: 1.2em;

                    background: transparent;
                    border: 1px solid transparent;
                    color: var(--foreground-color);
                    transition:
                        background-color 0.05s ease-in-out,
                        border-color 0.05s ease-in-out;

                    &:focus {
                        background: #fffa;
                        color: black;
                        font-weight: normal;
                    }
                }
            }
            .iter {
                display: flex;
                align-items: center;
                font-size: 0.8em;
                font-weight: 400;
            }
        }
    }

    .tb-controls {
        display: flex;
        justify-content: space-between;

        .tb-buttons {
            flex: 1;
            display: flex;
            gap: 4px;

            .group {
                display: flex;
                :global(.container:first-child button) {
                    border-top-left-radius: 8px;
                    border-bottom-left-radius: 8px;
                }
                :global(.container:last-child button) {
                    border-top-right-radius: 8px;
                    border-bottom-right-radius: 8px;
                }
            }

            .colors-container {
                margin-left: 2px;
                flex: 1;
                display: flex;
                gap: 2px;
            }
        }

        .tb-tab {
            display: flex;
            select {
                flex: 1;
                background: #fffa;
                color: black;
                border: none;
                font-size: 0.8em;
                padding: 0 0.5em;
                border-radius: 8px;

                &:hover {
                    background: #fffc;
                }
            }
        }
    }

    .no-paths {
        display: flex;
        flex-direction: column;
        justify-content: center;
        align-items: center;
        gap: 4px;
        text-align: center;
        font-size: 0.8em;
        padding: 4px;

        .title {
            font-size: 1.2em;
            font-weight: bold;
        }

        .description {
            font-weight: 400;
        }
    }

    .color-button {
        flex: 1;
        color: black;
        border: none;
        font-size: 0.8em;
        padding: 0 0.5em;
        border-radius: 8px;
    }

    .footer {
        background: var(--background-color);
        color: var(--foreground-color);
        padding: 4px;
        text-align: center;
        font-size: 0.8em;
    }

    .hidden {
        display: none !important;
    }
    .contents {
        display: contents;
    }
</style>
