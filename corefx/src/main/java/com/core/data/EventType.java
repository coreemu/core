package com.core.data;

import java.util.Arrays;
import java.util.HashMap;
import java.util.Map;

public enum EventType {
    NONE(0),
    DEFINITION_STATE(1),
    CONFIGURATION_STATE(2),
    INSTANTIATION_STATE(3),
    RUNTIME_STATE(4),
    DATACOLLECT_STATE(5),
    SHUTDOWN_STATE(6),
    START(7),
    STOP(8),
    PAUSE(9),
    RESTART(10),
    FILE_OPEN(11),
    FILE_SAVE(12),
    SCHEDULED(13),
    RECONFIGURE(14),
    INSTANTIATION_COMPLETE(15);

    private static final Map<Integer, EventType> LOOKUP = new HashMap<>();

    static {
        Arrays.stream(EventType.values()).forEach(x -> LOOKUP.put(x.getValue(), x));
    }

    private final int value;

    EventType(int value) {
        this.value = value;
    }

    public int getValue() {
        return value;
    }


    public static EventType get(int value) {
        return LOOKUP.get(value);
    }
}
