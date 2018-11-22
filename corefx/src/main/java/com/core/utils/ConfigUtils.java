package com.core.utils;

import org.apache.logging.log4j.LogManager;
import org.apache.logging.log4j.Logger;

import java.io.FileInputStream;
import java.io.IOException;
import java.io.PrintWriter;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;

public final class ConfigUtils {
    private static final Logger logger = LogManager.getLogger();
    private static final String CONFIG_FILE_NAME = "config.json";
    private static final String DEFAULT_CONFIG = "/" + CONFIG_FILE_NAME;
    private static final Path HOME = Paths.get(System.getProperty("user.home"), ".core");
    private static final Path CONFIG_FILE = Paths.get(HOME.toString(), CONFIG_FILE_NAME);
    private static final Path XML_DIR = Paths.get(HOME.toString(), "xml");
    private static final Path MOBILITY_DIR = Paths.get(HOME.toString(), "mobility");


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

    public static Configuration load() {
        try {
            if (!HOME.toFile().exists()) {
                logger.info("creating core home directory");
                Files.createDirectory(HOME);
                Files.createDirectory(XML_DIR);
                Files.createDirectory(MOBILITY_DIR);
            }

            Configuration configuration;
            if (!CONFIG_FILE.toFile().exists()) {
                logger.info("creating default configuration");
                Files.copy(ConfigUtils.class.getResourceAsStream(DEFAULT_CONFIG), CONFIG_FILE);
                configuration = readConfig();
                configuration.setXmlPath(XML_DIR.toString());
                configuration.setMobilityPath(MOBILITY_DIR.toString());
                save(configuration);
            } else {
                configuration = readConfig();
            }

            return configuration;
        } catch (IOException ex) {
            logger.error("error reading config file");
            throw new RuntimeException("configuration file did not exist");
        }
    }
}
