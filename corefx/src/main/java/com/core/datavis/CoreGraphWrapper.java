package com.core.datavis;

import javafx.scene.chart.*;
import org.apache.logging.log4j.LogManager;
import org.apache.logging.log4j.Logger;

import java.util.HashMap;
import java.util.Map;
import java.util.concurrent.atomic.AtomicInteger;

public class CoreGraphWrapper {
    private static final Logger logger = LogManager.getLogger();
    private final GraphType graphType;
    private PieChart pieChart;
    private final Map<String, PieChart.Data> pieData = new HashMap<>();
    private BarChart<String, Number> barChart;
    private final Map<String, XYChart.Data<String, Number>> barMap = new HashMap<>();
    private XYChart<Number, Number> xyChart;
    private final XYChart.Series<Number, Number> series = new XYChart.Series<>();
    private final XYChart.Series<String, Number> barSeries = new XYChart.Series<>();
    private AtomicInteger timeValue = new AtomicInteger(0);

    public CoreGraphWrapper(CoreGraph coreGraph) {
        graphType = coreGraph.getGraphType();
        createChart(coreGraph);
    }

    public Chart getChart() {
        switch (graphType) {
            case PIE:
                return pieChart;
            case BAR:
                return barChart;
            default:
                return xyChart;
        }
    }

    public void add(CoreGraphData coreGraphData) {
        switch (graphType) {
            case PIE:
            case BAR:
                add(coreGraphData.getName(), coreGraphData.getY());
                break;
            case TIME:
                add(coreGraphData.getY());
                break;
            case BUBBLE:
                add(coreGraphData.getX(), coreGraphData.getY(), coreGraphData.getWeight());
                break;
            default:
                add(coreGraphData.getX(), coreGraphData.getY());
        }
    }

    public void add(String name, double value) {
        if (GraphType.PIE == graphType) {
            PieChart.Data data = pieData.computeIfAbsent(name, x -> {
                PieChart.Data newData = new PieChart.Data(x, value);
                pieChart.getData().add(newData);
                return newData;
            });
            data.setPieValue(value);
        } else {
            XYChart.Data<String, Number> data = barMap.computeIfAbsent(name, x -> {
                XYChart.Data<String, Number> newData = new XYChart.Data<>(name, value);
                barSeries.getData().add(newData);
                return newData;
            });
            data.setYValue(value);
        }
    }

    public void add(Number y) {
        series.getData().add(new XYChart.Data<>(timeValue.getAndIncrement(), y));
    }

    public void add(Number x, Number y) {
        series.getData().add(new XYChart.Data<>(x, y));
    }

    public void add(Number x, Number y, Number weight) {
        series.getData().add(new XYChart.Data<>(x, y, weight));
    }

    private NumberAxis getAxis(CoreGraphAxis graphAxis) {
        return new NumberAxis(graphAxis.getLabel(), graphAxis.getLower(),
                graphAxis.getUpper(), graphAxis.getTick());
    }

    private void createChart(CoreGraph coreGraph) {
        NumberAxis xAxis;
        NumberAxis yAxis;

        switch (coreGraph.getGraphType()) {
            case AREA:
                xAxis = getAxis(coreGraph.getXAxis());
                yAxis = getAxis(coreGraph.getYAxis());
                xyChart = new AreaChart<>(xAxis, yAxis);
                xyChart.setTitle(coreGraph.getTitle());
                xyChart.setLegendVisible(false);
                xyChart.getData().add(series);
                break;
            case TIME:
                xAxis = new NumberAxis();
                xAxis.setLabel(coreGraph.getXAxis().getLabel());
                xAxis.setTickUnit(1);
                xAxis.setLowerBound(0);
                yAxis = getAxis(coreGraph.getYAxis());
                xyChart = new LineChart<>(xAxis, yAxis);
                xyChart.setTitle(coreGraph.getTitle());
                xyChart.setLegendVisible(false);
                xyChart.getData().add(series);
                break;
            case LINE:
                xAxis = getAxis(coreGraph.getXAxis());
                yAxis = getAxis(coreGraph.getYAxis());
                xyChart = new LineChart<>(xAxis, yAxis);
                xyChart.setTitle(coreGraph.getTitle());
                xyChart.setLegendVisible(false);
                xyChart.getData().add(series);
                break;
            case BUBBLE:
                xAxis = getAxis(coreGraph.getXAxis());
                yAxis = getAxis(coreGraph.getYAxis());
                xyChart = new BubbleChart<>(xAxis, yAxis);
                xyChart.setTitle(coreGraph.getTitle());
                xyChart.setLegendVisible(false);
                xyChart.getData().add(series);
                break;
            case SCATTER:
                xAxis = getAxis(coreGraph.getXAxis());
                yAxis = getAxis(coreGraph.getYAxis());
                xyChart = new ScatterChart<>(xAxis, yAxis);
                xyChart.setTitle(coreGraph.getTitle());
                xyChart.setLegendVisible(false);
                xyChart.getData().add(series);
                break;
            case PIE:
                pieChart = new PieChart();
                pieChart.setTitle(coreGraph.getTitle());
                break;
            case BAR:
                CategoryAxis categoryAxis = new CategoryAxis();
                categoryAxis.setLabel(coreGraph.getXAxis().getLabel());
                yAxis = getAxis(coreGraph.getYAxis());
                barChart = new BarChart<>(categoryAxis, yAxis);
                barChart.setLegendVisible(false);
                barChart.setTitle(coreGraph.getTitle());
                barChart.getData().add(barSeries);
                break;
            default:
                throw new IllegalArgumentException(String.format("unknown graph type: %s",
                        coreGraph.getGraphType()));
        }
    }
}
