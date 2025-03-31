<script lang="ts">
    import Hint from "svelte-hint";

    export let tooltip: string;
    export let disabled: boolean = false;

    export let value: boolean;
    export let trueIcon: string;
    export let falseIcon: string;
</script>

<div class="container">
    <Hint text={tooltip}>
        <button {disabled} on:click class:active={value}>
            <img
                src="/icons/{value ? trueIcon : falseIcon}.svg"
                alt={tooltip}
            />
        </button>
    </Hint>
</div>

<style lang="scss">
    .container {
        display: contents;
    }

    button {
        all: unset;
        width: 1.5em;
        height: 1.5em;

        display: inline-flex;
        justify-content: center;
        align-items: center;

        background: #fff8;

        cursor: pointer;
        transition: background-color 0.2s;

        &.active {
            background: #fffc;
        }
        &:hover {
            background: #fffa;
        }
    }
</style>
