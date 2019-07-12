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
import inet.ipaddr.IPAddress;
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

import java.util.Collections;
import java.util.Set;

public class NodeDetails extends ScrollPane {
    private static final Logger logger = LogManager.getLogger();
    private static final int START_INDEX = 1;
    private final Controller controller;
    @FXML private Label title;
    @FXML private ScrollPane scrollPane;
    @FXML private GridPane gridPane;
    private int index = START_INDEX;

    public NodeDetails(Controller controller) {
        this.controller = controller;
        FxmlUtils.loadRootController(this, "/fxml/node_details.fxml");
        setPrefWidth(400);
    }

    public void setNode(CoreNode node) {
        clear();
        boolean sessionRunning = controller.getCoreClient().isRunning();

        title.setText(node.getName());
        addSeparator();

        addLabel("Properties");
        addRow("ID", node.getId().toString(), true);
        if (node.getType() == NodeType.DEFAULT) {
            addRow("Model", node.getModel(), true);
        } else {
            addRow("Type", node.getNodeType().getDisplay(), true);
        }
        addRow("EMANE", node.getEmane(), true);
        addRow("X", node.getPosition().getX().toString(), true);
        addRow("Y", node.getPosition().getY().toString(), true);

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
        addButton("Update", event -> {
            if (node.getType() == NodeType.DOCKER || node.getType() == NodeType.LXC) {
                node.setImage(imageField.getText());
            }
        });
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
        label.getStyleClass().add("details-label");
        gridPane.add(label, 0, index++, 2, 1);
    }

    private void addSeparator() {
        Separator separator = new Separator(Orientation.HORIZONTAL);
        gridPane.add(separator, 0, index++, 2, 1);
        GridPane.setMargin(separator, new Insets(10, 0, 0, 0));
    }

    private void addInterface(CoreInterface coreInterface, CoreNode linkedNode) {
        addRow("Linked To", linkedNode.getName(), true);
        addRow("Interface", coreInterface.getName(), true);
        addRow("MAC", coreInterface.getMac(), true);
        addAddress("IP4", coreInterface.getIp4());
        addAddress("IP6", coreInterface.getIp6());
    }

    private JFXTextField addRow(String labelText, String value, boolean disabled) {
        Label label = new Label(labelText);
        JFXTextField textField = new JFXTextField(value);
        textField.setDisable(disabled);
        gridPane.addRow(index++, label, textField);
        return textField;
    }

    private void addAddress(String label, IPAddress ip) {
        if (ip == null) {
            return;
        }
        addRow(label, ip.toString(), true);
    }

    private void clear() {
        if (gridPane.getChildren().size() > START_INDEX) {
            gridPane.getChildren().remove(START_INDEX, gridPane.getChildren().size());
        }
        index = START_INDEX;
    }
}
