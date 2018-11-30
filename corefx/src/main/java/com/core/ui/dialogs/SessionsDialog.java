package com.core.ui.dialogs;

import com.core.Controller;
import com.core.data.SessionOverview;
import com.core.data.SessionState;
import com.core.ui.Toast;
import com.jfoenix.controls.JFXButton;
import javafx.fxml.FXML;
import javafx.scene.control.TableColumn;
import javafx.scene.control.TableView;
import javafx.scene.control.cell.PropertyValueFactory;
import lombok.Data;
import org.apache.logging.log4j.LogManager;
import org.apache.logging.log4j.Logger;

import java.io.IOException;
import java.util.List;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.stream.Collectors;

public class SessionsDialog extends StageDialog {
    private static final Logger logger = LogManager.getLogger();
    @FXML private TableView<SessionRow> sessionsTable;
    @FXML private TableColumn<SessionRow, Integer> sessionIdColumn;
    @FXML private TableColumn<SessionRow, String> stateColumn;
    @FXML private TableColumn<SessionRow, Integer> nodeCountColumn;
    private final ExecutorService executorService = Executors.newSingleThreadExecutor();
    private final JFXButton joinButton;
    private final JFXButton deleteButton;

    public SessionsDialog(Controller controller) {
        super(controller, "/fxml/sessions_dialog.fxml");
        setTitle("Sessions");

        // add dialog buttons
        addCreateButton();
        deleteButton = createDeleteButton();
        joinButton = createJoinButton();
        addCancelButton();

        // update table cell factories
        sessionIdColumn.setCellValueFactory(new PropertyValueFactory<>("id"));
        stateColumn.setCellValueFactory(new PropertyValueFactory<>("state"));
        nodeCountColumn.setCellValueFactory(new PropertyValueFactory<>("nodes"));

        // handle table row selection
        sessionsTable.getSelectionModel().selectedItemProperty().addListener((ov, prev, current) -> {
            if (current != null) {
                boolean isCurrentSession = current.getId().equals(controller.getCoreClient().currentSession());
                deleteButton.setDisable(isCurrentSession);
                joinButton.setDisable(isCurrentSession);
            } else {
                deleteButton.setDisable(true);
                joinButton.setDisable(true);
            }
        });
    }

    private void addCreateButton() {
        JFXButton createButton = createButton("New");
        createButton.setOnAction(event -> {
            logger.info("creating new session");
            executorService.submit(() -> {
                try {
                    SessionOverview sessionOverview = getCoreClient().createSession();
                    getController().joinSession(sessionOverview.getId());
                    Toast.success(String.format("Created Session %s", sessionOverview.getId()));
                } catch (IOException ex) {
                    Toast.error("Error creating new session", ex);
                }
            });
            close();
        });
    }

    private JFXButton createJoinButton() {
        JFXButton button = createButton("Join");
        button.setDisable(true);
        button.setOnAction(event -> {
            SessionRow row = sessionsTable.getSelectionModel().getSelectedItem();
            Integer sessionId = row.getId();
            logger.info("joining session: {}", sessionId);
            executorService.submit(() -> {
                try {
                    getController().joinSession(sessionId);
                    Toast.info(String.format("Joined Session %s", sessionId));
                } catch (IOException ex) {
                    Toast.error(String.format("Error joining session: %s", sessionId), ex);
                }
            });
            close();
        });
        return button;
    }

    private JFXButton createDeleteButton() {
        JFXButton button = createButton("Delete");
        button.setDisable(true);
        button.setOnAction(event -> {
            SessionRow row = sessionsTable.getSelectionModel().getSelectedItem();
            Integer sessionId = row.getId();
            logger.info("deleting session: {}", sessionId);
            executorService.submit(() -> {
                try {
                    boolean result = getCoreClient().deleteSession(sessionId);
                    if (result) {
                        sessionsTable.getItems().remove(row);
                        sessionsTable.getSelectionModel().clearSelection();
                        Toast.info(String.format("Deleted Session %s", sessionId));
                    } else {
                        Toast.error(String.format("Failure to delete session %s", sessionId));
                    }
                } catch (IOException ex) {
                    Toast.error(String.format("Error deleting session: %s", sessionId), ex);
                }
            });
        });
        return button;
    }

    @Data
    protected class SessionRow {
        private Integer id;
        private String state;
        private Integer nodes;

        SessionRow(SessionOverview sessionOverview) {
            id = sessionOverview.getId();
            state = SessionState.get(sessionOverview.getState()).name();
            nodes = sessionOverview.getNodes();
        }
    }

    public void showDialog() throws IOException {
        List<SessionOverview> sessions = getCoreClient().getSessions();
        List<SessionRow> rows = sessions.stream().map(SessionRow::new).collect(Collectors.toList());
        sessionsTable.getItems().setAll(rows);
        show();
    }

    @Override
    public void close() {
        sessionsTable.getSelectionModel().clearSelection();
        super.close();
    }
}
