<script lang="ts">
    import { onDestroy, onMount } from "svelte";
    import type { MatrixSelection, SourceTargetMatrix } from "./stm";

    export let stm: SourceTargetMatrix;
    export let highlightDuringSelection = false;
    export let selectionInfo: MatrixSelection | null = null;

    let canvas: HTMLCanvasElement;
    let ctx: CanvasRenderingContext2D;

    onMount(() => {
        ctx = canvas.getContext("2d")!;
        drawSelection(stm.selection);
    });
    const unsub = stm.updateStore.subscribe(() => {
        if (!canvas) return;
        drawSelection(stm.selection);
    });
    onDestroy(() => {
        unsub();
        window.removeEventListener("mousemove", mouseMove);
        window.removeEventListener("mouseup", mouseUp);
    });

    interface Cell {
        i: number;
        j: number;
    }

    let startSelection: Cell | null = null;

    function getHoveredCell(event: MouseEvent): Cell {
        const rect = canvas.getBoundingClientRect();

        const x = ((event.clientX - rect.left) / rect.width) * stm.matrix.cols;
        const y = ((event.clientY - rect.top) / rect.height) * stm.matrix.rows;

        const i = Math.max(Math.min(Math.floor(x), stm.matrix.cols), 0);
        const j = Math.max(Math.min(Math.floor(y), stm.matrix.rows), 0);

        return { i, j };
    }

    function mouseDown(event: MouseEvent) {
        const { i, j } = getHoveredCell(event);
        startSelection = { i, j };
        window.addEventListener("mousemove", mouseMove);
        window.addEventListener("mouseup", mouseUp);
    }
    function mouseMove(event: MouseEvent) {
        if (!startSelection) return;
        updateSelection(event, startSelection);
    }
    function mouseUp(event: MouseEvent) {
        if (!startSelection) return;
        updateSelection(event, startSelection);
        startSelection = null;
        window.removeEventListener("mousemove", mouseMove);
        window.removeEventListener("mouseup", mouseUp);
    }

    function updateSelection(event: MouseEvent, startSelection: Cell) {
        const { i: i1, j: j1 } = startSelection;
        const { i, j } = getHoveredCell(event);

        const x1 = Math.min(i1, i);
        const x2 = Math.max(i1, i);
        const y1 = Math.min(j1, j);
        const y2 = Math.max(j1, j);

        stm.selection = { x1, x2, y1, y2 };
        selectionInfo = stm.selection;

        drawSelection(stm.selection);
        if (highlightDuringSelection) stm.selectHosts();
    }

    function drawSelection(selection: MatrixSelection | null) {
        stm.pasteMatrix(canvas);

        if (!selection) return;
        let { x1, x2, y1, y2 } = selection;

        ctx.fillStyle = "rgba(255, 255, 255, 0.6)";
        // Draw the outlines of the selection, on top
        // so if the selection includes the whole matrix,
        // it will be visible.
        const SIZE = 1;
        const dx = x2 - x1 + 1;
        const dy = y2 - y1 + 1;
        ctx.fillRect(x1 - SIZE, y1 - SIZE, dx + 2 * SIZE, SIZE);
        ctx.fillRect(x1 - SIZE, y1, SIZE, dy + SIZE);
        ctx.fillRect(x2 + 1, y1, SIZE, dy + SIZE);
        ctx.fillRect(x1, y2 + 1, dx, SIZE);

        ctx.fillStyle = "rgba(255, 255, 255, 0.3)";
        ctx.fillRect(x1, y1, dx, dy);
    }
</script>

<canvas bind:this={canvas} on:mousedown={mouseDown} />
