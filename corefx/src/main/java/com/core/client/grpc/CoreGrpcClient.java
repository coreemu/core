package com.core.client.grpc;

import com.core.client.ICoreClient;
import com.core.client.rest.ServiceFile;
import com.core.client.rest.WlanConfig;
import com.core.data.*;
import com.google.protobuf.ByteString;
import io.grpc.ManagedChannel;
import io.grpc.ManagedChannelBuilder;
import org.apache.logging.log4j.LogManager;
import org.apache.logging.log4j.Logger;

import java.io.File;
import java.io.FileInputStream;
import java.io.IOException;
import java.io.PrintWriter;
import java.util.*;

public class CoreGrpcClient implements ICoreClient {
    private static final Logger logger = LogManager.getLogger();
    private String address;
    private int port;
    private Integer sessionId;
    private SessionState sessionState;
    private CoreApiGrpc.CoreApiBlockingStub blockingStub;
    private ManagedChannel channel;

    private CoreProto.Node nodeToProto(CoreNode node) {
        CoreProto.Position position = CoreProto.Position.newBuilder()
                .setX(node.getPosition().getX().floatValue())
                .setY(node.getPosition().getY().floatValue())
                .build();
        CoreProto.Node.Builder builder = CoreProto.Node.newBuilder()
                .addAllServices(node.getServices())
                .setType(CoreProto.NodeType.forNumber(node.getType()))
                .setPosition(position);
        if (node.getId() != null) {
            builder.setId(node.getId());
        }
        if (node.getName() != null) {
            builder.setName(node.getName());
        }
        if (node.getEmane() != null) {
            builder.setEmane(node.getEmane());
        }
        if (node.getModel() != null) {
            builder.setModel(node.getModel());
        }
        if (node.getIcon() != null) {
            builder.setIcon(node.getIcon());
        }

        return builder.build();
    }

    private List<ConfigGroup> protoToConfigGroups(List<CoreProto.ConfigGroup> protoConfigs) {
        List<ConfigGroup> configs = new ArrayList<>();
        for (CoreProto.ConfigGroup protoConfig : protoConfigs) {
            ConfigGroup config = new ConfigGroup();
            config.setName(protoConfig.getName());
            for (CoreProto.ConfigOption protoOption : protoConfig.getOptionsList()) {
                ConfigOption option = new ConfigOption();
                option.setType(protoOption.getType());
                option.setLabel(protoOption.getLabel());
                option.setName(protoOption.getName());
                option.setValue(protoOption.getValue());
                option.setSelect(protoOption.getSelectList());
                config.getOptions().add(option);
            }
            configs.add(config);
        }
        return configs;
    }

    private CoreProto.LinkOptions linkOptionsToProto(CoreLinkOptions options) {
        CoreProto.LinkOptions.Builder builder = CoreProto.LinkOptions.newBuilder();
        boolean unidirectional = false;
        if (options.getUnidirectional() != null && options.getUnidirectional() == 1) {
            unidirectional = true;
        }
        if (options.getBandwidth() != null) {
            builder.setBandwidth(options.getBandwidth().floatValue());
        }
        if (options.getBurst() != null) {
            builder.setBurst(options.getBurst().floatValue());
        }
        if (options.getDelay() != null) {
            builder.setDelay(options.getDelay().floatValue());
        }
        if (options.getDup() != null) {
            builder.setDup(options.getDup().floatValue());
        }
        if (options.getJitter() != null) {
            builder.setJitter(options.getJitter().floatValue());
        }
        if (options.getMburst() != null) {
            builder.setMburst(options.getMburst().floatValue());
        }
        if (options.getMer() != null) {
            builder.setMer(options.getMer().floatValue());
        }
        if (options.getPer() != null) {
            builder.setPer(options.getPer().floatValue());
        }
        if (options.getKey() != null) {
            builder.setKey(options.getKey().toString());
        }
        if (options.getOpaque() != null) {
            builder.setOpaque(options.getOpaque());
        }
        builder.setUnidirectional(unidirectional);
        return builder.build();
    }

