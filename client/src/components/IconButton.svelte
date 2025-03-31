<script lang="ts">
    export let icon: string | null = null;
    export let active: boolean = false;
    export let noactive: boolean = false;
</script>

<button class="icon-button" class:active on:click class:noactive>
    {#if icon}
        <img src={`icons/${icon}.svg`} alt="icon" />
    {/if}

    {#if $$slots.default}
        <span class="icon-button-text">
            <slot />
        </span>
    {/if}
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

        &:hover {
            background: rgba(0, 0, 0, 0.1);
        }

        &.active,
        &:not(.noactive):active {
            background: #1779ba68;
        }
    }
</style>
