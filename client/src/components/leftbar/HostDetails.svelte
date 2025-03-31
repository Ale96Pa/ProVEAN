<script lang="ts">
    import { server } from "@lib/server";
    import IconButton from "../IconButton.svelte";
    import { slide } from "svelte/transition";
    import CveCard from "@components/CveCard.svelte";
    import { intersection } from "d3";

    export let sourceHosts: Set<number>;
    export let targetHosts: Set<number>;
    export let selection: number[];
    selection.sort((a, b) => a - b);

    const hosts = server.model?.hosts!;

    let expanded = new Set<number>();
    function toggle(host: number) {
        if (expanded.has(host)) {
            expanded.delete(host);
        } else {
            expanded.add(host);
        }

        expanded = expanded;
    }

    let done = true;
    async function copySelection(selection: number[]) {
        done = false;
        navigator.clipboard.writeText(selection.join(","));
        await new Promise((resolve) => setTimeout(resolve, 1000));
        done = true;
    }
</script>

<div class="container">
    <div class="row">
        <i>
            Use the buttons below to copy the selections. If your selection does
            not appear, close and reopen the Host Details tab.
        </i>
        <div class="col">
            <input type="text" value={selection} readonly />
            <button disabled={!done} on:click={() => copySelection(selection)}>
                {done ? "Copy entire selection" : "Copied!"}
            </button>
        </div>

        {#if sourceHosts.size > 0}
            <div class="col">
                <input type="text" value={[...sourceHosts]} readonly />
                <button
                    disabled={!done}
                    on:click={() => copySelection([...sourceHosts])}
                >
                    {done ? "Copy Sources" : "Copied!"}
                </button>
            </div>
        {/if}

        {#if targetHosts.size > 0}
            <div class="col">
                <input type="text" value={[...targetHosts]} readonly />
                <button
                    disabled={!done}
                    on:click={() => copySelection([...targetHosts])}
                >
                    {done ? "Copy Targets" : "Copied!"}
                </button>
            </div>
        {/if}

        {#if targetHosts.intersection(sourceHosts).size > 0}
            <div class="col">
                <input
                    type="text"
                    value={[...targetHosts.intersection(sourceHosts)]}
                    readonly
                />
                <button
                    disabled={!done}
                    on:click={() =>
                        copySelection([
                            ...targetHosts.intersection(sourceHosts),
                        ])}
                >
                    {done ? "Copy Sources & Targets" : "Copied!"}
                </button>
            </div>
        {/if}
    </div>

    {#each selection as id (id)}
        {@const host = hosts[id]}
        {@const selected = expanded.has(id) || selection.length === 1}

        <IconButton
            noactive
            icon="host"
            active={selected}
            on:click={() => toggle(id)}
        >
            {#if sourceHosts.has(id)}
                (source)
            {/if}
            {#if targetHosts.has(id)}
                (target)
            {/if}
            <div class="host">
                <div class="ip">
                    {host.ipv4}
                </div>
                <div class="id">
                    id: {id}
                </div>
                <div class="domain">
                    dom: {host.domain}
                </div>
                <div class="hostname">
                    {host.hostname}
                </div>
                <div class="expand">
                    {#if selection.length > 1}
                        {#if selected}
                            Collapse vulnerabilities
                        {:else}
                            Expand {host.cves.length} vulnerabilities
                        {/if}
                    {/if}
                </div>
            </div>
        </IconButton>

        {#if selected}
            <div class="vulnerabilities" transition:slide={{ duration: 100 }}>
                {#each host.cves as cveId (cveId)}
                    <CveCard {cveId} />
                {/each}
            </div>
        {/if}
    {/each}
</div>

<style lang="scss">
    .container {
        display: grid;
        flex-direction: column;
        gap: 1rem;
    }

    .host {
        width: 324px;
        padding-left: 16px;
        display: grid;
        grid-template-columns: max-content 1fr;
        grid-template-rows: repeat(2, min-content) 1fr;
        grid-template-areas: "id ip" "domain hostname" "expand expand";
        gap: 0 0.5rem;

        .ip {
            grid-area: ip;
        }
        .id {
            grid-area: id;
            font-size: 0.75em;
            padding-top: 0.25rem;
        }
        .domain {
            grid-area: domain;
            font-size: 0.75em;
            padding-top: 0.25rem;
        }
        .hostname {
            grid-area: hostname;
        }
        .expand {
            grid-area: expand;
            font-size: 0.9em;
            padding-top: 0.1rem;
            font-weight: 500;
        }
    }

    .vulnerabilities {
        display: grid;
        gap: 0.5rem;
        padding-left: 32px;
    }

    .col {
        display: flex;
        gap: 0.125rem;
    }
    .row {
        display: flex;
        flex-direction: column;
        gap: 0.5rem;

        input {
            flex: 1;
        }
        button {
            width: 160px;
        }
    }
</style>
