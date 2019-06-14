package com.core.data;

import lombok.Data;

@Data
public class CoreEvent {
    private Integer session;
    private Integer node;
    private String name;
    private Double time;
    private EventType eventType;
    private String data;
}
