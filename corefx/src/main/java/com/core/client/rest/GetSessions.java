package com.core.client.rest;

import com.core.data.SessionOverview;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.util.ArrayList;
import java.util.List;

@Data
@NoArgsConstructor
public class GetSessions {
    private List<SessionOverview> sessions = new ArrayList<>();
}
