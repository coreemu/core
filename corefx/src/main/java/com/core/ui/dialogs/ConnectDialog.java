package com.core.ui.dialogs;

import com.core.Controller;
import com.jfoenix.controls.JFXButton;
import com.jfoenix.controls.JFXTextField;
import javafx.fxml.FXML;
import javafx.stage.Modality;
import javafx.stage.StageStyle;
import lombok.Data;
import org.apache.logging.log4j.LogManager;
import org.apache.logging.log4j.Logger;

@Data
public class ConnectDialog extends StageDialog {
    private static final Logger logger = LogManager.getLogger();
    private String coreUrl;
    private JFXButton saveButton;
    @FXML JFXTextField urlTextField;

    public ConnectDialog(Controller controller) {
        super(controller, "/fxml/connect_dialog.fxml");
        saveButton = createButton("Connect");
        saveButton.setOnAction(event -> {
            coreUrl = urlTextField.getText();
            controller.connectToCore(coreUrl);
            close();
        });
        addCancelButton();
        setTitle("CORE Connection");
        getStage().sizeToScene();
    }

    public void showDialog() {
        urlTextField.setText(coreUrl);
        show();
    }
}
