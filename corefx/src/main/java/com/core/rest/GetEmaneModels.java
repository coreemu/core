package com.core.rest;

import lombok.Data;

import java.util.ArrayList;
import java.util.List;

@Data
public class GetEmaneModels {
    private List<String> models = new ArrayList<>();
}
