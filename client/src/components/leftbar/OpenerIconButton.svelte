<script lang="ts">
    import type { LeftBarTab } from "./LeftBar.svelte";

    export let icon: string;
    export let tab: LeftBarTab | null;
    export let thisTab: LeftBarTab | undefined = undefined;
    export let onClick: () => void = () =>
        thisTab === undefined
            ? () => null
            : (tab = tab === thisTab ? null : thisTab);
</script>

<button
    class="icon-button"
    class:active={tab === thisTab}
    class:visible={tab !== null}
    on:click={onClick}
>
    <img src={`icons/${icon}.svg`} alt="icon" />
    <div class="text">
        <slot />
    </div>
</button>

<style lang="scss">
    .icon-button {
        all: unset;
        pointer-events: all;

        position: relative;
        width: max-content;
        display: flex;
        align-items: center;
        gap: 8px;
        margin-bottom: 4px;

        border-radius: 10px;
        user-select: none;

        padding: 8px;
        cursor: pointer;

        height: 24px;

        .text {
            display: none;
        }

        &:hover {
            background: rgba(0, 0, 0, 0.1);
            .text {
                display: block;
            }
        }

        &.active,
        &:not(.noactive):active {
            background: #1779ba68;
            .text {
                display: block;
            }
        }

        &.visible {
            .text {
                display: block;
            }
        }
    }
</style>
