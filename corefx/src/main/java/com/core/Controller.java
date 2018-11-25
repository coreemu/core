package com.core;

import com.core.client.ICoreClient;
import com.core.client.rest.CoreRestClient;
import com.core.data.*;
import com.core.graph.NetworkGraph;
import com.core.ui.*;
import com.core.ui.dialogs.*;
import com.core.utils.ConfigUtils;
import com.core.utils.Configuration;
import com.core.utils.NodeTypeConfig;
import com.core.websocket.CoreWebSocket;
import com.jfoenix.controls.JFXDecorator;
import com.jfoenix.controls.JFXProgressBar;
import javafx.application.Application;
import javafx.application.Platform;
import javafx.embed.swing.SwingNode;
import javafx.event.ActionEvent;
import javafx.fxml.FXML;
import javafx.fxml.Initializable;
import javafx.scene.control.MenuItem;
import javafx.scene.layout.BorderPane;
import javafx.scene.layout.StackPane;
import javafx.scene.layout.VBox;
import javafx.stage.FileChooser;
import javafx.stage.Stage;
import lombok.Data;
import org.apache.logging.log4j.LogManager;
import org.apache.logging.log4j.Logger;

import java.awt.event.ItemEvent;
import java.io.File;
import java.io.IOException;
import java.net.URISyntaxException;
import java.net.URL;
import java.util.*;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.stream.Collectors;

@Data
public class Controller implements Initializable {
    private static final Logger logger = LogManager.getLogger();
    @FXML private StackPane stackPane;
    @FXML private BorderPane borderPane;
    @FXML private VBox top;
    @FXML private VBox bottom;
    @FXML private SwingNode swingNode;
    @FXML private MenuItem saveXmlMenuItem;
    @FXML private JFXProgressBar progressBar;

    private Application application;
    private JFXDecorator decorator;
    private Stage window;
    private Configuration configuration;
    private Map<String, Set<String>> defaultServices = new HashMap<>();

    // core client utilities
    private ICoreClient coreClient = new CoreRestClient();
    private CoreWebSocket coreWebSocket;

    // ui elements
    private NetworkGraph networkGraph = new NetworkGraph(this);
    private AnnotationToolbar annotationToolbar = new AnnotationToolbar(networkGraph);
    private NodeDetails nodeDetails = new NodeDetails(this);
    private LinkDetails linkDetails = new LinkDetails(this);
    private GraphToolbar graphToolbar = new GraphToolbar(this);
    private MobilityPlayer mobilityPlayer = new MobilityPlayer(this);

    // dialogs
    private SessionsDialog sessionsDialog = new SessionsDialog(this);
    private ServiceDialog serviceDialog = new ServiceDialog(this);
    private NodeServicesDialog nodeServicesDialog = new NodeServicesDialog(this);
    private NodeEmaneDialog nodeEmaneDialog = new NodeEmaneDialog(this);
    private NodeWlanDialog nodeWlanDialog = new NodeWlanDialog(this);
    private ConfigDialog configDialog = new ConfigDialog(this);
    private HooksDialog hooksDialog = new HooksDialog(this);
    private MobilityDialog mobilityDialog = new MobilityDialog(this);
    private ChartDialog chartDialog = new ChartDialog(this);
    private NodeTypesDialog nodeTypesDialog = new NodeTypesDialog(this);
    private BackgroundDialog backgroundDialog = new BackgroundDialog(this);
    private LocationDialog locationDialog = new LocationDialog(this);
    private GeoDialog geoDialog = new GeoDialog(this);
    private ConnectDialog connectDialog = new ConnectDialog(this);
    private GuiPreferencesDialog guiPreferencesDialog = new GuiPreferencesDialog(this);
    private NodeTypeCreateDialog nodeTypeCreateDialog = new NodeTypeCreateDialog(this);

    public void connectToCore(String coreUrl) {
        coreWebSocket.stop();

        ExecutorService executorService = Executors.newSingleThreadExecutor();
        executorService.submit(() -> {
            try {
                coreWebSocket.start(coreUrl);
                coreClient.setUrl(coreUrl);
                initialJoin();
            } catch (IOException | URISyntaxException ex) {
                Toast.error(String.format("Connection failure: %s", ex.getMessage()), ex);
                Platform.runLater(() -> connectDialog.showDialog());
            }
        });
    }

