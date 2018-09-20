package com.core.ui;

import com.core.Controller;
import com.core.data.CoreInterface;
import com.core.data.CoreLink;
import com.core.data.CoreNode;
import com.core.data.NodeType;
import com.core.utils.FxmlUtils;
import com.jfoenix.controls.JFXButton;
import com.jfoenix.controls.JFXListView;
import com.jfoenix.controls.JFXScrollPane;
import com.jfoenix.controls.JFXTextField;
import javafx.event.ActionEvent;
import javafx.event.EventHandler;
import javafx.fxml.FXML;
import javafx.geometry.Insets;
import javafx.geometry.Orientation;
import javafx.scene.control.Label;
import javafx.scene.control.ScrollPane;
import javafx.scene.control.Separator;
import javafx.scene.layout.GridPane;
import org.apache.logging.log4j.LogManager;
import org.apache.logging.log4j.Logger;

public class NodeDetails extends ScrollPane {
    private static final Logger logger = LogManager.getLogger();
    private static final int START_INDEX = 1;
    private final Controller controller;
    @FXML private ScrollPane scrollPane;
    @FXML private GridPane gridPane;
    private int index = START_INDEX;

    public NodeDetails(Controller controller) {
        this.controller = controller;
        FxmlUtils.loadRootController(this, "/fxml/node_details.fxml");
        setPrefWidth(500);
    }

    public void setNode(CoreNode node) {
        clear();
        addSeparator();

        addRow("Name", node.getName());
        if (node.getType() == NodeType.DEFAULT) {
            addRow("Model", node.getModel());
        } else {
            addRow("Type", node.getNodeType().getDisplay());
        }
        if (node.getEmane() != null) {
            addRow("EMANE", node.getEmane());
        }

        addSeparator();

        if (node.getPosition().getX() != null) {
            addRow("X", node.getPosition().getX().toString());
        }
        if (node.getPosition().getY() != null) {
            addRow("Y", node.getPosition().getY().toString());
        }

        for (CoreLink link : controller.getNetworkGraph().getGraph().getIncidentEdges(node)) {
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

            addSeparator();
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


        if (!node.getServices().isEmpty()) {
            addSeparator();
            addLabel("Services");
            JFXListView<String> listView = new JFXListView<>();
            listView.setMouseTransparent(true);
            listView.setFocusTraversable(false);
            for (String service : node.getServices()) {
                listView.getItems().add(service);
            }
            gridPane.add(listView, 0, index++, 2, 1);
        }

        JFXScrollPane.smoothScrolling(scrollPane);
    }

    private void addButton(String text, EventHandler<ActionEvent> handler) {
        JFXButton emaneButton = new JFXButton(text);
        emaneButton.getStyleClass().add("core-button");
        emaneButton.setMaxWidth(Double.MAX_VALUE);
        emaneButton.setOnAction(handler);
        gridPane.add(emaneButton, 0, index++, 2, 1);
    }

    private void addLabel(String text) {
        Label label = new Label(text);
        label.getStyleClass().add("details-title");
        gridPane.add(label, 0, index++, 2, 1);
    }

    private void addSeparator() {
        Separator separator = new Separator(Orientation.HORIZONTAL);
        gridPane.add(separator, 0, index++, 2, 1);
        GridPane.setMargin(separator, new Insets(10, 0, 0, 0));
    }

    private void addInterface(CoreInterface coreInterface, CoreNode linkedNode) {
        addRow("Linked To", linkedNode.getName());
        addRow("Interface", coreInterface.getName());
        if (coreInterface.getMac() != null) {
            addRow("MAC", coreInterface.getMac());
        }
        addIp4Address(coreInterface.getIp4(), coreInterface.getIp4Mask());
        addIp6Address(coreInterface.getIp6(), coreInterface.getIp6Mask());
    }

    private void addRow(String labelText, String value) {
        Label label = new Label(labelText);
        JFXTextField textField = new JFXTextField(value);
        gridPane.addRow(index++, label, textField);
    }

    private void addIp4Address(String ip, Integer mask) {
        if (ip == null) {
            return;
        }
        addRow("IP4", String.format("%s/%s", ip, mask));
    }

    private void addIp6Address(String ip, String mask) {
        if (ip == null) {
            return;
        }
        addRow("IP6", String.format("%s/%s", ip, mask));
    }

    private void clear() {
        if (gridPane.getChildren().size() > START_INDEX) {
            gridPane.getChildren().remove(START_INDEX, gridPane.getChildren().size());
        }
        index = START_INDEX;
    }
}
