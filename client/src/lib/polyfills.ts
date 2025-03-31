if (Set.prototype.intersection === undefined) {
    Set.prototype.intersection = function <T>(other: Set<T>): Set<T> {
        const intersection = new Set<T>(this);
        for (const item of other)
            if (!intersection.has(item))
                intersection.delete(item);
        return intersection;
    }
}

if (Set.prototype.difference === undefined) {
    Set.prototype.difference = function <T>(other: Set<T>): Set<T> {
        const difference = new Set<T>(this);
        for (const item of other)
            difference.delete(item);
        return difference;
    }
}

if (Set.prototype.union === undefined) {
    Set.prototype.union = function <T>(other: Set<T>): Set<T> {
        const union = new Set<T>(this);
        for (const item of other)
            union.add(item);
        return union;
    }
}
