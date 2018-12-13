package com.core.websocket;

import com.core.Controller;
import com.core.data.*;
import com.core.ui.dialogs.MobilityPlayerDialog;
import com.core.utils.JsonUtils;
import io.socket.client.IO;
import io.socket.client.Socket;
import org.apache.logging.log4j.LogManager;
import org.apache.logging.log4j.Logger;

import java.io.IOException;
import java.net.URISyntaxException;

public class CoreWebSocket {
    private static final Logger logger = LogManager.getLogger();
    private final Controller controller;
    private Thread socketThread;
    private Socket socket;

    public CoreWebSocket(Controller controller) {
        this.controller = controller;
    }

    public void start(String address, int port) throws URISyntaxException {
        socket = IO.socket(String.format("http://%s:%s", address, port));
        socket.on(Socket.EVENT_CONNECT, args -> logger.info("connected to web socket"));
        socket.on("node", this::handleNodes);
        socket.on("event", this::handleEvents);
        socket.on("config", this::handleConfigs);
        socket.on("link", this::handleLinks);
        socket.on("throughput", this::handleThroughputs);
        socket.on(Socket.EVENT_DISCONNECT, args -> logger.info("disconnected from web socket"));

        logger.info("attempting to connect to web socket!");
        socketThread = new Thread(socket::connect);
        socketThread.setDaemon(true);
        socketThread.start();
    }

    public void stop() {
        if (socketThread != null) {
            socket.close();
            socketThread.interrupt();
        }
    }

    private void handleThroughputs(Object... args) {
        for (Object arg : args) {
            logger.info("throughput update: {}", arg);
            try {
                Throughputs throughputs = JsonUtils.read(arg.toString(), Throughputs.class);
                controller.handleThroughputs(throughputs);
            } catch (IOException ex) {
                logger.error("error getting throughputs", ex);
            }
        }
    }

    private void handleNodes(Object... args) {
        for (Object arg : args) {
            try {
                CoreNode node = JsonUtils.read(arg.toString(), CoreNode.class);
                logger.info("core node update: {}", node);
                controller.getNetworkGraph().setNodeLocation(node);
            } catch (IOException ex) {
                logger.error("error getting core node", ex);
            }
        }
    }

    private void handleEvents(Object... args) {
        for (Object arg : args) {
            try {
                CoreEvent event = JsonUtils.read(arg.toString(), CoreEvent.class);
                logger.info("handling broadcast event: {}", event);
                SessionState state = SessionState.get(event.getEventType().getValue());
                if (state == null) {
                    logger.warn("unknown event type: {}", event.getEventType().getValue());
                    return;
                }

                // session state event
                if (state.getValue() <= 6) {
                    logger.info("event updating session state: {}", state);
                    controller.getCoreClient().updateState(state);
                    // mobility script event
                } else if (state.getValue() <= 9) {
                    Integer nodeId = event.getNode();
                    String[] values = event.getData().split("\\s+");
                    Integer start = Integer.parseInt(values[0].split("=")[1]);
                    Integer end = Integer.parseInt(values[1].split("=")[1]);
                    logger.info(String.format("node(%s) mobility event (%s) - start(%s) stop(%s)",
                            nodeId, state, start, end));
                    logger.info("all dialogs: {}", controller.getMobilityPlayerDialogs().keySet());
                    MobilityPlayerDialog mobilityPlayerDialog = controller.getMobilityPlayerDialogs().get(nodeId);
                    mobilityPlayerDialog.event(state, start, end);
                }
            } catch (IOException ex) {
                logger.error("error getting core event", ex);
            }
        }
    }

    private void handleLinks(Object... args) {
        for (Object arg : args) {
            try {
                CoreLink link = JsonUtils.read(arg.toString(), CoreLink.class);
                logger.info("handling broadcast link: {}", link);
                MessageFlags flag = MessageFlags.get(link.getMessageType());
                if (MessageFlags.DELETE == flag) {
                    logger.info("delete");
                    controller.getNetworkGraph().removeWirelessLink(link);
                } else if (MessageFlags.ADD == flag) {
                    link.setLoaded(true);
                    controller.getNetworkGraph().addLink(link);
                }
                controller.getNetworkGraph().getGraphViewer().repaint();
            } catch (IOException ex) {
                logger.error("error handling broadcast link", ex);
            }
        }
    }

    private void handleConfigs(Object... args) {
        for (Object arg : args) {
            logger.info("handling broadcast config: {}", arg);
        }
    }
}