    private CoreProto.Interface interfaceToProto(CoreInterface coreInterface) {
        CoreProto.Interface.Builder builder = CoreProto.Interface.newBuilder();
        if (coreInterface.getName() != null) {
            builder.setName(coreInterface.getName());
        }
        if (coreInterface.getMac() != null) {
            builder.setMac(coreInterface.getMac());
        }
        if (coreInterface.getIp4() != null) {
            builder.setIp4(coreInterface.getIp4());
        }
        if (coreInterface.getIp4Mask() != null) {
            builder.setIp4Mask(coreInterface.getIp4Mask());
        }
        if (coreInterface.getIp6() != null) {
            builder.setIp6(coreInterface.getIp6());
        }
        if (coreInterface.getIp6Mask() != null) {
            builder.setIp6Mask(Integer.parseInt(coreInterface.getIp6Mask()));
        }
        return builder.build();
    }

    private Map<String, String> configOptionListToMap(List<ConfigOption> options) {
        Map<String, String> config = new HashMap<>();
        for (ConfigOption option : options) {
            config.put(option.getName(), option.getValue());
        }
        return config;
    }

    @Override
    public void setConnection(String address, int port) {
        this.address = address;
        this.port = port;
        logger.info("set connection: {}:{}", this.address, this.port);
        channel = ManagedChannelBuilder.forAddress(this.address, this.port).usePlaintext().build();
        logger.info("channel: {}", channel);
        blockingStub = CoreApiGrpc.newBlockingStub(channel);
        logger.info("stub: {}", blockingStub);
    }

    @Override
    public boolean isLocalConnection() {
        return address.equals("127.0.0.1") || address.equals("localhost");
    }

    @Override
    public Integer currentSession() {
        return sessionId;
    }

    @Override
    public boolean startThroughput() throws IOException {
        // TODO: convert
        return false;
    }

    @Override
    public boolean stopThroughput() throws IOException {
        // TODO: convert
        return false;
    }

    @Override
    public void updateSession(Integer sessionId) {
        this.sessionId = sessionId;
    }

    @Override
    public void updateState(SessionState state) {
        sessionState = state;
    }

    @Override
    public SessionOverview createSession() throws IOException {
        CoreProto.CreateSessionRequest request = CoreProto.CreateSessionRequest.newBuilder().build();
        CoreProto.CreateSessionResponse response = blockingStub.createSession(request);
        SessionOverview overview = new SessionOverview();
        overview.setId(response.getId());
        overview.setState(response.getStateValue());
        overview.setNodes(0);
        return overview;
    }

    @Override
    public boolean deleteSession(Integer sessionId) throws IOException {
        CoreProto.DeleteSessionRequest request = CoreProto.DeleteSessionRequest.newBuilder().setId(sessionId).build();
        return blockingStub.deleteSession(request).getResult();
    }

    @Override
    public List<SessionOverview> getSessions() throws IOException {
        CoreProto.GetSessionsRequest request = CoreProto.GetSessionsRequest.newBuilder().build();
        CoreProto.GetSessionsResponse response = blockingStub.getSessions(request);
        List<SessionOverview> sessions = new ArrayList<>();
        for (CoreProto.SessionSummary summary : response.getSessionsList()) {
            SessionOverview overview = new SessionOverview();
            overview.setId(summary.getId());
            overview.setNodes(summary.getNodes());
            overview.setState(summary.getStateValue());
            sessions.add(overview);
        }
        return sessions;
    }