    private void initialJoin() throws IOException {
        Map<String, List<String>> serviceGroups = coreClient.getServices();
        logger.info("core services: {}", serviceGroups);
        nodeServicesDialog.setServices(serviceGroups);
        nodeTypeCreateDialog.setServices(serviceGroups);

        logger.info("initial core session join");
        List<SessionOverview> sessions = coreClient.getSessions();

        logger.info("existing sessions: {}", sessions);
        Integer sessionId;
        if (sessions.isEmpty()) {
            logger.info("creating initial session");
            SessionOverview sessionOverview = coreClient.createSession();
            sessionId = sessionOverview.getId();
            Toast.info(String.format("Created Session %s", sessionId));
        } else {
            SessionOverview sessionOverview = sessions.get(0);
            sessionId = sessionOverview.getId();
            Toast.info(String.format("Joined Session %s", sessionId));
        }

        joinSession(sessionId);

        // set emane models
        List<String> emaneModels = coreClient.getEmaneModels();
        nodeEmaneDialog.setModels(emaneModels);
    }

    public void joinSession(Integer sessionId) throws IOException {
        // clear graph
        networkGraph.reset();

        // clear out any previously set information
        Platform.runLater(() -> {
            bottom.getChildren().remove(mobilityPlayer);
            borderPane.setRight(null);
        });
        mobilityDialog.setNode(null);

        // get session to join
        Session session = coreClient.getSession(sessionId);
        SessionState sessionState = SessionState.get(session.getState());

        // update client to use this session
        coreClient.updateSession(sessionId);
        coreClient.updateState(sessionState);

        // display all nodes
        logger.info("joining core session({}) state({}): {}", sessionId, sessionState, session);
        for (CoreNode node : session.getNodes()) {
            NodeType nodeType = NodeType.find(node.getType(), node.getModel());
            if (nodeType == null) {
                logger.info(String.format("failed to find node type(%s) model(%s): %s",
                        node.getType(), node.getModel(), node.getName()));
                continue;
            }

            node.setNodeType(nodeType);
            networkGraph.addNode(node);
        }

        // display all links
        for (CoreLink link : session.getLinks()) {
            if (link.getInterfaceOne() != null || link.getInterfaceTwo() != null) {
                link.setType(LinkTypes.WIRED.getValue());
            }

            networkGraph.addLink(link);
        }

        // refresh graph
        networkGraph.getGraphViewer().repaint();

        // update other components for new session
        graphToolbar.setRunButton(coreClient.isRunning());
        hooksDialog.updateHooks();

        // update session default services
        setCoreDefaultServices();

        // display first mobility script in player, if needed
        Map<Integer, MobilityConfig> mobilityConfigMap = coreClient.getMobilityConfigs();
        Optional<Integer> nodeIdOptional = mobilityConfigMap.keySet().stream().findFirst();
        if (nodeIdOptional.isPresent()) {
            Integer nodeId = nodeIdOptional.get();
            MobilityConfig mobilityConfig = mobilityConfigMap.get(nodeId);
            CoreNode node = networkGraph.getVertex(nodeId);
            if (node != null) {
                mobilityPlayer.show(node, mobilityConfig);
                Platform.runLater(() -> bottom.getChildren().add(mobilityPlayer));
            }
        }

        Platform.runLater(() -> decorator.setTitle(String.format("CORE (Session %s)", sessionId)));
    }

    public boolean startSession() throws IOException {
        // force nodes to get latest positions
        networkGraph.updatePositions();

        // retrieve items for creation/start
        Collection<CoreNode> nodes = networkGraph.getGraph().getVertices();
        Collection<CoreLink> links = networkGraph.getGraph().getEdges();
        List<Hook> hooks = hooksDialog.getHooks();

        // start/create session
        progressBar.setVisible(true);
        boolean result = coreClient.start(nodes, links, hooks);
        progressBar.setVisible(false);
        if (result) {
            // configure and add mobility player
            CoreNode node = mobilityDialog.getNode();
            if (node != null) {
                MobilityConfig mobilityConfig = mobilityDialog.getMobilityScripts().get(node.getId());
                if (mobilityConfig != null) {
                    mobilityPlayer.show(node, mobilityConfig);
                    Platform.runLater(() -> bottom.getChildren().add(mobilityPlayer));
                }
            }
            saveXmlMenuItem.setDisable(false);
        }
        return result;
    }

