package com.core.ui;

import com.core.Controller;
import com.core.client.ICoreClient;
import com.core.data.CoreInterface;
import com.core.data.CoreLink;
import com.core.data.CoreLinkOptions;
import com.core.data.CoreNode;
import com.core.graph.NetworkGraph;
import com.core.ui.textfields.DoubleFilter;
import com.core.utils.FxmlUtils;
import com.jfoenix.controls.JFXButton;
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
import javafx.scene.control.TextFormatter;
import javafx.scene.layout.GridPane;
import javafx.util.converter.DoubleStringConverter;
import org.apache.logging.log4j.LogManager;
import org.apache.logging.log4j.Logger;

import java.io.IOException;

public class LinkDetails extends ScrollPane {
    private static final Logger logger = LogManager.getLogger();
    private static final int START_INDEX = 1;
    private final Controller controller;
    private int index = START_INDEX;
    @FXML private GridPane gridPane;

    public LinkDetails(Controller controller) {
        this.controller = controller;
        FxmlUtils.loadRootController(this, "/fxml/link_details.fxml");
        setPrefWidth(400);
    }

    public void setLink(CoreLink link) {
        NetworkGraph graph = controller.getNetworkGraph();
        ICoreClient coreClient = controller.getCoreClient();
        clear();
        addSeparator();

        CoreNode nodeOne = graph.getVertex(link.getNodeOne());
        CoreInterface interfaceOne = link.getInterfaceOne();
        addLabel(nodeOne.getName());
        if (interfaceOne != null) {
            addInterface(interfaceOne);
        }

        CoreNode nodeTwo = graph.getVertex(link.getNodeTwo());
        CoreInterface interfaceTwo = link.getInterfaceTwo();
        addLabel(nodeTwo.getName());
        if (interfaceTwo != null) {
            addInterface(interfaceTwo);
        }

        addLabel("Properties");
        JFXTextField bandwidthField = addRow("Bandwidth (bps)", link.getOptions().getBandwidth());
        JFXTextField delayField = addRow("Delay (us)", link.getOptions().getDelay());
        JFXTextField jitterField = addRow("Jitter (us)", link.getOptions().getJitter());
        JFXTextField lossField = addRow("Loss (%)", link.getOptions().getPer());
        JFXTextField dupsField = addRow("Duplicate (%)", link.getOptions().getDup());
        addButton("Update", event -> {
            CoreLinkOptions options = link.getOptions();
            options.setBandwidth(getDouble(bandwidthField));
            options.setDelay(getDouble(delayField));
            options.setJitter(getDouble(jitterField));
            options.setPer(getDouble(lossField));
            options.setDup(getDouble(dupsField));

            if (coreClient.isRunning()) {
                try {
                    coreClient.editLink(link);
                    Toast.info("Link updated!");
                } catch (IOException ex) {
                    Toast.error("Failure to update link", ex);
                }
            }
        });
    }

    private Double getDouble(JFXTextField textField) {
        if (textField.getText() == null) {
            return null;
        }

        Double value = null;
        try {
            logger.info("double field text: {}", textField.getText());
            value = Double.parseDouble(textField.getText());
        } catch (NumberFormatException ex) {
            logger.error("error getting double value", ex);
        }
        return value;
    }

    private void addButton(String text, EventHandler<ActionEvent> handler) {
        JFXButton button = new JFXButton(text);
        button.getStyleClass().add("core-button");
        button.setMaxWidth(Double.MAX_VALUE);
        button.setOnAction(handler);
        gridPane.add(button, 0, index++, 2, 1);
        GridPane.setMargin(button, new Insets(10, 0, 0, 0));
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

    private void addInterface(CoreInterface coreInterface) {
        addRow("Interface", coreInterface.getName(), true);
        addRow("MAC", coreInterface.getMac(), true);
        addAddress("IP4", coreInterface.getIp4());
        addAddress("IP6", coreInterface.getIp6());
    }

    private void addRow(String labelText, String value, boolean disabled) {
        if (value == null) {
            return;
        }
        Label label = new Label(labelText);
        JFXTextField textField = new JFXTextField(value);
        textField.setDisable(disabled);
        gridPane.addRow(index++, label, textField);
    }

    private JFXTextField addRow(String labelText, Double value) {
        Label label = new Label(labelText);
        String doubleString = null;
        if (value != null) {
            doubleString = value.toString();
        }
        JFXTextField textField = new JFXTextField();
        TextFormatter<Double> formatter = new TextFormatter<>(
                new DoubleStringConverter(), null, new DoubleFilter());
        textField.setTextFormatter(formatter);
        textField.setText(doubleString);
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