    @Override
    public Session getSession(Integer sessionId) throws IOException {
        logger.info("getting session: {}", sessionId);
        CoreProto.GetSessionRequest request = CoreProto.GetSessionRequest.newBuilder().setId(sessionId).build();
        CoreProto.GetSessionResponse response = blockingStub.getSession(request);
        Session session = new Session();
        for (CoreProto.Node protoNode : response.getSession().getNodesList()) {
            if (CoreProto.NodeType.NODE_PEER_TO_PEER == protoNode.getType()) {
                continue;
            }

            logger.info("adding node: {}", protoNode);
            CoreNode node = new CoreNode(protoNode.getId());
            node.setName(protoNode.getName());
            node.setEmane(protoNode.getEmane());
            node.setIcon(protoNode.getIcon());
            node.setModel(protoNode.getModel());
            node.setServices(new HashSet<>(protoNode.getServicesList()));
            node.getPosition().setX((double) protoNode.getPosition().getX());
            node.getPosition().setY((double) protoNode.getPosition().getY());
            node.setType(protoNode.getTypeValue());
            session.getNodes().add(node);
        }
        for (CoreProto.Link linkProto : response.getSession().getLinksList()) {
            logger.info("adding link: {} - {}", linkProto.getNodeOne(), linkProto.getNodeTwo());
            CoreLink link = new CoreLink();
            link.setNodeOne(linkProto.getNodeOne());
            link.setNodeTwo(linkProto.getNodeTwo());
            CoreProto.Interface interfaceOneProto = linkProto.getInterfaceOne();
            CoreInterface interfaceOne = new CoreInterface();
            interfaceOne.setId(interfaceOneProto.getId());
            interfaceOne.setName(interfaceOneProto.getName());
            interfaceOne.setMac(interfaceOneProto.getMac());
            interfaceOne.setIp4(interfaceOneProto.getIp4());
            interfaceOne.setIp4Mask(interfaceOneProto.getIp4Mask());
            interfaceOne.setIp6(interfaceOneProto.getIp6());
            interfaceOne.setIp6Mask(Integer.toString(interfaceOneProto.getIp6Mask()));
            link.setInterfaceOne(interfaceOne);

            CoreProto.Interface interfaceTwoProto = linkProto.getInterfaceTwo();
            CoreInterface interfaceTwo = new CoreInterface();
            interfaceTwo.setId(interfaceTwoProto.getId());
            interfaceTwo.setName(interfaceTwoProto.getName());
            interfaceTwo.setMac(interfaceTwoProto.getMac());
            interfaceTwo.setIp4(interfaceTwoProto.getIp4());
            interfaceTwo.setIp4Mask(interfaceTwoProto.getIp4Mask());
            interfaceTwo.setIp6(interfaceTwoProto.getIp6());
            interfaceTwo.setIp6Mask(Integer.toString(interfaceTwoProto.getIp6Mask()));
            link.setInterfaceTwo(interfaceTwo);

            CoreLinkOptions options = new CoreLinkOptions();
            CoreProto.LinkOptions protoOptions = linkProto.getOptions();
            options.setBandwidth((double) protoOptions.getBandwidth());
            options.setDelay((double) protoOptions.getDelay());
            options.setDup((double) protoOptions.getDup());
            options.setJitter((double) protoOptions.getJitter());
            options.setPer((double) protoOptions.getPer());
            options.setBurst((double) protoOptions.getBurst());
            if (!protoOptions.getKey().isEmpty()) {
                options.setKey(Integer.parseInt(protoOptions.getKey()));
            }
            options.setMburst((double) protoOptions.getMburst());
            options.setMer((double) protoOptions.getMer());
            options.setOpaque(protoOptions.getOpaque());
            options.setUnidirectional(protoOptions.getUnidirectional() ? 1 : 0);
            link.setOptions(options);
            session.getLinks().add(link);
        }
        session.setState(response.getSession().getStateValue());
        return session;
    }

    @Override
    public boolean start(Collection<CoreNode> nodes, Collection<CoreLink> links, List<Hook> hooks) throws IOException {
        boolean result = setState(SessionState.DEFINITION);
        if (!result) {
            return false;
        }

        result = setState(SessionState.CONFIGURATION);
        if (!result) {
            return false;
        }

        for (Hook hook : hooks) {
            if (!createHook(hook)) {
                return false;
            }
        }

        for (CoreNode node : nodes) {
            // must pre-configure wlan nodes, if not already
            if (node.getNodeType().getValue() == NodeType.WLAN) {
                WlanConfig config = getWlanConfig(node);
                setWlanConfig(node, config);
            }

            if (!createNode(node)) {
                return false;
            }
        }

        for (CoreLink link : links) {
            if (!createLink(link)) {
                return false;
            }
        }

        return setState(SessionState.INSTANTIATION);
    }

