package com.core.utils;

import com.fasterxml.jackson.core.type.TypeReference;
import okhttp3.*;
import org.apache.logging.log4j.LogManager;
import org.apache.logging.log4j.Logger;

import java.io.*;
import java.util.Collections;
import java.util.Map;

public final class WebUtils {
    private static final Logger logger = LogManager.getLogger();
    private static final OkHttpClient client = new OkHttpClient();
    private static final MediaType JSON = MediaType.parse("application/json; charset=utf-8");

    private WebUtils() {
    }

    public static <T> T getJson(String url, Class<T> clazz) throws IOException {
        return getJson(url, clazz, Collections.emptyMap());
    }

    public static <T> T getJson(String url, Class<T> clazz, Map<String, String> args) throws IOException {
        logger.debug("get json: {}", url);
        HttpUrl.Builder urlBuilder = HttpUrl.parse(url).newBuilder();
        args.forEach(urlBuilder::addQueryParameter);
        HttpUrl httpUrl = urlBuilder.build();

        Request request = new Request.Builder()
                .url(httpUrl)
                .build();
        String response = readResponse(request);
        return JsonUtils.read(response, clazz);
    }

    public static void getFile(String url, File file) throws IOException {
        logger.debug("get file: {}", url);
        Request request = new Request.Builder()
                .url(url)
                .build();
        try (Response response = client.newCall(request).execute()) {
            InputStream input = response.body().byteStream();
            try (OutputStream output = new FileOutputStream(file)) {
                int count;
                byte[] data = new byte[1024];
                while ((count = input.read(data)) != -1) {
                    output.write(data, 0, count);
                }
            }
        }
    }

    public static <T> T putFile(String url, File file, Class<T> clazz) throws IOException {
        MediaType mediaType = MediaType.parse("File/*");
        RequestBody requestBody = new MultipartBody.Builder()
                .setType(MultipartBody.FORM)
                .addFormDataPart("session", file.getName(), RequestBody.create(mediaType, file))
                .build();

        Request request = new Request.Builder()
                .url(url)
                .post(requestBody)
                .build();

        String response = readResponse(request);
        return JsonUtils.read(response, clazz);
    }

    public static <T> T getJson(String url, TypeReference<T> reference) throws IOException {
        Request request = new Request.Builder()
                .url(url)
                .build();
        String response = readResponse(request);
        return JsonUtils.getMapper().readValue(response, reference);
    }

    private static String readResponse(Request request) throws IOException {
        try (Response response = client.newCall(request).execute()) {
            ResponseBody body = response.body();
            if (body == null) {
                throw new IOException("failed to received body");
            } else {
                return body.string();
            }
        }
    }

    public static boolean postJson(String url, String json) throws IOException {
        logger.debug("post json: {} - {}", url, json);
        RequestBody body = RequestBody.create(JSON, json);
        Request request = new Request.Builder()
                .url(url)
                .post(body)
                .build();
        try (Response response = client.newCall(request).execute()) {
            return response.isSuccessful();
        }
    }

    public static boolean putJson(String url) throws IOException {
        logger.debug("put json: {}", url);
        RequestBody body = new FormBody.Builder().build();
        Request request = new Request.Builder()
                .url(url)
                .put(body)
                .build();
        try (Response response = client.newCall(request).execute()) {
            return response.isSuccessful();
        }
    }

    public static boolean putJson(String url, String json) throws IOException {
        logger.debug("put json: {} - {}", url, json);
        RequestBody body = RequestBody.create(JSON, json);
        Request request = new Request.Builder()
                .url(url)
                .put(body)
                .build();
        try (Response response = client.newCall(request).execute()) {
            return response.isSuccessful();
        }
    }

    public static <T> T post(String url, Class<T> clazz) throws IOException {
        logger.debug("post: {}", url);
        RequestBody body = new FormBody.Builder().build();
        Request request = new Request.Builder()
                .url(url)
                .post(body)
                .build();
        String response = readResponse(request);
        return JsonUtils.read(response, clazz);
    }

    public static boolean delete(String url) throws IOException {
        logger.debug("delete: {}", url);
        Request request = new Request.Builder()
                .url(url)
                .delete()
                .build();
        try (Response response = client.newCall(request).execute()) {
            return response.isSuccessful();
        }
    }
}
