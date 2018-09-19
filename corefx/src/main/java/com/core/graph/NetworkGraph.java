package com.core.graph;

import com.core.Controller;
import com.core.data.*;
import com.core.ui.Toast;
import com.core.utils.IconUtils;
import com.google.common.base.Supplier;
import edu.uci.ics.jung.algorithms.layout.StaticLayout;
import edu.uci.ics.jung.graph.ObservableGraph;
import edu.uci.ics.jung.graph.event.GraphEvent;
import edu.uci.ics.jung.graph.event.GraphEventListener;
import edu.uci.ics.jung.graph.util.Pair;
import edu.uci.ics.jung.visualization.RenderContext;
import edu.uci.ics.jung.visualization.VisualizationViewer;
import edu.uci.ics.jung.visualization.annotations.AnnotationControls;
import edu.uci.ics.jung.visualization.control.EditingModalGraphMouse;
import edu.uci.ics.jung.visualization.control.GraphMouseListener;
import edu.uci.ics.jung.visualization.control.ModalGraphMouse;
import edu.uci.ics.jung.visualization.decorators.EdgeShape;
import edu.uci.ics.jung.visualization.renderers.Renderer;
import lombok.Data;
import org.apache.commons.net.util.SubnetUtils;
import org.apache.logging.log4j.LogManager;
import org.apache.logging.log4j.Logger;

import javax.swing.*;
import java.awt.*;
import java.awt.event.MouseEvent;
import java.awt.geom.Ellipse2D;
import java.io.IOException;
import java.util.*;
import java.util.List;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.TimeUnit;
import java.util.stream.Collectors;


@Data
public class NetworkGraph {
    private static final Logger logger = LogManager.getLogger();
    private Controller controller;
    private ObservableGraph<CoreNode, CoreLink> graph;
    private StaticLayout<CoreNode, CoreLink> graphLayout;
    private VisualizationViewer<CoreNode, CoreLink> graphViewer;
    private EditingModalGraphMouse<CoreNode, CoreLink> graphMouse;
    private AnnotationControls<CoreNode, CoreLink> annotationControls;

    private SubnetUtils subnetUtils = new SubnetUtils("10.0.0.0/24");
    private CoreAddresses coreAddresses = new CoreAddresses("10.0");
    private NodeType nodeType;
    private Map<Integer, CoreNode> nodeMap = new ConcurrentHashMap<>();
    private int vertexId = 1;
    private int linkId = 1;
    private Supplier<CoreNode> vertexFactory = () -> new CoreNode(vertexId++);
    private Supplier<CoreLink> linkFactory = () -> new CoreLink(linkId++);
    private CorePopupGraphMousePlugin customPopupPlugin;
    private CoreAnnotatingGraphMousePlugin<CoreNode, CoreLink> customAnnotatingPlugin;
    private BackgroundPaintable<CoreNode, CoreLink> backgroundPaintable;