    @Override
    public boolean stop() throws IOException {
        return setState(SessionState.SHUTDOWN);
    }

    @Override
    public boolean setState(SessionState state) throws IOException {
        CoreProto.SetSessionStateRequest request = CoreProto.SetSessionStateRequest.newBuilder()
                .setId(sessionId)
                .setStateValue(state.getValue())
                .build();
        CoreProto.SetSessionStateResponse response = blockingStub.setSessionState(request);
        return response.getResult();
    }

    @Override
    public Map<String, List<String>> getServices() throws IOException {
        CoreProto.GetServicesRequest request = CoreProto.GetServicesRequest.newBuilder().build();
        CoreProto.GetServicesResponse response = blockingStub.getServices(request);
        Map<String, List<String>> servicesMap = new HashMap<>();
        for (CoreProto.Service protoService : response.getServicesList()) {
            List<String> services = servicesMap.computeIfAbsent(protoService.getGroup(), x -> new ArrayList<>());
            services.add(protoService.getName());
        }
        return servicesMap;
    }

    @Override
    public Map<String, List<String>> getDefaultServices() throws IOException {
        CoreProto.GetServiceDefaultsRequest request = CoreProto.GetServiceDefaultsRequest.newBuilder().build();
        CoreProto.GetServiceDefaultsResponse response = blockingStub.getServiceDefaults(request);
        Map<String, List<String>> servicesMap = new HashMap<>();
        for (CoreProto.ServiceDefaults serviceDefaults : response.getDefaultsList()) {
            servicesMap.put(serviceDefaults.getNodeType(), serviceDefaults.getServicesList());
        }
        return servicesMap;
    }

    @Override
    public boolean setDefaultServices(Map<String, Set<String>> defaults) throws IOException {
        List<CoreProto.ServiceDefaults> allDefaults = new ArrayList<>();
        for (Map.Entry<String, Set<String>> entry : defaults.entrySet()) {
            String nodeType = entry.getKey();
            Set<String> services = entry.getValue();
            CoreProto.ServiceDefaults serviceDefaults = CoreProto.ServiceDefaults.newBuilder()
                    .setNodeType(nodeType)
                    .addAllServices(services)
                    .build();
            allDefaults.add(serviceDefaults);
        }

        CoreProto.SetServiceDefaultsRequest request = CoreProto.SetServiceDefaultsRequest.newBuilder()
                .setSession(sessionId)
                .addAllDefaults(allDefaults)
                .build();
        CoreProto.SetServiceDefaultsResponse response = blockingStub.setServiceDefaults(request);
        return response.getResult();
    }

    @Override
    public CoreService getService(CoreNode node, String serviceName) throws IOException {
        CoreProto.GetNodeServiceRequest request = CoreProto.GetNodeServiceRequest.newBuilder().build();
        CoreProto.GetNodeServiceResponse response = blockingStub.getNodeService(request);
        CoreProto.NodeServiceData nodeServiceData = response.getService();
        CoreService service = new CoreService();
        service.setShutdown(nodeServiceData.getShutdownList());
        service.setStartup(nodeServiceData.getStartupList());
        service.setValidate(nodeServiceData.getValidateList());
        service.setConfigs(nodeServiceData.getConfigsList());
        service.setDependencies(nodeServiceData.getDependenciesList());
        service.setDirs(nodeServiceData.getDirsList());
        service.setExecutables(nodeServiceData.getExecutablesList());
        service.setMeta(nodeServiceData.getMeta());
        service.setValidationMode(nodeServiceData.getValidationMode().name());
        service.setValidationTimer(Integer.toString(nodeServiceData.getValidationTimer()));
        return service;
    }

    @Override
    public boolean setService(CoreNode node, String serviceName, CoreService service) throws IOException {
        CoreProto.SetNodeServiceRequest request = CoreProto.SetNodeServiceRequest.newBuilder()
                .setId(node.getId())
                .setSession(sessionId)
                .setService(serviceName)
                .build();
        request.getShutdownList().addAll(service.getShutdown());
        request.getValidateList().addAll(service.getValidate());
        request.getStartupList().addAll(service.getStartup());
        return blockingStub.setNodeService(request).getResult();
    }

