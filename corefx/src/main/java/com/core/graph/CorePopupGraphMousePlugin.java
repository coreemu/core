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
import javafx.event.ActionEvent;
import javafx.event.EventHandler;
import javafx.scene.control.ContextMenu;
import javafx.scene.control.MenuItem;
import org.apache.logging.log4j.LogManager;
import org.apache.logging.log4j.Logger;

import java.awt.event.MouseEvent;
import java.awt.geom.Point2D;
import java.util.ArrayList;
import java.util.List;

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

        ContextMenu contextMenu = new ContextMenu();

        // edge picked
        if (node != null) {
            List<MenuItem> menuItems = handleNodeContext(node);
            contextMenu.getItems().addAll(menuItems);
        } else if (link != null) {
            List<MenuItem> menuItems = handleLinkContext(link);
            contextMenu.getItems().addAll(menuItems);
        }

        if (!contextMenu.getItems().isEmpty()) {
            logger.info("showing context menu");
            Platform.runLater(() -> contextMenu.show(controller.getWindow(),
                    e.getXOnScreen(), e.getYOnScreen()));
        }
    }

    private MenuItem createMenuItem(String text, EventHandler<ActionEvent> handler) {
        MenuItem menuItem = new MenuItem(text);
        menuItem.setOnAction(handler);
        return menuItem;
    }

    private List<MenuItem> handleNodeContext(final CoreNode node) {
        boolean isRunning = controller.getCoreClient().isRunning();

        List<MenuItem> menuItems = new ArrayList<>();

        switch (node.getType()) {
            case NodeType.DEFAULT:
                menuItems.add(createMenuItem("Services",
                        event -> controller.getNodeServicesDialog().showDialog(node)));
                break;
            case NodeType.WLAN:
                menuItems.add(createMenuItem("WLAN Settings",
                        event -> controller.getNodeWlanDialog().showDialog(node)));
                menuItems.add(createMenuItem("Mobility",
                        event -> controller.getMobilityDialog().showDialog(node)));
                menuItems.add(createMenuItem("Link MDRs",
                        event -> networkGraph.linkMdrs(node)));
                break;
            case NodeType.EMANE:
                menuItems.add(createMenuItem("EMANE Settings",
                        event -> controller.getNodeEmaneDialog().showDialog(node)));
                menuItems.add(createMenuItem("Mobility",
                        event -> controller.getMobilityDialog().showDialog(node)));
                menuItems.add(createMenuItem("Link MDRs",
                        event -> networkGraph.linkMdrs(node)));
                break;
            default:
                break;
        }

        if (!isRunning) {
            menuItems.add(createMenuItem("Delete Node",
                    event -> controller.deleteNode(node)));
        }

        return menuItems;
    }

    private List<MenuItem> handleLinkContext(final CoreLink link) {
        boolean isRunning = controller.getCoreClient().isRunning();

        List<MenuItem> menuItems = new ArrayList<>();

        if (!isRunning) {
            menuItems.add(createMenuItem("Delete Link",
                    event -> networkGraph.removeLink(link)));
        }

        return menuItems;
    }
}
