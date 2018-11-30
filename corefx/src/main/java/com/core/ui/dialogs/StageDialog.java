package com.core.ui.dialogs;

import com.core.Controller;
import com.core.client.ICoreClient;
import com.jfoenix.controls.JFXButton;
import com.jfoenix.controls.JFXDecorator;
import javafx.fxml.FXMLLoader;
import javafx.geometry.HPos;
import javafx.geometry.Insets;
import javafx.geometry.Pos;
import javafx.geometry.VPos;
import javafx.scene.Node;
import javafx.scene.Parent;
import javafx.scene.Scene;
import javafx.scene.image.Image;
import javafx.scene.image.ImageView;
import javafx.scene.input.KeyCode;
import javafx.scene.layout.*;
import javafx.stage.Modality;
import javafx.stage.Stage;
import javafx.stage.StageStyle;
import lombok.Data;
import org.apache.logging.log4j.LogManager;
import org.apache.logging.log4j.Logger;

import java.io.IOException;

@Data
public class StageDialog {
    private static final Logger logger = LogManager.getLogger();
    private final Controller controller;
    private final Stage stage = new Stage(StageStyle.DECORATED);
    private final Scene scene;
    private final GridPane gridPane = new GridPane();
    private final HBox buttonBar = new HBox();

    public StageDialog(Controller controller, String fxmlPath) {
        this.controller = controller;

        JFXDecorator decorator = new JFXDecorator(stage, gridPane);
        decorator.setCustomMaximize(true);
        Image coreIcon = new Image(getClass().getResourceAsStream("/core-icon.png"));
        decorator.setGraphic(new ImageView(coreIcon));

        scene = new Scene(decorator);
        stage.setScene(scene);

        stage.setWidth(800);
        stage.setHeight(600);
        scene.setOnKeyPressed(event -> {
            if (KeyCode.ESCAPE == event.getCode()) {
                stage.close();
            }
        });

        gridPane.setHgap(10);
        gridPane.setVgap(10);
        gridPane.setMaxWidth(Double.MAX_VALUE);
        gridPane.setMaxHeight(Double.MAX_VALUE);
        gridPane.setPadding(new Insets(10));

        gridPane.getColumnConstraints().add(new ColumnConstraints(10, Region.USE_COMPUTED_SIZE,
                Region.USE_COMPUTED_SIZE, Priority.ALWAYS, HPos.CENTER, true));
        gridPane.getRowConstraints().add(new RowConstraints(10, Region.USE_COMPUTED_SIZE,
                Region.USE_COMPUTED_SIZE, Priority.ALWAYS, VPos.CENTER, true));
        gridPane.getRowConstraints().add(new RowConstraints(30, 30,
                Region.USE_COMPUTED_SIZE, Priority.NEVER, VPos.CENTER, true));

        buttonBar.setAlignment(Pos.CENTER_RIGHT);
        buttonBar.setSpacing(10);

        stage.initModality(Modality.APPLICATION_MODAL);

        FXMLLoader loader = new FXMLLoader(getClass().getResource(fxmlPath));
        loader.setController(this);
        try {
            Parent parent = loader.load();
            setContent(parent);
        } catch (IOException ex) {
            logger.error("error loading fxml: {}", fxmlPath, ex);
            throw new RuntimeException(ex);
        }

        gridPane.addRow(1, buttonBar);
    }

    public void close() {
        stage.close();
    }

    public ICoreClient getCoreClient() {
        return controller.getCoreClient();
    }

    public void setContent(Node node) {
        gridPane.addRow(0, node);
    }

    public void setTitle(String title) {
        stage.setTitle(title);
    }

    public void setOwner(Stage window) {
        stage.initOwner(window);
        scene.getStylesheets().addAll(window.getScene().getStylesheets());
    }

    public JFXButton createButton(String label) {
        JFXButton button = new JFXButton(label);
        button.getStyleClass().add("core-button");
        buttonBar.getChildren().add(button);
        return button;
    }

    public void addCancelButton() {
        JFXButton button = createButton("Cancel");
        button.setOnAction(event -> close());
    }

    public void show() {
        if (buttonBar.getChildren().isEmpty() && gridPane.getChildren().contains(buttonBar)) {
            gridPane.getChildren().remove(1);
            gridPane.getRowConstraints().remove(1);
            gridPane.setVgap(0);
        }
        stage.showAndWait();
    }
}