    @Override
    public String getServiceFile(CoreNode node, String serviceName, String fileName) throws IOException {
        CoreProto.GetNodeServiceFileRequest request = CoreProto.GetNodeServiceFileRequest.newBuilder()
                .setSession(sessionId)
                .setId(node.getId())
                .setService(serviceName)
                .build();
        CoreProto.GetNodeServiceFileResponse response = blockingStub.getNodeServiceFile(request);
        return response.getData().toStringUtf8();
    }

    @Override
    public boolean startService(CoreNode node, String serviceName) throws IOException {
        CoreProto.ServiceActionRequest request = CoreProto.ServiceActionRequest.newBuilder()
                .setSession(sessionId)
                .setId(node.getId())
                .setService(serviceName)
                .setAction(CoreProto.ServiceAction.SERVICE_START)
                .build();
        return blockingStub.serviceAction(request).getResult();
    }

    @Override
    public boolean stopService(CoreNode node, String serviceName) throws IOException {
        CoreProto.ServiceActionRequest request = CoreProto.ServiceActionRequest.newBuilder()
                .setSession(sessionId)
                .setId(node.getId())
                .setService(serviceName)
                .setAction(CoreProto.ServiceAction.SERVICE_STOP)
                .build();
        return blockingStub.serviceAction(request).getResult();
    }

    @Override
    public boolean restartService(CoreNode node, String serviceName) throws IOException {
        CoreProto.ServiceActionRequest request = CoreProto.ServiceActionRequest.newBuilder()
                .setSession(sessionId)
                .setId(node.getId())
                .setService(serviceName)
                .setAction(CoreProto.ServiceAction.SERVICE_RESTART)
                .build();
        return blockingStub.serviceAction(request).getResult();
    }

    @Override
    public boolean validateService(CoreNode node, String serviceName) throws IOException {
        CoreProto.ServiceActionRequest request = CoreProto.ServiceActionRequest.newBuilder()
                .setSession(sessionId)
                .setId(node.getId())
                .setService(serviceName)
                .setAction(CoreProto.ServiceAction.SERVICE_VALIDATE)
                .build();
        return blockingStub.serviceAction(request).getResult();
    }

    @Override
    public boolean setServiceFile(CoreNode node, String serviceName, ServiceFile serviceFile) throws IOException {
        CoreProto.SetNodeServiceFileRequest request = CoreProto.SetNodeServiceFileRequest.newBuilder()
                .setSession(sessionId)
                .setId(node.getId())
                .setService(serviceName)
                .setFile(serviceFile.getName())
                .setData(ByteString.copyFromUtf8(serviceFile.getData()))
                .build();
        CoreProto.SetNodeServiceFileResponse response = blockingStub.setNodeServiceFile(request);
        return response.getResult();
    }

    @Override
    public List<ConfigGroup> getEmaneConfig(CoreNode node) throws IOException {
        CoreProto.GetEmaneConfigRequest request = CoreProto.GetEmaneConfigRequest.newBuilder()
                .setSession(sessionId)
                .build();
        CoreProto.GetEmaneConfigResponse response = blockingStub.getEmaneConfig(request);
        return protoToConfigGroups(response.getGroupsList());
    }

    @Override
    public List<String> getEmaneModels() throws IOException {
        CoreProto.GetEmaneModelsRequest request = CoreProto.GetEmaneModelsRequest.newBuilder()
                .setSession(sessionId)
                .build();
        CoreProto.GetEmaneModelsResponse response = blockingStub.getEmaneModels(request);
        return new ArrayList<>(response.getModelsList());
    }

    @Override
    public boolean setEmaneConfig(CoreNode node, List<ConfigOption> options) throws IOException {
        Map<String, String> config = configOptionListToMap(options);
        CoreProto.SetEmaneConfigRequest request = CoreProto.SetEmaneConfigRequest.newBuilder()
                .setSession(sessionId)
                .putAllConfig(config)
                .build();
        CoreProto.SetEmaneConfigResponse response = blockingStub.setEmaneConfig(request);
        return response.getResult();
    }

