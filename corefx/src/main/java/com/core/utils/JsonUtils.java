package com.core.utils;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.apache.logging.log4j.LogManager;
import org.apache.logging.log4j.Logger;

import java.io.IOException;
import java.io.InputStream;

public final class JsonUtils {
    private static final Logger logger = LogManager.getLogger();
    private static ObjectMapper mapper = new ObjectMapper();

    private JsonUtils() {
    }

    public static ObjectMapper getMapper() {
        return mapper;
    }

    public static <T> T read(byte[] data, Class<T> clazz) throws IOException {
        return mapper.readValue(data, clazz);
    }

    public static <T> T read(String data, Class<T> clazz) throws IOException {
        return mapper.readValue(data, clazz);
    }

    public static <T> T read(InputStream input, Class<T> clazz) throws IOException {
        return mapper.readValue(input, clazz);
    }

    public static void logPrettyJson(Object obj) {
        try {
            logger.debug(mapper.writerWithDefaultPrettyPrinter().writeValueAsString(obj));
        } catch (JsonProcessingException e) {
            logger.error("error making pretty json", e);
        }
    }

    public static String toPrettyString(Object obj) throws JsonProcessingException {
        return mapper.writerWithDefaultPrettyPrinter().writeValueAsString(obj);
    }

    public static String toString(Object obj) throws JsonProcessingException {
        return mapper.writeValueAsString(obj);
    }

    public static byte[] toBytes(Object obj) throws JsonProcessingException {
        return mapper.writeValueAsBytes(obj);
    }
}
