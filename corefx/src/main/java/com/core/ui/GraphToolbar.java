package com.core.ui;

import com.core.Controller;
import com.core.data.NodeType;
import com.core.utils.FxmlUtils;
import com.core.utils.IconUtils;
import com.jfoenix.controls.JFXButton;
import com.jfoenix.controls.JFXListView;
import com.jfoenix.controls.JFXPopup;
import com.jfoenix.svg.SVGGlyph;
import edu.uci.ics.jung.visualization.control.ModalGraphMouse;
import javafx.application.Platform;
import javafx.css.PseudoClass;
import javafx.event.ActionEvent;
import javafx.fxml.FXML;
import javafx.scene.control.ComboBox;
import javafx.scene.control.Label;
import javafx.scene.control.Tooltip;
import javafx.scene.image.ImageView;
import javafx.scene.layout.VBox;
import org.apache.logging.log4j.LogManager;
import org.apache.logging.log4j.Logger;

import java.io.IOException;
import java.util.Arrays;
import java.util.Comparator;
import java.util.HashMap;
import java.util.Map;

public class GraphToolbar extends VBox {
    private static final Logger logger = LogManager.getLogger();
    private static final int ICON_SIZE = 40;
    private static final int NODES_ICON_SIZE = 20;
    private static final PseudoClass START_CLASS = PseudoClass.getPseudoClass("start");
    private static final PseudoClass STOP_CLASS = PseudoClass.getPseudoClass("stop");
    private static final PseudoClass SELECTED_CLASS = PseudoClass.getPseudoClass("selected");
    private final Controller controller;
    private final Map<Integer, Label> labelMap = new HashMap<>();
    private SVGGlyph startIcon;
    private SVGGlyph stopIcon;
    private JFXListView<Label> nodesList = new JFXListView<>();
    private JFXListView<Label> devicesList = new JFXListView<>();
    private JFXButton selectedEditButton;
    private NodeType selectedNodeType;
    private boolean isEditing = false;
    @FXML private JFXButton runButton;
    @FXML private JFXButton pickingButton;
    @FXML private JFXButton drawingButton;
    @FXML private ComboBox<String> graphModeCombo;
    @FXML private JFXButton nodesButton;
    @FXML private JFXButton devicesButton;

    public GraphToolbar(Controller controller) {
        this.controller = controller;
        FxmlUtils.loadRootController(this, "/fxml/graph_toolbar.fxml");

        startIcon = IconUtils.get("play_circle_filled");
        startIcon.setSize(ICON_SIZE);
        stopIcon = IconUtils.get("stop");
        stopIcon.setSize(ICON_SIZE);

        setupPickingButton();
        setupDrawingButton();
        setupNodesButton();
        setupDevicesButton();

        // initial state
        setSelected(true, pickingButton);
        controller.getNetworkGraph().setMode(ModalGraphMouse.Mode.PICKING);
        runButton.setGraphic(startIcon);
    }

    private void setupPickingButton() {
        SVGGlyph pickingIcon = IconUtils.get("call_made");
        pickingIcon.setSize(ICON_SIZE);
        pickingButton.setGraphic(pickingIcon);
        pickingButton.setTooltip(new Tooltip("Pick/Move Nodes"));
        pickingButton.setOnAction(event -> {
            controller.getNetworkGraph().setMode(ModalGraphMouse.Mode.PICKING);
            controller.getBottom().getChildren().remove(controller.getAnnotationToolbar());
            controller.getBorderPane().setRight(null);
            setSelected(true, pickingButton);
            setSelected(false, drawingButton, selectedEditButton);
            isEditing = false;
        });
    }

    private void setEditMode() {
        controller.getNetworkGraph().setMode(ModalGraphMouse.Mode.EDITING);
        controller.getBottom().getChildren().remove(controller.getAnnotationToolbar());
        controller.getBorderPane().setRight(null);
        if (selectedEditButton != null) {
            setSelected(true, selectedEditButton);
        }
        setSelected(false, drawingButton, pickingButton);
        isEditing = true;
    }

    private void setupDrawingButton() {
        SVGGlyph pencilIcon = IconUtils.get("brush");
        pencilIcon.setSize(ICON_SIZE);
        drawingButton.setGraphic(pencilIcon);
        drawingButton.setTooltip(new Tooltip("Annotate Graph"));
        drawingButton.setOnAction(event -> {
            controller.getNetworkGraph().setMode(ModalGraphMouse.Mode.ANNOTATING);
            controller.getBottom().getChildren().add(controller.getAnnotationToolbar());
            controller.getBorderPane().setRight(null);
            setSelected(true, drawingButton);
            setSelected(false, pickingButton, selectedEditButton);
            isEditing = false;
        });
    }

    public void setupNodeTypes() {
        // clear existing configuration
        labelMap.clear();
        nodesList.getItems().clear();
        devicesList.getItems().clear();

        for (NodeType nodeType : NodeType.getAll()) {
            ImageView icon = new ImageView(nodeType.getIcon());
            icon.setFitWidth(NODES_ICON_SIZE);
            icon.setFitHeight(NODES_ICON_SIZE);
            Label label = new Label(nodeType.getDisplay(), icon);
            label.setUserData(nodeType.getId());
            labelMap.put(nodeType.getId(), label);

            if (nodeType.getValue() == NodeType.DEFAULT) {
                nodesList.getItems().add(label);
            } else {
                devicesList.getItems().add(label);
            }
        }

        Comparator<Label> comparator = Comparator.comparing(Label::getText);
        nodesList.getItems().sort(comparator);
        devicesList.getItems().sort(comparator);

        // initial node
        nodesList.getSelectionModel().selectFirst();
        Label selectedNodeLabel = nodesList.getSelectionModel().getSelectedItem();
        selectedNodeType = NodeType.get((int) selectedNodeLabel.getUserData());
        selectedEditButton = nodesButton;
        controller.getNetworkGraph().setNodeType(selectedNodeType);
        updateButtonValues(nodesButton, selectedNodeLabel);

        // initial device
        updateButtonValues(devicesButton, devicesList.getItems().get(0));
    }