    @Override
    public List<ConfigGroup> getEmaneModelConfig(Integer id, String model) throws IOException {
        CoreProto.GetEmaneModelConfigRequest request = CoreProto.GetEmaneModelConfigRequest.newBuilder()
                .setSession(sessionId)
                .setId(id)
                .setModel(model)
                .build();
        CoreProto.GetEmaneModelConfigResponse response = blockingStub.getEmaneModelConfig(request);
        return protoToConfigGroups(response.getGroupsList());
    }

    @Override
    public boolean setEmaneModelConfig(Integer id, String model, List<ConfigOption> options) throws IOException {
        Map<String, String> config = configOptionListToMap(options);
        CoreProto.SetEmaneModelConfigRequest request = CoreProto.SetEmaneModelConfigRequest.newBuilder()
                .setSession(sessionId)
                .setId(id)
                .setModel(model)
                .putAllConfig(config)
                .build();
        CoreProto.SetEmaneModelConfigResponse response = blockingStub.setEmaneModelConfig(request);
        return response.getResult();
    }

    @Override
    public boolean isRunning() {
        return sessionState == SessionState.RUNTIME;
    }

    @Override
    public void saveSession(File file) throws IOException {
        CoreProto.SaveXmlRequest request = CoreProto.SaveXmlRequest.newBuilder()
                .setSession(sessionId)
                .build();
        CoreProto.SaveXmlResponse response = blockingStub.saveXml(request);
        try (PrintWriter writer = new PrintWriter(file)) {
            writer.print(response.getData().toStringUtf8());
        }
    }

    @Override
    public SessionOverview openSession(File file) throws IOException {
        ByteString data = ByteString.readFrom(new FileInputStream(file));
        CoreProto.OpenXmlRequest request = CoreProto.OpenXmlRequest.newBuilder()
                .setData(data)
                .build();
        CoreProto.OpenXmlResponse response = blockingStub.openXml(request);
        SessionOverview sessionOverview = new SessionOverview();
        sessionOverview.setId(response.getSession());
        return sessionOverview;
    }

    @Override
    public List<ConfigGroup> getSessionConfig() throws IOException {
        CoreProto.GetSessionOptionsRequest request = CoreProto.GetSessionOptionsRequest.newBuilder()
                .setId(sessionId)
                .build();
        CoreProto.GetSessionOptionsResponse response = blockingStub.getSessionOptions(request);
        return protoToConfigGroups(response.getGroupsList());
    }

    @Override
    public boolean setSessionConfig(List<ConfigOption> configOptions) throws IOException {
        Map<String, String> config = configOptionListToMap(configOptions);
        CoreProto.SetSessionOptionsRequest request = CoreProto.SetSessionOptionsRequest.newBuilder()
                .setId(sessionId)
                .putAllConfig(config)
                .build();
        CoreProto.SetSessionOptionsResponse response = blockingStub.setSessionOptions(request);
        return response.getResult();
    }

    @Override
    public boolean createNode(CoreNode node) throws IOException {
        CoreProto.Node protoNode = nodeToProto(node);
        CoreProto.AddNodeRequest request = CoreProto.AddNodeRequest.newBuilder()
                .setSession(sessionId)
                .setNode(protoNode)
                .build();
        blockingStub.addNode(request);
        return true;
    }

    @Override
    public String nodeCommand(CoreNode node, String command) throws IOException {
        // TODO: convert
        return null;
    }

    @Override
    public boolean editNode(CoreNode node) throws IOException {
        CoreProto.Position position = CoreProto.Position.newBuilder()
                .setX(node.getPosition().getX().floatValue())
                .setY(node.getPosition().getY().floatValue())
                .build();
        CoreProto.EditNodeRequest request = CoreProto.EditNodeRequest.newBuilder()
                .setSession(sessionId)
                .setId(node.getId())
                .setPosition(position)
                .build();
        CoreProto.EditNodeResponse response = blockingStub.editNode(request);
        return response.getResult();
    }

