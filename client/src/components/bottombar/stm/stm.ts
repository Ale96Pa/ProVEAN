import type { OverviewCanvas } from '@components/topology/topology';
import reorder from '@lib/reorder';
import * as d3 from 'd3';
import { writable } from 'svelte/store';

export enum Metric {
    Absolute,
    AbsoluteSquare,
    Relative,
    RelativeSquare,
}

export enum Filter {
    None,
    Rows,
    Cols,
    Both,
}

export enum Sorting {
    None,
    Rows,
    Cols,
    PCA,
    RowsAndCols,
}


export interface MatrixSelection {
    x1: number;
    x2: number;
    y1: number;
    y2: number;
}



const DIAGONAL_MARK = 1e-64;

export class SourceTargetMatrix {
    private readonly colorMap = d3.interpolateMagma;

    private N: number = 0;

    /** Which matrix to compute before transformations. */
    #metric: Metric = Metric.Relative;
    /** The direction along which to perform filtering */
    #filter: Filter = Filter.None;
    /** The amount of filtering to perform */
    #filterAmount: number = 0.5;
    /** The sorting mode. */
    #sorting: Sorting = Sorting.None;

    /** Matrix to draw. */
    public matrix!: MappedMatrix;
    /** Matrix selection */
    public selection: MatrixSelection | null = null;

    constructor(
        public topology: OverviewCanvas,
        public statMatrix: number[][],
        public steerMatrix: number[][]
    ) {
        // Assert both matrices are square and of the same size
        if (this.statMatrix.length !== this.steerMatrix.length) {
            throw new Error("Matrix dimensions do not match");
        }
        if (this.statMatrix.length !== this.statMatrix[0].length) {
            throw new Error("Matrix is not square");
        }

        this.N = this.statMatrix.length;
    }

