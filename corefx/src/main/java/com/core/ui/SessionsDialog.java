package com.core.ui;

import com.core.Controller;
import com.core.data.SessionState;
import com.core.client.rest.GetSessions;
import com.core.client.rest.GetSessionsData;
import com.jfoenix.controls.JFXButton;
import javafx.fxml.FXML;
import javafx.scene.control.TableColumn;
import javafx.scene.control.TableView;
import javafx.scene.control.cell.PropertyValueFactory;
import lombok.Data;
import org.apache.logging.log4j.LogManager;
import org.apache.logging.log4j.Logger;

import java.io.IOException;
import java.util.stream.Collectors;

public class SessionsDialog extends StageDialog {
    private static final Logger logger = LogManager.getLogger();

    @FXML
    private TableView<SessionRow> sessionsTable;

    @FXML
    private TableColumn<SessionRow, Integer> sessionIdColumn;

    @FXML
    private TableColumn<SessionRow, String> stateColumn;

    @FXML
    private TableColumn<SessionRow, Integer> nodeCountColumn;

    public SessionsDialog(Controller controller) {
        super(controller, "/fxml/sessions_dialog.fxml");

        setTitle("Sessions");

        JFXButton joinButton = createButton("Join");
        joinButton.setOnAction(event -> {
            SessionRow row = sessionsTable.getSelectionModel().getSelectedItem();
            logger.info("selected session: {}", row);
            try {
                getCoreClient().joinSession(row.getId(), true);
            } catch (IOException ex) {
                logger.error("error joining session: {}", row.getId());
            }

            close();
        });
        addCancelButton();

        sessionIdColumn.setCellValueFactory(new PropertyValueFactory<>("id"));
        stateColumn.setCellValueFactory(new PropertyValueFactory<>("state"));
        nodeCountColumn.setCellValueFactory(new PropertyValueFactory<>("nodes"));
    }

    @Data
    protected class SessionRow {
        private Integer id;
        private String state;
        private Integer nodes;

        public SessionRow(GetSessionsData getSessionsData) {
            id = getSessionsData.getId();
            state = SessionState.get(getSessionsData.getState()).name();
            nodes = getSessionsData.getNodes();
        }
    }

    public void showDialog() throws IOException {
        sessionsTable.getItems().clear();
        GetSessions getSessions = getCoreClient().getSessions();
        sessionsTable.getItems().addAll(getSessions.getSessions().stream()
                .map(SessionRow::new)
                .collect(Collectors.toList()));

        show();
    }
}
