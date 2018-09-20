package com.core.ui;

import com.core.data.CoreInterface;
import com.core.data.CoreLink;
import com.core.data.CoreNode;
import com.core.graph.NetworkGraph;
import com.core.utils.FxmlUtils;
import com.jfoenix.controls.JFXTextField;
import javafx.fxml.FXML;
import javafx.geometry.Insets;
import javafx.geometry.Orientation;
import javafx.scene.control.Label;
import javafx.scene.control.ScrollPane;
import javafx.scene.control.Separator;
import javafx.scene.layout.GridPane;
import org.apache.logging.log4j.LogManager;
import org.apache.logging.log4j.Logger;

public class LinkDetails extends ScrollPane {
    private static final Logger logger = LogManager.getLogger();
    private static final int START_INDEX = 1;
    private NetworkGraph graph;
    private int index = START_INDEX;
    @FXML private GridPane gridPane;

    public LinkDetails(NetworkGraph graph) {
        this.graph = graph;
        FxmlUtils.loadRootController(this, "/fxml/link_details.fxml");
    }

    public void setLink(CoreLink link) {
        clear();

        addSeparator();
        CoreNode nodeOne = graph.getVertex(link.getNodeOne());
        CoreInterface interfaceOne = link.getInterfaceOne();
        addLabel(nodeOne.getName());
        if (interfaceOne != null) {
            addInterface(interfaceOne);
        }
        addSeparator();

        CoreNode nodeTwo = graph.getVertex(link.getNodeTwo());
        CoreInterface interfaceTwo = link.getInterfaceTwo();
        addLabel(nodeTwo.getName());
        if (interfaceTwo != null) {
            addInterface(interfaceTwo);
        }
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
