package com.core.data;

import java.util.HashMap;
import java.util.Map;

public enum MessageFlags {
    ADD(1),
    DELETE(2),
    CRI(4),
    LOCAL(8),
    STRING(16),
    TEXT(32),
    TTY(64);

    private static final Map<Integer, MessageFlags> LOOKUP = new HashMap<>();

    static {
        for (MessageFlags state : MessageFlags.values()) {
            LOOKUP.put(state.getValue(), state);
        }
    }

    private final int value;

    MessageFlags(int value) {
        this.value = value;
    }

    public int getValue() {
        return this.value;
    }

    public static MessageFlags get(int value) {
        return LOOKUP.get(value);
    }
}
