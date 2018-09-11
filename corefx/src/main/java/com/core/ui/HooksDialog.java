package com.core.ui;

import com.core.Controller;
import com.core.data.Hook;
import com.core.data.SessionState;
import com.core.rest.GetHooks;
import com.jfoenix.controls.JFXButton;
import javafx.fxml.FXML;
import javafx.scene.control.TableColumn;
import javafx.scene.control.TableView;
import javafx.scene.control.cell.PropertyValueFactory;
import javafx.stage.Stage;
import org.apache.logging.log4j.LogManager;
import org.apache.logging.log4j.Logger;

import java.io.IOException;
import java.util.List;

public class HooksDialog extends StageDialog {
    private static final Logger logger = LogManager.getLogger();
    private HookDialog hookDialog;
    private int fileCount = 0;

    @FXML
    private TableView<Hook> hooksTable;

    @FXML
    private TableColumn<Hook, Integer> fileColumn;

    @FXML
    private TableColumn<Hook, Integer> stateColumn;

    public HooksDialog(Controller controller) {
        super(controller, "/fxml/hooks_dialog.fxml");
        hookDialog = new HookDialog(controller);

        setTitle("Hooks");

        JFXButton createButton = createButton("Create");
        createButton.setOnAction(event -> {
            logger.info("showing create hook");
            hookDialog.showDialog(nextFile(), saveHandler, cancelHandler);
        });
        JFXButton editButton = createButton("Edit");
        editButton.setDisable(true);
        editButton.setOnAction(event -> {
            logger.info("edit hook");
            Hook hook = hooksTable.getSelectionModel().getSelectedItem();
            hookDialog.showEditDialog(hook, editHandler, cancelHandler);
        });
        JFXButton deleteButton = createButton("Delete");
        deleteButton.setDisable(true);
        deleteButton.setOnAction(event -> {
            logger.info("delete hook");
            Hook hook = hooksTable.getSelectionModel().getSelectedItem();
            hooksTable.getItems().remove(hook);
        });

        addCancelButton();

        hooksTable.getSelectionModel().selectedItemProperty().addListener((ov, old, current) -> {
            boolean hasNoSelection = current == null;
            editButton.setDisable(hasNoSelection);
            deleteButton.setDisable(hasNoSelection);
        });

        fileColumn.setCellValueFactory(new PropertyValueFactory<>("file"));
        stateColumn.setCellValueFactory(new PropertyValueFactory<>("stateDisplay"));
    }

    @Override
    public void setOwner(Stage window) {
        super.setOwner(window);
        hookDialog.setOwner(window);
    }

    private Runnable saveHandler = () -> {
        Hook hook = hookDialog.getHook();
        hooksTable.getItems().addAll(hook);
    };

    private Runnable editHandler = () -> {
        Hook hook = hooksTable.getSelectionModel().getSelectedItem();
        Hook update = hookDialog.getHook();
        SessionState state = SessionState.valueOf(update.getStateDisplay());
        hook.setState(state.getValue());
        hook.setData(update.getData());
    };

    private Runnable cancelHandler = this::showDialog;

    private String nextFile() {
        return String.format("file%s.sh", ++fileCount);
    }

    public List<Hook> getHooks() {
        return hooksTable.getItems();
    }

    public void updateHooks() {
        logger.info("updating hooks");
        hooksTable.getItems().clear();

        // update hooks
        try {
            GetHooks getHooks = getCoreClient().getHooks();
            for (Hook hook : getHooks.getHooks()) {
                SessionState state = SessionState.get(hook.getState());
                hook.setStateDisplay(state.name());
                hooksTable.getItems().add(hook);
            }
        } catch (IOException ex) {
            logger.error("error getting current hooks", ex);
            Toast.error("Error getting current hooks");
        }
    }

    public void showDialog() {
        // clear current selection
        hooksTable.getSelectionModel().clearSelection();
        show();
    }
}
