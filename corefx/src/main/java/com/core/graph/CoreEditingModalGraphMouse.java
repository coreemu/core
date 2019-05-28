package com.core.graph;

import com.core.Controller;
import com.google.common.base.Supplier;
import edu.uci.ics.jung.visualization.RenderContext;
import edu.uci.ics.jung.visualization.control.EditingModalGraphMouse;

public class CoreEditingModalGraphMouse<V, E> extends EditingModalGraphMouse<V, E> {
    public CoreEditingModalGraphMouse(Controller controller, NetworkGraph networkGraph,
                                      RenderContext<V, E> rc, Supplier<V> vertexFactory, Supplier<E> edgeFactory) {
        super(rc, vertexFactory, edgeFactory);
        remove(annotatingPlugin);
        remove(popupEditingPlugin);
        annotatingPlugin = new CoreAnnotatingGraphMousePlugin<>(controller, rc);
        popupEditingPlugin = new CorePopupGraphMousePlugin<>(controller, networkGraph, vertexFactory, edgeFactory);
    }
}
