package com.core.ui;

import com.core.Controller;
import com.core.data.CoreInterface;
import com.core.data.CoreNode;
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
import javafx.util.converter.IntegerStringConverter;
import org.apache.logging.log4j.LogManager;
import org.apache.logging.log4j.Logger;

import java.util.function.UnaryOperator;

abstract class DetailsPanel extends ScrollPane {
    private static final Logger logger = LogManager.getLogger();
    private static final int START_INDEX = 1;
    final Controller controller;
    @FXML Label title;
    @FXML ScrollPane scrollPane;
    @FXML GridPane gridPane;
    int index = START_INDEX;

    DetailsPanel(Controller controller) {
        this.controller = controller;
        FxmlUtils.loadRootController(this, "/fxml/details_panel.fxml");
        setPrefWidth(400);
    }

    void setTitle(String text) {
        title.setText(text);
    }

    void addButton(String text, EventHandler<ActionEvent> handler) {
        JFXButton emaneButton = new JFXButton(text);
        emaneButton.getStyleClass().add("core-button");
        emaneButton.setMaxWidth(Double.MAX_VALUE);
        emaneButton.setOnAction(handler);
        gridPane.add(emaneButton, 0, index++, 2, 1);
    }

    void addLabel(String text) {
        Label label = new Label(text);
        label.getStyleClass().add("details-label");
        gridPane.add(label, 0, index++, 2, 1);
    }

    void addSeparator() {
        Separator separator = new Separator(Orientation.HORIZONTAL);
        gridPane.add(separator, 0, index++, 2, 1);
        GridPane.setMargin(separator, new Insets(10, 0, 0, 0));
    }

    void addInterface(CoreInterface coreInterface, CoreNode linkedNode) {
        if (linkedNode != null) {
            addRow("Linked To", linkedNode.getName(), true);
        }
        addRow("Interface", coreInterface.getName(), true);
        if (coreInterface.getMac() != null) {
            addRow("MAC", coreInterface.getMac(), true);
        }
        addAddress("IP4", coreInterface.getIp4());
        addAddress("IP6", coreInterface.getIp6());
    }

    void addInterface(CoreInterface coreInterface) {
        addInterface(coreInterface, null);
    }

    JFXTextField addRow(String labelText, String value, boolean disabled) {
        Label label = new Label(labelText);
        JFXTextField textField = new JFXTextField(value);
        textField.setDisable(disabled);
        gridPane.addRow(index++, label, textField);
        return textField;
    }

    JFXTextField addDoubleRow(String labelText, Double value) {
        Label label = new Label(labelText);
        String valueString = null;
        if (value != null) {
            valueString = value.toString();
        }
        JFXTextField textField = new JFXTextField();
        TextFormatter<Double> formatter = new TextFormatter<>(
                new DoubleStringConverter(), null, new DoubleFilter());
        textField.setTextFormatter(formatter);
        textField.setText(valueString);
        gridPane.addRow(index++, label, textField);
        return textField;
    }

    Double getDouble(JFXTextField textField) {
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

    JFXTextField addIntegerRow(String labelText, Integer value) {
        Label label = new Label(labelText);
        String valueString = null;
        if (value != null) {
            valueString = value.toString();
        }
        JFXTextField textField = new JFXTextField();
        UnaryOperator<TextFormatter.Change> filter = change -> {
            String text = change.getText();
            if (text.matches("[0-9]*")) {
                return change;
            }
            return null;
        };
        TextFormatter<Integer> formatter = new TextFormatter<>(
                new IntegerStringConverter(), null, filter);
        textField.setTextFormatter(formatter);
        textField.setText(valueString);
        gridPane.addRow(index++, label, textField);
        return textField;
    }

    Integer getInteger(JFXTextField textField) {
        if (textField.getText() == null) {
            return null;
        }

        Integer value = null;
        try {
            logger.info("integer field text: {}", textField.getText());
            value = Integer.parseInt(textField.getText());
        } catch (NumberFormatException ex) {
            logger.error("error getting integer value", ex);
        }
        return value;
    }

    private void addAddress(String label, IPAddress ip) {
        if (ip == null) {
            return;
        }
        addRow(label, ip.toString(), true);
    }

    void clear() {
        if (gridPane.getChildren().size() > START_INDEX) {
            gridPane.getChildren().remove(START_INDEX, gridPane.getChildren().size());
        }
        index = START_INDEX;
    }
}
