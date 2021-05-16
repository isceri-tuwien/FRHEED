# -*- coding: utf-8 -*-
"""
Widgets for RHEED analysis.
"""

from typing import Union

from PyQt5.QtWidgets import (
    QWidget,
    QGridLayout,
    QSizePolicy,
    QPushButton,
    QSplitter,
    QSpacerItem,
    
    )
from PyQt5.QtCore import (
    Qt,
    pyqtSlot,
    
    )
# from PyQt5.QtGui import (
    
#     )

from FRHEED.widgets.camera_widget import VideoWidget
from FRHEED.cameras.FLIR import FlirCamera
from FRHEED.cameras.USB import UsbCamera
from FRHEED.widgets.plot_widgets import PlotWidget
from FRHEED.widgets.canvas_widget import CanvasShape, CanvasLine
from FRHEED.widgets.selection_widgets import CameraSelection
from FRHEED.widgets.common_widgets import HSpacer, VSpacer
from FRHEED.utils import snip_lists


class RHEEDWidget(QWidget):
    _initialized = False
    
    def __init__(self, parent: QWidget = None):
        super().__init__(parent)
        
        # Settings
        self.setSizePolicy(QSizePolicy.MinimumExpanding,
                           QSizePolicy.MinimumExpanding)
        
        # Create the layout
        self.layout = QGridLayout()
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(4)
        self.setLayout(self.layout)
        
        # Create camera selection widget and wait for choice
        self.setVisible(False)
        self.cam_selection = CameraSelection()
        self.cam_selection.camera_selected.connect(self._init_ui)
        self.cam_selection.raise_()
        
    @pyqtSlot()
    def _init_ui(self) -> None:
        """ Finish UI setup after selecting a camera. """
        # Show the widget
        self.setVisible(True)
        
        # Create the camera widget
        camera = self.cam_selection._cam
        self.camera_widget = VideoWidget(camera, parent=self)
        self.camera_widget.setSizePolicy(QSizePolicy.MinimumExpanding,
                                         QSizePolicy.MinimumExpanding)
        
        # Create the plot widgets
        # self.region_plot = PlotWidget(parent=self, popup=True, name="Regions (Live)")
        # self.profile_plot = PlotWidget(parent=self, popup=True, name="Line Profiles (Live)")
        self.plot_grid = PlotGridWidget(parent=self)
        self.region_plot = self.plot_grid.region_plot
        self.profile_plot = self.plot_grid.profile_plot
        
        # Add widgets to layout
        self.layout.addWidget(self.camera_widget, 0, 0, 1, 1)
        self.layout.setRowStretch(0, 1)
        self.layout.setColumnStretch(0, 1)
        
        # Connect signals
        self.camera_widget.analysis_worker.data_ready.connect(self.plot_data)
        self.camera_widget.display.canvas.shape_deleted.connect(self.remove_line)
        
        # Mark as initialized
        self._initialized = True
        
    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        
    def closeEvent(self, event) -> None:
        if self._initialized:
            [wid.setParent(None) for wid in 
             [self.region_plot, self.profile_plot, self, self.plot_grid]]
            self.camera_widget.closeEvent(event)
        self.cam_selection.close()
        
    @pyqtSlot(dict)
    def plot_data(self, data: dict) -> None:
        """ Plot data from the camera """
        for color, color_data in data.items():
            if color_data["kind"] in ["rectangle", "ellipse"]:
                curve = self.region_plot.add_curve(color)
                # Catch RuntimeError if widget has been closed
                try:
                    curve.setData(*snip_lists(color_data["time"], color_data["average"]))
                except RuntimeError:
                    pass
            elif color_data["kind"] == "line":
                curve = self.profile_plot.add_curve(color)
                try:
                    curve.setData(color_data["y"][-1])
                except RuntimeError:
                    pass
                
    @pyqtSlot(object)
    def remove_line(self, shape: Union["CanvasShape", "CanvasLine"]) -> None:
        """ Remove a line from the plot it is part of """
        
        # Get the plot widget
        plot = self.profile_plot if shape.kind == "line" else self.region_plot
        
        # Remove the line
        plot.plot_widget.removeItem(plot.plot_items.pop(shape.color_name))
        self.camera_widget.analysis_worker.data.pop(shape.color_name)


class PlotGridWidget(QWidget):
    """ Widget for containing the live RHEED plots and plot transformations. """
    def __init__(self, parent = None):
        super().__init__(parent)
        self._parent = parent
        
        # Create layout
        self.layout = QGridLayout()
        self.layout.setContentsMargins(8, 8, 8, 8)
        self.layout.setSpacing(4)
        self.setLayout(self.layout)
        
        # Create controls layout
        self.controls_layout = QGridLayout()
        self.controls_layout.setContentsMargins(0, 0, 0, 0)
        self.controls_layout.setSpacing(4)
        
        # Create controls buttons
        self.start_button = QPushButton("Start")  # TODO: Add icon
        self.stop_button = QPushButton("Stop")  # TODO: Add icon
        
        # Create plots layout
        self.plots_layout = QGridLayout()
        self.plots_layout.setContentsMargins(8, 8, 8, 8)
        self.plots_layout.setSpacing(4)
        
        # Create plot widgets
        self.region_plot = PlotWidget(parent=self, popup=False, title="Region Intensity")
        self.region_fft_plot = PlotWidget(parent=self, popup=False, title="Region Intensity FFT")
        self.growth_rate_plot = PlotWidget(parent=self, popup=False, title="Growth Rate")
        self.profile_plot = PlotWidget(parent=self, popup=False, title="Line Profile")
        self.profile_fft_plot = PlotWidget(parent=self, popup=False, title="Line Profile FFT")
        self.profile_2d_plot = PlotWidget(parent=self, popup=False, title="2D Line Profile")
        
        # Create containers for plots
        self.main_splitter = QSplitter(Qt.Horizontal)
        self.region_plots_splitter = QSplitter(Qt.Vertical)
        self.profile_plots_splitter = QSplitter(Qt.Vertical)
        
        # Add items to main layout
        self.layout.addLayout(self.controls_layout, 0, 0, 1, 1)
        self.layout.addLayout(self.plots_layout, 1, 0, 1, 1)
        self.controls_layout.addWidget(self.start_button, 0, 0, 1, 1)
        self.controls_layout.addWidget(self.stop_button, 0, 1, 1, 1)
        self.controls_layout.addItem(HSpacer(), 0, 2, 1, 1)
        self.layout.addWidget(self.main_splitter, 1, 0, 1, 1)
        self.main_splitter.addWidget(self.region_plots_splitter)
        self.main_splitter.addWidget(self.profile_plots_splitter)
        [self.region_plots_splitter.addWidget(w) 
         for w in (self.region_plot, self.region_fft_plot, self.growth_rate_plot)]
        [self.profile_plots_splitter.addWidget(w)
         for w in (self.profile_plot, self.profile_fft_plot, self.profile_2d_plot)]
        
        
        # Show widget
        popup = True
        name = "Plots"
        _DEFAULT_SIZE = (800, 600)
        if popup:
            self.setWindowFlags(Qt.Window)
            self.show()
            self.raise_()
            self.setWindowTitle(str(name) if name is not None else "Plots")
            self.resize(*_DEFAULT_SIZE)


if __name__ == "__main__":
    def test():
        from FRHEED.utils import test_widget
        
        return test_widget(RHEEDWidget, block=True)
        
    widget, app = test()