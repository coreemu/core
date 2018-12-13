package com.core.data;

import java.util.HashMap;
import java.util.Map;

public enum SessionState {
    DEFINITION(1),
    CONFIGURATION(2),
    INSTANTIATION(3),
    RUNTIME(4),
    DATA_COLLECT(5),
    SHUTDOWN(6),
    START(7),
    STOP(8),
    PAUSE(9);

    private static final Map<Integer, SessionState> LOOKUP = new HashMap<>();

    static {
        for (SessionState state : SessionState.values()) {
            LOOKUP.put(state.getValue(), state);
        }
    }

    private final int value;

    SessionState(int value) {
        this.value = value;
    }

    public int getValue() {
        return this.value;
    }

    public static SessionState get(int value) {
        return LOOKUP.get(value);
    }
}
