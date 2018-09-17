package com.core.websocket;

import com.core.Controller;
import com.core.data.*;
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
    private final String url;
    private final Socket socket;
    private Thread socketThread;

    public CoreWebSocket(Controller controller, String url) throws URISyntaxException {
        this.controller = controller;
        this.url = url;
        socket = IO.socket(this.url);
        socket.on(Socket.EVENT_CONNECT, args -> {
            logger.info("connected to web socket");
        });
        socket.on("node", this::handleNodes);
        socket.on("event", this::handleEvents);
        socket.on("config", this::handleConfigs);
        socket.on("link", this::handleLinks);
        socket.on(Socket.EVENT_DISCONNECT, args -> {
            logger.info("disconnected from web socket");
        });
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
                if (state != null) {
                    logger.info("event updating session state: {}", state);
                    controller.getCoreClient().updateState(state);
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

    public void start() {
        logger.info("attempting to connect to web socket!");
        socketThread = new Thread(socket::connect);
        socketThread.setDaemon(true);
        socketThread.start();
    }
}
