package com.core.data;

import com.fasterxml.jackson.annotation.JsonSetter;
import lombok.Data;

@Data
public class CoreEvent {
    private Integer session;
    private Integer node;
    private String name;
    private Double time;
    private EventType eventType;
    private String data;

    @JsonSetter("event_type")
    public void setEventType(int value) {
        eventType = EventType.get(value);
    }
}
