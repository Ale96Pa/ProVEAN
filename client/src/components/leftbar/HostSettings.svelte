<script lang="ts">
    import IconButton from "@components/IconButton.svelte";
    import {
        LinkStyle,
        type OverviewCanvas,
    } from "@components/topology/topology";

    export let topology: OverviewCanvas;
    const LINK_STYLES = [
        {
            value: LinkStyle.Absolute,
            name: "Absolute Path Count per Query",
            description: `
                The absolute count of paths passing through this link, normalized to fit on each link. 
                Thicker links represent more paths.`,
        },
        {
            value: LinkStyle.RelativeSum,
            name: "Relative Path Count per Query over Sum",
            description: `
                The ratio of paths passing through this link in each query, normalized to fit on each link.`,
        },
        {
            value: LinkStyle.RelativeMax,
            name: "Relative Path Count per Query over Max",
            description: `
                The ratio of paths passing through this link over the maximum ratio found in the query, 
                normalized to fit on each link. Emphasizes where the query has the most paths.`,
        },
        {
            value: LinkStyle.RelativeStat,
            name: "Thickness Relative to StatAG",
            description: `
                The ratio of paths passing through this link, but the total thickness of each link is fixed by StatAG,
                saves on computation.`,
        },
    ];
</script>

<h3>Host Settings</h3>

<IconButton
    icon="circle-{topology.showCircles ? 'full' : 'empty'}"
    bind:active={topology.showCircles}
    on:click={() => (topology.showCircles = !topology.showCircles)}
>
    <div class="option">
        <div class="name">View Circles on Hosts</div>
        <div class="description">
            Show a circle around each host for each query, varying in
            transparency based on how much more frequent paths of the query are
            on that host compared to the statistical generation.
        </div>
    </div>
</IconButton>

<IconButton
    icon="circle-{topology.showConvexHulls ? 'full' : 'empty'}"
    bind:active={topology.showConvexHulls}
    on:click={() => (topology.showConvexHulls = !topology.showConvexHulls)}
>
    <div class="option">
        <div class="name">View Convex Hulls on Hosts</div>
        <div class="description">
            Draws one or more convex hulls for each query on top of the topology
            view. The convex hulls are drawn around the hosts that appear more
            frequently in the query than in the statistical generation.
        </div>
    </div>
</IconButton>

{#if topology.showConvexHulls}
    <IconButton noactive>
        <div class="option big">
            <div class="name">Convex Hull Radius</div>
            <div class="description">
                The maximum radius of the convex hulls around the hosts.
                Increasing this value will make the convex hulls larger and more
                likely to overlap.
                <br />
            </div>
            <div class="slider">
                <input
                    type="range"
                    min={40}
                    max={300}
                    step={10}
                    bind:value={topology.convexHullThreshold}
                />
                <span>{topology.convexHullThreshold}px</span>
            </div>
        </div>
    </IconButton>
{/if}
<br />

<h3>Link Settings</h3>
<IconButton noactive icon="stats">
    <div class="option">
        <div class="name">Links Data</div>
        <div class="description">
            Select what data is used to determine the appearance of the links.

            <select bind:value={topology.linkStyle}>
                {#each LINK_STYLES as { value, name }}
                    <option {value}>{name}</option>
                {/each}
            </select><br />

            {LINK_STYLES[topology.linkStyle].description}
        </div>
    </div>
</IconButton>

<IconButton
    icon="link-{topology.showStatAGRatios ? 'full' : 'empty'}"
    bind:active={topology.showStatAGRatios}
    on:click={() => (topology.showStatAGRatios = !topology.showStatAGRatios)}
>
    <div class="option">
        <div class="name">Show StatAG Ratios on Links</div>
        <div class="description">
            Shows the ratio of the number of paths that pass through the link in
            the statistical generation alongside the ones for the selected
            queries.
        </div>
    </div>
</IconButton>

<style lang="scss">
    .option {
        width: 320px;
        padding-left: 8px;

        &.big {
            width: 344px;
        }

        .name {
            font-weight: 500;
        }
        .description {
            font-size: 0.8em;
            color: rgba(0, 0, 0, 0.6);
        }
        .slider {
            display: flex;
            align-items: center;

            input {
                flex: 1;
                margin: 8px 0;
            }
            span {
                font-size: 0.8em;
                margin-left: 8px;
            }
        }
    }
</style>
