package com.core.client.rest;

import com.core.data.Hook;
import lombok.Data;

import java.util.ArrayList;
import java.util.List;

@Data
public class GetHooks {
    private List<Hook> hooks = new ArrayList<>();
}
