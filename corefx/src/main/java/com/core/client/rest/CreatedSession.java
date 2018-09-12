package com.core.client.rest;

import lombok.Data;

@Data
public class CreatedSession {
    private Integer id;
    private Integer state;
    private String url;
}
