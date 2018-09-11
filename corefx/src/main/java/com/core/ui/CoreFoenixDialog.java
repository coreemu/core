package com.core.ui;

import com.core.Controller;
import com.core.CoreClient;
import com.jfoenix.controls.JFXButton;
import com.jfoenix.controls.JFXDialog;
import com.jfoenix.controls.JFXDialogLayout;
import javafx.fxml.FXMLLoader;
import javafx.scene.Parent;
import javafx.scene.text.Text;
import javafx.stage.Stage;
import lombok.Data;
import org.apache.logging.log4j.LogManager;
import org.apache.logging.log4j.Logger;

import java.io.IOException;

@Data
public class CoreFoenixDialog extends JFXDialog {
    private static final Logger logger = LogManager.getLogger();
    private final Controller controller;
    private final JFXDialog dialog;
    private final JFXDialogLayout dialogLayout = new JFXDialogLayout();
    private final Text heading = new Text();

    public CoreFoenixDialog(Controller controller, String fxmlPath) {
        this.controller = controller;

        FXMLLoader loader = new FXMLLoader(getClass().getResource(fxmlPath));
        loader.setController(this);

        try {
            Parent parent = loader.load();
            dialogLayout.setBody(parent);
        } catch (IOException ex) {
            logger.error("error loading fxml: {}", fxmlPath, ex);
            throw new RuntimeException(ex);
        }

        dialogLayout.setHeading(heading);
        dialog = new JFXDialog(controller.getStackPane(), dialogLayout, DialogTransition.CENTER);
        dialogLayout.setPrefWidth(800);
        dialogLayout.setPrefHeight(600);;
    }

    public void setOwner(Stage window) {
    }

    public CoreClient getCoreClient() {
        return controller.getCoreClient();
    }

    public JFXButton createButton(String text) {
        JFXButton button = new JFXButton(text);
        button.getStyleClass().add("core-button");
        return button;
    }
}
