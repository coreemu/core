package com.core;

import com.core.client.ICoreClient;
import com.core.client.grpc.CoreGrpcClient;
import com.core.data.*;
import com.core.graph.NetworkGraph;
import com.core.ui.*;
import com.core.ui.dialogs.*;
import com.core.utils.ConfigUtils;
import com.core.utils.Configuration;
import com.core.utils.NodeTypeConfig;
import com.jfoenix.controls.JFXDecorator;
import com.jfoenix.controls.JFXProgressBar;
import javafx.application.Application;
import javafx.application.Platform;
import javafx.concurrent.Task;
import javafx.embed.swing.SwingNode;
import javafx.event.ActionEvent;
import javafx.fxml.FXML;
import javafx.fxml.Initializable;
import javafx.scene.control.CheckMenuItem;
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
    @FXML private CheckMenuItem throughputMenuItem;

    private final ExecutorService executorService = Executors.newSingleThreadExecutor();
    private final Map<Integer, MobilityConfig> mobilityScripts = new HashMap<>();
    private final Map<Integer, MobilityPlayerDialog> mobilityPlayerDialogs = new HashMap<>();
    private Application application;
    private JFXDecorator decorator;
    private Stage window;
    private Configuration configuration;
    private Map<String, Set<String>> defaultServices = new HashMap<>();

    // core client utilities
    private ICoreClient coreClient = new CoreGrpcClient();

    // ui elements
    private NetworkGraph networkGraph = new NetworkGraph(this);
    private AnnotationToolbar annotationToolbar = new AnnotationToolbar(networkGraph);
    private NodeDetails nodeDetails = new NodeDetails(this);
    private LinkDetails linkDetails = new LinkDetails(this);
    private GraphToolbar graphToolbar = new GraphToolbar(this);

    // dialogs
    private Rj45Dialog rj45Dialog = new Rj45Dialog(this);
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

    public void connectToCore(String address, int port) {
        executorService.submit(() -> {
            try {
                coreClient.setConnection(address, port);
                initialJoin();
            } catch (IOException ex) {
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
        logger.info("emane models: {}", emaneModels);
        nodeEmaneDialog.setModels(emaneModels);
    }

    public void joinSession(Integer sessionId) throws IOException {
        // clear graph
        networkGraph.reset();

        // clear out any previously set information
        mobilityPlayerDialogs.clear();
        mobilityScripts.clear();
        mobilityDialog.setNode(null);
        Platform.runLater(() -> borderPane.setRight(null));

        // get session to join
        Session session = coreClient.joinSession(sessionId);

        // display all nodes
        for (CoreNode node : session.getNodes()) {
            networkGraph.addNode(node);
        }

        // display all links
        for (CoreLink link : session.getLinks()) {
            networkGraph.addLink(link);
        }

        // refresh graph
        networkGraph.getGraphViewer().repaint();

        // update other components for new session
        graphToolbar.setRunButton(coreClient.isRunning());
        hooksDialog.updateHooks();

        // update session default services
        setCoreDefaultServices();

        // retrieve current mobility script configurations and show dialogs
        Map<Integer, MobilityConfig> mobilityConfigMap = coreClient.getMobilityConfigs();
        mobilityScripts.putAll(mobilityConfigMap);
        showMobilityScriptDialogs();

        Platform.runLater(() -> decorator.setTitle(String.format("CORE (Session %s)", sessionId)));
    }

    public boolean startSession() {
        // force nodes to get latest positions
        networkGraph.updatePositions();

        // retrieve items for creation/start
        Collection<CoreNode> nodes = networkGraph.getGraph().getVertices();
        Collection<CoreLink> links = networkGraph.getGraph().getEdges();
        List<Hook> hooks = hooksDialog.getHooks();

        // start/create session
        boolean result = false;
        progressBar.setVisible(true);
        try {
            result = coreClient.start(nodes, links, hooks);
            if (result) {
                showMobilityScriptDialogs();
                saveXmlMenuItem.setDisable(false);
            }
        } catch (IOException ex) {
            Toast.error("Failure Starting Session", ex);
        } finally {
            progressBar.setVisible(false);
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
            saveXmlMenuItem.setDisable(true);
        }
        return result;
    }

    public void handleThroughputs(Throughputs throughputs) {
        for (InterfaceThroughput interfaceThroughput : throughputs.getInterfaces()) {
            int nodeId = interfaceThroughput.getNode();
            CoreNode node = networkGraph.getVertex(nodeId);
            Collection<CoreLink> links = networkGraph.getGraph().getIncidentEdges(node);
            int interfaceId = interfaceThroughput.getNodeInterface();
            for (CoreLink link : links) {
                if (nodeId == link.getNodeOne()) {
                    if (interfaceId == link.getInterfaceOne().getId()) {
                        link.setThroughput(interfaceThroughput.getThroughput());
                    }
                } else {
                    if (interfaceId == link.getInterfaceTwo().getId()) {
                        link.setThroughput(interfaceThroughput.getThroughput());
                    }
                }
            }
        }
        networkGraph.getGraphViewer().repaint();
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
        rj45Dialog.setOwner(window);
    }

    private void showMobilityScriptDialogs() {
        for (Map.Entry<Integer, MobilityConfig> entry : mobilityScripts.entrySet()) {
            Integer nodeId = entry.getKey();
            CoreNode node = networkGraph.getVertex(nodeId);
            MobilityConfig mobilityConfig = entry.getValue();
            Platform.runLater(() -> {
                MobilityPlayerDialog mobilityPlayerDialog = new MobilityPlayerDialog(this, node);
                mobilityPlayerDialog.setOwner(window);
                mobilityPlayerDialogs.put(nodeId, mobilityPlayerDialog);
                mobilityPlayerDialog.showDialog(mobilityConfig);
            });
        }
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
        configuration = ConfigUtils.load();
        String address = configuration.getCoreAddress();
        int port = configuration.getCorePort();
        logger.info("core connection: {}:{}", address, port);
        connectDialog.setAddress(address);
        connectDialog.setPort(port);
        connectToCore(address, port);

        logger.info("controller initialize");
        coreClient.initialize(this);
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

        // setup throughput menu item
        throughputMenuItem.setOnAction(event -> executorService.submit(new ChangeThroughputTask()));

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

    private class ChangeThroughputTask extends Task<Boolean> {
        @Override
        protected Boolean call() throws Exception {
            if (throughputMenuItem.isSelected()) {
                return coreClient.startThroughput(Controller.this);
            } else {
                return coreClient.stopThroughput();
            }
        }

        @Override
        protected void succeeded() {
            if (getValue()) {
                if (throughputMenuItem.isSelected()) {
                    networkGraph.setShowThroughput(true);
                } else {
                    networkGraph.setShowThroughput(false);
                    networkGraph.getGraph().getEdges().forEach(edge -> edge.setThroughput(0));
                    networkGraph.getGraphViewer().repaint();
                }
            } else {
                Toast.error("Failure changing throughput");
            }
        }

        @Override
        protected void failed() {
            Toast.error("Error changing throughput", new RuntimeException(getException()));
        }
    }
}
