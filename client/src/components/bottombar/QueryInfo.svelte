<script lang="ts">
    import IconButton from "@components/IconButton.svelte";
    import type { OverviewCanvas } from "@components/topology/topology";
    import { server } from "@lib/server";

    const steerAGs = server.steeringQueries;

    export let id: number;
    export let steering: boolean;
    export let topology: OverviewCanvas;

    const METRICS = [
        ["Likelihood", "likelihood_range"],
        ["Impact", "impact_range"],
        ["Risk", "risk_range"],
        ["Score", "score_range"],
    ] as const;

    function highlightHosts(sources?: number[], targets?: number[]) {
        if (!sources && !targets) return;

        if (!sources) sources = [];
        if (!targets) targets = [];
        topology.selectHosts({
            sources,
            targets,
        });
    }

    function hostsText(sources?: number[], targets?: number[]) {
        if (!sources) sources = [];
        if (!targets) targets = [];

        let sourceText =
            sources.length === 1
                ? `host ${sources[0]}`
                : `${sources.length} source hosts`;
        let targetText =
            targets.length === 1
                ? `host ${targets[0]}`
                : `${targets.length} target hosts`;

        if (sources.length > 0 && targets.length > 0) {
            return `${sourceText} \u2192 ${targetText}`;
        } else if (targets.length > 0) {
            return `Any host \u2192 ${targetText}`;
        } else if (sources.length > 0) {
            return `${sourceText} \u2192 Any host`;
        }
    }
</script>

<div class="container">
    {#if $steerAGs && $steerAGs[id]}
        {@const q = $steerAGs[id].query}

        {#if q.sources || q.targets}
            <div class="hosts">
                {hostsText(q.sources, q.targets)}
                <IconButton
                    icon="host"
                    on:click={() => highlightHosts(q.sources, q.targets)}
                >
                    Highlight
                </IconButton>
            </div>
        {:else}
            <div class="hosts">Any host &rarr; Any host</div>
        {/if}

        <table>
            <thead>
                <th>Metric</th>
                <th>Range Start</th>
                <th>Range End</th>
            </thead>
            <tbody>
                {#each METRICS as [metricName, rangeName]}
                    {#if q[rangeName]}
                        {@const [min, max] = q[rangeName]}
                        <tr>
                            <td>{metricName}</td>
                            <td>{min.toFixed(2)}</td>
                            <td>{max.toFixed(2)}</td>
                        </tr>
                    {/if}
                {/each}

                {#if q.length_range}
                    {@const [min, max] = q.length_range}
                    <tr>
                        <td>Length</td>
                        {#if min !== max}
                            <td>{min}</td>
                            <td>{max}</td>
                        {:else}
                            <td colspan="2">Only {min}</td>
                        {/if}
                    </tr>
                {/if}
            </tbody>
        </table>

        <div style="text-align:center">
            {#if steering}
                Accelerating with <b>SteerAG</b>.
            {:else}
                Simple filter on StatAG.
            {/if}
        </div>
    {:else}
        Loading...
    {/if}
</div>

<style lang="scss">
    .container {
        font: 1px;
        display: flex;
        flex-direction: column;

        .hosts {
            background: #f0f0f0;
            height: 36px;
            color: black;
            display: flex;
            flex-direction: row;
            align-items: center;
            justify-content: center;
            gap: 4px;
        }
    }
</style>
