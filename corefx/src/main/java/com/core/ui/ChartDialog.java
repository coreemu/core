package com.core.ui;

import com.core.Controller;
import com.core.datavis.*;
import com.jfoenix.controls.JFXButton;
import com.jfoenix.controls.JFXComboBox;
import javafx.application.Platform;
import javafx.fxml.FXML;
import javafx.scene.chart.Chart;
import javafx.scene.layout.Pane;
import org.apache.logging.log4j.LogManager;
import org.apache.logging.log4j.Logger;

import java.util.Arrays;
import java.util.List;
import java.util.Random;
import java.util.concurrent.atomic.AtomicBoolean;

public class ChartDialog extends StageDialog {
    private static final Logger logger = LogManager.getLogger();
    private final AtomicBoolean running = new AtomicBoolean(false);
    private final Random numbers = new Random();
    private final List<String> chartNames = Arrays.asList("Name 1", "Name 2", "Name 3", "Name 4", "Name 5");

    @FXML
    private JFXComboBox<String> chartCombo;

    @FXML
    private Pane chartPane;

    @FXML
    private JFXButton stopButton;

    private CoreGraph coreGraph;

    public ChartDialog(Controller controller) {
        super(controller, "/fxml/chart_dialog.fxml");
        addCancelButton();

        coreGraph = new CoreGraph();
        coreGraph.setTitle("My Graph");
        coreGraph.setXAxis(new CoreGraphAxis("X Label", 0.0, 100.0, 1.0));
        coreGraph.setYAxis(new CoreGraphAxis("Y Label", 0.0, 100.0, 1.0));

        chartCombo.getItems().addAll("pie", "line", "area", "bar", "scatter", "bubble", "time");
        chartCombo.getSelectionModel().selectedItemProperty().addListener((ov, prev, curr) -> {
            if (curr == null) {
                return;
            }

            running.set(false);
            switch (curr) {
                case "pie":
                    pieChart();
                    break;
                case "line":
                    lineChart();
                    break;
                case "area":
                    areaChart();
                    break;
                case "bar":
                    barChart();
                    break;
                case "scatter":
                    scatterChart();
                    break;
                case "bubble":
                    bubbleChart();
                    break;
                case "time":
                    timeChart();
                    break;
            }
        });

        stopButton.setOnAction(event -> running.set(false));
        chartCombo.getSelectionModel().selectFirst();
    }

    private void timeChart() {
        coreGraph.setGraphType(GraphType.TIME);
        CoreGraphWrapper graphWrapper = new CoreGraphWrapper(coreGraph);
        setChart(graphWrapper.getChart());

        new Thread(() -> {
            while (running.get()) {
                try {
                    double y = numbers.nextInt(100);
                    Platform.runLater(() -> graphWrapper.add(new CoreGraphData(null, null, y, null)));
                    Thread.sleep(1000);
                } catch (Exception ex) {
                    logger.error("error adding data", ex);
                }
            }
        }).start();
    }

    private void bubbleChart() {
        coreGraph.setGraphType(GraphType.BUBBLE);
        CoreGraphWrapper graphWrapper = new CoreGraphWrapper(coreGraph);
        setChart(graphWrapper.getChart());

        new Thread(() -> {
            while (running.get()) {
                try {
                    double x = numbers.nextInt(100);
                    double y = numbers.nextInt(100);
                    double weight = numbers.nextInt(10);
                    Platform.runLater(() -> graphWrapper.add(new CoreGraphData(null, x, y, weight)));
                    Thread.sleep(1000);
                } catch (Exception ex) {
                    logger.error("error adding data", ex);
                }
            }
        }).start();
    }

    private void scatterChart() {
        coreGraph.setGraphType(GraphType.SCATTER);
        CoreGraphWrapper graphWrapper = new CoreGraphWrapper(coreGraph);
        setChart(graphWrapper.getChart());

        new Thread(() -> {
            while (running.get()) {
                try {
                    double x = numbers.nextInt(100);
                    double y = numbers.nextInt(100);
                    Platform.runLater(() -> graphWrapper.add(new CoreGraphData(null, x, y, null)));
                    Thread.sleep(1000);
                } catch (Exception ex) {
                    logger.error("error adding data", ex);
                }
            }
        }).start();
    }

    private void areaChart() {
        coreGraph.setGraphType(GraphType.AREA);
        CoreGraphWrapper graphWrapper = new CoreGraphWrapper(coreGraph);
        setChart(graphWrapper.getChart());

        new Thread(() -> {
            while (running.get()) {
                try {
                    double x = numbers.nextInt(100);
                    double y = numbers.nextInt(100);
                    Platform.runLater(() -> graphWrapper.add(new CoreGraphData(null, x, y, null)));
                    Thread.sleep(1000);
                } catch (Exception ex) {
                    logger.error("error adding data", ex);
                }
            }
        }).start();
    }

    private void setChart(Chart chart) {
        chart.prefHeightProperty().bind(chartPane.heightProperty());
        chart.prefWidthProperty().bind(chartPane.widthProperty());
        chartPane.getChildren().clear();
        chartPane.getChildren().add(chart);
        running.set(true);
    }

    private void lineChart() {
        coreGraph.setGraphType(GraphType.LINE);
        CoreGraphWrapper graphWrapper = new CoreGraphWrapper(coreGraph);
        setChart(graphWrapper.getChart());

        new Thread(() -> {
            while (running.get()) {
                try {
                    double x = numbers.nextInt(100);
                    double y = numbers.nextInt(100);
                    Platform.runLater(() -> graphWrapper.add(new CoreGraphData(null, x, y, null)));
                    Thread.sleep(1000);
                } catch (Exception ex) {
                    logger.error("error adding data", ex);
                }
            }
        }).start();
    }

    private void pieChart() {
        coreGraph.setGraphType(GraphType.PIE);
        CoreGraphWrapper graphWrapper = new CoreGraphWrapper(coreGraph);
        setChart(graphWrapper.getChart());
        new Thread(() -> {
            while (running.get()) {
                try {
                    String name = chartNames.get(numbers.nextInt(chartNames.size()));
                    double y = numbers.nextInt(100);
                    Platform.runLater(() -> graphWrapper.add(new CoreGraphData(name, null, y, null)));
                    Thread.sleep(1000);
                } catch (Exception ex) {
                    logger.error("error adding data", ex);
                }
            }
        }).start();
    }

    private void barChart() {
        coreGraph.setGraphType(GraphType.BAR);
        CoreGraphWrapper graphWrapper = new CoreGraphWrapper(coreGraph);
        setChart(graphWrapper.getChart());
        new Thread(() -> {
            while (running.get()) {
                try {
                    String name = chartNames.get(numbers.nextInt(chartNames.size()));
                    Integer y = numbers.nextInt(100);
                    Platform.runLater(() -> graphWrapper.add(name, y));
                    Thread.sleep(1000);
                } catch (Exception ex) {
                    logger.error("error adding data", ex);
                }
            }
        }).start();
    }


    public void showDialog() {
        chartCombo.getSelectionModel().selectFirst();
    }
}
