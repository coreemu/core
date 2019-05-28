package com.core.ui.dialogs;

import com.core.Controller;
import com.core.data.NodeType;
import com.jfoenix.controls.JFXButton;
import com.jfoenix.controls.JFXListView;
import com.jfoenix.controls.JFXTextField;
import javafx.fxml.FXML;
import javafx.scene.control.SelectionMode;
import lombok.Data;
import org.apache.logging.log4j.LogManager;
import org.apache.logging.log4j.Logger;

import java.util.ArrayList;
import java.util.List;
import java.util.Map;

@Data
public class NodeTypeCreateDialog extends StageDialog {
    private static final Logger logger = LogManager.getLogger();
    @FXML private JFXListView<String> servicesListView;
    @FXML private JFXTextField modelTextField;
    @FXML private JFXTextField displayTextField;
    private Runnable onCreateHandler;

    public NodeTypeCreateDialog(Controller controller) {
        super(controller, "/fxml/node_type_create_dialog.fxml");
        setTitle("Create Node Configuration");

        JFXButton saveButton = createButton("Create");
        saveButton.setOnAction(event -> {
            onCreateHandler.run();
            close();
        });
        addCancelButton();

        servicesListView.getSelectionModel().setSelectionMode(SelectionMode.MULTIPLE);
        displayTextField.focusedProperty().addListener((obs, prev, current) -> {
            if (!current) {
                return;
            }

            String model = modelTextField.getText();
            if (!model.isEmpty()) {
                displayTextField.setText(model.substring(0, 1).toUpperCase() + model.substring(1));
            }
        });
    }

    public NodeType getCreatedNodeType() {
        NodeType nodeType = new NodeType(NodeType.DEFAULT, modelTextField.getText(), displayTextField.getText(),
                "/icons/host-100.png");
        nodeType.getServices().addAll(servicesListView.getSelectionModel().getSelectedItems());
        return nodeType;
    }

    public void setServices(Map<String, List<String>> serviceGroups) {
        List<String> services = new ArrayList<>();
        for (List<String> groupServices : serviceGroups.values()) {
            services.addAll(groupServices);
        }
        services.sort(String::compareTo);
        servicesListView.getItems().setAll(services);
    }


    public void showDialog(Runnable runnable) {
        onCreateHandler = runnable;
        modelTextField.setText("");
        displayTextField.setText("");
        servicesListView.getSelectionModel().clearSelection();
        show();
    }
}
