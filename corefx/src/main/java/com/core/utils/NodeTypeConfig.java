package com.core.utils;

import lombok.AllArgsConstructor;
import lombok.Data;
import lombok.EqualsAndHashCode;
import lombok.NoArgsConstructor;

import java.util.Set;

@Data
@EqualsAndHashCode(onlyExplicitlyIncluded = true)
@NoArgsConstructor
@AllArgsConstructor
public class NodeTypeConfig {
    @EqualsAndHashCode.Include
    private String model;
    private String display;
    private String icon;
    private Set<String> services;
}
