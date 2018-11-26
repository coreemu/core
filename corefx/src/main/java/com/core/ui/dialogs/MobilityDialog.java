package com.core.ui.dialogs;

import com.core.Controller;
import com.core.data.CoreNode;
import com.core.data.MobilityConfig;
import com.core.ui.Toast;
import com.jfoenix.controls.JFXButton;
import com.jfoenix.controls.JFXTextField;
import com.jfoenix.controls.JFXToggleButton;
import javafx.event.ActionEvent;
import javafx.fxml.FXML;
import javafx.scene.layout.GridPane;
import javafx.stage.FileChooser;
import lombok.Data;
import org.apache.logging.log4j.LogManager;
import org.apache.logging.log4j.Logger;

import java.io.File;
import java.io.IOException;
import java.util.HashMap;
import java.util.Map;

@Data
public class MobilityDialog extends StageDialog {
    private static final Logger logger = LogManager.getLogger();
    @FXML private JFXTextField fileTextField;
    @FXML private JFXTextField refreshTextField;
    @FXML private JFXToggleButton loopToggleButton;
    @FXML private JFXTextField nodeMappingTextField;
    @FXML private JFXTextField autoStartTextField;
    @FXML private JFXTextField startTextField;
    @FXML private JFXTextField pauseTextField;
    @FXML private JFXTextField stopTextField;
    private Map<Integer, MobilityConfig> mobilityScripts = new HashMap<>();
    private CoreNode node;

    public MobilityDialog(Controller controller) {
        super(controller, "/fxml/mobility_dialog.fxml");
        setTitle("Mobility Script");

        JFXButton saveButton = createButton("Save");
        saveButton.setOnAction(event -> {
            MobilityConfig mobilityConfig = new MobilityConfig();
            mobilityConfig.setFile(fileTextField.getText());
            mobilityConfig.setScriptFile(new File(mobilityConfig.getFile()));
            mobilityConfig.setAutostart(autoStartTextField.getText());
            String loop = loopToggleButton.isSelected() ? "1" : "";
            mobilityConfig.setLoop(loop);
            mobilityConfig.setRefresh(Integer.parseInt(refreshTextField.getText()));
            mobilityConfig.setMap(nodeMappingTextField.getText());
            mobilityConfig.setStartScript(startTextField.getText());
            mobilityConfig.setPauseScript(pauseTextField.getText());
            mobilityConfig.setStopScript(stopTextField.getText());

            try {
                controller.getCoreClient().setMobilityConfig(node, mobilityConfig);
                mobilityScripts.put(node.getId(), mobilityConfig);
            } catch (IOException ex) {
                Toast.error("error setting mobility configuration", ex);
            }

            close();
        });
        addCancelButton();
    }

    @FXML
    private void onSelectAction(ActionEvent event) {
        JFXButton button = (JFXButton) event.getSource();
        GridPane gridPane = (GridPane) button.getParent();
        JFXTextField textField = (JFXTextField) gridPane.getChildren().get(0);

        FileChooser fileChooser = new FileChooser();
        fileChooser.setTitle("Select File");
        String mobilityPath = getController().getConfiguration().getMobilityPath();
        fileChooser.setInitialDirectory(new File(mobilityPath));
        fileChooser.getExtensionFilters().add(new FileChooser.ExtensionFilter("Mobility",
                "*.mobility"));
        try {
            File file = fileChooser.showOpenDialog(getController().getWindow());
            if (file != null) {
                logger.info("opening session xml: {}", file.getPath());
                textField.setText(file.getPath());
            }
        } catch (IllegalArgumentException ex) {
            Toast.error(String.format("Invalid mobility directory: %s",
                    getController().getConfiguration().getMobilityPath()));
        }
    }

    public void showDialog(CoreNode node) {
        this.node = node;

        try {
            MobilityConfig mobilityConfig = getController().getCoreClient().getMobilityConfig(this.node);
            fileTextField.setText(mobilityConfig.getFile());
            autoStartTextField.setText(mobilityConfig.getAutostart());
            boolean loop = "1".equals(mobilityConfig.getLoop());
            loopToggleButton.setSelected(loop);
            refreshTextField.setText(mobilityConfig.getRefresh().toString());
            nodeMappingTextField.setText(mobilityConfig.getMap());
            startTextField.setText(mobilityConfig.getStartScript());
            pauseTextField.setText(mobilityConfig.getPauseScript());
            stopTextField.setText(mobilityConfig.getStopScript());
        } catch (IOException ex) {
            Toast.error("error getting mobility config", ex);
        }

        show();
    }
}
