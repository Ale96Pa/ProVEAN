import * as reorder from "reorder.js";

interface ReorderJsLibrary {
    /** Generates a random matrix of size (n,m). */
    random_matrix: (p: number, n: number, m: number, symmetric: boolean) => number[][];
    /** Permutes the rows and cols of matrix. */
    permute(matrix: number[][], rows: number[], cols: number[]): number[][];
    /** Performs Principal Component Analysis (PCA) ordering on matrices and 
     *  returns the columns permutation. */
    pca_order(matrix: number[][]): number[];

    correlation: {
        pearson: any;
        pearsonMatrix: any;
    }
    distance: {
        braycurtis: any;
        chebyshev: any;
        euclidean: any;
        hamming: any;
        jaccard: any;
        manhattan: any;
        minkowski: any;
        morans: any;
    }
    adjacent_exchange: any;
    all_pairs_distance: any;
    all_pairs_distance_bfs: any;
    all_pairs_distance_floyd_warshall: any;
    array1d: any;
    array_to_dicts: any;
    assert: any;
    bandwidth: any;
    bandwidth_matrix: any;
    barycenter: any;
    barycenter_order: any;
    bfs: any;
    bfs_distances: any;
    bfs_order: any;
    ca: any;
    ca_decorana: any;
    ca_order: any;
    check_distance_matrix: any;
    cmp_number: any;
    cmp_number_asc: any;
    cmp_number_desc: any;
    complete_graph: any;
    condition: any;
    count_all_crossings: any;
    count_crossings: any;
    count_in_crossings: any;
    count_out_crossings: any;
    covariance: any;
    covariancetranspose: any;
    cuthill_mckee: any;
    cuthill_mckee_order: any;
    debugdicts_to_array: any;
    displaymat: any;
    dist: any;
    dist_remove: any;
    distmat2valuemat: any;
    distmax: any;
    distmin: any;
    dot: any;
    edgesum: any;
    fiedler_vector: any;
    fix_distance_matrix: any;
    flatten: any;
    floyd_warshall_path: any;
    floyd_warshall_with_path: any;
    graph: any;
    graph2mat: any;
    graph2valuemats: any;
    graph_connect: any;
    graph_empty: any;
    graph_empty_nodes: any;
    graph_random: any;
    graph_random_erdos_renyi: any;
    hcluster: any;
    infinities: any;
    intersect_sorted_ints: any;
    inverse_permutation: any;
    laplacian: any;
    length: any;
    linear_arrangement: any;
    mat2graph: any;
    mean: any;
    meancolumns: any;
    meantranspose: any;
    morans_i: any;
    mult_adjacent_exchange: any;
    mult_barycenter: any;
    mult_barycenter_order: any;
    mult_dist: any;
    nn_2opt: any;
    normalize: any;
    optimal_leaf_order: any;
    order: any;
    parcoords: any;
    parcoords_es: any;
    pca1d: any;
    pcp: any;
    permutation: any;
    permute_inplace: any;
    permute_matrix: any;
    permutetranspose: any;
    poweriteration: any;
    poweriteration_n: any;
    printhcluster: any;
    printmat: any;
    printvec: any;
    profile: any;
    randomPermutation: any;
    randomPermute: any;
    random_array: any;
    range: any;
    reverse_cuthill_mckee: any;
    reverse_cuthill_mckee_order: any;
    set_debug: any;
    sort_order: any;
    sort_order_ascending: any;
    sort_order_descending: any;
    spectral_order: any;
    stablepermute: any;
    sum: any;
    transpose: any;
    transposeSlice: any;
    union: any;
    valuemats_reorder: any;
    variancecovariance: any;
    version: "2.2.5"
    zeroes: any;
}

export default reorder as unknown as ReorderJsLibrary;