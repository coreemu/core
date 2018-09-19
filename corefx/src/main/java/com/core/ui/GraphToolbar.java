package com.core.ui;

import com.core.Controller;
import com.core.data.NodeType;
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
import javafx.fxml.FXMLLoader;
import javafx.scene.control.ComboBox;
import javafx.scene.control.Label;
import javafx.scene.control.ProgressBar;
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

    @FXML
    private JFXButton runButton;

    @FXML
    private JFXButton pickingButton;

    @FXML
    private JFXButton editingButton;

    @FXML
    private JFXButton drawingButton;

    @FXML
    private ComboBox<String> graphModeCombo;

    @FXML
    private JFXButton nodesButton;

    @FXML
    private JFXButton devicesButton;

    public GraphToolbar(Controller controller) {
        this.controller = controller;
        FXMLLoader loader = new FXMLLoader(getClass().getResource("/fxml/graph_toolbar.fxml"));
        loader.setRoot(this);
        loader.setController(this);

        try {
            loader.load();
        } catch (IOException ex) {
            throw new RuntimeException(ex);
        }

        startIcon = IconUtils.get("play_circle_filled");
        startIcon.setSize(ICON_SIZE);
        stopIcon = IconUtils.get("stop");
        stopIcon.setSize(ICON_SIZE);

        setupPickingButton();
        setupEditingButton();
        setupDrawingButton();

        setupNodeTypes();
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
            controller.getBorderPane().setBottom(null);
            controller.getBorderPane().setRight(null);
            setSelected(true, pickingButton);
            setSelected(false, editingButton, drawingButton, selectedEditButton);
            isEditing = false;
        });
    }

    private void setupEditingButton() {
        SVGGlyph editIcon = IconUtils.get("mode_edit");
        editIcon.setSize(ICON_SIZE);
        editingButton.setGraphic(editIcon);
        editingButton.setTooltip(new Tooltip("Edit Graph"));
        editingButton.setOnAction(event -> {
            controller.getNetworkGraph().setMode(ModalGraphMouse.Mode.EDITING);
            controller.getBorderPane().setBottom(null);
            controller.getBorderPane().setRight(null);
            setSelected(true, editingButton, selectedEditButton);
            setSelected(false, drawingButton, pickingButton);
            isEditing = true;
        });
    }

    private void setupDrawingButton() {
        SVGGlyph pencilIcon = IconUtils.get("brush");
        pencilIcon.setSize(ICON_SIZE);
        drawingButton.setGraphic(pencilIcon);
        drawingButton.setTooltip(new Tooltip("Annotate Graph"));
        drawingButton.setOnAction(event -> {
            controller.getNetworkGraph().setMode(ModalGraphMouse.Mode.ANNOTATING);
            controller.getBorderPane().setBottom(controller.getAnnotationToolbar());
            controller.getBorderPane().setRight(null);
            setSelected(true, drawingButton);
            setSelected(false, editingButton, pickingButton, selectedEditButton);
            isEditing = false;
        });
    }

    private void setupNodeTypes() {
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
            setSelected(false, previous);
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
        nodesButton.setOnAction(event -> popup.show(nodesButton, JFXPopup.PopupVPosition.TOP,
                JFXPopup.PopupHPosition.LEFT, nodesButton.getWidth(), 0));
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
        devicesButton.setOnAction(event -> popup.show(devicesButton, JFXPopup.PopupVPosition.TOP,
                JFXPopup.PopupHPosition.LEFT, devicesButton.getWidth(), 0));
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
        try {
            ProgressBar progressBar = new ProgressBar();
            progressBar.setPrefWidth(Double.MAX_VALUE);
            controller.getBorderPane().setBottom(progressBar);

            boolean result = controller.getCoreClient().start();
            if (result) {
                controller.sessionStarted();
                Toast.success("Session Started");
                setRunButton(true);
            }

            controller.getBorderPane().setBottom(null);
        } catch (IOException ex) {
            logger.error("failure starting session", ex);
        }
    }

    private void stopSession() {
        try {
            boolean result = controller.getCoreClient().stop();
            if (result) {
                controller.sessionStopped();
                Toast.success("Session Stopped");
                setRunButton(false);
            }
        } catch (IOException ex) {
            logger.error("failure to stopSession session", ex);
        }
    }

    public void setRunButton(boolean isRunning) {
        if (isRunning) {
            Platform.runLater(() -> {
                pickingButton.fire();
                editingButton.setDisable(true);
                runButton.pseudoClassStateChanged(START_CLASS, false);
                runButton.pseudoClassStateChanged(STOP_CLASS, true);
                if (runButton.getGraphic() != stopIcon) {
                    runButton.setGraphic(stopIcon);
                }
            });
        } else {
            Platform.runLater(() -> {
                editingButton.setDisable(false);
                runButton.pseudoClassStateChanged(START_CLASS, true);
                runButton.pseudoClassStateChanged(STOP_CLASS, false);
                if (runButton.getGraphic() != startIcon) {
                    runButton.setGraphic(startIcon);
                }
            });
        }
    }
}
