<script lang="ts">
    import { onMount } from "svelte";
    import { AMOverview } from "./adjacency";

    // Clear everything!
    let svg: SVGSVGElement;

    onMount(() => {
        new AMOverview(svg);
    });
</script>

<div class="container">
    <svg bind:this={svg} />
</div>

<style>
    .container {
        position: absolute;
        top: 32px;
        left: 32px;

        max-width: 256px;
        max-height: 256px;

        overflow: auto;
        border-radius: 16px;
        box-shadow: 0 0 10px rgba(0, 0, 0, 0.5);
        transition: transform 200ms ease-out;
    }

    svg {
        aspect-ratio: 1;
    }

    .container:hover {
        transform: scale(2) translate(25%, 25%);
        background: white;
    }
</style>
