<script lang="ts">
    import { server } from "@lib/server";

    import type { OverviewCanvas } from "@components/topology/topology";
    import OpenerIconButton from "./OpenerIconButton.svelte";
    import type { LeftBarTab } from "./LeftBar.svelte";
    import { onDestroy } from "svelte";
    import { get } from "svelte/store";

    export let tab: LeftBarTab | null;
    export let canvas: OverviewCanvas;

    const isPaused = server.paused;
    const stats = server.statistics;

    let selectedHosts: number[] | null = null;

    let selectionUnsub: () => void;
    $: ((canvas) => {
        if (!canvas) return;
        if (selectionUnsub !== undefined) selectionUnsub();
        selectionUnsub = canvas.selection.subscribe((s) => {
            if (s !== null) {
                selectedHosts = s;
            }
            if (s === null && tab === null) {
                selectedHosts = null;
            }
        });
    })(canvas);
    onDestroy(() => {
        selectionUnsub();
    });

    $: (() => {
        if (tab !== "hosts" && !get(canvas?.selection)) {
            selectedHosts = null;
            return;
        }
    })();

    /** Pause the generation of any new path. */
    async function pause() {
        // Wait until the server does that.
        await server.request("set_paused", !$isPaused);
        // Update the local store.
        server.paused.update((p) => !p);
    }

    const resetCamera = () => canvas.centerCamera();
</script>

<!-- svelte-ignore a11y-no-static-element-interactions -->
<div class="container">
    {#if selectedHosts}
        {@const l = selectedHosts.length}
        <OpenerIconButton icon="host" thisTab="hosts" bind:tab>
            {#if l === 1}
                Host Details
            {:else if l > 1}
                Hosts Details ({l})
            {/if}
        </OpenerIconButton>
    {/if}

    <OpenerIconButton icon="database" thisTab="models" bind:tab>
        Select New Model
    </OpenerIconButton>

    <OpenerIconButton icon="network" thisTab="settings" bind:tab>
        Topology View Settings
    </OpenerIconButton>
    <OpenerIconButton icon="pencil" thisTab="positions" bind:tab>
        Host Position Editing
    </OpenerIconButton>

    <OpenerIconButton icon="home" onClick={resetCamera} {tab}>
        Reset Camera
    </OpenerIconButton>
    <OpenerIconButton icon={$isPaused ? "play" : "pause"} onClick={pause} {tab}>
        {$isPaused ? "Resume Generation" : "Pause Generation"}
    </OpenerIconButton>
    <div class="iteration">
        {#if $stats && $stats?.stat}
            {@const { iteration, generated, collision, unique, stability } =
                $stats.stat}

            StatAG Statistics @ iteration <b>{iteration}</b>
            {#if $isPaused}
                (paused)
            {/if}
            <br />
            &nbsp; &nbsp; New paths: {generated}
            Collisions: {(collision * 100).toFixed(2)}%
            <br />
            &nbsp; &nbsp; Current Stability:
            {stability
                ? (stability.reduce((a, b) => a + b) / 5).toFixed(8)
                : "N / D"}
            <br />
            Total paths: <b>{unique}</b>
        {/if}
    </div>
</div>

<style lang="scss">
    .container {
        flex: 1;
        display: flex;
        flex-direction: column;
        justify-content: flex-end;
        pointer-events: none;

        padding: 8px;
    }

    .iteration {
        font-size: 0.8em;
        width: 640px;

        img {
            position: relative;
            top: 3px;
        }
    }
</style>
