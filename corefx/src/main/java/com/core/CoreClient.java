package com.core;

import com.core.data.*;
import com.core.graph.NetworkGraph;
import com.core.rest.*;
import com.core.ui.Toast;
import lombok.Data;
import org.apache.logging.log4j.LogManager;
import org.apache.logging.log4j.Logger;

import java.io.File;
import java.io.IOException;
import java.util.ArrayList;
import java.util.List;

@Data
public class CoreClient {
    private static final Logger logger = LogManager.getLogger();
    private final Controller controller;
    private final NetworkGraph networkGraph;
    private final CoreApi coreApi;
    private Integer sessionId;
    private SessionState sessionState;
    private GetServices services;
    private List<String> emaneModels = new ArrayList<>();

    public CoreClient(Controller controller) {
        this.controller = controller;
        this.networkGraph = controller.getNetworkGraph();
        this.coreApi = controller.getCoreApi();
    }

    public void joinSession(Integer joinId, boolean notification) throws IOException {
        networkGraph.reset();
        GetSession session = coreApi.getSession(joinId);
        sessionId = joinId;
        sessionState = SessionState.get(session.getState());

        logger.info("joining core session({}) state({}): {}", sessionId, sessionState, session);
        for (CoreNode node : session.getNodes()) {
            if (node.getModel() == null) {
                logger.info("skipping joined session node: {}", node.getName());
                continue;
            }
            
            NodeType nodeType = NodeType.getNodeType(node.getNodeTypeKey());
            node.setIcon(nodeType.getIcon());
            networkGraph.addNode(node);
        }

        for (CoreLink link : session.getLinks()) {
            networkGraph.addLink(link);
        }

        networkGraph.getGraphViewer().repaint();

        if (notification) {
            Toast.info(String.format("Joined Session %s", sessionId.toString()));
        }

        updateController();
    }

    public void createSession() throws IOException {
        CreatedSession session = coreApi.createSession();
        logger.info("created session: {}", session);
        sessionId = session.getId();
        sessionState = SessionState.get(session.getState());
        Toast.info(String.format("Created Session %s", sessionId.toString()));
        joinSession(sessionId, false);
    }

    public void initialJoin() throws IOException {
        services = coreApi.getServices();
        controller.getNodeServicesDialog().setServices(services);

        logger.info("core services: {}", services);

        logger.info("initial core session join");
        GetSessions response = coreApi.getSessions();
        logger.info("existing sessions: {}", response);
        if (response.getSessions().isEmpty()) {
            logger.info("creating initial session");
            createSession();
            updateController();
        } else {
            GetSessionsData getSessionsData = response.getSessions().get(0);
            Integer joinId = getSessionsData.getId();
            joinSession(joinId, true);
        }

        // set emane models
        emaneModels = coreApi.getEmaneModels(sessionId).getModels();
        controller.getNodeEmaneDialog().setModels(emaneModels);
    }

    public boolean start() throws IOException {
        networkGraph.updatePositions();

        boolean result = setState(SessionState.DEFINITION);
        if (!result) {
            return false;
        }

        result = setState(SessionState.CONFIGURATION);
        if (!result) {
            return false;
        }

        for (Hook hook : controller.getHooksDialog().getHooks()) {
            if (!createHook(hook)) {
                return false;
            }
        }

        for (CoreNode node : networkGraph.getGraph().getVertices()) {
            if (!coreApi.createNode(sessionId, node)) {
                return false;
            }
        }

        for (CoreLink link : networkGraph.getGraph().getEdges()) {
            if (!coreApi.createLink(sessionId, link)) {
                return false;
            }
        }

        return setState(SessionState.INSTANTIATION);
    }

    public boolean setState(SessionState state) throws IOException {
        boolean result = coreApi.setSessionState(sessionId, state);
        if (result) {
            sessionState = state;
        }
        return result;
    }

    public CoreService getService(CoreNode node, String serviceName) throws IOException {
        return coreApi.getService(sessionId, node, serviceName);
    }

    public boolean setService(CoreNode node, String serviceName, CoreService service) throws IOException {
        return coreApi.setService(sessionId, node, serviceName, service);
    }

    public String getServiceFile(CoreNode node, String serviceName, String fileName) throws IOException {
        return coreApi.getServiceFile(sessionId, node, serviceName, fileName);
    }

    public boolean setServiceFile(CoreNode node, String serviceName, ServiceFile serviceFile) throws IOException {
        return coreApi.setServiceFile(sessionId, node, serviceName, serviceFile);
    }

    public GetConfig getEmaneModelConfig(CoreNode node, String model) throws IOException {
        return coreApi.getEmaneModelConfig(sessionId, node, model);
    }

    public GetConfig getEmaneConfig(CoreNode node) throws IOException {
        return coreApi.getEmaneConfig(sessionId, node);
    }

    public boolean setEmaneConfig(CoreNode node, List<ConfigOption> options) throws IOException {
        return coreApi.setEmaneConfig(sessionId, node, options);
    }

    public boolean setEmaneModelConfig(CoreNode node, String model, List<ConfigOption> options) throws IOException {
        return coreApi.setEmaneModelConfig(sessionId, node, model, options);
    }

    private void updateController() {
        controller.getGraphToolbar().setRunButton(isRunning());
        controller.getHooksDialog().updateHooks();
    }

    public boolean isRunning() {
        return sessionState == SessionState.RUNTIME;
    }

    public void saveSession(File file) throws IOException {
        coreApi.saveSession(sessionId, file);
    }

    public void openSession(File file) throws IOException {
        CreatedSession createdSession = coreApi.openSession(file);
        joinSession(createdSession.getId(), true);
    }

    public GetConfig getSessionConfig() throws IOException {
        return coreApi.getSessionConfig(sessionId);
    }

    public boolean setSessionConfig(SetConfig config) throws IOException {
        return coreApi.setSessionConfig(sessionId, config);
    }

    public boolean createNode(CoreNode node) throws IOException {
        return coreApi.createNode(sessionId, node);
    }

    public boolean deleteNode(CoreNode node) throws IOException {
        return coreApi.deleteNode(sessionId, node);
    }

    public boolean createHook(Hook hook) throws IOException {
        return coreApi.createHook(sessionId, hook);
    }

    public GetHooks getHooks() throws IOException {
        return coreApi.getHooks(sessionId);
    }

    public WlanConfig getWlanConfig(CoreNode node) throws IOException {
        return coreApi.getWlanConfig(sessionId, node);
    }

    public boolean setWlanConfig(CoreNode node, WlanConfig config) throws IOException {
        return coreApi.setWlanConfig(sessionId, node, config);
    }

    public String getTerminalCommand(CoreNode node) throws IOException {
        return coreApi.getTerminalCommand(sessionId, node);
    }

    public boolean setMobilityConfig(CoreNode node, MobilityConfig config) throws IOException {
        return coreApi.setMobilityConfig(sessionId, node, config);
    }

    public MobilityConfig getMobilityConfig(CoreNode node) throws IOException {
        return coreApi.getMobilityConfig(sessionId, node);
    }

    public boolean mobilityAction(CoreNode node, String action) throws IOException {
        return coreApi.mobilityAction(sessionId, node, action);
    }
}
