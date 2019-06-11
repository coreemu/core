package com.core.graph;

import edu.uci.ics.jung.graph.UndirectedSparseGraph;
import edu.uci.ics.jung.graph.util.EdgeType;
import edu.uci.ics.jung.graph.util.Pair;

public class UndirectedSimpleGraph<V, E> extends UndirectedSparseGraph<V, E> {
    @Override
    public boolean addEdge(E edge, Pair<? extends V> endpoints, EdgeType edgeType) {
        Pair<V> newEndpoints = getValidatedEndpoints(edge, endpoints);
        if (newEndpoints == null) {
            return false;
        }

        V first = newEndpoints.getFirst();
        V second = newEndpoints.getSecond();

        if (first.equals(second)) {
            return false;
        } else {
            return super.addEdge(edge, endpoints, edgeType);
        }
    }
}