    @Override
    public boolean deleteNode(CoreNode node) throws IOException {
        CoreProto.DeleteNodeRequest request = CoreProto.DeleteNodeRequest.newBuilder()
                .build();
        CoreProto.DeleteNodeResponse response = blockingStub.deleteNode(request);
        return response.getResult();
    }

    @Override
    public boolean createLink(CoreLink link) throws IOException {
        CoreProto.Link.Builder builder = CoreProto.Link.newBuilder()
                .setTypeValue(link.getType());
        if (link.getNodeOne() != null) {
            builder.setNodeOne(link.getNodeOne());
        }
        if (link.getNodeTwo() != null) {
            builder.setNodeTwo(link.getNodeTwo());
        }
        if (link.getInterfaceOne() != null) {
            builder.setInterfaceOne(interfaceToProto(link.getInterfaceOne()));
        }
        if (link.getInterfaceTwo() != null) {
            builder.setInterfaceTwo(interfaceToProto(link.getInterfaceTwo()));
        }
        if (link.getOptions() != null) {
            builder.setOptions(linkOptionsToProto(link.getOptions()));
        }
        CoreProto.Link protoLink = builder.build();
        CoreProto.AddLinkRequest request = CoreProto.AddLinkRequest.newBuilder()
                .setSession(sessionId)
                .setLink(protoLink)
                .build();
        CoreProto.AddLinkResponse response = blockingStub.addLink(request);
        return response.getResult();
    }

    @Override
    public boolean editLink(CoreLink link) throws IOException {
        CoreProto.EditLinkRequest.Builder builder = CoreProto.EditLinkRequest.newBuilder()
                .setSession(sessionId);
        if (link.getNodeOne() != null) {
            builder.setNodeOne(link.getNodeOne());
        }
        if (link.getNodeTwo() != null) {
            builder.setNodeTwo(link.getNodeTwo());
        }
        if (link.getInterfaceOne() != null) {
            builder.setInterfaceOne(link.getInterfaceOne().getId());
        }
        if (link.getInterfaceTwo() != null) {
            builder.setInterfaceTwo(link.getInterfaceTwo().getId());
        }
        if (link.getOptions() != null) {
            CoreProto.LinkOptions protoOptions = linkOptionsToProto(link.getOptions());
            builder.setOptions(protoOptions);
        }
        CoreProto.EditLinkRequest request = builder.build();
        CoreProto.EditLinkResponse response = blockingStub.editLink(request);
        return response.getResult();
    }

    @Override
    public boolean createHook(Hook hook) throws IOException {
        CoreProto.Hook hookProto = CoreProto.Hook.newBuilder()
                .setStateValue(hook.getState())
                .setData(ByteString.copyFromUtf8(hook.getData()))
                .setFile(hook.getFile())
                .build();
        CoreProto.AddHookRequest request = CoreProto.AddHookRequest.newBuilder()
                .setHook(hookProto)
                .build();
        CoreProto.AddHookResponse response = blockingStub.addHook(request);
        return response.getResult();
    }

    @Override
    public List<Hook> getHooks() throws IOException {
        CoreProto.GetHooksRequest request = CoreProto.GetHooksRequest.newBuilder().setSession(sessionId).build();
        CoreProto.GetHooksResponse response = blockingStub.getHooks(request);
        List<Hook> hooks = new ArrayList<>();
        for (CoreProto.Hook protoHook : response.getHooksList()) {
            Hook hook = new Hook();
            hook.setFile(protoHook.getFile());
            hook.setData(protoHook.getData().toStringUtf8());
            hook.setState(protoHook.getStateValue());
            hooks.add(hook);
        }
        return hooks;
    }

    @Override
    public WlanConfig getWlanConfig(CoreNode node) throws IOException {
        // TODO: convert
        return null;
    }

    @Override
    public boolean setWlanConfig(CoreNode node, WlanConfig config) throws IOException {
        // TODO: convert
        return false;
    }

    @Override
    public String getTerminalCommand(CoreNode node) throws IOException {
        // TODO: convert
        return null;
    }

