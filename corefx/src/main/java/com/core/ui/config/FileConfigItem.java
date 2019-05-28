package com.core.ui.config;

import com.core.data.ConfigOption;
import com.jfoenix.controls.JFXButton;
import com.jfoenix.controls.JFXTextField;
import javafx.scene.Node;
import javafx.scene.layout.ColumnConstraints;
import javafx.scene.layout.GridPane;
import javafx.scene.layout.Priority;
import javafx.scene.layout.RowConstraints;
import javafx.stage.FileChooser;
import javafx.stage.Stage;

import java.io.File;

public class FileConfigItem extends BaseConfigItem {
    private GridPane gridPane;

    public FileConfigItem(Stage stage, ConfigOption option) {
        super(stage, option);
        gridPane = new GridPane();
        gridPane.setHgap(5);
        gridPane.setMaxWidth(Double.MAX_VALUE);
        RowConstraints rowConstraints = new RowConstraints();
        rowConstraints.setVgrow(Priority.SOMETIMES);
        ColumnConstraints textFieldConstraints = new ColumnConstraints();
        textFieldConstraints.setHgrow(Priority.SOMETIMES);
        textFieldConstraints.setPercentWidth(60);
        ColumnConstraints buttonConstraints = new ColumnConstraints();
        buttonConstraints.setHgrow(Priority.SOMETIMES);
        buttonConstraints.setPercentWidth(40);
        gridPane.getColumnConstraints().addAll(textFieldConstraints, buttonConstraints);

        JFXTextField textField = new JFXTextField();
        textField.setMaxWidth(Double.MAX_VALUE);
        textField.textProperty().addListener(((observable, oldValue, newValue) -> getOption().setValue(newValue)));
        JFXButton button = new JFXButton("Select File");
        button.getStyleClass().add("core-button");
        button.setMaxWidth(Double.MAX_VALUE);
        button.setOnAction(event -> {
            FileChooser fileChooser = new FileChooser();
            fileChooser.setTitle("Select File");
            fileChooser.setInitialDirectory(new File(System.getProperty("user.home")));
            File file = fileChooser.showOpenDialog(stage);
            if (file != null) {
                textField.setText(file.getPath());
            }
        });
        gridPane.addRow(0, textField, button);
    }

    @Override
    public Node getNode() {
        return gridPane;
    }
}
