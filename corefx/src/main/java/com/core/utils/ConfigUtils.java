package com.core.utils;

import com.core.data.NodeType;
import org.apache.logging.log4j.LogManager;
import org.apache.logging.log4j.Logger;

import java.io.FileInputStream;
import java.io.IOException;
import java.io.PrintWriter;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.util.*;

public final class ConfigUtils {
    private static final Logger logger = LogManager.getLogger();
    private static final Path HOME = Paths.get(System.getProperty("user.home"), ".core");
    private static final String CONFIG_FILE_NAME = "config.json";
    private static final String DEFAULT_CONFIG = "/" + CONFIG_FILE_NAME;
    private static final Path CONFIG_FILE = Paths.get(HOME.toString(), CONFIG_FILE_NAME);
    private static final Path XML_DIR = Paths.get(HOME.toString(), "xml");
    private static final Path MOBILITY_DIR = Paths.get(HOME.toString(), "mobility");
    private static final Path ICON_DIR = Paths.get(HOME.toString(), "icons");


    private ConfigUtils() {

    }

    public static void save(Configuration configuration) throws IOException {
        String fileData = JsonUtils.toPrettyString(configuration);
        try (PrintWriter out = new PrintWriter(CONFIG_FILE.toFile())) {
            out.println(fileData);
        }
    }

    private static Configuration readConfig() throws IOException {
        return JsonUtils.read(new FileInputStream(CONFIG_FILE.toFile()), Configuration.class);
    }

    private static List<NodeTypeConfig> createDefaults() throws IOException {
        return Arrays.asList(
                createDefault("host", "Host", "/icons/host-100.png", new TreeSet<>(Arrays.asList(
                        "DefaultRoute", "SSH"
                ))),
                createDefault("PC", "PC", "/icons/pc-100.png",
                        new TreeSet<>(Collections.singletonList("DefaultRoute"))),
                createDefault("mdr", "MDR", "/icons/router-100.png", new TreeSet<>(Arrays.asList(
                        "zebra", "OSPFv3MDR", "IPForward"
                )))
        );
    }

    private static NodeTypeConfig createDefault(String model, String display, String icon,
                                                Set<String> services) throws IOException {
        String fileName = Paths.get(icon).getFileName().toString();
        Path iconPath = Paths.get(ICON_DIR.toString(), fileName);
        Files.copy(ConfigUtils.class.getResourceAsStream(icon), iconPath);
        return new NodeTypeConfig(model, display, iconPath.toUri().toString(), services);
    }

    public static void checkForHomeDirectory() throws IOException {
        if (!HOME.toFile().exists()) {
            logger.info("creating core home directory");
            Files.createDirectory(HOME);
            Files.createDirectory(XML_DIR);
            Files.createDirectory(MOBILITY_DIR);
            Files.createDirectory(ICON_DIR);
            createDefaultConfigFile();
        }
    }

    private static void createDefaultConfigFile() throws IOException {
        logger.info("creating default configuration");
        Files.copy(ConfigUtils.class.getResourceAsStream(DEFAULT_CONFIG), CONFIG_FILE);
        Configuration configuration = readConfig();
        configuration.setXmlPath(XML_DIR.toString());
        configuration.setMobilityPath(MOBILITY_DIR.toString());
        configuration.setIconPath(ICON_DIR.toString());
        configuration.setNodeTypeConfigs(createDefaults());
        save(configuration);
    }

    public static Configuration load() {
        try {
            Configuration configuration = readConfig();

            // initialize node types
            for (NodeTypeConfig nodeTypeConfig : configuration.getNodeTypeConfigs()) {
                NodeType nodeType = new NodeType(
                        NodeType.DEFAULT,
                        nodeTypeConfig.getModel(),
                        nodeTypeConfig.getDisplay(),
                        nodeTypeConfig.getIcon()
                );
                nodeType.getServices().addAll(nodeTypeConfig.getServices());
                NodeType.add(nodeType);
            }

            // override configuration from command line
            String coreRest = System.getProperty("core-rest");
            configuration.setCoreRest(coreRest);

            return configuration;
        } catch (IOException ex) {
            logger.error("error reading config file");
            throw new RuntimeException("configuration file did not exist");
        }
    }
}