    private void updateButtonValues(JFXButton button, Label label) {
        ImageView icon = new ImageView(((ImageView) label.getGraphic()).getImage());
        icon.setFitHeight(ICON_SIZE);
        icon.setFitWidth(ICON_SIZE);
        button.setGraphic(icon);
    }

    private void setSelectedEditButton(JFXButton button) {
        JFXButton previous = selectedEditButton;
        selectedEditButton = button;
        if (isEditing) {
            if (previous != null) {
                setSelected(false, previous);
            }
            setSelected(true, selectedEditButton);
        }
    }

    private void setupNodesButton() {
        nodesButton.setTooltip(new Tooltip("Network Nodes (host, pc, etc)"));
        nodesList.getSelectionModel().selectedItemProperty().addListener((ov, old, current) -> {
            if (current == null) {
                return;
            }

            updateButtonValues(nodesButton, current);
            selectedNodeType = NodeType.get((int) current.getUserData());
            logger.info("selected node type: {}", selectedNodeType);
            setSelectedEditButton(nodesButton);
            devicesList.getSelectionModel().clearSelection();
            controller.getNetworkGraph().setNodeType(selectedNodeType);
            logger.info("node selected: {} - type: {}", current, selectedNodeType);
        });

        JFXPopup popup = new JFXPopup(nodesList);
        nodesButton.setOnAction(event -> {
            setEditMode();
            popup.show(nodesButton, JFXPopup.PopupVPosition.TOP,
                    JFXPopup.PopupHPosition.LEFT, nodesButton.getWidth(), 0);
        });
    }

    private void setupDevicesButton() {
        devicesButton.setTooltip(new Tooltip("Device Nodes (WLAN, EMANE, Switch, etc)"));
        devicesList.getSelectionModel().selectedItemProperty().addListener((ov, old, current) -> {
            if (current == null) {
                return;
            }

            updateButtonValues(devicesButton, current);
            selectedNodeType = NodeType.get((int) current.getUserData());
            logger.info("selected node type: {}", selectedNodeType);
            controller.getNetworkGraph().setNodeType(selectedNodeType);
            setSelectedEditButton(devicesButton);
            nodesList.getSelectionModel().clearSelection();
            logger.info("device selected: {} - type: {}", current, selectedNodeType);
        });

        JFXPopup popup = new JFXPopup(devicesList);
        devicesButton.setOnAction(event -> {
            setEditMode();
            popup.show(devicesButton, JFXPopup.PopupVPosition.TOP,
                    JFXPopup.PopupHPosition.LEFT, devicesButton.getWidth(), 0);
        });
    }

    @FXML
    private void onRunButtonAction(ActionEvent event) {
        if (runButton.getGraphic() == startIcon) {
            startSession();
        } else {
            stopSession();
        }
    }

    public void updateNodeType(int id, String uri) {
        Label label = labelMap.get(id);
        ImageView icon = new ImageView(uri);
        icon.setFitWidth(NODES_ICON_SIZE);
        icon.setFitHeight(NODES_ICON_SIZE);
        label.setGraphic(icon);

        if (selectedNodeType.getId() == id) {
            updateButtonValues(nodesButton, label);
        }
    }

    private void setSelected(boolean isSelected, JFXButton... others) {
        Arrays.stream(others)
                .forEach(x -> x.pseudoClassStateChanged(SELECTED_CLASS, isSelected));
    }

    private void startSession() {
        runButton.setDisable(true);
        new Thread(() -> {
            try {
                boolean result = controller.startSession();
                if (result) {
                    Toast.success("Session Started");
                    setRunButton(true);
                }
            } catch (IOException ex) {
                Toast.error("Failure Starting Session", ex);
            }
        }).start();
    }

    private void stopSession() {
        runButton.setDisable(true);
        new Thread(() -> {
            try {
                boolean result = controller.stopSession();
                if (result) {
                    Toast.success("Session Stopped");
                    setRunButton(false);
                }
            } catch (IOException ex) {
                Toast.error("Failure Stopping Session", ex);
            }
        }).start();
    }

    public void setRunButton(boolean isRunning) {
        if (isRunning) {
            Platform.runLater(() -> {
                pickingButton.fire();
                devicesButton.setDisable(true);
                nodesButton.setDisable(true);
                runButton.pseudoClassStateChanged(START_CLASS, false);
                runButton.pseudoClassStateChanged(STOP_CLASS, true);
                if (runButton.getGraphic() != stopIcon) {
                    runButton.setGraphic(stopIcon);
                }
                runButton.setDisable(false);
            });
        } else {
            Platform.runLater(() -> {
                devicesButton.setDisable(false);
                nodesButton.setDisable(false);
                runButton.pseudoClassStateChanged(START_CLASS, true);
                runButton.pseudoClassStateChanged(STOP_CLASS, false);
                if (runButton.getGraphic() != startIcon) {
                    runButton.setGraphic(startIcon);
                }
                runButton.setDisable(false);
            });
        }
    }
}
