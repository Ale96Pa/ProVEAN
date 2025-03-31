<script lang="ts">
    import IconButton from "@components/IconButton.svelte";
    import type { OverviewCanvas } from "@components/topology/topology";
    import { server } from "@lib/server";
    import { type APCondition, type AttackPath } from "@lib/types";
    import Hint from "svelte-hint";
    import ApConditionsSelect from "./ApConditionsSelect.svelte";

    export let id: number;
    export let topology: OverviewCanvas;

    let conditions: APCondition[] = [];
    let loading = false;
    let aps: AttackPath[] = [];

    function getAttackPathData(ap: AttackPath) {
        // Split by steps
        const steps = ap.trace.split("##").map((step) => step.split("#"));

        return {
            source: steps[0][0],
            target: steps[steps.length - 1][2],
        };
    }

    function copyAttackPath(ap: AttackPath) {
        navigator.clipboard.writeText(ap.trace);
    }

    function highlightAttackPath(ap: AttackPath) {
        topology.selectAttackPaths(id, [[ap.trace, 1]]);
    }

    async function launchQuery(query: APCondition[]) {
        loading = true;

        const result = await server.requestAnalysis(
            "select_attack_paths",
            id,
            query,
        );
        aps = result;

        loading = false;
    }

    function getScoreRange(score: number | null) {
        if (score === null) {
            return "unknown";
        }

        if (score > 8.9) {
            return "critical";
        }
        if (score < 3.9) {
            return "low";
        } else if (score < 7.9) {
            return "medium";
        } else {
            return "high";
        }
    }

    $: launchQuery(conditions);
</script>

<div class="container">
    <div class="query">
        <ApConditionsSelect bind:conditions />
        <small>
            {#if loading}
                Loading. This might take a few seconds...
            {:else if aps.length === 0}
                No attack paths found.
            {:else if aps.length === 100}
                Showing the first 100 attack paths.
            {:else}
                Only found {aps.length} attack paths.
            {/if}
        </small>
    </div>

    <div class="list" on:wheel|stopPropagation>
        {#each aps as ap}
            {@const { source, target } = getAttackPathData(ap)}
            <div class="ap">
                <div class="title">
                    {source} &rarr; {target} (length: {ap.length})
                </div>

                <div class="buttons">
                    <Hint text="Show attack path">
                        <IconButton
                            icon="host"
                            on:click={() => highlightAttackPath(ap)}
                        />
                    </Hint>
                    <Hint text="Copy Attack Path">
                        <IconButton
                            icon="copy"
                            on:click={() => copyAttackPath(ap)}
                        />
                    </Hint>
                </div>

                <div class="spans">
                    <Hint text="Score = {ap.score}">
                        <span class="score score_{getScoreRange(ap.score)}">
                            <b>S={ap.score.toFixed(1)}</b>
                        </span>
                    </Hint>
                    <Hint text="Likelihood = {ap.likelihood}">
                        <span
                            class="score score_{getScoreRange(ap.likelihood)}"
                        >
                            <b>L={ap.likelihood.toFixed(1)}</b>
                        </span>
                    </Hint>
                    <Hint text="Impact = {ap.impact}">
                        <span class="score score_{getScoreRange(ap.impact)}">
                            <b>I={ap.impact.toFixed(1)}</b>
                        </span>
                    </Hint>
                    <Hint text="Risk = {ap.risk}">
                        <span class="score score_{getScoreRange(ap.risk)}">
                            <b>R={ap.risk.toFixed(1)}</b>
                        </span>
                    </Hint>
                    <Hint text="Damage = {ap.damage}">
                        <span class="score score_{getScoreRange(ap.damage)}">
                            <b>D={ap.damage.toFixed(1)}</b>
                        </span>
                    </Hint>
                </div>
            </div>
        {/each}
    </div>
</div>

<style lang="scss">
    .container {
        flex: 1;
        overflow: hidden;

        display: flex;
        flex-direction: column;

        .query {
            padding: 2px;
            background: white;

            display: flex;
            flex-direction: column;
            gap: 2px;
        }

        .list {
            flex: 1;
            overflow-y: scroll;
            overflow-x: hidden;
            height: 100px;
        }
    }

    .ap {
        flex: 1;

        padding: 2px;
        border-bottom: 1px solid #333;
        display: grid;
        grid-template-rows: auto auto;
        grid-template-columns: 1fr auto;

        .title {
            font-weight: bold;
            font-size: 0.9em;
        }

        .score {
            display: inline-block;
            padding: 0.125rem 0.25rem;
            border-radius: 4px;
            font-size: 0.75em;

            &.score_low {
                background: #4caf50;
            }
            &.score_medium {
                background: #ffeb3b;
            }
            &.score_high {
                background: #ff9800;
            }
            &.score_critical {
                background: #f44336;
                color: white;
            }
        }

        .buttons {
            grid-row: 1 / -1;
            grid-column: 2;

            display: flex;
            align-items: center;
        }
    }
</style>