    public NetworkGraph(Controller controller) {
        this.controller = controller;
        graph = new CoreObservableGraph<>(new UndirectedSimpleGraph<>());
        graph.addGraphEventListener(graphEventListener);
        graphLayout = new StaticLayout<>(graph);
        graphViewer = new VisualizationViewer<>(graphLayout);
        graphViewer.setBackground(Color.WHITE);
        graphViewer.getRenderer().getVertexLabelRenderer().setPosition(Renderer.VertexLabel.Position.S);

        RenderContext<CoreNode, CoreLink> renderContext = graphViewer.getRenderContext();

        // vertext render properties
        renderContext.setVertexLabelTransformer(CoreNode::getName);
        renderContext.setVertexShapeTransformer(node -> {
            double offset = -(IconUtils.ICON_SIZE / 2);
            return new Ellipse2D.Double(offset, offset, IconUtils.ICON_SIZE, IconUtils.ICON_SIZE);
        });
        renderContext.setVertexIconTransformer(vertex -> {
            long wirelessLinks = wirelessLinkCount(vertex);
            vertex.getRadioIcon().setWiressLinks(wirelessLinks);
            return vertex.getGraphIcon();
        });

        // edge render properties
        renderContext.setEdgeStrokeTransformer(edge -> {
            LinkTypes linkType = LinkTypes.get(edge.getType());
            if (LinkTypes.WIRELESS == linkType) {
                float[] dash = {15.0f};
                return new BasicStroke(5, BasicStroke.CAP_SQUARE, BasicStroke.JOIN_ROUND,
                        0, dash, 0);
            } else {
                return new BasicStroke(5);
            }
        });
        renderContext.setEdgeShapeTransformer(EdgeShape.line(graph));
        renderContext.setEdgeDrawPaintTransformer(edge -> {
            LinkTypes linkType = LinkTypes.get(edge.getType());
            if (LinkTypes.WIRELESS == linkType) {
                return Color.BLUE;
            } else {
                return Color.BLACK;
            }
        });
        renderContext.setEdgeIncludePredicate(predicate -> predicate.element.isVisible());

        graphViewer.setVertexToolTipTransformer(renderContext.getVertexLabelTransformer());
        graphMouse = new CoreEditingModalGraphMouse<>(controller, this, renderContext,
                vertexFactory, linkFactory);
        graphViewer.setGraphMouse(graphMouse);

        // mouse events
        graphViewer.addGraphMouseListener(new GraphMouseListener<CoreNode>() {
            @Override
            public void graphClicked(CoreNode node, MouseEvent mouseEvent) {
                // double click
                logger.info("click count: {}, running?: {}", mouseEvent.getClickCount(),
                        controller.getCoreClient().isRunning());

                if (mouseEvent.getClickCount() == 2 && controller.getCoreClient().isRunning()) {
                    try {
                        String terminalCommand = controller.getCoreClient().getTerminalCommand(node);
                        terminalCommand = String.format("gnome-terminal -x %s", terminalCommand);
                        logger.info("launching node terminal: {}", terminalCommand);
                        String[] commands = terminalCommand.split("\\s+");
                        logger.info("launching node terminal: {}", Arrays.toString(commands));
                        Process p = new ProcessBuilder(commands).start();
                        try {
                            if (!p.waitFor(5, TimeUnit.SECONDS)) {
                                Toast.error("Node terminal command failed");
                            }
                        } catch (InterruptedException ex) {
                            logger.error("error waiting for terminal to start", ex);
                        }
                    } catch (IOException ex) {
                        logger.error("error launching terminal", ex);
                        Toast.error("Node terminal failed to start");
                    }
                }
            }

            @Override
            public void graphPressed(CoreNode node, MouseEvent mouseEvent) {
                logger.debug("graph pressed: {} - {}", node, mouseEvent);
            }

            @Override
            public void graphReleased(CoreNode node, MouseEvent mouseEvent) {
                logger.info("graph released mouse event: {}", mouseEvent);
                if (SwingUtilities.isLeftMouseButton(mouseEvent)) {
                    double x = graphLayout.getX(node);
                    double y = graphLayout.getY(node);
                    logger.debug("graph moved node({}): {},{}", node.getName(), x, y);
                    node.getPosition().setX(x);
                    node.getPosition().setY(y);

                    // upate node when session is active
                    if (controller.getCoreClient().isRunning()) {
                        try {
                            controller.getCoreClient().editNode(node);
                        } catch (IOException ex) {
                            Toast.error("failed to update node location");
                        }
                    }
                }
            }
        });
    }

    public void setBackground(String imagePath) {
        try {
            backgroundPaintable = new BackgroundPaintable<>(imagePath, graphViewer);
            graphViewer.addPreRenderPaintable(backgroundPaintable);
            graphViewer.repaint();
        } catch (IOException ex) {
            logger.error("error setting background", ex);
        }
    }

    public void removeBackground() {
        if (backgroundPaintable != null) {
            graphViewer.removePreRenderPaintable(backgroundPaintable);
            graphViewer.repaint();
            backgroundPaintable = null;
        }
    }

    public void setMode(ModalGraphMouse.Mode mode) {
        graphMouse.setMode(mode);
    }

    public void reset() {
        logger.info("network graph reset");
        vertexId = 1;
        linkId = 1;
        for (CoreNode node : nodeMap.values()) {
            graph.removeVertex(node);
        }
        nodeMap.clear();
        graphViewer.repaint();
    }

