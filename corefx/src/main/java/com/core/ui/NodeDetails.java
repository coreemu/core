package com.core.ui;

import com.core.Controller;
import com.core.data.CoreInterface;
import com.core.data.CoreLink;
import com.core.data.CoreNode;
import com.core.data.NodeType;
import com.jfoenix.controls.JFXListView;
import com.jfoenix.controls.JFXScrollPane;
import com.jfoenix.controls.JFXTextField;
import org.apache.logging.log4j.LogManager;
import org.apache.logging.log4j.Logger;

import java.util.Collections;
import java.util.Set;

public class NodeDetails extends DetailsPanel {
    private static final Logger logger = LogManager.getLogger();

    public NodeDetails(Controller controller) {
        super(controller);
    }

    public void setNode(CoreNode node) {
        clear();
        boolean sessionRunning = controller.getCoreClient().isRunning();

        setTitle(node.getName());
        addSeparator();

        addLabel("Properties");
        addRow("ID", node.getId().toString(), true);
        if (node.getType() == NodeType.DEFAULT) {
            addRow("Model", node.getModel(), true);
        } else {
            addRow("Type", node.getNodeType().getDisplay(), true);
        }
        addRow("X", node.getPosition().getX().toString(), true);
        addRow("Y", node.getPosition().getY().toString(), true);

        if (node.getType() == NodeType.EMANE) {
            addRow("EMANE", node.getEmane(), true);
        }

        if (node.getType() == NodeType.DOCKER || node.getType() == NodeType.LXC) {
            setContainerDetails(node, sessionRunning);
        }

        boolean firstInterface = true;
        for (CoreLink link : controller.getNetworkGraph().getGraph().getIncidentEdges(node)) {
            if (firstInterface) {
                firstInterface = false;
                addLabel("Interfaces");
            } else {
                addSeparator();
            }

            CoreNode linkedNode;
            CoreInterface coreInterface;
            if (node.getId().equals(link.getNodeOne())) {
                coreInterface = link.getInterfaceOne();
                linkedNode = controller.getNetworkGraph().getNodeMap().get(link.getNodeTwo());
            } else {
                coreInterface = link.getInterfaceTwo();
                linkedNode = controller.getNetworkGraph().getNodeMap().get(link.getNodeOne());
            }

            if (coreInterface == null) {
                continue;
            }

            if (linkedNode.getType() == NodeType.EMANE) {
                String emaneModel = linkedNode.getEmane();
                String linkedLabel = String.format("%s - %s", linkedNode.getName(), emaneModel);
                addButton(linkedLabel, event -> controller.getNodeEmaneDialog()
                        .displayEmaneModelConfig(linkedNode.getId(), emaneModel));
                String nodeLabel = String.format("%s - %s", node.getName(), emaneModel);
                addButton(nodeLabel, event -> controller.getNodeEmaneDialog()
                        .displayEmaneModelConfig(node.getId(), emaneModel));
                String interfaceLabel = String.format("%s - %s", coreInterface.getName(), emaneModel);
                Integer interfaceId = 1000 * node.getId() + coreInterface.getId();
                addButton(interfaceLabel, event -> controller.getNodeEmaneDialog()
                        .displayEmaneModelConfig(interfaceId, emaneModel));
            }

            if (linkedNode.getType() == NodeType.WLAN) {
                addButton(linkedNode.getName(), event -> controller.getNodeWlanDialog().showDialog(linkedNode));
            }
            addInterface(coreInterface, linkedNode);
        }

        // display custom or default node services
        Set<String> services = node.getServices();
        if (services.isEmpty()) {
            services = controller.getDefaultServices().getOrDefault(node.getModel(), Collections.emptySet());
        }

        if (!services.isEmpty()) {
            addLabel("Services");
            JFXListView<String> listView = new JFXListView<>();
            listView.setMouseTransparent(true);
            listView.setFocusTraversable(false);
            listView.getItems().setAll(services);
            gridPane.add(listView, 0, index++, 2, 1);
        }

        JFXScrollPane.smoothScrolling(scrollPane);
    }

    private void setContainerDetails(CoreNode node, boolean sessionRunning) {
        JFXTextField imageField = addRow("Image", node.getImage(), sessionRunning);
        if (!sessionRunning) {
            addButton("Update", event -> {
                if (node.getType() == NodeType.DOCKER || node.getType() == NodeType.LXC) {
                    node.setImage(imageField.getText());
                }
            });
        }
    }
}
