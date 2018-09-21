package com.core.ui.dialogs;

import com.core.Controller;
import com.core.data.CoreNode;
import com.core.data.NodeType;
import com.core.ui.Toast;
import com.jfoenix.controls.JFXButton;
import com.jfoenix.controls.JFXListView;
import com.jfoenix.controls.JFXTextField;
import javafx.fxml.FXML;
import javafx.scene.image.Image;
import javafx.scene.image.ImageView;
import javafx.stage.FileChooser;
import org.apache.logging.log4j.LogManager;
import org.apache.logging.log4j.Logger;

import java.io.File;
import java.util.HashMap;
import java.util.Map;

public class NodeTypesDialog extends StageDialog {
    private static final Logger logger = LogManager.getLogger();
    private final Map<String, NodeType> nodeTypeMap = new HashMap<>();
    private NodeType selectedNodeType;
    @FXML private JFXListView<String> listView;
    @FXML private JFXTextField modelTextField;
    @FXML private JFXTextField displayTextField;
    @FXML private JFXTextField iconTextField;
    @FXML private JFXButton iconButton;
    @FXML private ImageView iconImage;
    @FXML private JFXButton saveButton;
    @FXML private JFXButton addButton;
    @FXML private JFXButton deleteButton;

    public NodeTypesDialog(Controller controller) {
        super(controller, "/fxml/node_types_dialog.fxml");
        setTitle("Node Configuration");
        addCancelButton();

        listView.getSelectionModel().selectedItemProperty().addListener((ov, prev, current) -> {
            if (current == null) {
                return;
            }

            NodeType nodeType = nodeTypeMap.get(current);
            modelTextField.setText(nodeType.getModel());
            displayTextField.setText(nodeType.getDisplay());
            iconTextField.setText(nodeType.getIcon());
            iconImage.setImage(new Image(nodeType.getIcon()));
            selectedNodeType = nodeType;
        });

        iconButton.setOnAction(event -> {
            FileChooser fileChooser = new FileChooser();
            fileChooser.setTitle("Select Icon");
            fileChooser.setInitialDirectory(new File(System.getProperty("user.home")));
            fileChooser.getExtensionFilters().add(new FileChooser.ExtensionFilter("PNG", "*.png"));
            File file = fileChooser.showOpenDialog(controller.getWindow());
            if (file != null) {
                String uri = file.toURI().toString();
                iconImage.setImage(new Image(uri));
                iconTextField.setText(uri);
            }
        });

        saveButton.setOnAction(event -> {
            String iconPath = iconTextField.getText();
            selectedNodeType.setIcon(iconPath);
            for (CoreNode node : controller.getNetworkGraph().getGraph().getVertices()) {
                if (selectedNodeType != node.getNodeType()) {
                    continue;
                }

                node.setNodeType(selectedNodeType);
            }
            controller.getNetworkGraph().getGraphViewer().repaint();
            controller.getGraphToolbar().updateNodeType(selectedNodeType.getId(), iconPath);
            Toast.info(String.format("Node %s Updated", selectedNodeType.getDisplay()));
        });
    }

    public void showDialog() {
        listView.getItems().clear();
        nodeTypeMap.clear();
        for (NodeType nodeType : NodeType.getAll()) {
            if (nodeType.getValue() != NodeType.DEFAULT) {
                continue;
            }
            nodeTypeMap.put(nodeType.getDisplay(), nodeType);
            listView.getItems().add(nodeType.getDisplay());
        }
        listView.getSelectionModel().selectFirst();

        show();
    }
}