    public set metric(mode: Metric) {
        if (mode === this.#metric) return;
        this.#metric = mode;
        this.update();
    }
    public get metric() {
        return this.#metric;
    }

    public setFilter(filter: Filter, amount: number) {
        if (filter === this.#filter && amount === this.#filterAmount) return;

        this.#filter = filter;
        this.#filterAmount = amount;
        this.update();
    }
    public get filter() {
        return this.#filter;
    }
    public get filterAmount() {
        return this.#filterAmount;
    }

    public set sorting(mode: Sorting) {
        if (mode === this.#sorting) return;
        this.#sorting = mode;
        this.update();
    }
    public get sorting() {
        return this.#sorting;
    }



    /** Perform all actions and re-draw. */
    public update(
        statMatrix: number[][] = this.statMatrix,
        steerMatrix: number[][] = this.steerMatrix
    ) {
        this.statMatrix = statMatrix;
        this.steerMatrix = steerMatrix;

        const data = this.computeMatrix();
        this.matrix = new MappedMatrix(data);

        this.filterMatrix();
        this.sortMatrix();
        this.renderMatrix();
    }

    /** Compute the image matrix starting from the input matrices. */
    private computeMatrix() {
        let matrix: number[][] = this.statMatrix;

        switch (this.#metric) {
            case Metric.Absolute:
                matrix = this.getAbsoluteMatrix(false);
                break;
            case Metric.AbsoluteSquare:
                matrix = this.getAbsoluteMatrix(true);
                break;
            case Metric.Relative:
                matrix = this.getRelativeMatrix(false);
                break;
            case Metric.RelativeSquare:
                matrix = this.getRelativeMatrix(true);
                break;
        }

        // Set the middle diagonal to null
        for (let i = 0; i < this.N; i++) {
            matrix[i][i] = DIAGONAL_MARK;
        }

        return matrix;
    }
    /** Perform the filtering operation */
    private filterMatrix() {
        if (this.#filter === Filter.None) return;

        // This filtering operation is rather complicated.
        if (this.#filter === Filter.Cols || this.#filter === Filter.Both) {
            // Get the sum of each column.
            const cols = this.matrix.sum('cols');
            const percentile = getPercentile(cols, this.#filterAmount);

            // Filter the columns that fall below the percentile.
            let filteredCols = [];
            for (let i = 0; i < cols.length; i++)
                if (cols[i] >= percentile) filteredCols.push(i);
            this.matrix.takeCols(filteredCols);
        }
        if (this.#filter === Filter.Rows || this.#filter === Filter.Both) {
            // Get the sum of each row.
            const rows = this.matrix.sum('rows');
            const percentile = getPercentile(rows, this.#filterAmount);

            // Filter the rows that fall below the percentile.
            let filteredRows = [];
            for (let i = 0; i < rows.length; i++)
                if (rows[i] >= percentile) filteredRows.push(i);
            this.matrix.takeRows(filteredRows);
        }
    }
    /** Perform the sorting operation on the matrix. */
    private sortMatrix() {
        if (this.#sorting === Sorting.None) return;

        if (this.#sorting === Sorting.Rows || this.#sorting === Sorting.RowsAndCols) {
            const rows = this.matrix.sum('rows');
            // Save the indices of the sorted rows
            const rowsInd = rows.map((v, i) => [v, i]);
            rowsInd.sort((a, b) => b[0] - a[0]);

            this.matrix.takeRows(rowsInd.map(v => v[1]));
        }
        if (this.#sorting === Sorting.Cols || this.#sorting === Sorting.RowsAndCols) {
            const cols = this.matrix.sum('cols');
            // Save the indices of the sorted rows
            const colsInd = cols.map((v, i) => [v, i]);
            colsInd.sort((a, b) => b[0] - a[0]);

            this.matrix.takeCols(colsInd.map(v => v[1]));
        }

        if (this.#sorting === Sorting.PCA) {
            this.matrix.sortPca();
        }
    }


    private getRelativeMatrix(square: boolean = false): number[][] {
        const statSum = sumMatrix(this.statMatrix);
        const steerSum = sumMatrix(this.steerMatrix);
        const finalMatrix: number[][] = [];

        for (let i = 0; i < this.N; i++) {
            finalMatrix[i] = [];
            for (let j = 0; j < this.N; j++) {
                const stat = this.statMatrix[i][j] / statSum;
                const steer = this.steerMatrix[i][j] / steerSum;
                finalMatrix[i][j] = (steer - stat) > 0 ? steer - stat : 0;
            }
        }

        // Normalize the final matrix so that the values are in the range [-1, 1]
        const max = maxMatrix(finalMatrix);
        for (let i = 0; i < this.N; i++) {
            for (let j = 0; j < this.N; j++) {
                finalMatrix[i][j] = finalMatrix[i][j] / max;
                if (square) finalMatrix[i][j] **= 2;
            }
        }

        return finalMatrix;
    }
    private getAbsoluteMatrix(square: boolean = false): number[][] {
        const finalMatrix: number[][] = [];

        // Normalize the final matrix so that the values are in the range [-1, 1]
        const max = maxMatrix(this.steerMatrix);
        for (let i = 0; i < this.N; i++) {
            finalMatrix[i] = [];
            for (let j = 0; j < this.N; j++) {
                finalMatrix[i][j] = this.steerMatrix[i][j] / max;
                if (square) finalMatrix[i][j] **= 2;
            }
        }

        return finalMatrix;
    }

    renderedMatrix: ImageData | null = null;
    public updateStore = writable({});

    /** Draw the matrix on the canvas. */
    public renderMatrix() {
        const width = this.matrix.cols;
        const height = this.matrix.rows;

        const imgData = new ImageData(
            width,
            height,
        );

        const diagonalColor = d3.rgb("#888");
        for (let i = 0; i < height; i++) {
            for (let j = 0; j < width; j++) {
                const value = this.matrix.data[i][j]
                const color = value === DIAGONAL_MARK ? diagonalColor : d3.rgb(this.colorMap(value));
                const index = 4 * (i * width + j);
                imgData.data[index + 0] = color.r;
                imgData.data[index + 1] = color.g;
                imgData.data[index + 2] = color.b;
                imgData.data[index + 3] = 255;
            }
        }

        this.renderedMatrix = imgData;
        this.updateStore.set({});
    }

    public pasteMatrix(canvas: HTMLCanvasElement) {
        if (!this.renderedMatrix) return;

        const width = this.renderedMatrix.width;
        const height = this.renderedMatrix.height;

        canvas.width = width;
        canvas.height = height;

        const ctx = canvas.getContext('2d');
        if (!ctx) throw new Error("Could not get canvas context");
        ctx.putImageData(this.renderedMatrix, 0, 0);
    }

    public selectHosts() {
        if (!this.selection) return;
        const { x1, x2, y1, y2 } = this.selection;

        const selectedCols = this.matrix.colIndices.slice(
            x1,
            Math.min(x2 + 1, this.matrix.cols),
        );
        const selectedRows = this.matrix.rowIndices.slice(
            y1,
            Math.min(y2 + 1, this.matrix.rows),
        );

        this.topology.selectHosts({
            sources: selectedRows,
            targets: selectedCols
        });
    }

    public computeSelectionSummary(selection: MatrixSelection) {
        const { x1, x2, y1, y2 } = selection;

        const targets = this.matrix.colIndices.slice(
            x1,
            Math.min(x2 + 1, this.matrix.cols),
        );
        const sources = this.matrix.rowIndices.slice(
            y1,
            Math.min(y2 + 1, this.matrix.rows),
        );

        let totalStat = sumMatrix(this.statMatrix);
        let totalSteer = sumMatrix(this.steerMatrix);

        let selectedStat = 0;
        let selectedSteer = 0;
        for (const i of sources) {
            for (const j of targets) {
                selectedStat += this.statMatrix[i][j];
                selectedSteer += this.steerMatrix[i][j];
            }
        }

        return {
            sources: sources.length,
            targets: targets.length,
            selStat: selectedStat,
            selSteer: selectedSteer,
            totalStat,
            totalSteer,
        }
    }
}


function sumMatrix(matrix: number[][]) {
    const N = matrix.length;
    const M = matrix[0].length;

    let sum = 0;
    for (let i = 0; i < N; i++) {
        for (let j = 0; j < M; j++) {
            sum += matrix[i][j];
        }
    }

    return sum;
}
function maxMatrix(matrix: number[][]) {
    const N = matrix.length;
    const M = matrix[0].length;

    let max = 0;
    for (let i = 0; i < N; i++) {
        for (let j = 0; j < M; j++) {
            max = Math.max(max, matrix[i][j]);
        }
    }

    return max;
}
function getPercentile(array: number[], perc: number) {
    if (perc === 1) return Math.max(...array);
    const sorted = [...array];
    sorted.sort((a, b) => a - b);
    return sorted[Math.floor(perc * sorted.length)];
}
function take<T>(array: T[], indices: number[]) {
    return indices.map(i => array[i]);
}


class MappedMatrix {
    data: number[][];
    rowIndices: number[];
    colIndices: number[];

    rows: number;
    cols: number;

    constructor(matrix: number[][]) {
        this.data = matrix;

        this.rows = matrix.length;
        this.cols = matrix[0].length;

        this.rowIndices = Array.from({ length: this.rows }, (_, i) => i);
        this.colIndices = Array.from({ length: this.cols }, (_, i) => i);
    }

    public sum(): number;
    public sum(axis: 'rows' | 'cols'): number[];
    public sum(axis: 'rows' | 'cols' | void): number[] | number {
        if (!axis) {
            return sumMatrix(this.data);
        }
        else if (axis === 'rows') {
            let sums = [];
            for (let i = 0; i < this.rows; i++) {
                let rowSum = 0;
                for (let j = 0; j < this.cols; j++) {
                    rowSum += this.data[i][j];
                }
                sums.push(rowSum);
            }
            return sums;
        }
        else if (axis === 'cols') {
            let sums = [];
            for (let j = 0; j < this.cols; j++) {
                let colSum = 0;
                for (let i = 0; i < this.rows; i++) {
                    colSum += this.data[i][j];
                }
                sums.push(colSum);
            }
            return sums;
        }
        else {
            throw new Error("Invalid axis");
        }
    }


    public takeCols(keep: number[]) {
        for (let i = 0; i < this.rows; i++) {
            this.data[i] = take(this.data[i], keep);
        }
        this.colIndices = take(this.colIndices, keep);
        this.cols = keep.length;
    }
    public takeRows(keep: number[]) {
        this.data = take(this.data, keep);
        this.rowIndices = take(this.rowIndices, keep);
        this.rows = keep.length;
    }

    public sortPca() {
        const order = reorder.pca_order(this.data);
        this.takeCols(order);
    }
}
