<script lang="ts">
    import { AP_METRICS } from "@lib/types";
    import { server, type SteerAGInstance } from "@lib/server";
    import type { HistogramScale } from "@lib/histogram";

    import MetricHistogram from "./MetricHistogram.svelte";

    const steerAGs = server.steeringQueries;

    /** Selected query ids. */
    export let ids: number[];

    /** Selected query instances. */
    let queries: SteerAGInstance[] = [];
    $: queries = ids.map((id) => $steerAGs[id]);

    /** Histogram scale */
    export let scale: HistogramScale;
</script>

<div class="histograms">
    <div class="scale-select">
        <button on:click={() => (scale = "lin")} disabled={scale === "lin"}>
            Linear / Relative Counts
        </button>
        <button on:click={() => (scale = "log")} disabled={scale === "log"}>
            Logarithmic / Absolute Counts
        </button>
    </div>

    {#each AP_METRICS as metric}
        <MetricHistogram label={metric} {metric} {queries} {scale} />
    {/each}
</div>

<style>
    .histograms {
        display: flex;
        flex-direction: column;
        width: 100%;
        height: 100%;
        background-color: #f0f0f0;
    }

    .scale-select {
        flex-shrink: 1;

        display: flex;
        justify-content: space-around;
        margin: 0.25em 0.5em;
    }

    .scale-select button {
        padding: 0.5em;
        border: 1px solid #ccc;
        border-radius: 0.5em;
        background-color: #f0f0f0;
        color: #333;
        cursor: pointer;
    }

    .scale-select button:disabled {
        color: black;
        background-color: lightblue;
    }
</style>
