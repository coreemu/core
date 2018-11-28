package com.core.graph;

import com.core.Controller;
import com.core.data.CoreLink;
import com.core.data.CoreNode;
import com.core.data.NodeType;
import com.google.common.base.Supplier;
import edu.uci.ics.jung.algorithms.layout.GraphElementAccessor;
import edu.uci.ics.jung.algorithms.layout.Layout;
import edu.uci.ics.jung.visualization.control.EditingPopupGraphMousePlugin;
import javafx.application.Platform;
import javafx.scene.control.ContextMenu;
import org.apache.logging.log4j.LogManager;
import org.apache.logging.log4j.Logger;

import java.awt.event.MouseEvent;
import java.awt.geom.Point2D;

public class CorePopupGraphMousePlugin<V, E> extends EditingPopupGraphMousePlugin<V, E> {
    private static final Logger logger = LogManager.getLogger();
    private final Controller controller;
    private final NetworkGraph networkGraph;
    private final Layout<CoreNode, CoreLink> graphLayout;
    private final GraphElementAccessor<CoreNode, CoreLink> pickSupport;

    public CorePopupGraphMousePlugin(Controller controller, NetworkGraph networkGraph,
                                     Supplier<V> vertexFactory, Supplier<E> edgeFactory) {
        super(vertexFactory, edgeFactory);
        this.controller = controller;
        this.networkGraph = networkGraph;
        graphLayout = this.networkGraph.getGraphLayout();
        pickSupport = this.networkGraph.getGraphViewer().getPickSupport();
    }

    @Override
    protected void handlePopup(MouseEvent e) {
        logger.info("showing popup!");
        final Point2D p = e.getPoint();

        final CoreNode node = pickSupport.getVertex(graphLayout, p.getX(), p.getY());
        final CoreLink link = pickSupport.getEdge(graphLayout, p.getX(), p.getY());

        final ContextMenu contextMenu;
        if (node != null) {
            contextMenu = handleNodeContext(node);
        } else if (link != null) {
            contextMenu = new LinkContextMenu(controller, link);
        } else {
            contextMenu = new ContextMenu();
        }

        if (!contextMenu.getItems().isEmpty()) {
            logger.info("showing context menu");
            Platform.runLater(() -> contextMenu.show(controller.getWindow(),
                    e.getXOnScreen(), e.getYOnScreen()));
        }
    }

    private ContextMenu handleNodeContext(final CoreNode node) {
        ContextMenu contextMenu = new ContextMenu();
        switch (node.getType()) {
            case NodeType.DEFAULT:
                contextMenu = new NodeContextMenu(controller, node);
                break;
            case NodeType.WLAN:
                contextMenu = new WlanContextMenu(controller, node);
                break;
            case NodeType.EMANE:
                contextMenu = new EmaneContextMenu(controller, node);
                break;
            default:
                logger.warn("no context menu for node: {}", node.getType());
                break;
        }

        return contextMenu;
    }
}
