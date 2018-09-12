package com.core.rest;

import com.core.data.*;
import com.core.utils.JsonUtils;
import com.core.utils.WebUtils;
import lombok.AllArgsConstructor;

import java.io.File;
import java.io.IOException;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

@AllArgsConstructor
public class CoreApi {
    private final String baseUrl;

    private String getUrl(String path) {
        return String.format("%s/%s", baseUrl, path);
    }

    public GetSessions getSessions() throws IOException {
        String url = getUrl("sessions");
        return WebUtils.getJson(url, GetSessions.class);
    }

    public GetSession getSession(Integer session) throws IOException {
        String path = String.format("sessions/%s", session);
        String url = getUrl(path);
        return WebUtils.getJson(url, GetSession.class);
    }

    public CreatedSession createSession() throws IOException {
        String url = getUrl("sessions");
        return WebUtils.post(url, CreatedSession.class);
    }

    public void saveSession(Integer id, File file) throws IOException {
        String path = String.format("sessions/%s/xml", id);
        String url = getUrl(path);
        WebUtils.getFile(url, file);
    }

    public CreatedSession openSession(File file) throws IOException {
        String url = getUrl("sessions/xml");
        return WebUtils.putFile(url, file, CreatedSession.class);
    }

    public GetConfig getSessionConfig(Integer session) throws IOException {
        String url = getUrl(String.format("sessions/%s/options", session));
        return WebUtils.getJson(url, GetConfig.class);
    }

    public boolean setSessionConfig(Integer session, SetConfig config) throws IOException {
        String url = getUrl(String.format("sessions/%s/options", session));
        return WebUtils.putJson(url, JsonUtils.toString(config));
    }

    public boolean setSessionState(Integer session, SessionState state) throws IOException {
        String url = getUrl(String.format("sessions/%s/state", session));
        Map<String, Integer> data = new HashMap<>();
        data.put("state", state.getValue());
        return WebUtils.putJson(url, JsonUtils.toString(data));
    }

    public boolean createNode(Integer session, CoreNode node) throws IOException {
        String url = getUrl(String.format("sessions/%s/nodes", session));
        String data = JsonUtils.toString(node);
        return WebUtils.postJson(url, data);
    }

    public boolean deleteNode(Integer session, CoreNode node) throws IOException {
        String url = getUrl(String.format("/sessions/%s/nodes/%s", session, node.getId()));
        return WebUtils.delete(url);
    }

    public boolean createLink(Integer session, CoreLink link) throws IOException {
        String url = getUrl(String.format("sessions/%s/links", session));
        String data = JsonUtils.toString(link);
        return WebUtils.postJson(url, data);
    }

    public GetServices getServices() throws IOException {
        String url = getUrl("services");
        return WebUtils.getJson(url, GetServices.class);
    }

    public CoreService getService(Integer session, CoreNode node, String serviceName) throws IOException {
        String url = getUrl(String.format("sessions/%s/nodes/%s/services/%s", session, node.getId(), serviceName));
        return WebUtils.getJson(url, CoreService.class);
    }

    public String getServiceFile(Integer session, CoreNode node, String serviceName, String fileName)
            throws IOException {
        String url = getUrl(String.format("sessions/%s/nodes/%s/services/%s/file", session, node.getId(), serviceName));
        Map<String, String> args = new HashMap<>();
        args.put("file", fileName);
        return WebUtils.getJson(url, String.class, args);
    }

    public boolean setService(Integer session, CoreNode node, String serviceName, CoreService service)
            throws IOException {
        String url = getUrl(String.format("sessions/%s/nodes/%s/services/%s", session, node.getId(), serviceName));
        return WebUtils.putJson(url, JsonUtils.toString(service));
    }

    public boolean setServiceFile(Integer session, CoreNode node, String service, ServiceFile serviceFile)
            throws IOException {
        String url = getUrl(String.format("sessions/%s/nodes/%s/services/%s/file", session, node.getId(), service));
        return WebUtils.putJson(url, JsonUtils.toString(serviceFile));
    }