    @Override
    public Map<Integer, MobilityConfig> getMobilityConfigs() throws IOException {
        CoreProto.GetMobilityConfigsRequest request = CoreProto.GetMobilityConfigsRequest.newBuilder()
                .setSession(sessionId).build();
        CoreProto.GetMobilityConfigsResponse response = blockingStub.getMobilityConfigs(request);

        Map<Integer, MobilityConfig> mobilityConfigs = new HashMap<>();
        for (Integer nodeId : response.getConfigsMap().keySet()) {
            CoreProto.GetMobilityConfigsResponse.MobilityConfig protoMobilityConfig = response.getConfigsMap()
                    .get(nodeId);
            MobilityConfig mobilityConfig = new MobilityConfig();
            CoreProto.ConfigGroup configGroup = protoMobilityConfig.getGroups(0);
            mobilityConfigs.put(nodeId, mobilityConfig);
        }
        return mobilityConfigs;
    }

    @Override
    public boolean setMobilityConfig(CoreNode node, MobilityConfig config) throws IOException {
        // TODO: convert
        return false;
    }

    @Override
    public MobilityConfig getMobilityConfig(CoreNode node) throws IOException {
        CoreProto.GetMobilityConfigRequest request = CoreProto.GetMobilityConfigRequest.newBuilder()
                .setSession(sessionId)
                .setId(node.getId())
                .build();
        CoreProto.GetMobilityConfigResponse response = blockingStub.getMobilityConfig(request);
        // TODO: convert
        return null;
    }

    @Override
    public boolean mobilityAction(CoreNode node, String action) throws IOException {
        CoreProto.MobilityActionRequest request = CoreProto.MobilityActionRequest.newBuilder()
                .setSession(sessionId)
                .setId(node.getId())
                .setAction(CoreProto.MobilityAction.valueOf(action))
                .build();
        CoreProto.MobilityActionResponse response = blockingStub.mobilityAction(request);
        return response.getResult();
    }

    @Override
    public LocationConfig getLocationConfig() throws IOException {
        CoreProto.GetSessionLocationRequest request = CoreProto.GetSessionLocationRequest.newBuilder()
                .setId(sessionId)
                .build();
        CoreProto.GetSessionLocationResponse response = blockingStub.getSessionLocation(request);
        LocationConfig config = new LocationConfig();
        config.setScale((double) response.getScale());
        config.getPosition().setX((double) response.getPosition().getX());
        config.getPosition().setY((double) response.getPosition().getY());
        config.getPosition().setZ((double) response.getPosition().getZ());
        config.getLocation().setLatitude((double) response.getPosition().getLat());
        config.getLocation().setLongitude((double) response.getPosition().getLon());
        config.getLocation().setAltitude((double) response.getPosition().getAlt());
        return config;
    }

    @Override
    public boolean setLocationConfig(LocationConfig config) throws IOException {
        CoreProto.SetSessionLocationRequest.Builder builder = CoreProto.SetSessionLocationRequest.newBuilder()
                .setId(sessionId);
        if (config.getScale() != null) {
            builder.setScale(config.getScale().floatValue());
        }
        CoreProto.Position.Builder positionBuilder = CoreProto.Position.newBuilder();
        if (config.getPosition().getX() != null) {
            positionBuilder.setX(config.getPosition().getX().floatValue());
        }
        if (config.getPosition().getY() != null) {
            positionBuilder.setY(config.getPosition().getY().floatValue());
        }
        if (config.getPosition().getZ() != null) {
            positionBuilder.setZ(config.getPosition().getZ().floatValue());
        }
        if (config.getLocation().getLongitude() != null) {
            positionBuilder.setLon(config.getLocation().getLongitude().floatValue());
        }
        if (config.getLocation().getLatitude() != null) {
            positionBuilder.setLat(config.getLocation().getLatitude().floatValue());
        }
        if (config.getLocation().getAltitude() != null) {
            positionBuilder.setAlt(config.getLocation().getAltitude().floatValue());
        }
        CoreProto.SetSessionLocationResponse response = blockingStub.setSessionLocation(builder.build());
        return response.getResult();
    }
}