    public boolean stopSession() throws IOException {
        // clear out any drawn wireless links
        List<CoreLink> wirelessLinks = networkGraph.getGraph().getEdges().stream()
                .filter(CoreLink::isWireless)
                .collect(Collectors.toList());
        wirelessLinks.forEach(networkGraph::removeWirelessLink);
        networkGraph.getGraphViewer().repaint();

        // stop session
        progressBar.setVisible(true);
        boolean result = coreClient.stop();
        progressBar.setVisible(false);
        if (result) {
            Platform.runLater(() -> bottom.getChildren().remove(mobilityPlayer));
            saveXmlMenuItem.setDisable(true);
        }
        return result;
    }

    private void setCoreDefaultServices() {
        try {
            coreClient.setDefaultServices(defaultServices);
        } catch (IOException ex) {
            Toast.error("Error updating core default services", ex);
        }
    }

    public void updateNodeTypes() {
        graphToolbar.setupNodeTypes();
        setCoreDefaultServices();
        try {
            ConfigUtils.save(configuration);
        } catch (IOException ex) {
            Toast.error("Error saving configuration", ex);
        }
    }

    public void deleteNode(CoreNode node) {
        networkGraph.removeNode(node);
        CoreNode mobilityNode = mobilityDialog.getNode();
        if (mobilityNode != null && mobilityNode.getId().equals(node.getId())) {
            mobilityDialog.setNode(null);
        }
    }

    void setWindow(Stage window) {
        this.window = window;
        sessionsDialog.setOwner(window);
        hooksDialog.setOwner(window);
        nodeServicesDialog.setOwner(window);
        serviceDialog.setOwner(window);
        nodeWlanDialog.setOwner(window);
        nodeEmaneDialog.setOwner(window);
        configDialog.setOwner(window);
        mobilityDialog.setOwner(window);
        nodeTypesDialog.setOwner(window);
        backgroundDialog.setOwner(window);
        locationDialog.setOwner(window);
        connectDialog.setOwner(window);
        guiPreferencesDialog.setOwner(window);
        nodeTypeCreateDialog.setOwner(window);
    }

    @FXML
    private void onCoreMenuConnect(ActionEvent event) {
        logger.info("showing connect!");
        connectDialog.showDialog();
    }

    @FXML
    private void onOptionsMenuNodeTypes(ActionEvent event) {
        nodeTypesDialog.showDialog();
    }

    @FXML
    private void onOptionsMenuBackground(ActionEvent event) {
        backgroundDialog.showDialog();
    }

    @FXML
    private void onOptionsMenuLocation(ActionEvent event) {
        locationDialog.showDialog();
    }

    @FXML
    private void onOptionsMenuPreferences(ActionEvent event) {
        guiPreferencesDialog.showDialog();
    }

    @FXML
    private void onHelpMenuWebsite(ActionEvent event) {
        application.getHostServices().showDocument("https://github.com/coreemu/core");
    }

    @FXML
    private void onHelpMenuDocumentation(ActionEvent event) {
        application.getHostServices().showDocument("http://coreemu.github.io/core/");
    }

    @FXML
    private void onHelpMenuMailingList(ActionEvent event) {
        application.getHostServices().showDocument("https://publists.nrl.navy.mil/mailman/listinfo/core-users");
    }

    @FXML
    private void onOpenXmlAction() {
        FileChooser fileChooser = new FileChooser();
        fileChooser.setTitle("Open Session");
        fileChooser.setInitialDirectory(new File(configuration.getXmlPath()));
        fileChooser.getExtensionFilters().add(new FileChooser.ExtensionFilter("XML", "*.xml"));
        try {
            File file = fileChooser.showOpenDialog(window);
            if (file != null) {
                openXml(file);
            }
        } catch (IllegalArgumentException ex) {
            Toast.error(String.format("Invalid XML directory: %s", configuration.getXmlPath()));
        }
    }

