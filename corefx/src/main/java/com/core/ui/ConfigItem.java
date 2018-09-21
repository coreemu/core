package com.core.ui;

import com.core.client.rest.ConfigOption;
import com.core.data.ConfigDataType;
import com.jfoenix.controls.JFXButton;
import com.jfoenix.controls.JFXComboBox;
import com.jfoenix.controls.JFXTextField;
import com.jfoenix.controls.JFXToggleButton;
import javafx.scene.Node;
import javafx.scene.control.Label;
import javafx.scene.layout.ColumnConstraints;
import javafx.scene.layout.GridPane;
import javafx.stage.FileChooser;
import javafx.stage.Stage;
import javafx.stage.Window;
import lombok.Data;

import java.io.File;

@Data
public class ConfigItem {
    private final Window window;
    private ConfigOption option;
    private Label label;
    private Node node;

    public ConfigItem(Stage window, ConfigOption option) {
        this.window = window;
        this.option = option;
        label = new Label(option.getLabel());
        createNode();
    }

    private void createNode() {
        ConfigDataType dataType = ConfigDataType.get(option.getType());
        switch (dataType) {
            case BOOL:
                node = booleanConfig();
                break;
            default:
                if (!option.getSelect().isEmpty()) {
                    node = optionsConfig();
                } else if (option.getLabel().contains("file")) {
                    node = fileConfigItem();
                } else {
                    node = defaultConfigItem();
                }
                break;
        }
    }

    public ConfigOption getOption() {
        String value;
        ConfigDataType dataType = ConfigDataType.get(option.getType());
        switch (dataType) {
            case BOOL:
                JFXToggleButton button = (JFXToggleButton) node;
                if (button.isSelected()) {
                    value = "1";
                } else {
                    value = "0";
                }
                break;
            default:
                if (!option.getSelect().isEmpty()) {
                    JFXComboBox<String> comboBox = (JFXComboBox<String>) node;
                    value = comboBox.getSelectionModel().getSelectedItem();
                } else {
                    JFXTextField textField = (JFXTextField) node;
                    value = textField.getText();
                }
                break;
        }
        option.setValue(value);
        return option;
    }

    private GridPane fileConfigItem() {
        GridPane gridPane = new GridPane();
        gridPane.setHgap(10);
        JFXTextField textField = new JFXTextField(option.getValue());
        textField.setMaxWidth(Double.MAX_VALUE);
        gridPane.addColumn(0, textField);
        JFXButton button = new JFXButton("File");
        button.setMaxWidth(Double.MAX_VALUE);
        button.getStyleClass().add("core-button");
        gridPane.addColumn(1, button);
        ColumnConstraints firstColumn = new ColumnConstraints(10);
        firstColumn.setPercentWidth(80);
        ColumnConstraints secondColumn = new ColumnConstraints(10);
        secondColumn.setPercentWidth(20);
        gridPane.getColumnConstraints().addAll(firstColumn, secondColumn);
        button.setOnAction(event -> {
            FileChooser fileChooser = new FileChooser();
            fileChooser.setTitle("Select File");
            fileChooser.setInitialDirectory(new File(System.getProperty("user.home")));
            File file = fileChooser.showOpenDialog(window);
            if (file != null) {
                textField.setText(file.getPath());
            }
        });
        return gridPane;
    }

    private JFXTextField defaultConfigItem() {
        JFXTextField textField = new JFXTextField(option.getValue());
        textField.setMaxWidth(Double.MAX_VALUE);
        return textField;
    }

    private JFXToggleButton booleanConfig() {
        JFXToggleButton button = new JFXToggleButton();
        button.setMaxWidth(Double.MAX_VALUE);
        if ("1".equals(option.getValue())) {
            button.setSelected(true);
        }
        return button;
    }

    private JFXComboBox<String> optionsConfig() {
        JFXComboBox<String> comboBox = new JFXComboBox<>();
        comboBox.setMaxWidth(Double.MAX_VALUE);
        comboBox.getItems().addAll(option.getSelect());
        comboBox.getSelectionModel().select(option.getValue());
        return comboBox;
    }
}
