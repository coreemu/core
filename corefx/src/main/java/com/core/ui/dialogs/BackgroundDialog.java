package com.core.ui.dialogs;

import com.core.Controller;
import com.core.data.CoreLink;
import com.core.data.CoreNode;
import com.core.graph.BackgroundPaintable;
import com.jfoenix.controls.JFXButton;
import com.jfoenix.controls.JFXTextField;
import javafx.event.ActionEvent;
import javafx.fxml.FXML;
import javafx.scene.image.Image;
import javafx.scene.image.ImageView;
import javafx.scene.layout.HBox;
import javafx.stage.FileChooser;
import org.apache.logging.log4j.LogManager;
import org.apache.logging.log4j.Logger;

import java.io.File;
import java.nio.file.Paths;

public class BackgroundDialog extends StageDialog {
    private static final Logger logger = LogManager.getLogger();
    @FXML private ImageView imageView;
    @FXML private JFXTextField fileTextField;
    @FXML private JFXButton fileButton;
    private JFXButton saveButton;
    private JFXButton clearButton;

    public BackgroundDialog(Controller controller) {
        super(controller, "/fxml/background_dialog.fxml");
        setTitle("Background Configuration");
        saveButton = createButton("Save");
        saveButton.setOnAction(this::saveAction);

        clearButton = createButton("Clear");
        clearButton.setOnAction(this::clearAction);
        addCancelButton();

        HBox parent = (HBox) imageView.getParent();
        imageView.fitHeightProperty().bind(parent.heightProperty());

        fileButton.setOnAction(this::fileAction);
    }

    private void fileAction(ActionEvent event) {
        FileChooser fileChooser = new FileChooser();
        fileChooser.setTitle("Select Background");
        fileChooser.setInitialDirectory(new File(System.getProperty("user.home")));
        fileChooser.getExtensionFilters().add(new FileChooser.ExtensionFilter("PNG", "*.png"));
        File file = fileChooser.showOpenDialog(getStage());
        if (file != null) {
            String uri = file.toURI().toString();
            imageView.setImage(new Image(uri));
            fileTextField.setText(file.getPath());
            saveButton.setDisable(false);
        }
    }

    private void saveAction(ActionEvent event) {
        getController().getNetworkGraph().setBackground(fileTextField.getText());
        close();
    }

    private void clearAction(ActionEvent event) {
        getController().getNetworkGraph().removeBackground();
        close();
    }

    public void showDialog() {
        BackgroundPaintable<CoreNode, CoreLink> backgroundPaintable = getController().getNetworkGraph()
                .getBackgroundPaintable();
        saveButton.setDisable(true);
        fileTextField.setText(null);
        imageView.setImage(null);
        if (backgroundPaintable == null) {
            clearButton.setDisable(true);
        } else {
            String imagePath = backgroundPaintable.getImage();
            fileTextField.setText(imagePath);
            imageView.setImage(new Image(Paths.get(imagePath).toUri().toString()));
            clearButton.setDisable(false);
        }

        show();
    }
}
