package com.core.client;

import com.core.client.rest.*;
import com.core.data.*;

import java.io.File;
import java.io.IOException;
import java.util.List;

public interface ICoreClient {
    void joinSession(Integer joinId, boolean notification) throws IOException;

    void createSession() throws IOException;

    GetSessions getSessions() throws IOException;

    GetSession getSession(Integer sessionId) throws IOException;

    void initialJoin() throws IOException;

    boolean start() throws IOException;

    void updateState(SessionState state);

    boolean setState(SessionState state) throws IOException;

    GetServices getServices() throws IOException;

    CoreService getService(CoreNode node, String serviceName) throws IOException;

    boolean setService(CoreNode node, String serviceName, CoreService service) throws IOException;

    String getServiceFile(CoreNode node, String serviceName, String fileName) throws IOException;

    boolean setServiceFile(CoreNode node, String serviceName, ServiceFile serviceFile) throws IOException;

    GetConfig getEmaneModelConfig(CoreNode node, String model) throws IOException;

    GetConfig getEmaneConfig(CoreNode node) throws IOException;

    GetEmaneModels getEmaneModels() throws IOException;

    boolean setEmaneConfig(CoreNode node, List<ConfigOption> options) throws IOException;

    boolean setEmaneModelConfig(CoreNode node, String model, List<ConfigOption> options) throws IOException;

    boolean isRunning();

    void saveSession(File file) throws IOException;

    void openSession(File file) throws IOException;

    GetConfig getSessionConfig() throws IOException;

    boolean setSessionConfig(SetConfig config) throws IOException;

    boolean createNode(CoreNode node) throws IOException;

    boolean deleteNode(CoreNode node) throws IOException;

    boolean createLink(CoreLink link) throws IOException;

    boolean createHook(Hook hook) throws IOException;

    GetHooks getHooks() throws IOException;

    WlanConfig getWlanConfig(CoreNode node) throws IOException;

    boolean setWlanConfig(CoreNode node, WlanConfig config) throws IOException;

    String getTerminalCommand(CoreNode node) throws IOException;

    boolean setMobilityConfig(CoreNode node, MobilityConfig config) throws IOException;

    MobilityConfig getMobilityConfig(CoreNode node) throws IOException;

    boolean mobilityAction(CoreNode node, String action) throws IOException;
}
