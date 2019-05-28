package com.core.client.rest;

import lombok.Data;
import lombok.NoArgsConstructor;

import java.util.List;
import java.util.Map;

@Data
@NoArgsConstructor
public class GetServices {
    private Map<String, List<String>> groups;
}
