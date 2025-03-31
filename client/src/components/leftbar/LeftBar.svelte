<script context="module" lang="ts">
    export type LeftBarTab = "settings" | "positions" | "hosts" | "models";
</script>

<script lang="ts">
    import type { Writable } from "svelte/store";

    import type { OverviewCanvas } from "@components/topology/topology";
    import IconButton from "../IconButton.svelte";
    import HostDetails from "./HostDetails.svelte";
    import SelectModel from "./SelectModel.svelte";
    import HostSettings from "./HostSettings.svelte";

    export let tab: LeftBarTab | null;
    export let topology: OverviewCanvas;

    let undoStackLength: Writable<number>;
    $: undoStackLength = topology?.undoStackLength;
    let selection = topology?.selection;
    $: selection = topology?.selection;

    let hostSelection: number[] = [];
    $: {
        if (tab === "hosts" && $selection) {
            hostSelection = $selection;
        }
    }

    const NAMES = {
        settings: "Topology View Settings",
        positions: "Host Position Editing",
        hosts: "Host Details",
        models: "Select Another Model",
    };

    function getName(tab: LeftBarTab | null): string {
        return tab ? NAMES[tab] : "";
    }
    function close() {
        tab = null;
    }
</script>

<div class="container">
    <div class="title">
        <h2>{getName(tab)}</h2>
        <button class="close" on:click={close}> Close </button>
    </div>

    <div class="content">
        {#if tab === "hosts"}
            <HostDetails
                selection={hostSelection}
                sourceHosts={topology.selectedHosts.sourceHosts}
                targetHosts={topology.selectedHosts.targetHosts}
            />
        {:else if tab === "models"}
            <SelectModel />
        {:else if tab === "settings"}
            <HostSettings {topology} />
        {:else if tab === "positions"}
            <IconButton
                icon="reload"
                on:click={() => topology.resetPositions()}
            >
                <div class="option">
                    <div class="name">Reload Host Positions</div>
                    <div class="description">
                        Reload the host positions from the server. <br />
                        This will discard any changes made since the last save operation.
                    </div>
                </div>
            </IconButton>
            <IconButton icon="save" on:click={() => topology.sendPositions()}>
                <div class="option">
                    <div class="name">Save Host Positions</div>
                    <div class="description">
                        Save the host positions to the server. <br />
                        When this is done, the current positions will survive a page
                        reload.
                    </div>
                </div>
            </IconButton>
            <IconButton icon="undo" on:click={() => topology.undoMovement()}>
                <div class="option">
                    <div class="name">Undo Last Movement</div>
                    <div class="description">
                        {#if $undoStackLength === 0}
                            There are no movements to undo.
                        {:else}
                            {#if $undoStackLength === 1}
                                There is one movement to undo.
                            {:else}
                                There are {$undoStackLength} movements to undo.
                            {/if}<br />

                            Undo the last movement of a host. <br />
                            This will revert the last change made to the host positions.
                        {/if}
                    </div>
                </div>
            </IconButton>

            <div class="instructions">
                <h3>Instructions</h3>
                <ol>
                    <li>
                        Drag on the topology with the left mouse button to
                        select hosts with a lasso.<br />

                        While dragging, hold the <kbd>Shift</kbd> key to remove
                        hosts from the selection.<br />
                    </li>
                    <li>
                        Clicking outside of any host will deselect all hosts.<br
                        />

                        Clicking on any host will toggle its selection.<br />

                        Hold the <kbd>Shift</kbd> key while clicking on an host to
                        avoid deselecting the other hosts by mistake.
                    </li>
                    <li>
                        Start dragging with the middle mouse button to move the
                        selected hosts.
                    </li>
                    <li>
                        Once the hosts are in the desired position, click on the
                        <b>Save Host Positions</b> button above to save the changes.
                    </li>
                </ol>
            </div>
        {/if}
    </div>
</div>

<style lang="scss">
    .container {
        display: grid;
        grid-template-rows: min-content 1fr;
        max-height: 100%;
        gap: 8px;
        padding: 8px;
    }

    .title {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 8px;
        border-bottom: 1px solid rgba(0, 0, 0, 0.1);

        h2 {
            margin: 0;
            font-size: 1.2em;
            font-weight: 500;
        }

        .close {
            all: unset;
            cursor: pointer;
            padding: 4px 8px;
            border-radius: 4px;
            background: rgba(0, 0, 0, 0.1);

            &:hover {
                background: rgba(0, 0, 0, 0.2);
            }
        }
    }

    .content {
        overflow-x: hidden;
        overflow-y: auto;

        h3 {
            margin: 0;
            font-size: 1.125em;
            font-weight: 500;
            padding-bottom: 8px;
        }

        .option {
            width: 320px;
            padding-left: 8px;

            .name {
                font-weight: 500;
            }
            .description {
                font-size: 0.8em;
                color: rgba(0, 0, 0, 0.6);
            }
        }

        .instructions {
            margin-top: 16px;

            li {
                margin-top: 8px;
                font-size: 0.8em;
                color: rgba(0, 0, 0, 0.6);
            }
        }
    }
</style>
