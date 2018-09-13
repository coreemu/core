package com.core.ui;

import com.core.Controller;
import com.core.data.CoreInterface;
import com.core.data.CoreLink;
import com.core.data.CoreNode;
import com.core.data.NodeType;
import com.jfoenix.controls.JFXButton;
import com.jfoenix.controls.JFXListView;
import com.jfoenix.controls.JFXScrollPane;
import com.jfoenix.controls.JFXTextField;
import javafx.event.ActionEvent;
import javafx.event.EventHandler;
import javafx.fxml.FXML;
import javafx.fxml.FXMLLoader;
import javafx.geometry.Insets;
import javafx.geometry.Orientation;
import javafx.scene.control.Label;
import javafx.scene.control.ScrollPane;
import javafx.scene.control.Separator;
import javafx.scene.layout.GridPane;
import org.apache.logging.log4j.LogManager;
import org.apache.logging.log4j.Logger;

import java.io.IOException;

public class NodeDetails extends ScrollPane {
    private static final Logger logger = LogManager.getLogger();
    private static final int START_INDEX = 1;
    private final Controller controller;

    @FXML
    private ScrollPane scrollPane;

    @FXML
    private GridPane gridPane;

    private int index = START_INDEX;

    public NodeDetails(Controller controller) {
        this.controller = controller;
        FXMLLoader loader = new FXMLLoader(getClass().getResource("/fxml/node_details.fxml"));
        loader.setRoot(this);
        loader.setController(this);

        try {
            loader.load();
        } catch (IOException ex) {
            throw new RuntimeException(ex);
        }
    }

    public void setNode(CoreNode node) {
        clear();

        addSeparator();

        addRow("Name", node.getName());
        if (node.getType() == NodeType.DEFAULT) {
            addRow("Model", node.getModel());
        } else {
            addRow("Type", NodeType.getDisplay(node.getType()));
        }
        if (node.getEmane() != null) {
            addRow("EMANE", node.getEmane());
        }

        addSeparator();

        addRow("X", node.getPosition().getX().toString());
        addRow("Y", node.getPosition().getY().toString());

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
                addButton(linkedNode.getName(), event -> controller.getNodeEmaneDialog().showDialog(linkedNode));
            }

            if (linkedNode.getType() == NodeType.WLAN) {
                addButton(linkedNode.getName(), event -> controller.getNodeWlanDialog().showDialog(linkedNode));
            }
            addInterface(coreInterface);
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

    private void addInterface(CoreInterface coreInterface) {
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