    public GetEmaneModels getEmaneModels(Integer session) throws IOException {
        String url = getUrl(String.format("sessions/%s/emane/models", session));
        return WebUtils.getJson(url, GetEmaneModels.class);
    }

    public GetConfig getEmaneModelConfig(Integer session, CoreNode node, String model) throws IOException {
        String url = getUrl(String.format("sessions/%s/emane/model/config", session));
        Map<String, String> args = new HashMap<>();
        args.put("node", node.getId().toString());
        args.put("name", model);
        return WebUtils.getJson(url, GetConfig.class, args);
    }

    public GetConfig getEmaneConfig(Integer session, CoreNode node) throws IOException {
        String url = getUrl(String.format("sessions/%s/emane/config", session));
        Map<String, String> args = new HashMap<>();
        args.put("node", node.getId().toString());
        return WebUtils.getJson(url, GetConfig.class, args);
    }

    public boolean setEmaneConfig(Integer session, CoreNode node, List<ConfigOption> options) throws IOException {
        String url = getUrl(String.format("sessions/%s/emane/config", session));
        SetEmaneConfig setEmaneConfig = new SetEmaneConfig();
        setEmaneConfig.setNode(node.getId());
        setEmaneConfig.setValues(options);
        return WebUtils.putJson(url, JsonUtils.toString(setEmaneConfig));
    }

    public boolean setEmaneModelConfig(Integer session, CoreNode node, String model, List<ConfigOption> options)
            throws IOException {
        String url = getUrl(String.format("sessions/%s/emane/model/config", session));
        SetEmaneModelConfig setEmaneModelConfig = new SetEmaneModelConfig();
        setEmaneModelConfig.setNode(node.getId());
        setEmaneModelConfig.setName(model);
        setEmaneModelConfig.setValues(options);
        return WebUtils.putJson(url, JsonUtils.toString(setEmaneModelConfig));
    }

    public boolean createHook(Integer session, Hook hook) throws IOException {
        String url = getUrl(String.format("sessions/%s/hooks", session));
        String data = JsonUtils.toString(hook);
        return WebUtils.postJson(url, data);
    }

    public GetHooks getHooks(Integer session) throws IOException {
        String url = getUrl(String.format("sessions/%s/hooks", session));
        return WebUtils.getJson(url, GetHooks.class);
    }

    public WlanConfig getWlanConfig(Integer session, CoreNode node) throws IOException {
        String url = getUrl(String.format("sessions/%s/nodes/%s/wlan", session, node.getId()));
        return WebUtils.getJson(url, WlanConfig.class);
    }

    public boolean setWlanConfig(Integer session, CoreNode node, WlanConfig config) throws IOException {
        String url = getUrl(String.format("sessions/%s/nodes/%s/wlan", session, node.getId()));
        String jsonData = JsonUtils.toString(config);
        return WebUtils.putJson(url, jsonData);
    }

    public boolean setMobilityConfig(Integer session, CoreNode node, MobilityConfig config) throws IOException {
        String url = getUrl(String.format("sessions/%s/nodes/%s/mobility", session, node.getId()));
        String data = JsonUtils.toString(config);
        return WebUtils.postJson(url, data);
    }

    public MobilityConfig getMobilityConfig(Integer session, CoreNode node) throws IOException {
        String url = getUrl(String.format("sessions/%s/nodes/%s/mobility", session, node.getId()));
        return WebUtils.getJson(url, MobilityConfig.class);
    }

    public boolean mobilityAction(Integer session, CoreNode node, String action) throws IOException {
        String url = getUrl(String.format("sessions/%s/nodes/%s/mobility/%s", session, node.getId(), action));
        return WebUtils.putJson(url, null);
    }

    public String getTerminalCommand(Integer session, CoreNode node) throws IOException {
        String url = getUrl(String.format("sessions/%s/nodes/%s/terminal", session, node.getId()));
        return WebUtils.getJson(url, String.class);
    }
}
