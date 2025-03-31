<script lang="ts">
    import IconButton from "@components/IconButton.svelte";
    import { server } from "@lib/server";

    const models = server.otherModelPaths;

    async function selectModel(model: string) {
        const response = confirm(
            `Are you sure you want to change the model to ${model}?
This will reload the page and CANCEL all running queries.`,
        );
        if (!response) return;

        server.changeModel(model);
    }

    function map(models: string[]) {
        return models.map((model) => {
            return {
                value: model,
                label: model.split("/").pop()!.split(".")[0],
            };
        });
    }
</script>

<div class="container">
    <p class="attention">
        <strong>Warning:</strong> Changing the model will reload the page and cancel
        all running queries.
    </p>

    {#each map(models) as { value, label }}
        <IconButton
            noactive
            icon="database"
            on:click={() => selectModel(value)}
        >
            <div class="size">
                {label}
            </div>
        </IconButton>
    {/each}
</div>

<style lang="scss">
    .container {
        display: grid;
        flex-direction: column;
        gap: 1rem;
    }

    .attention {
        font-size: 0.8em;
        color: #f00;
        font-weight: bold;
    }

    .size {
        width: 300px;
    }
</style>
