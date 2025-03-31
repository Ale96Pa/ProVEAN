<script lang="ts">
    import { Metric } from "./stm";

    export let metric: Metric;
    export let description: boolean = false;

    const METRIC_DESCRIPTIONS = {
        [Metric.Absolute]:
            "The absolute count of paths starting from the source and ending at the target.",
        [Metric.AbsoluteSquare]:
            "The absolute count of paths starting from the source and ending at the target, " +
            "squared after being rescaled from 0 to 1 to emphasize higher values.",
        [Metric.Relative]:
            "The relative count of paths starting from the source and ending at the target " +
            "for this query minus the same value for the baseline query, set to zero if negative.",
        [Metric.RelativeSquare]:
            "The relative count of paths starting from the source and ending at the target " +
            "for this query minus the same value for the baseline query, set to zero if negative, " +
            "squared after being rescaled from 0 to 1 to emphasize higher values.",
    };
</script>

<select bind:value={metric}>
    <option value={Metric.Absolute}>Absolute Count</option>
    <option value={Metric.AbsoluteSquare}> Absolute Count (x²) </option>
    <option value={Metric.Relative}> StatAG-Relative</option>
    <option value={Metric.RelativeSquare}> StatAG-Relative (x²) </option>
</select>

{#if description}
    <div class="description">
        {METRIC_DESCRIPTIONS[metric]}
    </div>
{/if}

<style>
    .description {
        font-size: 0.8em;
        margin-top: 0.5em;
    }
</style>
