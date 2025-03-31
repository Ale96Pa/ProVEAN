<script lang="ts">
    import { onDestroy } from "svelte";

    export let type:
        | "connectingToBackend"
        | "waitingForBriefing"
        | "waitingForBackend";

    let dots = 1;

    const interval = setInterval(() => {
        dots = (dots + 1) % 3;
    }, 1000);
    const DOTS = [".", "..", "..."];

    onDestroy(() => clearInterval(interval));
</script>

<div class="container">
    {#if type === "connectingToBackend"}
        <h1>Connecting to the backend{DOTS[dots]}</h1>

        <p>
            If this message persists, it means the backend server is not
            running.
        </p>
        <p>Please make sure it is running on the correct port (46715).</p>
    {:else if type === "waitingForBriefing"}
        <h1>Waiting for initial message{DOTS[dots]}</h1>

        <p>This might take a while if the network model is large.</p>
    {:else}
        <h1>Waiting to reload{DOTS[dots]}</h1>

        <p>
            The server is starting with the new model, the page will
            automatically refresh when done.
        </p>
    {/if}
</div>

<style lang="scss">
    $size: 80px;
    $bg1: #f0f0f0;
    $bg2: #e0e0e0;
    $animSpeed: 2s;

    .container {
        grid-row: 1 / -1;
        grid-column: 1 / -1;

        display: flex;
        flex-direction: column;
        justify-content: center;
        align-items: center;

        text-shadow: 0px 0px 16px #fff;

        /* Add the coolest background you can manage, possibly animated */
        background: linear-gradient(
            45deg,
            $bg1 25%,
            $bg2 25%,
            $bg2 50%,
            $bg1 50%,
            $bg1 75%,
            $bg2 75%,
            $bg2
        );
        background-size: $size $size;
        animation: background-spin $animSpeed linear infinite;
    }

    @keyframes background-spin {
        0% {
            background-position: 0 0;
        }
        100% {
            background-position: -2 * $size 0;
        }
    }
</style>
