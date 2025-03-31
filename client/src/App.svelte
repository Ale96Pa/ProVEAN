<script lang="ts">
    import { onMount } from "svelte";
    import { writable, type Writable } from "svelte/store";

    import { server } from "@lib/server";

    import TopologyView from "@components/topology/TopologyView.svelte";
    import { OverviewCanvas } from "@components/topology/topology";
    import ConnectionError from "@components/ConnectionError.svelte";
    import BottomBar from "@components/bottombar/BottomBar.svelte";
    import SideBar from "@components/sidebar/SideBar.svelte";
    import AdjacencyMatrixView from "@components/topology/AdjacencyMatrixView.svelte";
    import LeftBar, {
        type LeftBarTab,
    } from "@components/leftbar/LeftBar.svelte";
    import Opener from "@components/leftbar/Opener.svelte";

    onMount(() => {
        // Start connecting once the app is mounted.
        server.connect();
    });

    // We get the stores from inside `server` to allow
    // using the `$` prefix to access the values.
    // This is a common pattern in this project.
    const isConnected = server.isConnected;
    const isBriefed = server.isBriefed;
    const isStopped = server.isStopped;

    /** Topology canvas to pass to the lower levels. */
    let topology: Writable<OverviewCanvas> = writable();

    let leftBarTab: LeftBarTab | null = null;
</script>

<main>
    {#if $isStopped}
        <ConnectionError type="waitingForBackend" />
    {:else if $isBriefed && server.model}
        <div class="app-grid" class:open={leftBarTab !== null}>
            <div class="topology-view">
                <TopologyView model={server.model} bind:canvas={$topology} />
            </div>
            <div class="sidebar">
                {#if $topology}
                    <SideBar topology={$topology} />
                {/if}
            </div>
            <div class="leftbar">
                <LeftBar bind:tab={leftBarTab} topology={$topology} />
            </div>
            <div class="bottombar">
                {#if $topology}
                    <BottomBar topology={$topology} />
                {/if}
            </div>
        </div>

        <div class="opener" class:shift={leftBarTab !== null}>
            <Opener bind:tab={leftBarTab} canvas={$topology} />
        </div>

        <AdjacencyMatrixView />
    {:else if !$isConnected}
        <ConnectionError type="connectingToBackend" />
    {:else if !$isBriefed || server.model === null}
        <ConnectionError type="waitingForBriefing" />
    {/if}
</main>

<style lang="scss">
    $sidebar-width: 400px;
    $leftbar-width: 400px;
    $bottombar-height: 300px;

    main {
        height: 100vh;
        display: grid;
        overflow: hidden;
    }

    .app-grid {
        .leftbar {
            display: none;
        }

        display: grid;
        height: 100vh;
        grid-template-columns: 0 1fr $sidebar-width;
        grid-template-rows: 1fr $bottombar-height;
        grid-template-areas: "left topology side" "left bottom side";

        &.open {
            grid-template-columns: $leftbar-width 1fr $sidebar-width;

            .leftbar {
                grid-area: left;
                display: flex;

                background: #e8e8ee;
                box-shadow: 0 0 10px 0 rgba(0, 0, 0, 0.1);
            }
        }

        .topology-view {
            grid-area: topology;
            display: flex;
        }
        .sidebar {
            grid-area: side;
            background: #eee8e8;
            display: flex;
        }
        .bottombar {
            grid-area: bottom;
            background: #e8e8e8;
            overflow: hidden;
            display: flex;
        }
    }

    .opener {
        position: absolute;
        bottom: $bottombar-height;
        left: 0;
        width: 50px;
        height: 100%;
        display: flex;

        &.shift {
            left: $leftbar-width;
        }
    }
</style>
