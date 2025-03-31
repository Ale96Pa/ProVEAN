<script lang="ts">
    import { server } from "@lib/server";
    import SteerAGView from "./QueryBox.svelte";
    import type { OverviewCanvas } from "@components/topology/topology";
    import { derived } from "svelte/store";

    const steeringQueries = server.steeringQueries;
    const activeSteeringQueries = derived(steeringQueries, ($steeringQueries) =>
        $steeringQueries.filter((q) => q.active),
    );

    /** The topology object */
    export let topology: OverviewCanvas;

    let container: HTMLDivElement | null = null;
    function scrollByPage(event: WheelEvent) {
        if (!container) return;
        event.preventDefault();

        // Get the scroll direction
        const delta = Math.sign(event.deltaY);
        const scrollAmount = container.clientHeight;

        // Scroll by a page
        container.scrollBy({
            left: delta * scrollAmount,
        });
    }
</script>

<div
    class="container"
    bind:this={container}
    class:flex={$activeSteeringQueries.length === 0}
>
    {#if $activeSteeringQueries.length > 0}
        <!-- svelte-ignore a11y-no-static-element-interactions -->
        <div class="subcontainer" on:wheel={scrollByPage}>
            <!-- svelte-ignore a11y-click-events-have-key-events -->
            <div
                class="statag"
                class:selected={topology.showStatAGRatios}
                on:click={() =>
                    (topology.showStatAGRatios = !topology.showStatAGRatios)}
            >
                <div class="text">
                    {topology.showStatAGRatios ? "Hide" : "Show"} StatAG Results
                </div>
            </div>

            {#each $steeringQueries.filter((q) => q.active) as query (query.id)}
                <SteerAGView
                    {topology}
                    id={query.id}
                    color={query.color}
                    name={query.name}
                    steering={query.steering}
                />
            {/each}
        </div>
    {:else}
        <div class="no-query">
            <div>No active SteerAG Query</div>
            <p>Start a new query in the right panel to see the results here.</p>
        </div>
    {/if}
</div>

<style lang="scss">
    .container {
        flex: 1;
        overflow-x: scroll;

        &.flex {
            display: flex;
        }

        .subcontainer {
            width: max-content;
            display: block;
            margin-left: 24px;

            .statag {
                display: flex;
                align-items: center;
                justify-content: center;

                position: absolute;
                margin-left: -24px;
                height: 300px;
                width: 24px;
                cursor: pointer;
                border-right: 2px solid #777;
                user-select: none;

                &.selected {
                    background-color: #00a;
                    color: #fff;
                }

                .text {
                    writing-mode: vertical-rl;
                    transform: rotate(180deg);
                    font-size: 1em;
                    font-weight: bold;
                }
            }
        }

        &::-webkit-scrollbar {
            display: none;
        }
    }

    .no-query {
        flex: 1;

        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        gap: 1rem;
        padding: 1rem;

        div {
            font-size: 1.5rem;
            font-weight: bold;
        }
        p {
            font-size: 1rem;
        }
    }
</style>