    public void updatePositions() {
        for (CoreNode node : graph.getVertices()) {
            Double x = graphLayout.getX(node);
            Double y = graphLayout.getY(node);
            node.getPosition().setX(x);
            node.getPosition().setY(y);
            logger.debug("updating node position node({}): {},{}", node, x, y);
        }
    }

    public CoreNode getVertex(int id) {
        return nodeMap.get(id);
    }

    private GraphEventListener<CoreNode, CoreLink> graphEventListener = graphEvent -> {
        logger.info("graph event: {}", graphEvent.getType());
        switch (graphEvent.getType()) {
            case EDGE_ADDED:
                handleEdgeAdded((GraphEvent.Edge<CoreNode, CoreLink>) graphEvent);
                break;
            case EDGE_REMOVED:
                handleEdgeRemoved((GraphEvent.Edge<CoreNode, CoreLink>) graphEvent);
                break;
            case VERTEX_ADDED:
                handleVertexAdded((GraphEvent.Vertex<CoreNode, CoreLink>) graphEvent);
                break;
            case VERTEX_REMOVED:
                handleVertexRemoved((GraphEvent.Vertex<CoreNode, CoreLink>) graphEvent);
                break;
        }
    };

    private void handleEdgeAdded(GraphEvent.Edge<CoreNode, CoreLink> edgeEvent) {
        CoreLink link = edgeEvent.getEdge();
        if (!link.isLoaded()) {
            Pair<CoreNode> endpoints = graph.getEndpoints(link);

            CoreNode nodeOne = endpoints.getFirst();
            CoreNode nodeTwo = endpoints.getSecond();

            // create interfaces for nodes
            int sub = coreAddresses.getSubnet(
                    getInterfaces(nodeOne),
                    getInterfaces(nodeTwo)
            );

            link.setNodeOne(nodeOne.getId());
            if (isNode(nodeOne)) {
                int interfaceOneId = nextInterfaceId(nodeOne);
                CoreInterface interfaceOne = createInterface(nodeOne, sub, interfaceOneId);
                link.setInterfaceOne(interfaceOne);
            }

            link.setNodeTwo(nodeTwo.getId());
            if (isNode(nodeTwo)) {
                int interfaceTwoId = nextInterfaceId(nodeTwo);
                CoreInterface interfaceTwo = createInterface(nodeTwo, sub, interfaceTwoId);
                link.setInterfaceTwo(interfaceTwo);
            }

            boolean isVisible = !checkForWirelessNode(nodeOne, nodeTwo);
            link.setVisible(isVisible);

            logger.info("adding user created edge: {}", link);
        }
    }

    public List<CoreInterface> getInterfaces(CoreNode node) {
        return graph.getIncidentEdges(node).stream()
                .map(link -> {
                    if (node.getId().equals(link.getNodeOne())) {
                        return link.getInterfaceOne();
                    } else {
                        return link.getInterfaceTwo();
                    }
                })
                .filter(Objects::nonNull)
                .collect(Collectors.toList());
    }

    private int nextInterfaceId(CoreNode node) {
        Set<Integer> interfaceIds = graph.getIncidentEdges(node).stream()
                .map(link -> {
                    if (node.getId().equals(link.getNodeOne())) {
                        return link.getInterfaceOne();
                    } else {
                        return link.getInterfaceTwo();
                    }
                })
                .filter(Objects::nonNull)
                .map(CoreInterface::getId)
                .collect(Collectors.toSet());

        int i = 0;
        while (true) {
            if (!interfaceIds.contains(i)) {
                return i;
            }

            i += 1;
        }
    }

    private boolean isNode(CoreNode node) {
        return node.getType() == NodeType.DEFAULT;
    }

    private CoreInterface createInterface(CoreNode node, int sub, int interfaceId) {
        CoreInterface coreInterface = new CoreInterface();
        coreInterface.setId(interfaceId);
        coreInterface.setName(String.format("eth%s", interfaceId));
        String nodeOneIp4 = coreAddresses.getIp4Address(sub, node.getId());
        coreInterface.setIp4(nodeOneIp4);
        coreInterface.setIp4Mask(CoreAddresses.IP4_MASK);
        return coreInterface;
    }

    private void handleEdgeRemoved(GraphEvent.Edge<CoreNode, CoreLink> edgeEvent) {
        CoreLink link = edgeEvent.getEdge();
        logger.info("removed edge: {}", link);
    }

