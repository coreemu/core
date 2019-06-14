package com.core.client.grpc;

import com.core.Controller;
import com.core.client.ICoreClient;
import com.core.client.rest.ServiceFile;
import com.core.client.rest.WlanConfig;
import com.core.data.*;
import com.core.ui.dialogs.MobilityPlayerDialog;
import inet.ipaddr.IPAddress;
import inet.ipaddr.IPAddressString;
import io.grpc.Context;
import io.grpc.ManagedChannel;
import io.grpc.ManagedChannelBuilder;
import io.grpc.StatusRuntimeException;
import org.apache.logging.log4j.LogManager;
import org.apache.logging.log4j.Logger;

import java.io.File;
import java.io.IOException;
import java.io.PrintWriter;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.util.*;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

public class CoreGrpcClient implements ICoreClient {
    private static final Logger logger = LogManager.getLogger();
    private String address;
    private int port;
    private Integer sessionId;
    private SessionState sessionState;
    private CoreApiGrpc.CoreApiBlockingStub blockingStub;
    private ManagedChannel channel;
    private final ExecutorService executorService = Executors.newFixedThreadPool(6);
    private boolean handlingEvents = false;
    private boolean handlingThroughputs = false;

    private CoreProto.Node nodeToProto(CoreNode node) {
        CoreProto.Position position = CoreProto.Position.newBuilder()
                .setX(node.getPosition().getX().intValue())
                .setY(node.getPosition().getY().intValue())
                .build();
        CoreProto.Node.Builder builder = CoreProto.Node.newBuilder()
                .addAllServices(node.getServices())
                .setType(CoreProto.NodeType.Enum.forNumber(node.getType()))
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
            builder.setBandwidth(options.getBandwidth().intValue());
        }
        if (options.getBurst() != null) {
            builder.setBurst(options.getBurst().intValue());
        }
        if (options.getDelay() != null) {
            builder.setDelay(options.getDelay().intValue());
        }
        if (options.getDup() != null) {
            builder.setDup(options.getDup().intValue());
        }
        if (options.getJitter() != null) {
            builder.setJitter(options.getJitter().intValue());
        }
        if (options.getMburst() != null) {
            builder.setMburst(options.getMburst().intValue());
        }
        if (options.getMer() != null) {
            builder.setMer(options.getMer().intValue());
        }
        if (options.getPer() != null) {
            builder.setPer(options.getPer().intValue());
        }
        if (options.getKey() != null) {
            builder.setKey(options.getKey());
        }
        if (options.getOpaque() != null) {
            builder.setOpaque(options.getOpaque());
        }
        builder.setUnidirectional(unidirectional);
        return builder.build();
    }

    private CoreProto.Interface interfaceToProto(CoreInterface coreInterface) {
        CoreProto.Interface.Builder builder = CoreProto.Interface.newBuilder();
        if (coreInterface.getId() != null) {
            builder.setId(coreInterface.getId());
        }
        if (coreInterface.getName() != null) {
            builder.setName(coreInterface.getName());
        }
        if (coreInterface.getMac() != null) {
            builder.setMac(coreInterface.getMac());
        }
        if (coreInterface.getIp4() != null) {
            builder.setIp4(coreInterface.getIp4().toAddressString().getHostAddress().toString());
        }
        if (coreInterface.getIp4() != null) {
            builder.setIp4Mask(coreInterface.getIp4().getPrefixLength());
        }
        if (coreInterface.getIp6() != null) {
            builder.setIp6(coreInterface.getIp6().toAddressString().getHostAddress().toString());
        }
        if (coreInterface.getIp6() != null) {
            builder.setIp6Mask(coreInterface.getIp6().getPrefixLength());
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

    private CoreNode protoToNode(CoreProto.Node protoNode) {
        CoreNode node = new CoreNode(protoNode.getId());
        node.setName(protoNode.getName());
        node.setEmane(protoNode.getEmane());
        node.setIcon(protoNode.getIcon());
        node.setModel(protoNode.getModel());
        node.setServices(new HashSet<>(protoNode.getServicesList()));
        node.getPosition().setX((double) protoNode.getPosition().getX());
        node.getPosition().setY((double) protoNode.getPosition().getY());
        node.setType(protoNode.getTypeValue());
        return node;
    }

    private CoreInterface protoToInterface(CoreProto.Interface protoInterface) {
        CoreInterface coreInterface = new CoreInterface();
        coreInterface.setId(protoInterface.getId());
        coreInterface.setName(protoInterface.getName());
        coreInterface.setMac(protoInterface.getMac());
        String ip4String = String.format("%s/%s", protoInterface.getIp4(), protoInterface.getIp4Mask());
        IPAddress ip4 = new IPAddressString(ip4String).getAddress();
        coreInterface.setIp4(ip4);
        String ip6String = String.format("%s/%s", protoInterface.getIp6(), protoInterface.getIp6Mask());
        IPAddress ip6 = new IPAddressString(ip6String).getAddress();
        coreInterface.setIp6(ip6);
        return coreInterface;
    }

    private CoreLink protoToLink(CoreProto.Link linkProto) {
        CoreLink link = new CoreLink();
        link.setNodeOne(linkProto.getNodeOneId());
        link.setNodeTwo(linkProto.getNodeTwoId());
        CoreInterface interfaceOne = protoToInterface(linkProto.getInterfaceOne());
        link.setInterfaceOne(interfaceOne);
        CoreInterface interfaceTwo = protoToInterface(linkProto.getInterfaceTwo());
        link.setInterfaceTwo(interfaceTwo);

        CoreLinkOptions options = new CoreLinkOptions();
        CoreProto.LinkOptions protoOptions = linkProto.getOptions();
        options.setBandwidth((double) protoOptions.getBandwidth());
        options.setDelay((double) protoOptions.getDelay());
        options.setDup((double) protoOptions.getDup());
        options.setJitter((double) protoOptions.getJitter());
        options.setPer((double) protoOptions.getPer());
        options.setBurst((double) protoOptions.getBurst());
        if (protoOptions.hasField(CoreProto.LinkOptions.getDescriptor().findFieldByName("key"))) {
            options.setKey(protoOptions.getKey());
        }
        options.setMburst((double) protoOptions.getMburst());
        options.setMer((double) protoOptions.getMer());
        options.setOpaque(protoOptions.getOpaque());
        options.setUnidirectional(protoOptions.getUnidirectional() ? 1 : 0);
        link.setOptions(options);

        return link;
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
    public boolean startThroughput(Controller controller) throws IOException {
        CoreProto.ThroughputsRequest request = CoreProto.ThroughputsRequest.newBuilder().build();
        try {
            handlingThroughputs = true;
            executorService.submit(() -> {
                Context.CancellableContext context = Context.current().withCancellation();
                context.run(() -> {
                    try {
                        Iterator<CoreProto.ThroughputsEvent> iterator = blockingStub.throughputs(request);
                        while (handlingThroughputs) {
                            CoreProto.ThroughputsEvent event = iterator.next();
                            logger.info("handling throughputs: {}", event);
                            Throughputs throughputs = new Throughputs();
                            for (CoreProto.BridgeThroughput protoBridge : event.getBridgeThroughputsList()) {
                                BridgeThroughput bridge = new BridgeThroughput();
                                bridge.setNode(protoBridge.getNodeId());
                                bridge.setThroughput(protoBridge.getThroughput());
                                throughputs.getBridges().add(bridge);
                            }
                            for (CoreProto.InterfaceThroughput protoInterface : event.getInterfaceThroughputsList()) {
                                InterfaceThroughput interfaceThroughput = new InterfaceThroughput();
                                interfaceThroughput.setNode(protoInterface.getNodeId());
                                interfaceThroughput.setNodeInterface(protoInterface.getInterfaceId());
                                interfaceThroughput.setThroughput(protoInterface.getThroughput());
                                throughputs.getInterfaces().add(interfaceThroughput);
                            }
                            controller.handleThroughputs(throughputs);
                        }
                        logger.info("exiting handling throughputs");
                    } catch (StatusRuntimeException ex) {
                        logger.error("error handling session events", ex);
                    } finally {
                        context.cancel(null);
                        context.close();
                    }
                });
            });
            return true;
        } catch (StatusRuntimeException ex) {
            throw new IOException("setup event handlers error", ex);
        }
    }

    @Override
    public boolean stopThroughput() throws IOException {
        logger.info("cancelling throughputs");
        handlingThroughputs = false;
        return true;
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
        try {
            CoreProto.CreateSessionResponse response = blockingStub.createSession(request);
            SessionOverview overview = new SessionOverview();
            overview.setId(response.getSessionId());
            overview.setState(response.getStateValue());
            overview.setNodes(0);
            return overview;
        } catch (StatusRuntimeException ex) {
            throw new IOException(ex);
        }
    }

    @Override
    public boolean deleteSession(Integer sessionId) throws IOException {
        CoreProto.DeleteSessionRequest request = CoreProto.DeleteSessionRequest.newBuilder()
                .setSessionId(sessionId).build();
        try {
            return blockingStub.deleteSession(request).getResult();
        } catch (StatusRuntimeException ex) {
            throw new IOException(ex);
        }
    }

    @Override
    public List<SessionOverview> getSessions() throws IOException {
        CoreProto.GetSessionsRequest request = CoreProto.GetSessionsRequest.newBuilder().build();
        try {
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
        } catch (StatusRuntimeException ex) {
            throw new IOException(ex);
        }
    }

    @Override
    public Session getSession(Integer sessionId) throws IOException {
        logger.info("getting session: {}", sessionId);
        CoreProto.GetSessionRequest request = CoreProto.GetSessionRequest.newBuilder().setSessionId(sessionId).build();
        try {
            CoreProto.GetSessionResponse response = blockingStub.getSession(request);
            Session session = new Session();
            for (CoreProto.Node protoNode : response.getSession().getNodesList()) {
                if (CoreProto.NodeType.Enum.PEER_TO_PEER == protoNode.getType()) {
                    continue;
                }

                logger.info("adding node: {}", protoNode);
                CoreNode node = protoToNode(protoNode);
                session.getNodes().add(node);
            }
            for (CoreProto.Link linkProto : response.getSession().getLinksList()) {
                logger.info("adding link: {} - {}", linkProto.getNodeOneId(), linkProto.getNodeTwoId());
                CoreLink link = protoToLink(linkProto);
                session.getLinks().add(link);
            }
            session.setState(response.getSession().getStateValue());
            return session;
        } catch (StatusRuntimeException ex) {
            throw new IOException(ex);
        }
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
        handlingEvents = false;
        return setState(SessionState.SHUTDOWN);
    }

    @Override
    public boolean setState(SessionState state) throws IOException {
        CoreProto.SetSessionStateRequest request = CoreProto.SetSessionStateRequest.newBuilder()
                .setSessionId(sessionId)
                .setStateValue(state.getValue())
                .build();
        try {
            CoreProto.SetSessionStateResponse response = blockingStub.setSessionState(request);
            if (response.getResult()) {
                sessionState = state;
            }
            return response.getResult();
        } catch (StatusRuntimeException ex) {
            throw new IOException(ex);
        }
    }

    @Override
    public Map<String, List<String>> getServices() throws IOException {
        CoreProto.GetServicesRequest request = CoreProto.GetServicesRequest.newBuilder().build();
        try {
            CoreProto.GetServicesResponse response = blockingStub.getServices(request);
            Map<String, List<String>> servicesMap = new HashMap<>();
            for (CoreProto.Service protoService : response.getServicesList()) {
                List<String> services = servicesMap.computeIfAbsent(protoService.getGroup(), x -> new ArrayList<>());
                services.add(protoService.getName());
            }
            return servicesMap;
        } catch (StatusRuntimeException ex) {
            throw new IOException(ex);
        }
    }

    @Override
    public Map<String, List<String>> getDefaultServices() throws IOException {
        CoreProto.GetServiceDefaultsRequest request = CoreProto.GetServiceDefaultsRequest.newBuilder().build();
        try {
            CoreProto.GetServiceDefaultsResponse response = blockingStub.getServiceDefaults(request);
            Map<String, List<String>> servicesMap = new HashMap<>();
            for (CoreProto.ServiceDefaults serviceDefaults : response.getDefaultsList()) {
                servicesMap.put(serviceDefaults.getNodeType(), serviceDefaults.getServicesList());
            }
            return servicesMap;
        } catch (StatusRuntimeException ex) {
            throw new IOException(ex);
        }
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
                .setSessionId(sessionId)
                .addAllDefaults(allDefaults)
                .build();
        try {
            CoreProto.SetServiceDefaultsResponse response = blockingStub.setServiceDefaults(request);
            return response.getResult();
        } catch (StatusRuntimeException ex) {
            throw new IOException(ex);
        }
    }

    @Override
    public CoreService getService(CoreNode node, String serviceName) throws IOException {
        CoreProto.GetNodeServiceRequest request = CoreProto.GetNodeServiceRequest.newBuilder().build();
        try {
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
        } catch (StatusRuntimeException ex) {
            throw new IOException(ex);
        }
    }

    @Override
    public boolean setService(CoreNode node, String serviceName, CoreService service) throws IOException {
        CoreProto.SetNodeServiceRequest request = CoreProto.SetNodeServiceRequest.newBuilder()
                .setNodeId(node.getId())
                .setSessionId(sessionId)
                .setService(serviceName)
                .build();
        request.getShutdownList().addAll(service.getShutdown());
        request.getValidateList().addAll(service.getValidate());
        request.getStartupList().addAll(service.getStartup());
        try {
            return blockingStub.setNodeService(request).getResult();
        } catch (StatusRuntimeException ex) {
            throw new IOException(ex);
        }
    }

    @Override
    public String getServiceFile(CoreNode node, String serviceName, String fileName) throws IOException {
        CoreProto.GetNodeServiceFileRequest request = CoreProto.GetNodeServiceFileRequest.newBuilder()
                .setSessionId(sessionId)
                .setNodeId(node.getId())
                .setService(serviceName)
                .build();
        try {
            CoreProto.GetNodeServiceFileResponse response = blockingStub.getNodeServiceFile(request);
            return response.getData();
        } catch (StatusRuntimeException ex) {
            throw new IOException(ex);
        }
    }

    @Override
    public boolean startService(CoreNode node, String serviceName) throws IOException {
        CoreProto.ServiceActionRequest request = CoreProto.ServiceActionRequest.newBuilder()
                .setSessionId(sessionId)
                .setNodeId(node.getId())
                .setService(serviceName)
                .setAction(CoreProto.ServiceAction.Enum.START)
                .build();
        try {
            return blockingStub.serviceAction(request).getResult();
        } catch (StatusRuntimeException ex) {
            throw new IOException(ex);
        }
    }

    @Override
    public boolean stopService(CoreNode node, String serviceName) throws IOException {
        CoreProto.ServiceActionRequest request = CoreProto.ServiceActionRequest.newBuilder()
                .setSessionId(sessionId)
                .setNodeId(node.getId())
                .setService(serviceName)
                .setAction(CoreProto.ServiceAction.Enum.STOP)
                .build();
        try {
            return blockingStub.serviceAction(request).getResult();
        } catch (StatusRuntimeException ex) {
            throw new IOException(ex);
        }
    }

    @Override
    public boolean restartService(CoreNode node, String serviceName) throws IOException {
        CoreProto.ServiceActionRequest request = CoreProto.ServiceActionRequest.newBuilder()
                .setSessionId(sessionId)
                .setNodeId(node.getId())
                .setService(serviceName)
                .setAction(CoreProto.ServiceAction.Enum.RESTART)
                .build();
        try {
            return blockingStub.serviceAction(request).getResult();
        } catch (StatusRuntimeException ex) {
            throw new IOException(ex);
        }
    }

    @Override
    public boolean validateService(CoreNode node, String serviceName) throws IOException {
        CoreProto.ServiceActionRequest request = CoreProto.ServiceActionRequest.newBuilder()
                .setSessionId(sessionId)
                .setNodeId(node.getId())
                .setService(serviceName)
                .setAction(CoreProto.ServiceAction.Enum.VALIDATE)
                .build();
        try {
            return blockingStub.serviceAction(request).getResult();
        } catch (StatusRuntimeException ex) {
            throw new IOException(ex);
        }
    }

    @Override
    public boolean setServiceFile(CoreNode node, String serviceName, ServiceFile serviceFile) throws IOException {
        CoreProto.SetNodeServiceFileRequest request = CoreProto.SetNodeServiceFileRequest.newBuilder()
                .setSessionId(sessionId)
                .setNodeId(node.getId())
                .setService(serviceName)
                .setFile(serviceFile.getName())
                .setData(serviceFile.getData())
                .build();
        try {
            CoreProto.SetNodeServiceFileResponse response = blockingStub.setNodeServiceFile(request);
            return response.getResult();
        } catch (StatusRuntimeException ex) {
            throw new IOException(ex);
        }
    }

    @Override
    public List<ConfigGroup> getEmaneConfig(CoreNode node) throws IOException {
        CoreProto.GetEmaneConfigRequest request = CoreProto.GetEmaneConfigRequest.newBuilder()
                .setSessionId(sessionId)
                .build();
        try {
            CoreProto.GetEmaneConfigResponse response = blockingStub.getEmaneConfig(request);
            return protoToConfigGroups(response.getGroupsList());
        } catch (StatusRuntimeException ex) {
            throw new IOException(ex);
        }
    }

    @Override
    public List<String> getEmaneModels() throws IOException {
        CoreProto.GetEmaneModelsRequest request = CoreProto.GetEmaneModelsRequest.newBuilder()
                .setSessionId(sessionId)
                .build();
        try {
            CoreProto.GetEmaneModelsResponse response = blockingStub.getEmaneModels(request);
            return new ArrayList<>(response.getModelsList());
        } catch (StatusRuntimeException ex) {
            throw new IOException(ex);
        }
    }

    @Override
    public boolean setEmaneConfig(CoreNode node, List<ConfigOption> options) throws IOException {
        Map<String, String> config = configOptionListToMap(options);
        CoreProto.SetEmaneConfigRequest request = CoreProto.SetEmaneConfigRequest.newBuilder()
                .setSessionId(sessionId)
                .putAllConfig(config)
                .build();
        try {
            CoreProto.SetEmaneConfigResponse response = blockingStub.setEmaneConfig(request);
            return response.getResult();
        } catch (StatusRuntimeException ex) {
            throw new IOException(ex);
        }
    }

    @Override
    public List<ConfigGroup> getEmaneModelConfig(Integer id, String model) throws IOException {
        CoreProto.GetEmaneModelConfigRequest request = CoreProto.GetEmaneModelConfigRequest.newBuilder()
                .setSessionId(sessionId)
                .setNodeId(id)
                .setModel(model)
                .build();
        try {
            CoreProto.GetEmaneModelConfigResponse response = blockingStub.getEmaneModelConfig(request);
            return protoToConfigGroups(response.getGroupsList());
        } catch (StatusRuntimeException ex) {
            throw new IOException(ex);
        }
    }

    @Override
    public boolean setEmaneModelConfig(Integer id, String model, List<ConfigOption> options) throws IOException {
        Map<String, String> config = configOptionListToMap(options);
        CoreProto.SetEmaneModelConfigRequest request = CoreProto.SetEmaneModelConfigRequest.newBuilder()
                .setSessionId(sessionId)
                .setNodeId(id)
                .setModel(model)
                .putAllConfig(config)
                .build();
        try {
            CoreProto.SetEmaneModelConfigResponse response = blockingStub.setEmaneModelConfig(request);
            return response.getResult();
        } catch (StatusRuntimeException ex) {
            throw new IOException(ex);
        }
    }

    @Override
    public boolean isRunning() {
        return sessionState == SessionState.RUNTIME;
    }

    @Override
    public void saveSession(File file) throws IOException {
        CoreProto.SaveXmlRequest request = CoreProto.SaveXmlRequest.newBuilder()
                .setSessionId(sessionId)
                .build();
        try {
            CoreProto.SaveXmlResponse response = blockingStub.saveXml(request);
            try (PrintWriter writer = new PrintWriter(file)) {
                writer.print(response.getData());
            }
        } catch (StatusRuntimeException ex) {
            throw new IOException(ex);
        }
    }

    @Override
    public SessionOverview openSession(File file) throws IOException {
        try {
            byte[] encoded = Files.readAllBytes(file.toPath());
            String data = new String(encoded, StandardCharsets.UTF_8);
            CoreProto.OpenXmlRequest request = CoreProto.OpenXmlRequest.newBuilder()
                    .setData(data)
                    .build();

            CoreProto.OpenXmlResponse response = blockingStub.openXml(request);
            SessionOverview sessionOverview = new SessionOverview();
            sessionOverview.setId(response.getSessionId());
            return sessionOverview;
        } catch (IOException | StatusRuntimeException ex) {
            throw new IOException(ex);
        }
    }

    @Override
    public List<ConfigGroup> getSessionConfig() throws IOException {
        CoreProto.GetSessionOptionsRequest request = CoreProto.GetSessionOptionsRequest.newBuilder()
                .setSessionId(sessionId)
                .build();
        try {
            CoreProto.GetSessionOptionsResponse response = blockingStub.getSessionOptions(request);
            return protoToConfigGroups(response.getGroupsList());
        } catch (StatusRuntimeException ex) {
            throw new IOException(ex);
        }
    }

    @Override
    public boolean setSessionConfig(List<ConfigOption> configOptions) throws IOException {
        Map<String, String> config = configOptionListToMap(configOptions);
        CoreProto.SetSessionOptionsRequest request = CoreProto.SetSessionOptionsRequest.newBuilder()
                .setSessionId(sessionId)
                .putAllConfig(config)
                .build();
        try {
            CoreProto.SetSessionOptionsResponse response = blockingStub.setSessionOptions(request);
            return response.getResult();
        } catch (StatusRuntimeException ex) {
            throw new IOException(ex);
        }
    }

    @Override
    public boolean createNode(CoreNode node) throws IOException {
        CoreProto.Node protoNode = nodeToProto(node);
        CoreProto.AddNodeRequest request = CoreProto.AddNodeRequest.newBuilder()
                .setSessionId(sessionId)
                .setNode(protoNode)
                .build();
        try {
            blockingStub.addNode(request);
            return true;
        } catch (StatusRuntimeException ex) {
            throw new IOException(ex);
        }
    }

    @Override
    public String nodeCommand(CoreNode node, String command) throws IOException {
        CoreProto.NodeCommandRequest request = CoreProto.NodeCommandRequest.newBuilder()
                .setSessionId(sessionId)
                .setNodeId(node.getId())
                .setCommand(command)
                .build();
        try {
            CoreProto.NodeCommandResponse response = blockingStub.nodeCommand(request);
            return response.getOutput();
        } catch (StatusRuntimeException ex) {
            throw new IOException(ex);
        }
    }

    @Override
    public boolean editNode(CoreNode node) throws IOException {
        CoreProto.Position position = CoreProto.Position.newBuilder()
                .setX(node.getPosition().getX().intValue())
                .setY(node.getPosition().getY().intValue())
                .build();
        CoreProto.EditNodeRequest request = CoreProto.EditNodeRequest.newBuilder()
                .setSessionId(sessionId)
                .setNodeId(node.getId())
                .setPosition(position)
                .build();
        try {
            CoreProto.EditNodeResponse response = blockingStub.editNode(request);
            return response.getResult();
        } catch (StatusRuntimeException ex) {
            throw new IOException(ex);
        }
    }

    @Override
    public boolean deleteNode(CoreNode node) throws IOException {
        CoreProto.DeleteNodeRequest request = CoreProto.DeleteNodeRequest.newBuilder()
                .build();
        try {
            CoreProto.DeleteNodeResponse response = blockingStub.deleteNode(request);
            return response.getResult();
        } catch (StatusRuntimeException ex) {
            throw new IOException(ex);
        }
    }

    @Override
    public boolean createLink(CoreLink link) throws IOException {
        CoreProto.Link.Builder builder = CoreProto.Link.newBuilder()
                .setTypeValue(link.getType());
        if (link.getNodeOne() != null) {
            builder.setNodeOneId(link.getNodeOne());
        }
        if (link.getNodeTwo() != null) {
            builder.setNodeTwoId(link.getNodeTwo());
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
                .setSessionId(sessionId)
                .setLink(protoLink)
                .build();
        try {
            CoreProto.AddLinkResponse response = blockingStub.addLink(request);
            return response.getResult();
        } catch (StatusRuntimeException ex) {
            throw new IOException(ex);
        }
    }

    @Override
    public boolean editLink(CoreLink link) throws IOException {
        CoreProto.EditLinkRequest.Builder builder = CoreProto.EditLinkRequest.newBuilder()
                .setSessionId(sessionId);
        if (link.getNodeOne() != null) {
            builder.setNodeOneId(link.getNodeOne());
        }
        if (link.getNodeTwo() != null) {
            builder.setNodeTwoId(link.getNodeTwo());
        }
        if (link.getInterfaceOne() != null) {
            builder.setInterfaceOneId(link.getInterfaceOne().getId());
        }
        if (link.getInterfaceTwo() != null) {
            builder.setInterfaceTwoId(link.getInterfaceTwo().getId());
        }
        if (link.getOptions() != null) {
            CoreProto.LinkOptions protoOptions = linkOptionsToProto(link.getOptions());
            builder.setOptions(protoOptions);
        }
        CoreProto.EditLinkRequest request = builder.build();
        try {
            CoreProto.EditLinkResponse response = blockingStub.editLink(request);
            return response.getResult();
        } catch (StatusRuntimeException ex) {
            throw new IOException(ex);
        }
    }

    @Override
    public boolean createHook(Hook hook) throws IOException {
        CoreProto.Hook hookProto = CoreProto.Hook.newBuilder()
                .setStateValue(hook.getState())
                .setData(hook.getData())
                .setFile(hook.getFile())
                .build();
        CoreProto.AddHookRequest request = CoreProto.AddHookRequest.newBuilder()
                .setHook(hookProto)
                .build();
        try {
            CoreProto.AddHookResponse response = blockingStub.addHook(request);
            return response.getResult();
        } catch (StatusRuntimeException ex) {
            throw new IOException(ex);
        }
    }

    @Override
    public List<Hook> getHooks() throws IOException {
        CoreProto.GetHooksRequest request = CoreProto.GetHooksRequest.newBuilder().setSessionId(sessionId).build();
        try {
            CoreProto.GetHooksResponse response = blockingStub.getHooks(request);
            List<Hook> hooks = new ArrayList<>();
            for (CoreProto.Hook protoHook : response.getHooksList()) {
                Hook hook = new Hook();
                hook.setFile(protoHook.getFile());
                hook.setData(protoHook.getData());
                hook.setState(protoHook.getStateValue());
                hooks.add(hook);
            }
            return hooks;
        } catch (StatusRuntimeException ex) {
            throw new IOException(ex);
        }
    }

    @Override
    public WlanConfig getWlanConfig(CoreNode node) throws IOException {
        CoreProto.GetWlanConfigRequest request = CoreProto.GetWlanConfigRequest.newBuilder()
                .setSessionId(sessionId)
                .setNodeId(node.getId())
                .build();
        try {
            CoreProto.GetWlanConfigResponse response = blockingStub.getWlanConfig(request);
            Map<String, String> protoConfig = new HashMap<>();
            for (CoreProto.ConfigGroup group : response.getGroupsList()) {
                for (CoreProto.ConfigOption option : group.getOptionsList()) {
                    protoConfig.put(option.getName(), option.getValue());
                }
            }
            WlanConfig config = new WlanConfig();
            config.setBandwidth(protoConfig.get("bandwidth"));
            config.setDelay(protoConfig.get("delay"));
            config.setError(protoConfig.get("error"));
            config.setJitter(protoConfig.get("jitter"));
            config.setRange(protoConfig.get("range"));
            return config;
        } catch (StatusRuntimeException ex) {
            throw new IOException(ex);
        }
    }

    @Override
    public boolean setWlanConfig(CoreNode node, WlanConfig config) throws IOException {
        Map<String, String> protoConfig = new HashMap<>();
        protoConfig.put("bandwidth", config.getBandwidth());
        protoConfig.put("delay", config.getDelay());
        protoConfig.put("error", config.getError());
        protoConfig.put("jitter", config.getJitter());
        protoConfig.put("range", config.getRange());
        CoreProto.SetWlanConfigRequest request = CoreProto.SetWlanConfigRequest.newBuilder()
                .setSessionId(sessionId)
                .setNodeId(node.getId())
                .putAllConfig(protoConfig)
                .build();
        try {
            CoreProto.SetWlanConfigResponse response = blockingStub.setWlanConfig(request);
            return response.getResult();
        } catch (StatusRuntimeException ex) {
            throw new IOException(ex);
        }
    }

    @Override
    public String getTerminalCommand(CoreNode node) throws IOException {
        CoreProto.GetNodeTerminalRequest request = CoreProto.GetNodeTerminalRequest.newBuilder()
                .setSessionId(sessionId)
                .setNodeId(node.getId())
                .build();
        try {
            return blockingStub.getNodeTerminal(request).getTerminal();
        } catch (StatusRuntimeException ex) {
            throw new IOException(ex);
        }
    }

    @Override
    public Map<Integer, MobilityConfig> getMobilityConfigs() throws IOException {
        CoreProto.GetMobilityConfigsRequest request = CoreProto.GetMobilityConfigsRequest.newBuilder()
                .setSessionId(sessionId).build();
        try {
            CoreProto.GetMobilityConfigsResponse response = blockingStub.getMobilityConfigs(request);

            Map<Integer, MobilityConfig> mobilityConfigs = new HashMap<>();
            for (Integer nodeId : response.getConfigsMap().keySet()) {
                CoreProto.GetMobilityConfigsResponse.MobilityConfig protoMobilityConfig = response.getConfigsMap()
                        .get(nodeId);
                MobilityConfig mobilityConfig = new MobilityConfig();
                Map<String, String> protoConfig = new HashMap<>();
                for (CoreProto.ConfigGroup group : protoMobilityConfig.getGroupsList()) {
                    for (CoreProto.ConfigOption option : group.getOptionsList()) {
                        protoConfig.put(option.getName(), option.getValue());
                    }
                }
                mobilityConfig.setFile(protoConfig.get("file"));
                mobilityConfig.setRefresh(Integer.parseInt(protoConfig.get("refresh_ms")));
                mobilityConfig.setAutostart(protoConfig.get("autostart"));
                mobilityConfig.setLoop(protoConfig.get("loop"));
                mobilityConfig.setPauseScript(protoConfig.get("script_pause"));
                mobilityConfig.setStartScript(protoConfig.get("script_start"));
                mobilityConfig.setStopScript(protoConfig.get("script_stop"));
                mobilityConfig.setMap(protoConfig.get("map"));
                mobilityConfigs.put(nodeId, mobilityConfig);
            }
            return mobilityConfigs;
        } catch (StatusRuntimeException ex) {
            throw new IOException(ex);
        }
    }

    @Override
    public boolean setMobilityConfig(CoreNode node, MobilityConfig config) throws IOException {
        Map<String, String> protoConfig = new HashMap<>();
        protoConfig.put("file", config.getFile());
        if (config.getRefresh() != null) {
            protoConfig.put("refresh_ms", config.getRefresh().toString());
        }
        protoConfig.put("autostart", config.getAutostart());
        protoConfig.put("loop", config.getLoop());
        protoConfig.put("map", config.getMap());
        protoConfig.put("script_pause", config.getPauseScript());
        protoConfig.put("script_start", config.getStartScript());
        protoConfig.put("script_stop", config.getStopScript());
        CoreProto.SetMobilityConfigRequest request = CoreProto.SetMobilityConfigRequest.newBuilder()
                .setSessionId(sessionId)
                .setNodeId(node.getId())
                .putAllConfig(protoConfig)
                .build();
        try {
            CoreProto.SetMobilityConfigResponse response = blockingStub.setMobilityConfig(request);
            return response.getResult();
        } catch (StatusRuntimeException ex) {
            throw new IOException(ex);
        }
    }

    @Override
    public MobilityConfig getMobilityConfig(CoreNode node) throws IOException {
        CoreProto.GetMobilityConfigRequest request = CoreProto.GetMobilityConfigRequest.newBuilder()
                .setSessionId(sessionId)
                .setNodeId(node.getId())
                .build();
        try {
            CoreProto.GetMobilityConfigResponse response = blockingStub.getMobilityConfig(request);
            Map<String, String> protoConfig = new HashMap<>();
            for (CoreProto.ConfigGroup group : response.getGroupsList()) {
                for (CoreProto.ConfigOption option : group.getOptionsList()) {
                    protoConfig.put(option.getName(), option.getValue());
                }
            }
            MobilityConfig config = new MobilityConfig();
            config.setFile(protoConfig.get("file"));
            config.setRefresh(Integer.parseInt(protoConfig.get("refresh_ms")));
            config.setAutostart(protoConfig.get("autostart"));
            config.setLoop(protoConfig.get("loop"));
            config.setPauseScript(protoConfig.get("script_pause"));
            config.setStartScript(protoConfig.get("script_start"));
            config.setStopScript(protoConfig.get("script_stop"));
            config.setMap(protoConfig.get("map"));
            return config;
        } catch (StatusRuntimeException ex) {
            throw new IOException(ex);
        }
    }

    @Override
    public boolean mobilityAction(CoreNode node, String action) throws IOException {
        CoreProto.MobilityActionRequest request = CoreProto.MobilityActionRequest.newBuilder()
                .setSessionId(sessionId)
                .setNodeId(node.getId())
                .setAction(CoreProto.MobilityAction.Enum.valueOf(action))
                .build();
        try {
            CoreProto.MobilityActionResponse response = blockingStub.mobilityAction(request);
            return response.getResult();
        } catch (StatusRuntimeException ex) {
            throw new IOException(ex);
        }
    }

    @Override
    public LocationConfig getLocationConfig() throws IOException {
        CoreProto.GetSessionLocationRequest request = CoreProto.GetSessionLocationRequest.newBuilder()
                .setSessionId(sessionId)
                .build();
        try {
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
        } catch (StatusRuntimeException ex) {
            throw new IOException(ex);
        }
    }

    @Override
    public boolean setLocationConfig(LocationConfig config) throws IOException {
        CoreProto.SetSessionLocationRequest.Builder builder = CoreProto.SetSessionLocationRequest.newBuilder()
                .setSessionId(sessionId);
        if (config.getScale() != null) {
            builder.setScale(config.getScale().floatValue());
        }
        CoreProto.Position.Builder positionBuilder = CoreProto.Position.newBuilder();
        if (config.getPosition().getX() != null) {
            positionBuilder.setX(config.getPosition().getX().intValue());
        }
        if (config.getPosition().getY() != null) {
            positionBuilder.setY(config.getPosition().getY().intValue());
        }
        if (config.getPosition().getZ() != null) {
            positionBuilder.setZ(config.getPosition().getZ().intValue());
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
        try {
            CoreProto.SetSessionLocationResponse response = blockingStub.setSessionLocation(builder.build());
            return response.getResult();
        } catch (StatusRuntimeException ex) {
            throw new IOException(ex);
        }
    }

    @Override
    public void setupEventHandlers(Controller controller) throws IOException {
        logger.info("setting up event handlers");
        handlingEvents = true;
        try {
            CoreProto.EventsRequest request = CoreProto.EventsRequest.newBuilder()
                    .setSessionId(sessionId)
                    .build();

            Iterator<CoreProto.Event> events = blockingStub.events(request);
            executorService.submit(() -> {
                Context.CancellableContext context = Context.current().withCancellation();
                context.run(() -> {
                    try {
                        while (handlingEvents) {
                            CoreProto.Event event = events.next();
                            logger.info("handling event: {}", event);
                            switch (event.getEventTypeCase()) {
                                case SESSION_EVENT:
                                    handleSessionEvents(controller, event.getSessionEvent());
                                    break;
                                case NODE_EVENT:
                                    handleNodeEvents(controller, event.getNodeEvent());
                                    break;
                                case LINK_EVENT:
                                    handleLinkEvents(controller, event.getLinkEvent());
                                    break;
                                case CONFIG_EVENT:
                                    handleConfigEvents(controller, event.getConfigEvent());
                                    break;
                                case EXCEPTION_EVENT:
                                    handleExceptionEvents(controller, event.getExceptionEvent());
                                    break;
                                case FILE_EVENT:
                                    handleFileEvents(controller, event.getFileEvent());
                                    break;
                                default:
                                    logger.error("unknown event type: {}", event.getEventTypeCase());
                            }
                        }
                    } catch (StatusRuntimeException ex) {
                        logger.error("error handling session events", ex);
                    } finally {
                        context.cancel(null);
                        context.close();
                    }
                });
            });
        } catch (StatusRuntimeException ex) {
            throw new IOException("setup event handlers error", ex);
        }
    }

    private void handleSessionEvents(Controller controller, CoreProto.SessionEvent event) {
        logger.info("session event: {}", event);
        SessionState state = SessionState.get(event.getEvent());
        if (state == null) {
            logger.warn("unknown session event: {}", event.getEvent());
            return;
        }

        // session state event
        if (state.getValue() <= 6) {
            logger.info("event updating session state: {}", state);
            updateState(state);
            // mobility script event
        } else if (state.getValue() <= 9) {
            Integer nodeId = event.getNodeId();
            String[] values = event.getData().split("\\s+");
            Integer start = Integer.parseInt(values[0].split("=")[1]);
            Integer end = Integer.parseInt(values[1].split("=")[1]);
            logger.info(String.format("node(%s) mobility event (%s) - start(%s) stop(%s)",
                    nodeId, state, start, end));
            logger.info("all dialogs: {}", controller.getMobilityPlayerDialogs().keySet());
            MobilityPlayerDialog mobilityPlayerDialog = controller.getMobilityPlayerDialogs().get(nodeId);
            mobilityPlayerDialog.event(state, start, end);
        }
    }

    private void handleNodeEvents(Controller controller, CoreProto.NodeEvent event) {
        logger.info("node event: {}", event);
        CoreNode node = protoToNode(event.getNode());
        controller.getNetworkGraph().setNodeLocation(node);
    }

    private void handleExceptionEvents(Controller controller, CoreProto.ExceptionEvent event) {
        logger.info("exception event: {}", event);
    }

    private void handleConfigEvents(Controller controller, CoreProto.ConfigEvent event) {
        logger.info("config event: {}", event);
    }

    private void handleLinkEvents(Controller controller, CoreProto.LinkEvent event) {
        logger.info("link event: {}", event);
        CoreLink link = protoToLink(event.getLink());
        MessageFlags flag = MessageFlags.get(event.getMessageTypeValue());
        if (MessageFlags.DELETE == flag) {
            logger.info("delete");
            controller.getNetworkGraph().removeWirelessLink(link);
        } else if (MessageFlags.ADD == flag) {
            link.setLoaded(true);
            controller.getNetworkGraph().addLink(link);
        }
        controller.getNetworkGraph().getGraphViewer().repaint();
    }

    private void handleFileEvents(Controller controller, CoreProto.FileEvent event) {
        logger.info("file event: {}", event);
    }
}
