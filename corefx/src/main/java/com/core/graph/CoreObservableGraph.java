package com.core.graph;

import edu.uci.ics.jung.graph.Graph;
import edu.uci.ics.jung.graph.ObservableGraph;
import edu.uci.ics.jung.graph.util.EdgeType;
import org.apache.logging.log4j.LogManager;
import org.apache.logging.log4j.Logger;

public class CoreObservableGraph<V, E> extends ObservableGraph<V, E> {
    private static final Logger logger = LogManager.getLogger();

    public CoreObservableGraph(Graph<V, E> graph) {
        super(graph);
    }

    @Override
    public boolean addEdge(E e, V v1, V v2, EdgeType edgeType) {
        if (v1 == null || v2 == null) {
            return false;
        }
        return super.addEdge(e, v1, v2, edgeType);
    }

    @Override
    public boolean addEdge(E e, V v1, V v2) {
        if (v1 == null || v2 == null) {
            return false;
        }
        return super.addEdge(e, v1, v2);
    }
}