    private void openXml(File file) {
        logger.info("opening session xml: {}", file.getPath());
        try {
            SessionOverview sessionOverview = coreClient.openSession(file);
            Integer sessionId = sessionOverview.getId();
            joinSession(sessionId);
            Toast.info(String.format("Joined Session %s", sessionId));
        } catch (IOException ex) {
            Toast.error("Error opening session xml", ex);
        }
    }

    @FXML
    private void onSaveXmlAction() {
        FileChooser fileChooser = new FileChooser();
        fileChooser.setTitle("Save Session");
        fileChooser.setInitialFileName("session.xml");
        fileChooser.setInitialDirectory(new File(configuration.getXmlPath()));
        fileChooser.getExtensionFilters().add(new FileChooser.ExtensionFilter("XML", "*.xml"));
        File file = fileChooser.showSaveDialog(window);
        if (file != null) {
            logger.info("saving session xml: {}", file.getPath());
            try {
                coreClient.saveSession(file);
            } catch (IOException ex) {
                Toast.error("Error saving session xml", ex);
            }
        }
    }

    @FXML
    private void onSessionMenu(ActionEvent event) {
        logger.info("sessions menu clicked");
        try {
            sessionsDialog.showDialog();
        } catch (IOException ex) {
            Toast.error("Error retrieving sessions", ex);
        }
    }

    @FXML
    private void onSessionHooksMenu(ActionEvent event) {
        hooksDialog.showDialog();
    }

    @FXML
    private void onSessionOptionsMenu(ActionEvent event) {
        try {
            List<ConfigGroup> configGroups = coreClient.getSessionConfig();
            configDialog.showDialog("Session Options", configGroups, () -> {
                List<ConfigOption> options = configDialog.getOptions();
                try {
                    boolean result = coreClient.setSessionConfig(options);
                    if (result) {
                        Toast.info("Session options saved");
                    } else {
                        Toast.error("Failure to set session config");
                    }
                } catch (IOException ex) {
                    logger.error("error getting session config");
                }
            });
        } catch (IOException ex) {
            logger.error("error getting session config");
        }
    }

    @FXML
    private void onTestMenuCharts(ActionEvent event) {
        chartDialog.show();
    }

    @FXML
    private void onTestMenuGeo(ActionEvent event) {
        geoDialog.showDialog();
    }

    @Override
    public void initialize(URL location, ResourceBundle resources) {
        coreWebSocket = new CoreWebSocket(this);
        configuration = ConfigUtils.load();
        String coreUrl = configuration.getCoreRest();
        logger.info("core rest: {}", coreUrl);
        connectDialog.setCoreUrl(coreUrl);
        connectToCore(coreUrl);

        logger.info("controller initialize");
        swingNode.setContent(networkGraph.getGraphViewer());

        // update graph preferences
        networkGraph.updatePreferences(configuration);

        // set node types / default services
        graphToolbar.setupNodeTypes();
        defaultServices = configuration.getNodeTypeConfigs().stream()
                .collect(Collectors.toMap(NodeTypeConfig::getModel, NodeTypeConfig::getServices));

        // set graph toolbar
        borderPane.setLeft(graphToolbar);

        // setup snackbar
        Toast.setSnackbarRoot(stackPane);

        // node details
        networkGraph.getGraphViewer().getPickedVertexState().addItemListener(event -> {
            CoreNode node = (CoreNode) event.getItem();
            logger.info("picked: {}", node.getName());
            if (event.getStateChange() == ItemEvent.SELECTED) {
                Platform.runLater(() -> {
                    nodeDetails.setNode(node);
                    borderPane.setRight(nodeDetails);
                });
            } else {
                Platform.runLater(() -> borderPane.setRight(null));
            }
        });

        // edge details
        networkGraph.getGraphViewer().getPickedEdgeState().addItemListener(event -> {
            CoreLink link = (CoreLink) event.getItem();
            logger.info("picked: {} - {}", link.getNodeOne(), link.getNodeTwo());
            if (event.getStateChange() == ItemEvent.SELECTED) {
                Platform.runLater(() -> {
                    linkDetails.setLink(link);
                    borderPane.setRight(linkDetails);
                });
            } else {
                Platform.runLater(() -> borderPane.setRight(null));
            }
        });
    }
}
