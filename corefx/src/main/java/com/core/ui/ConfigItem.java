package com.core.ui;

import com.core.data.ConfigDataType;
import com.core.client.rest.ConfigOption;
import com.jfoenix.controls.JFXComboBox;
import com.jfoenix.controls.JFXTextField;
import com.jfoenix.controls.JFXToggleButton;
import javafx.scene.Node;
import javafx.scene.control.Label;
import lombok.Data;

@Data
public class ConfigItem {
    private ConfigOption option;
    private Label label;
    private Node node;

    public ConfigItem(ConfigOption option) {
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
