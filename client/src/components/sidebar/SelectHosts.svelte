<script lang="ts">
    import IconButton from "@components/IconButton.svelte";
    import type { OverviewCanvas } from "@components/topology/topology";
    import Hint from "svelte-hint";

    export let topology: OverviewCanvas;
    export let name: "source" | "target";

    export let selected: number[] | null = null;

    const selection = topology.selection;

    function remove() {
        selected = null;
    }

    function grab() {
        if ($selection === null) return;
        selected = [...$selection];
    }

    function show() {
        if (selected === null) return;
        const hosts = {
            sources: name === "source" ? selected : [],
            targets: name === "target" ? selected : [],
        };

        topology.selectHosts(hosts);
    }
</script>

<div class="select-hosts">
    <div class="selected">
        {#if selected === null}
            Any {name} host
        {:else}
            {selected.length} {name} hosts
        {/if}
    </div>

    <div class="buttons">
        {#if $selection && $selection.length > 0}
            <Hint text="Grab from selection">
                <IconButton icon="circle-add" on:click={grab} />
            </Hint>
        {/if}

        {#if selected}
            <Hint text="Remove filter">
                <IconButton icon="clear-selection" on:click={remove} />
            </Hint>
            <Hint text="Show selection">
                <IconButton icon="show" on:click={show} />
            </Hint>
        {/if}
    </div>
</div>

<style lang="scss">
    .select-hosts {
        flex: 1;

        display: flex;
        flex-direction: column;
        align-items: center;

        background: #e8e8ee;
        border-radius: 16px;
        padding: 8px;
        padding-bottom: 8px;

        font-size: 0.8em;

        :global(.icon-button) {
            margin-bottom: 0;
        }
    }
</style>
