<script lang="ts">
    import { AP_METRICS, type APCondition } from "@lib/types";

    export let conditions: APCondition[];

    function addCondition() {
        // Select a metric that is not already selected
        const metric = AP_METRICS.find(
            (metric) => !conditions.find((q) => q[0] === metric),
        );

        if (metric) {
            conditions.push([metric, 0, 10]);
            conditions = conditions;
        }
    }

    function removeCondition(i: number) {
        if (conditions.length === 0) return;

        conditions.splice(i, 1);
        conditions = conditions;
    }

    function updateNumber(event: Event, clauseIndex: number, index: number) {
        const value = Number((event.target as HTMLInputElement).value);

        conditions[clauseIndex][index] = value;
        conditions = conditions;
    }
</script>

{#if conditions.length === 0}
    <div class="row">
        Any attack path
        <button on:click={addCondition}>Add condition</button>
    </div>
{:else}
    {#each conditions as clause, i}
        {@const min = clause[0] === "length" ? 1 : 0.0}
        {@const max = clause[0] === "length" ? 39 : 10.0}

        <div class="row">
            <input
                type="number"
                value={clause[1]}
                on:change={(e) => updateNumber(e, i, 1)}
                {min}
                {max}
            />
            &leq;
            <select bind:value={clause[0]}>
                {#each AP_METRICS as metric}
                    <option value={metric}>{metric}</option>
                {/each}
            </select>
            &leq;
            <input
                type="number"
                value={clause[2]}
                on:change={(e) => updateNumber(e, i, 2)}
                {min}
                {max}
            />

            <button
                on:click={() => removeCondition(i)}
                disabled={conditions.length == 0}
                >Remove
            </button>
            <button on:click={addCondition} disabled={!(conditions.length < 5)}
                >Add
            </button>
        </div>
    {/each}
{/if}

<style lang="scss">
    .row {
        display: flex;
        flex-direction: row;
        gap: 4px;
    }

    select,
    input,
    button {
        all: unset;
        cursor: pointer;
        border-bottom: 1px solid black;
        user-select: none;

        &:hover {
            color: #f00;
            border-bottom: 1px solid #f00;
        }

        &[disabled] {
            cursor: not-allowed;
            color: #ccc;
            border-bottom: 1px solid #ccc;
        }
    }
</style>
