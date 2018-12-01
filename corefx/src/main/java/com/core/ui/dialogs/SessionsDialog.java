package com.core.ui.dialogs;

import com.core.Controller;
import com.core.data.SessionOverview;
import com.core.data.SessionState;
import com.core.ui.Toast;
import com.jfoenix.controls.JFXButton;
import javafx.concurrent.Task;
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

    public SessionsDialog(Controller controller) {
        super(controller, "/fxml/sessions_dialog.fxml");
        setTitle("Sessions");

        // add dialog buttons
        JFXButton createButton = createButton("New");
        createButton.setOnAction(event -> {
            logger.info("creating new session");
            executorService.submit(new CreateSessionTask());
        });

        JFXButton deleteButton = createButton("Delete");
        deleteButton.setDisable(true);
        deleteButton.setOnAction(event -> {
            SessionRow row = sessionsTable.getSelectionModel().getSelectedItem();
            Integer sessionId = row.getId();
            logger.info("deleting session: {}", sessionId);
            executorService.submit(new DeleteSessionTask(row, sessionId));
        });

        JFXButton joinButton = createButton("Join");
        joinButton.setDisable(true);
        joinButton.setOnAction(event -> {
            SessionRow row = sessionsTable.getSelectionModel().getSelectedItem();
            Integer sessionId = row.getId();
            logger.info("joining session: {}", sessionId);
            executorService.submit(new JoinSessionTask(sessionId));
        });

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

    private class CreateSessionTask extends Task<Integer> {
        @Override
        protected Integer call() throws Exception {
            SessionOverview sessionOverview = getCoreClient().createSession();
            Integer sessionId = sessionOverview.getId();
            getController().joinSession(sessionId);
            return sessionId;
        }

        @Override
        protected void succeeded() {
            Toast.success(String.format("Created Session %s", getValue()));
            close();
        }

        @Override
        protected void failed() {
            Toast.error("Error creating new session", new RuntimeException(getException()));
        }
    }

    private class JoinSessionTask extends Task<Void> {
        private Integer sessionId;

        JoinSessionTask(Integer sessionId) {
            this.sessionId = sessionId;
        }

        @Override
        protected Void call() throws Exception {
            getController().joinSession(sessionId);
            return null;
        }

        @Override
        protected void succeeded() {
            Toast.info(String.format("Joined Session %s", sessionId));
            close();
        }

        @Override
        protected void failed() {
            Toast.error(String.format("Error joining session: %s", sessionId), new RuntimeException(getException()));
        }
    }

    private class DeleteSessionTask extends Task<Boolean> {
        private SessionRow row;
        private Integer sessionId;

        DeleteSessionTask(SessionRow row, Integer sessionId) {
            this.row = row;
            this.sessionId = sessionId;
        }

        @Override
        protected Boolean call() throws Exception {
            return getCoreClient().deleteSession(sessionId);
        }

        @Override
        protected void succeeded() {
            if (getValue()) {
                sessionsTable.getItems().remove(row);
                sessionsTable.getSelectionModel().clearSelection();
                Toast.info(String.format("Deleted Session %s", sessionId));
            } else {
                Toast.error(String.format("Failure to delete session %s", sessionId));
            }
        }

        @Override
        protected void failed() {
            Toast.error(String.format("Error deleting session: %s", sessionId), new RuntimeException(getException()));
        }
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
        sessionsTable.getSelectionModel().clearSelection();
        sessionsTable.getItems().setAll(rows);
        show();
    }
}
