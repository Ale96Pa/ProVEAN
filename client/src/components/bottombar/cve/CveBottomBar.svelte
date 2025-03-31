<script lang="ts">
    import CveCard from "@components/CveCard.svelte";
    import IconButton from "@components/IconButton.svelte";
    import type { OverviewCanvas } from "@components/topology/topology";
    import { server, type TopVulnerabilitiesOutput } from "@lib/server";
    import { onDestroy, onMount } from "svelte";
    import Hint from "svelte-hint";

    export let id: number;
    export let topology: OverviewCanvas;

    let data: TopVulnerabilitiesOutput | null = null;
    let cves: [string, number, number][] = [];
    let sum: number = 0;
    let timeout: ReturnType<typeof setTimeout>;

    async function loadData() {
        data = await server.requestAnalysis("top_vulnerabilities", id);
        sum = 0;
        data.cves.forEach(([x, y], i) => {
            cves[i] = [x, y, i];
            sum += y;
        });

        timeout = setTimeout(loadData, 10000);
    }

    function select(cveId: string) {
        const hosts = server.model!.hosts;
        topology.selectedHosts.clear();
        for (const host of hosts) {
            if (host.cves.includes(cveId)) {
                topology.selectedHosts.add(host.id);
            }
        }
    }

    function copyTop(count: number) {
        if (!data) return;

        const top = data!.cves.slice(0, count);
        navigator.clipboard.writeText(top.map(([cveId]) => cveId).join(","));
    }

    onMount(() => {
        loadData();
    });

    onDestroy(() => {
        clearTimeout(timeout);
    });
</script>

<div class="container" on:wheel|stopPropagation>
    {#if data}
        {#each cves as [cveId, count, i] (i)}
            <div class="cve-group">
                <div class="title">
                    <div class="position" class:big={i < 9}>
                        #{i + 1}<br />
                    </div>
                    <div class="percentage">
                        {((count / sum) * 100).toFixed(2)}%
                    </div>
                </div>
                <div class="card">
                    <CveCard {cveId} />
                </div>
                <div class="button">
                    <Hint
                        text="Copy {i === 0
                            ? 'first CVE.'
                            : `top ${i + 1} CVEs.`}"
                    >
                        <IconButton
                            icon="copy"
                            on:click={() => copyTop(i + 1)}
                        />
                    </Hint>
                    <Hint text="Select all hosts with this vulnerability.">
                        <IconButton
                            icon="host"
                            on:click={() => select(cveId)}
                        />
                    </Hint>
                </div>
            </div>
        {/each}
    {:else}
        Loading...
    {/if}
</div>

<style lang="scss">
    .container {
        display: flex;
        flex-direction: column;
        overflow-y: scroll;
        // max-height: 100%;
        padding: 4px;
    }

    .cve-group {
        display: flex;
        flex-direction: row;
        gap: 4px;

        .title {
            display: flex;
            flex-direction: column;
            justify-content: center;
            align-items: center;

            .position {
                font-size: 1em;

                &.big {
                    font-size: 1.5em;
                    font-weight: bold;
                }
            }

            .percentage {
                font-size: 0.8em;
            }
        }

        .card {
            flex: 1;
            font-size: 0.8em;
        }

        .button {
            flex-shrink: 1;
            display: flex;
            justify-content: center;
            align-items: center;
        }
    }
</style>