    private void handleVertexAdded(GraphEvent.Vertex<CoreNode, CoreLink> vertexEvent) {
        CoreNode node = vertexEvent.getVertex();
        if (!node.isLoaded()) {
            node.setNodeType(nodeType);
            if (node.getType() == NodeType.EMANE) {
                String emaneModel = controller.getNodeEmaneDialog().getModels().get(0);
                node.setEmane(emaneModel);
            }

            logger.info("adding user created node: {}", node);
            nodeMap.put(node.getId(), node);
        }
    }

    private void handleVertexRemoved(GraphEvent.Vertex<CoreNode, CoreLink> vertexEvent) {
        CoreNode node = vertexEvent.getVertex();
        logger.info("removed vertex: {}", node);
        nodeMap.remove(node.getId());
    }

    public void addNode(CoreNode node) {
        vertexId = Math.max(node.getId() + 1, node.getId());
        Double x = Math.abs(node.getPosition().getX());
        Double y = Math.abs(node.getPosition().getY());
        logger.info("adding session node: {}", node);
        graph.addVertex(node);
        graphLayout.setLocation(node, x, y);
        nodeMap.put(node.getId(), node);
    }

    public void setNodeLocation(CoreNode nodeData) {
        // update actual graph node
        CoreNode node = nodeMap.get(nodeData.getId());
        node.getPosition().setX(nodeData.getPosition().getX());
        node.getPosition().setY(nodeData.getPosition().getY());

        // set graph node location
        Double x = Math.abs(node.getPosition().getX());
        Double y = Math.abs(node.getPosition().getY());
        graphLayout.setLocation(node, x, y);
        graphViewer.repaint();
    }

    public void removeNode(CoreNode node) {
        try {
            controller.getCoreClient().deleteNode(node);
        } catch (IOException ex) {
            logger.error("error deleting node");
            Toast.error(String.format("Error deleting node: %s", node.getName()));
        }
        graphViewer.getPickedVertexState().pick(node, false);
        graph.removeVertex(node);
        graphViewer.repaint();
    }

    private boolean isWirelessNode(CoreNode node) {
        return node.getType() == NodeType.EMANE || node.getType() == NodeType.WLAN;
    }

    private boolean checkForWirelessNode(CoreNode nodeOne, CoreNode nodeTwo) {
        boolean result = isWirelessNode(nodeOne);
        return result || isWirelessNode(nodeTwo);
    }

    private long wirelessLinkCount(CoreNode node) {
        return graph.getNeighbors(node).stream()
                .filter(this::isWirelessNode)
                .count();
    }

    public void addLink(CoreLink link) {
        logger.info("adding session link: {}", link);
        link.setId(linkId++);
        CoreNode nodeOne = nodeMap.get(link.getNodeOne());
        CoreNode nodeTwo = nodeMap.get(link.getNodeTwo());

        boolean isVisible = !checkForWirelessNode(nodeOne, nodeTwo);
        link.setVisible(isVisible);

        graph.addEdge(link, nodeOne, nodeTwo);
    }

    public void removeWirelessLink(CoreLink link) {
        logger.info("deleting link: {}", link);
        CoreNode nodeOne = nodeMap.get(link.getNodeOne());
        CoreNode nodeTwo = nodeMap.get(link.getNodeTwo());

        CoreLink existingLink = graph.findEdge(nodeOne, nodeTwo);
        if (existingLink != null) {
            graph.removeEdge(existingLink);
        }
    }

    public void removeLink(CoreLink link) {
        graphViewer.getPickedEdgeState().pick(link, false);
        graph.removeEdge(link);
        graphViewer.repaint();
    }

    public void linkMdrs(CoreNode node) {
        for (CoreNode currentNode : graph.getVertices()) {
            if (!"mdr".equals(currentNode.getModel())) {
                continue;
            }

            // only links mdrs we have not already linked
            Collection<CoreLink> links = graph.findEdgeSet(node, currentNode);
            if (links.isEmpty()) {
                CoreLink link = linkFactory.get();
                graph.addEdge(link, currentNode, node);
                graphViewer.repaint();
            }
        }
    }
}
