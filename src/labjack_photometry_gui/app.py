from __future__ import annotations

import sys
import time
from datetime import datetime
from pathlib import Path

import numpy as np
from PySide6 import QtCore, QtWidgets
import pyqtgraph as pg

from labjack_photometry_gui.config_file import load_gui_config, save_gui_config
from labjack_photometry_gui.hardware.base import AcquisitionBlock
from labjack_photometry_gui.hardware.base import PhotometryBackend
from labjack_photometry_gui.hardware.labjack_t7 import LabJackT7Backend
from labjack_photometry_gui.hardware.mock import MockBackend
from labjack_photometry_gui.models import (
    AnalogInputChannel,
    BackendKind,
    DigitalInputChannel,
    ModulationChannel,
    RigConfig,
    SessionConfig,
)
from labjack_photometry_gui.recording import H5Recorder


class SignalStripChart(QtWidgets.QWidget):
    def __init__(
        self,
        name: str,
        channel: str,
        color: str,
        is_digital: bool = False,
        y_min: float = -0.25,
        y_max: float = 5.25,
        suppress_short_low_glitches: bool = False,
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.name = name
        self.channel = channel
        self.is_digital = is_digital
        self.suppress_short_low_glitches = suppress_short_low_glitches
        if y_min == y_max:
            y_min -= 0.5
            y_max += 0.5
        self.y_min = y_min
        self.y_max = y_max
        self.x_values = np.array([], dtype=float)
        self.y_values = np.array([], dtype=float)
        self.setMinimumWidth(720)

        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(0, 2, 0, 2)
        layout.setSpacing(6)

        label = QtWidgets.QLabel(f"{channel}\n{name}")
        label.setFixedWidth(150)
        label.setWordWrap(True)
        label.setAlignment(QtCore.Qt.AlignmentFlag.AlignRight | QtCore.Qt.AlignmentFlag.AlignVCenter)
        layout.addWidget(label)

        self.plot = pg.PlotWidget()
        self.plot.setMinimumHeight(72)
        self.plot.setMaximumHeight(96)
        self.plot.setBackground("w")
        self.plot.showGrid(x=True, y=True, alpha=0.18)
        self.plot.setMouseEnabled(x=False, y=False)
        self.plot.hideButtons()
        self.plot.setMenuEnabled(False)
        self.plot.getPlotItem().hideAxis("left")
        self.plot.getPlotItem().hideAxis("bottom")
        if is_digital:
            self.plot.setYRange(-0.2, 1.2, padding=0)
            self.plot.addLine(
                y=0.0,
                pen=pg.mkPen("#999999", width=0.8, style=QtCore.Qt.PenStyle.DotLine),
            )
        else:
            self.plot.setYRange(self.y_min, self.y_max, padding=0)
        self.curve = self.plot.plot(pen=pg.mkPen(color, width=1.4))
        layout.addWidget(self.plot, stretch=1)

        self.value_label = QtWidgets.QLabel("--")
        self.value_label.setFixedWidth(74)
        self.value_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignRight | QtCore.Qt.AlignmentFlag.AlignVCenter)
        layout.addWidget(self.value_label)

    def set_row_height(self, height: int) -> None:
        height = int(max(34, min(96, height)))
        plot_height = max(26, height - 8)
        self.setMinimumHeight(height)
        self.setMaximumHeight(height)
        self.plot.setMinimumHeight(plot_height)
        self.plot.setMaximumHeight(plot_height)

    def clear(self) -> None:
        self.x_values = np.array([], dtype=float)
        self.y_values = np.array([], dtype=float)
        self.curve.setData([], [])
        self.value_label.setText("--")

    def push(
        self,
        t_seconds: np.ndarray,
        values: np.ndarray,
        display_seconds: float,
        max_display_points: int = 1200,
    ) -> None:
        if t_seconds.size == 0 or values.size == 0:
            return

        if self.is_digital:
            values = (values >= 0.5).astype(float)
        else:
            values = values.astype(float)

        self.x_values = np.concatenate((self.x_values, t_seconds.astype(float)))
        self.y_values = np.concatenate((self.y_values, values))

        cutoff = float(t_seconds[-1] - display_seconds)
        keep = self.x_values >= cutoff
        self.x_values = self.x_values[keep]
        self.y_values = self.y_values[keep]
        if self.x_values.size == 0:
            return

        y_for_plot = self.y_values
        if self.suppress_short_low_glitches and not self.is_digital:
            y_for_plot = _analog_lick_trace_for_display(self.x_values, self.y_values)

        x_plot, y_plot = _decimate_for_display(
            self.x_values,
            y_for_plot,
            max_display_points=max_display_points,
            is_digital=self.is_digital,
        )
        relative_x = x_plot - self.x_values[-1]
        self.curve.setData(relative_x, y_plot)
        self.plot.setXRange(-display_seconds, 0.0, padding=0)
        if not self.is_digital:
            self.plot.setYRange(self.y_min, self.y_max, padding=0)

        if self.is_digital:
            self.value_label.setText(str(int(round(float(self.y_values[-1])))))
        else:
            self.value_label.setText(f"{float(self.y_values[-1]):.3f}")


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("LabJack Photometry")
        self.resize(1200, 780)

        self.config = RigConfig()
        self.backend: PhotometryBackend = MockBackend()
        self.backend.configure(self.config)
        self.backend.connect()
        self.recorder: H5Recorder | None = None

        self.timer = QtCore.QTimer(self)
        self.timer.setInterval(50)
        self.timer.timeout.connect(self._poll_backend)

        self.mod_controls: list[
            tuple[
                QtWidgets.QCheckBox,
                QtWidgets.QLineEdit,
                QtWidgets.QLineEdit,
                QtWidgets.QDoubleSpinBox,
                QtWidgets.QDoubleSpinBox,
                QtWidgets.QDoubleSpinBox,
            ]
        ] = []
        self.strip_charts: dict[str, SignalStripChart] = {}
        self.chart_scroll_area: QtWidgets.QScrollArea | None = None
        self.display_order: list[str] = []
        self._pending_plot_blocks = []
        self._last_plot_update = 0.0
        self._plot_interval_s = 0.20

        self._build_ui()

    def _build_ui(self) -> None:
        central = QtWidgets.QWidget()
        layout = QtWidgets.QHBoxLayout(central)

        controls = QtWidgets.QWidget()
        controls.setMaximumWidth(390)
        controls_layout = QtWidgets.QVBoxLayout(controls)

        backend_group = QtWidgets.QGroupBox("Session")
        backend_layout = QtWidgets.QFormLayout(backend_group)
        self.backend_combo = QtWidgets.QComboBox()
        self.backend_combo.addItems([BackendKind.MOCK.value, BackendKind.LABJACK_T7.value])
        self.sample_rate_spin = QtWidgets.QDoubleSpinBox()
        self.sample_rate_spin.setRange(100.0, 100_000.0)
        self.sample_rate_spin.setDecimals(0)
        self.sample_rate_spin.setValue(self.config.sample_rate_hz)
        self.sample_rate_spin.setSuffix(" Hz")
        self.ain_settling_spin = QtWidgets.QDoubleSpinBox()
        self.ain_settling_spin.setRange(0.0, 500.0)
        self.ain_settling_spin.setDecimals(0)
        self.ain_settling_spin.setValue(self.config.ain_settling_us)
        self.ain_settling_spin.setSuffix(" us")
        self.stream_out_mode_combo = QtWidgets.QComboBox()
        self.stream_out_mode_combo.addItem("Trailing", "trailing")
        self.stream_out_mode_combo.addItem("Leading", "leading")
        self.stream_out_mode_combo.addItem("Inputs only (no DAC waveform)", "inputs_only")
        self.stream_out_mode_combo.setCurrentIndex(
            max(0, self.stream_out_mode_combo.findData(self.config.stream_out_scan_mode))
        )
        self.stream_debug_check = QtWidgets.QCheckBox("Stream debug")
        self.stream_debug_check.setChecked(self.config.labjack_stream_debug)
        self.display_seconds_spin = QtWidgets.QDoubleSpinBox()
        self.display_seconds_spin.setRange(1.0, 300.0)
        self.display_seconds_spin.setDecimals(0)
        self.display_seconds_spin.setValue(20.0)
        self.display_seconds_spin.setSuffix(" s")
        self.save_check = QtWidgets.QCheckBox("Save HDF5")
        self.save_check.setChecked(True)
        self.session_name_edit = QtWidgets.QLineEdit("photometry")
        self.output_dir_edit = QtWidgets.QLineEdit(str(Path.cwd() / "data"))
        browse_button = QtWidgets.QPushButton("Browse")
        browse_button.clicked.connect(self._browse_output_dir)
        output_row = QtWidgets.QWidget()
        output_layout = QtWidgets.QHBoxLayout(output_row)
        output_layout.setContentsMargins(0, 0, 0, 0)
        output_layout.addWidget(self.output_dir_edit, stretch=1)
        output_layout.addWidget(browse_button)
        backend_layout.addRow("Backend", self.backend_combo)
        backend_layout.addRow("Sample rate", self.sample_rate_spin)
        backend_layout.addRow("AIN settle", self.ain_settling_spin)
        backend_layout.addRow("Stream out", self.stream_out_mode_combo)
        backend_layout.addRow("Display", self.display_seconds_spin)
        backend_layout.addRow("Prefix", self.session_name_edit)
        backend_layout.addRow("Output", output_row)
        backend_layout.addRow(self.save_check)
        backend_layout.addRow(self.stream_debug_check)
        config_buttons = QtWidgets.QWidget()
        config_button_layout = QtWidgets.QHBoxLayout(config_buttons)
        config_button_layout.setContentsMargins(0, 0, 0, 0)
        load_config_button = QtWidgets.QPushButton("Load Config")
        save_config_button = QtWidgets.QPushButton("Save Config")
        load_config_button.clicked.connect(self._load_config_dialog)
        save_config_button.clicked.connect(self._save_config_dialog)
        config_button_layout.addWidget(load_config_button)
        config_button_layout.addWidget(save_config_button)
        backend_layout.addRow(config_buttons)

        self.start_button = QtWidgets.QPushButton("Start")
        self.start_button.clicked.connect(self._toggle_start)
        backend_layout.addRow(self.start_button)
        controls_layout.addWidget(backend_group)

        modulation_group = QtWidgets.QGroupBox("LED Modulation")
        modulation_layout = QtWidgets.QVBoxLayout(modulation_group)
        modulation_layout.addWidget(
            QtWidgets.QLabel("Enable, name, output channel, carrier, offset, and amplitude.")
        )
        for mod in self.config.modulations:
            row = QtWidgets.QWidget()
            row_layout = QtWidgets.QGridLayout(row)
            row_layout.setContentsMargins(0, 0, 0, 0)

            enabled = QtWidgets.QCheckBox(mod.name)
            enabled.setChecked(mod.enabled)
            name_edit = QtWidgets.QLineEdit(mod.name)
            output_edit = QtWidgets.QLineEdit(mod.output)
            frequency = QtWidgets.QDoubleSpinBox()
            frequency.setRange(0.0, 2_000.0)
            frequency.setDecimals(1)
            frequency.setValue(mod.frequency_hz)
            frequency.setSuffix(" Hz")
            offset = QtWidgets.QDoubleSpinBox()
            offset.setRange(0.0, 5.0)
            offset.setDecimals(3)
            offset.setValue(mod.offset_v)
            offset.setSuffix(" V offset")
            amplitude = QtWidgets.QDoubleSpinBox()
            amplitude.setRange(0.0, 2.5)
            amplitude.setDecimals(3)
            amplitude.setValue(mod.amplitude_v)
            amplitude.setSuffix(" V amp")

            row_layout.addWidget(enabled, 0, 0, 1, 2)
            row_layout.addWidget(QtWidgets.QLabel("Name"), 1, 0)
            row_layout.addWidget(name_edit, 1, 1)
            row_layout.addWidget(QtWidgets.QLabel("Output"), 2, 0)
            row_layout.addWidget(output_edit, 2, 1)
            row_layout.addWidget(frequency, 3, 0, 1, 2)
            row_layout.addWidget(offset, 4, 0)
            row_layout.addWidget(amplitude, 4, 1)
            modulation_layout.addWidget(row)
            self.mod_controls.append(
                (enabled, name_edit, output_edit, frequency, offset, amplitude)
            )

        self.waveform_status_label = QtWidgets.QLabel("Actual carriers: --")
        self.waveform_status_label.setWordWrap(True)
        modulation_layout.addWidget(self.waveform_status_label)

        controls_layout.addWidget(modulation_group)

        map_tabs = QtWidgets.QTabWidget()
        map_tabs.addTab(self._build_channel_table("analog"), "Analog In")
        map_tabs.addTab(self._build_channel_table("digital"), "Digital In")
        map_tabs.addTab(self._build_display_order_tab(), "Display Order")
        controls_layout.addWidget(map_tabs, stretch=1)

        layout.addWidget(controls)

        plot_area = QtWidgets.QWidget()
        plot_layout = QtWidgets.QVBoxLayout(plot_area)
        header = QtWidgets.QWidget()
        header_layout = QtWidgets.QHBoxLayout(header)
        header_layout.setContentsMargins(0, 0, 0, 0)
        title = QtWidgets.QLabel("Live Channel Views")
        title.setStyleSheet("font-weight: 600;")
        header_layout.addWidget(title)
        header_layout.addStretch()
        self.sample_count_label = QtWidgets.QLabel("Samples: 0")
        header_layout.addWidget(self.sample_count_label)
        plot_layout.addWidget(header)

        self.chart_container = QtWidgets.QWidget()
        self.chart_layout = QtWidgets.QVBoxLayout(self.chart_container)
        self.chart_layout.setContentsMargins(0, 0, 0, 0)
        self.chart_layout.setSpacing(2)
        self.chart_layout.addStretch()

        self.chart_scroll_area = QtWidgets.QScrollArea()
        self.chart_scroll_area.setWidgetResizable(True)
        self.chart_scroll_area.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)
        self.chart_scroll_area.setHorizontalScrollBarPolicy(
            QtCore.Qt.ScrollBarPolicy.ScrollBarAsNeeded
        )
        self.chart_scroll_area.setVerticalScrollBarPolicy(
            QtCore.Qt.ScrollBarPolicy.ScrollBarAsNeeded
        )
        self.chart_scroll_area.setWidget(self.chart_container)
        self.chart_scroll_area.viewport().installEventFilter(self)
        plot_layout.addWidget(self.chart_scroll_area, stretch=1)
        layout.addWidget(plot_area, stretch=1)

        self.setCentralWidget(central)
        self._rebuild_strip_charts()
        self.statusBar().showMessage("Mock backend connected")

    def eventFilter(self, watched: QtCore.QObject, event: QtCore.QEvent) -> bool:
        if (
            self.chart_scroll_area is not None
            and watched is self.chart_scroll_area.viewport()
            and event.type() == QtCore.QEvent.Type.Resize
        ):
            self._fit_strip_chart_heights()
        return super().eventFilter(watched, event)

    def _build_channel_table(self, kind: str) -> QtWidgets.QWidget:
        container = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(container)
        table = QtWidgets.QTableWidget()
        table.setProperty("kind", kind)
        if kind == "analog":
            table.setColumnCount(5)
            table.setHorizontalHeaderLabels(["On", "Name", "Channel", "Min V", "Max V"])
        else:
            table.setColumnCount(3)
            table.setHorizontalHeaderLabels(["On", "Name", "Channel"])
        table.verticalHeader().setVisible(False)
        table.horizontalHeader().setStretchLastSection(kind == "digital")
        table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        table.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.SingleSelection)
        table.setDragDropMode(QtWidgets.QAbstractItemView.DragDropMode.InternalMove)
        table.setDragDropOverwriteMode(False)
        table.setDefaultDropAction(QtCore.Qt.DropAction.MoveAction)
        table.setAlternatingRowColors(True)
        layout.addWidget(table)

        if kind == "analog":
            self.analog_table = table
            self._populate_channel_table(table, self.config.analog_inputs)
        else:
            self.digital_table = table
            self._populate_channel_table(table, self.config.digital_inputs)

        buttons = QtWidgets.QWidget()
        button_layout = QtWidgets.QHBoxLayout(buttons)
        button_layout.setContentsMargins(0, 0, 0, 0)
        add_button = QtWidgets.QPushButton("Add")
        remove_button = QtWidgets.QPushButton("Remove")
        up_button = QtWidgets.QPushButton("Up")
        down_button = QtWidgets.QPushButton("Down")
        apply_button = QtWidgets.QPushButton("Apply Map")
        add_button.clicked.connect(lambda: self._add_channel_row(table))
        remove_button.clicked.connect(lambda: self._remove_selected_rows(table))
        up_button.clicked.connect(lambda: self._move_selected_row(table, -1))
        down_button.clicked.connect(lambda: self._move_selected_row(table, 1))
        apply_button.clicked.connect(self._apply_channel_map_preview)
        button_layout.addWidget(add_button)
        button_layout.addWidget(remove_button)
        button_layout.addWidget(up_button)
        button_layout.addWidget(down_button)
        button_layout.addStretch()
        button_layout.addWidget(apply_button)
        layout.addWidget(buttons)
        return container

    def _build_display_order_tab(self) -> QtWidgets.QWidget:
        container = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(container)
        self.display_order_list = QtWidgets.QListWidget()
        self.display_order_list.setSelectionMode(
            QtWidgets.QAbstractItemView.SelectionMode.SingleSelection
        )
        self.display_order_list.setDragDropMode(QtWidgets.QAbstractItemView.DragDropMode.InternalMove)
        self.display_order_list.setDefaultDropAction(QtCore.Qt.DropAction.MoveAction)
        layout.addWidget(self.display_order_list)

        buttons = QtWidgets.QWidget()
        button_layout = QtWidgets.QHBoxLayout(buttons)
        button_layout.setContentsMargins(0, 0, 0, 0)
        refresh_button = QtWidgets.QPushButton("Refresh")
        up_button = QtWidgets.QPushButton("Up")
        down_button = QtWidgets.QPushButton("Down")
        apply_button = QtWidgets.QPushButton("Apply")
        refresh_button.clicked.connect(self._refresh_display_order_from_tables)
        up_button.clicked.connect(lambda: self._move_selected_display_order_row(-1))
        down_button.clicked.connect(lambda: self._move_selected_display_order_row(1))
        apply_button.clicked.connect(self._apply_channel_map_preview)
        button_layout.addWidget(refresh_button)
        button_layout.addWidget(up_button)
        button_layout.addWidget(down_button)
        button_layout.addStretch()
        button_layout.addWidget(apply_button)
        layout.addWidget(buttons)

        self._refresh_display_order_from_tables()
        return container

    def _populate_channel_table(
        self,
        table: QtWidgets.QTableWidget,
        channels: tuple[AnalogInputChannel, ...] | tuple[DigitalInputChannel, ...],
    ) -> None:
        table.setRowCount(0)
        for channel in channels:
            self._add_channel_row(
                table,
                channel.name,
                channel.channel,
                channel.enabled,
                getattr(channel, "display_min_v", -0.25),
                getattr(channel, "display_max_v", 5.25),
            )
        table.resizeColumnsToContents()

    def _add_channel_row(
        self,
        table: QtWidgets.QTableWidget,
        name: str = "",
        channel: str = "",
        enabled: bool = True,
        min_v: float = -0.25,
        max_v: float = 5.25,
    ) -> None:
        row = table.rowCount()
        table.insertRow(row)
        self._set_row_values(table, row, enabled, name, channel, min_v, max_v)

    def _remove_selected_rows(self, table: QtWidgets.QTableWidget) -> None:
        rows = sorted({index.row() for index in table.selectedIndexes()}, reverse=True)
        for row in rows:
            table.removeRow(row)

    def _move_selected_row(self, table: QtWidgets.QTableWidget, offset: int) -> None:
        selected_rows = sorted({index.row() for index in table.selectedIndexes()})
        if len(selected_rows) != 1:
            return
        source_row = selected_rows[0]
        target_row = source_row + offset
        if target_row < 0 or target_row >= table.rowCount():
            return

        row_values = self._row_values(table, source_row)
        table.removeRow(source_row)
        table.insertRow(target_row)
        self._set_row_values(table, target_row, *row_values)
        table.selectRow(target_row)

    def _row_values(
        self,
        table: QtWidgets.QTableWidget,
        row: int,
    ) -> tuple[bool, str, str, float, float]:
        enabled_item = table.item(row, 0)
        name_item = table.item(row, 1)
        channel_item = table.item(row, 2)
        enabled = enabled_item.checkState() == QtCore.Qt.CheckState.Checked
        name = name_item.text() if name_item is not None else ""
        channel = channel_item.text() if channel_item is not None else ""
        min_v = self._table_float(table, row, 3, -0.25)
        max_v = self._table_float(table, row, 4, 5.25)
        return enabled, name, channel, min_v, max_v

    def _set_row_values(
        self,
        table: QtWidgets.QTableWidget,
        row: int,
        enabled: bool,
        name: str,
        channel: str,
        min_v: float = -0.25,
        max_v: float = 5.25,
    ) -> None:
        enabled_item = QtWidgets.QTableWidgetItem()
        enabled_item.setFlags(
            QtCore.Qt.ItemFlag.ItemIsUserCheckable
            | QtCore.Qt.ItemFlag.ItemIsEnabled
            | QtCore.Qt.ItemFlag.ItemIsSelectable
        )
        enabled_item.setCheckState(
            QtCore.Qt.CheckState.Checked if enabled else QtCore.Qt.CheckState.Unchecked
        )
        table.setItem(row, 0, enabled_item)
        table.setItem(row, 1, QtWidgets.QTableWidgetItem(name))
        table.setItem(row, 2, QtWidgets.QTableWidgetItem(channel))
        if table.columnCount() >= 5:
            table.setItem(row, 3, QtWidgets.QTableWidgetItem(f"{min_v:g}"))
            table.setItem(row, 4, QtWidgets.QTableWidgetItem(f"{max_v:g}"))

    def _apply_channel_map_preview(self) -> None:
        try:
            self.config = self._config_from_controls()
        except ValueError as exc:
            QtWidgets.QMessageBox.warning(self, "Invalid channel map", str(exc))
            return
        self._rebuild_strip_charts()
        self.statusBar().showMessage("Applied channel map")

    def _refresh_display_order_from_tables(self) -> None:
        existing_order = self._display_order_keys_from_list()
        current_keys = self._display_keys_from_tables()
        ordered = [key for key in existing_order if key in current_keys]
        ordered.extend(key for key in current_keys if key not in ordered)
        self._set_display_order_list(ordered)

    def _display_keys_from_tables(self) -> list[str]:
        keys = []
        if hasattr(self, "analog_table"):
            keys.extend(
                f"ai:{name}"
                for enabled, name, _channel, _min_v, _max_v in self._analog_table_rows()
                if enabled
            )
        if hasattr(self, "digital_table"):
            keys.extend(
                f"di:{name}"
                for enabled, name, _channel in self._digital_table_rows()
                if enabled
            )
        return keys

    def _display_order_keys_from_list(self) -> list[str]:
        keys = []
        if not hasattr(self, "display_order_list"):
            return keys
        for row in range(self.display_order_list.count()):
            item = self.display_order_list.item(row)
            key = item.data(QtCore.Qt.ItemDataRole.UserRole)
            if isinstance(key, str):
                keys.append(key)
        return keys

    def _set_display_order_list(self, keys: list[str]) -> None:
        if not hasattr(self, "display_order_list"):
            self.display_order = keys
            return
        self.display_order_list.clear()
        for key in keys:
            item = QtWidgets.QListWidgetItem(_display_key_label(key))
            item.setData(QtCore.Qt.ItemDataRole.UserRole, key)
            self.display_order_list.addItem(item)
        self.display_order = keys

    def _move_selected_display_order_row(self, offset: int) -> None:
        row = self.display_order_list.currentRow()
        target = row + offset
        if row < 0 or target < 0 or target >= self.display_order_list.count():
            return
        item = self.display_order_list.takeItem(row)
        self.display_order_list.insertItem(target, item)
        self.display_order_list.setCurrentRow(target)

    def _config_from_controls(self) -> RigConfig:
        mods = []
        for base, controls in zip(self.config.modulations, self.mod_controls, strict=True):
            enabled, name_edit, output_edit, frequency, offset, amplitude = controls
            name = name_edit.text().strip()
            output = output_edit.text().strip().upper()
            if not name:
                raise ValueError("Every modulation output needs a name.")
            if not output:
                raise ValueError("Every enabled modulation output needs a LabJack output channel.")
            mods.append(
                ModulationChannel(
                    name=name,
                    output=output,
                    frequency_hz=frequency.value(),
                    offset_v=offset.value(),
                    amplitude_v=amplitude.value(),
                    enabled=enabled.isChecked(),
                )
            )
        analog_inputs = tuple(
            AnalogInputChannel(
                name=name,
                channel=channel,
                enabled=enabled,
                display_min_v=min_v,
                display_max_v=max_v,
            )
            for enabled, name, channel, min_v, max_v in self._analog_table_rows()
        )
        digital_inputs = tuple(
            DigitalInputChannel(name=name, channel=channel, enabled=enabled)
            for enabled, name, channel in self._digital_table_rows()
        )
        _validate_unique_enabled_names(analog_inputs, digital_inputs)
        current_keys = _display_keys_from_config(analog_inputs, digital_inputs)
        requested_order = [
            key
            for key in self._display_order_keys_from_list()
            if key in current_keys
        ]
        requested_order.extend(key for key in current_keys if key not in requested_order)
        self.display_order = requested_order

        return RigConfig(
            sample_rate_hz=self.sample_rate_spin.value(),
            ain_settling_us=self.ain_settling_spin.value(),
            stream_out_scan_mode=str(self.stream_out_mode_combo.currentData()),
            labjack_stream_debug=self.stream_debug_check.isChecked(),
            backend=BackendKind(self.backend_combo.currentText()),
            modulations=tuple(mods),
            analog_inputs=analog_inputs,
            digital_inputs=digital_inputs,
        )

    def _analog_table_rows(self) -> list[tuple[bool, str, str, float, float]]:
        rows = []
        for enabled, name, channel, min_v, max_v in self._table_rows(self.analog_table):
            if enabled and min_v >= max_v:
                raise ValueError(f"Analog input '{name}' needs Min V lower than Max V.")
            rows.append((enabled, name, channel, min_v, max_v))
        return rows

    def _digital_table_rows(self) -> list[tuple[bool, str, str]]:
        return [
            (enabled, name, channel)
            for enabled, name, channel, _min_v, _max_v in self._table_rows(self.digital_table)
        ]

    def _table_rows(
        self,
        table: QtWidgets.QTableWidget,
    ) -> list[tuple[bool, str, str, float, float]]:
        rows = []
        for row in range(table.rowCount()):
            enabled_item = table.item(row, 0)
            name_item = table.item(row, 1)
            channel_item = table.item(row, 2)
            enabled = enabled_item.checkState() == QtCore.Qt.CheckState.Checked
            name = name_item.text().strip() if name_item is not None else ""
            channel = channel_item.text().strip().upper() if channel_item is not None else ""
            if not name and not channel:
                continue
            if enabled and (not name or not channel):
                raise ValueError("Every enabled input row needs both a name and a channel.")
            min_v = self._table_float(table, row, 3, -0.25)
            max_v = self._table_float(table, row, 4, 5.25)
            rows.append((enabled, name, channel, min_v, max_v))
        return rows

    def _table_float(
        self,
        table: QtWidgets.QTableWidget,
        row: int,
        column: int,
        default: float,
    ) -> float:
        item = table.item(row, column)
        if item is None or not item.text().strip():
            return default
        try:
            return float(item.text())
        except ValueError as exc:
            name_item = table.item(row, 1)
            name = name_item.text().strip() if name_item is not None else f"row {row + 1}"
            raise ValueError(f"Invalid numeric display range for '{name}'.") from exc

    def _toggle_start(self) -> None:
        if self.timer.isActive():
            self._stop_recording()
            self.start_button.setText("Start")
            self.statusBar().showMessage("Stopped")
            return

        self.config = self._config_from_controls()
        self._coerce_stream_out_mode_for_modulation()
        try:
            self._start_recording()
        except Exception as exc:
            QtWidgets.QMessageBox.critical(self, "Start failed", str(exc))
            self._stop_recording()

    def _start_recording(self) -> None:
        self.backend = self._make_backend(self.config.backend)
        self.backend.configure(self.config)
        self.backend.connect()

        self._rebuild_strip_charts()
        self.sample_count_label.setText("Samples: 0")
        self._pending_plot_blocks.clear()
        self._last_plot_update = 0.0

        self.backend.start()
        runtime_metadata = {
            "actual_sample_rate_hz": getattr(
                self.backend,
                "actual_scan_rate_hz",
                self.config.sample_rate_hz,
            ),
            "waveforms": getattr(self.backend, "waveform_info", []),
            "stream_debug_log_path": getattr(self.backend, "debug_log_path", None),
            "stream_out_scan_mode": self.config.stream_out_scan_mode,
        }
        self._update_waveform_status(runtime_metadata["waveforms"])

        if self.save_check.isChecked():
            session_name = _timestamped_session_name(
                self.session_name_edit.text().strip() or "photometry"
            )
            session = SessionConfig(
                output_dir=Path(self.output_dir_edit.text()),
                session_name=session_name,
                save_h5=True,
            )
            self.recorder = H5Recorder(session, self.config, runtime_metadata=runtime_metadata)
            self.recorder.open()
        else:
            self.recorder = None

        self.timer.start()
        self.start_button.setText("Stop")
        self.statusBar().showMessage(
            f"Recording {self.config.backend.value} to {self.recorder.path.name if self.recorder else 'memory'} "
            f"at {runtime_metadata['actual_sample_rate_hz']:.1f} Hz"
        )

    def _stop_recording(self) -> None:
        self.timer.stop()
        self._pending_plot_blocks.clear()
        try:
            self.backend.stop()
        finally:
            self.backend.disconnect()
        if self.recorder is not None:
            self.recorder.close()
            self.recorder = None

    def _coerce_stream_out_mode_for_modulation(self) -> None:
        has_periodic_output = any(
            mod.enabled and mod.output.upper() in {"DAC0", "DAC1"} and mod.frequency_hz > 0.0
            for mod in self.config.modulations
        )
        if has_periodic_output and self.config.stream_out_scan_mode == "inputs_only":
            mode_index = self.stream_out_mode_combo.findData("trailing")
            self.stream_out_mode_combo.setCurrentIndex(max(0, mode_index))
            self.config = self._config_from_controls()
            self.statusBar().showMessage(
                "Switched stream-out mode to Trailing so DAC waveforms are clocked."
            )

    def _update_waveform_status(self, waveforms: object) -> None:
        if not hasattr(self, "waveform_status_label"):
            return
        if not isinstance(waveforms, list) or not waveforms:
            self.waveform_status_label.setText("Actual carriers: none")
            return

        parts = []
        warnings = []
        for waveform in waveforms:
            if not isinstance(waveform, dict):
                continue
            name = waveform.get("name", "carrier")
            output = waveform.get("output", "")
            requested = float(waveform.get("requested_frequency_hz", 0.0))
            actual = float(waveform.get("actual_frequency_hz", 0.0))
            parts.append(f"{name} {output}: {actual:.3f} Hz")
            if requested > 0 and abs(actual - requested) / requested > 0.01:
                warnings.append(f"{name} requested {requested:.3f} Hz")
        suffix = ""
        if warnings:
            suffix = " (quantized; " + "; ".join(warnings) + ")"
        self.waveform_status_label.setText("Actual carriers: " + ", ".join(parts) + suffix)

    def _make_backend(self, backend_kind: BackendKind) -> PhotometryBackend:
        if backend_kind == BackendKind.LABJACK_T7:
            return LabJackT7Backend()
        return MockBackend()

    def _browse_output_dir(self) -> None:
        directory = QtWidgets.QFileDialog.getExistingDirectory(
            self,
            "Select output folder",
            self.output_dir_edit.text(),
        )
        if directory:
            self.output_dir_edit.setText(directory)

    def _save_config_dialog(self) -> None:
        try:
            config = self._config_from_controls()
        except ValueError as exc:
            QtWidgets.QMessageBox.warning(self, "Invalid config", str(exc))
            return

        default_path = Path(self.output_dir_edit.text()) / "labjack_photometry_config.json"
        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self,
            "Save config",
            str(default_path),
            "JSON config (*.json)",
        )
        if not path:
            return

        save_gui_config(
            path,
            config,
            {
                "display_seconds": self.display_seconds_spin.value(),
                "output_dir": self.output_dir_edit.text(),
                "save_h5": self.save_check.isChecked(),
                "display_order": self._display_order_keys_from_list(),
            },
        )
        self.statusBar().showMessage(f"Saved config: {path}")

    def _load_config_dialog(self) -> None:
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self,
            "Load config",
            self.output_dir_edit.text(),
            "JSON config (*.json)",
        )
        if not path:
            return

        try:
            config, ui = load_gui_config(path)
        except Exception as exc:
            QtWidgets.QMessageBox.critical(self, "Load failed", str(exc))
            return

        self._load_config_into_controls(config, ui)
        self.statusBar().showMessage(f"Loaded config: {path}")

    def _load_config_into_controls(self, config: RigConfig, ui: dict[str, object]) -> None:
        self.config = config
        self.backend_combo.setCurrentText(config.backend.value)
        self.sample_rate_spin.setValue(config.sample_rate_hz)
        self.ain_settling_spin.setValue(config.ain_settling_us)
        mode_index = self.stream_out_mode_combo.findData(config.stream_out_scan_mode)
        self.stream_out_mode_combo.setCurrentIndex(max(0, mode_index))
        self.stream_debug_check.setChecked(config.labjack_stream_debug)
        self.display_seconds_spin.setValue(float(ui.get("display_seconds", 20.0)))
        self.output_dir_edit.setText(str(ui.get("output_dir", Path.cwd() / "data")))
        self.save_check.setChecked(bool(ui.get("save_h5", True)))

        for index, controls in enumerate(self.mod_controls):
            enabled, name_edit, output_edit, frequency, offset, amplitude = controls
            if index >= len(config.modulations):
                enabled.setChecked(False)
                continue
            modulation = config.modulations[index]
            enabled.setChecked(modulation.enabled)
            enabled.setText(modulation.name)
            name_edit.setText(modulation.name)
            output_edit.setText(modulation.output)
            frequency.setValue(modulation.frequency_hz)
            offset.setValue(modulation.offset_v)
            amplitude.setValue(modulation.amplitude_v)

        self._populate_channel_table(self.analog_table, config.analog_inputs)
        self._populate_channel_table(self.digital_table, config.digital_inputs)
        display_order = ui.get("display_order", [])
        if not isinstance(display_order, list):
            display_order = []
        current_keys = _display_keys_from_config(config.analog_inputs, config.digital_inputs)
        ordered = [key for key in display_order if isinstance(key, str) and key in current_keys]
        ordered.extend(key for key in current_keys if key not in ordered)
        self._set_display_order_list(ordered)
        self._rebuild_strip_charts()

    def _rebuild_strip_charts(self) -> None:
        while self.chart_layout.count() > 0:
            item = self.chart_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

        self.strip_charts.clear()
        color_index = 0
        analog_by_key = {
            f"ai:{channel.name}": channel
            for channel in self.config.analog_inputs
            if channel.enabled
        }
        digital_by_key = {
            f"di:{channel.name}": channel
            for channel in self.config.digital_inputs
            if channel.enabled
        }
        current_keys = [*analog_by_key, *digital_by_key]
        order = [key for key in self.display_order if key in current_keys]
        order.extend(key for key in current_keys if key not in order)
        self.display_order = order
        self._set_display_order_list(order)

        for key in order:
            is_digital = key.startswith("di:")
            channel = digital_by_key[key] if is_digital else analog_by_key[key]
            chart = SignalStripChart(
                name=channel.name,
                channel=channel.channel,
                color=pg.intColor(color_index).name(),
                is_digital=is_digital,
                y_min=-0.2 if is_digital else channel.display_min_v,
                y_max=1.2 if is_digital else channel.display_max_v,
                suppress_short_low_glitches=(
                    not is_digital and "lick" in channel.name.lower()
                ),
            )
            self.strip_charts[channel.name] = chart
            self.chart_layout.addWidget(chart)
            color_index += 1

        self.chart_layout.addStretch()
        self._fit_strip_chart_heights()

    def _fit_strip_chart_heights(self) -> None:
        if self.chart_scroll_area is None or not self.strip_charts:
            return

        viewport_height = self.chart_scroll_area.viewport().height()
        scrollbar_allowance = 20
        available_height = max(120, viewport_height - scrollbar_allowance)
        channel_count = len(self.strip_charts)
        spacing = max(0, self.chart_layout.spacing()) * max(0, channel_count - 1)
        row_height = int((available_height - spacing) / max(1, channel_count))
        row_height = max(34, min(86, row_height))
        for chart in self.strip_charts.values():
            chart.set_row_height(row_height)

    def _poll_backend(self) -> None:
        try:
            block = self.backend.read()
        except Exception as exc:
            self._stop_recording()
            self.start_button.setText("Start")
            self.statusBar().showMessage("Stopped after acquisition error")
            QtWidgets.QMessageBox.critical(self, "Acquisition stopped", str(exc))
            return
        if block.t_seconds.size == 0:
            return
        if self.recorder is not None:
            self.recorder.append(block)

        self._pending_plot_blocks.append(block)
        now = time.perf_counter()
        if now - self._last_plot_update < self._plot_interval_s:
            self.sample_count_label.setText(
                f"Samples: {int(block.t_seconds[-1] * self.config.sample_rate_hz):,}"
            )
            return
        plot_block = _combine_plot_blocks(self._pending_plot_blocks)
        self._pending_plot_blocks.clear()
        self._last_plot_update = now

        display_seconds = self.display_seconds_spin.value()
        for name, values in plot_block.analog.items():
            if name in self.strip_charts:
                self.strip_charts[name].push(
                    plot_block.t_seconds,
                    values,
                    display_seconds,
                )
        for name, values in plot_block.digital.items():
            if name in self.strip_charts:
                self.strip_charts[name].push(plot_block.t_seconds, values, display_seconds)
        self.sample_count_label.setText(
            f"Samples: {int(plot_block.t_seconds[-1] * self.config.sample_rate_hz):,}"
        )


def main() -> int:
    app = QtWidgets.QApplication(sys.argv)
    pg.setConfigOptions(antialias=True)
    window = MainWindow()
    window.show()
    return app.exec()


def _validate_unique_enabled_names(
    analog_inputs: tuple[AnalogInputChannel, ...],
    digital_inputs: tuple[DigitalInputChannel, ...],
) -> None:
    names = [
        channel.name
        for channel in (*analog_inputs, *digital_inputs)
        if channel.enabled
    ]
    duplicates = sorted({name for name in names if names.count(name) > 1})
    if duplicates:
        raise ValueError(f"Enabled channel names must be unique: {', '.join(duplicates)}")


def _timestamped_session_name(prefix: str) -> str:
    safe_prefix = _safe_filename_prefix(prefix) or "photometry"
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"{safe_prefix}_{timestamp}"


def _safe_filename_prefix(prefix: str) -> str:
    safe = "".join(char if char.isalnum() or char in ("-", "_") else "_" for char in prefix)
    safe = "_".join(part for part in safe.split("_") if part)
    return safe.strip("._-")


def _display_keys_from_config(
    analog_inputs: tuple[AnalogInputChannel, ...],
    digital_inputs: tuple[DigitalInputChannel, ...],
) -> list[str]:
    return [
        *(f"ai:{channel.name}" for channel in analog_inputs if channel.enabled),
        *(f"di:{channel.name}" for channel in digital_inputs if channel.enabled),
    ]


def _display_key_label(key: str) -> str:
    prefix, _, name = key.partition(":")
    label = "AI" if prefix == "ai" else "DI" if prefix == "di" else prefix.upper()
    return f"{label}: {name}"


def _decimate_for_display(
    x: np.ndarray,
    y: np.ndarray,
    max_display_points: int,
    is_digital: bool,
) -> tuple[np.ndarray, np.ndarray]:
    if is_digital:
        return _digital_trace_for_display(x, y, max_display_points)

    if x.size <= max_display_points:
        return x, y

    # Preserve envelope shape by plotting min and max from each display bin.
    bins = max(1, max_display_points // 2)
    edges = np.linspace(0, x.size, bins + 1, dtype=int)
    x_out: list[float] = []
    y_out: list[float] = []
    for start, stop in zip(edges[:-1], edges[1:]):
        if stop <= start:
            continue
        segment = y[start:stop]
        x_segment = x[start:stop]
        min_index = int(np.argmin(segment))
        max_index = int(np.argmax(segment))
        for index in sorted((min_index, max_index)):
            x_out.append(float(x_segment[index]))
            y_out.append(float(segment[index]))
    return np.asarray(x_out, dtype=float), np.asarray(y_out, dtype=float)


def _digital_trace_for_display(
    x: np.ndarray,
    y: np.ndarray,
    max_display_points: int,
) -> tuple[np.ndarray, np.ndarray]:
    digital = (y >= 0.5).astype(float)
    digital = _suppress_short_low_digital_glitches(x, digital)
    if x.size <= 1:
        return x, digital

    change_indices = np.flatnonzero(np.diff(digital) != 0) + 1
    keep: set[int] = {0, x.size - 1}
    for index in change_indices:
        keep.add(max(0, int(index) - 1))
        keep.add(int(index))

    if len(keep) <= max_display_points:
        indices = np.asarray(sorted(keep), dtype=int)
        return x[indices], digital[indices]

    # If transitions are very dense, draw the majority state per display bin.
    # This keeps state-like digital lines readable instead of turning brief
    # dropouts in an otherwise-high signal into a comb of high/low transitions.
    bins = max(1, max_display_points // 2)
    edges = np.linspace(0, x.size, bins + 1, dtype=int)
    x_out: list[float] = []
    y_out: list[float] = []
    for start, stop in zip(edges[:-1], edges[1:]):
        if stop <= start:
            continue
        segment = digital[start:stop]
        left_x = float(x[start])
        right_x = float(x[stop - 1])
        state = float(np.mean(segment) >= 0.5)
        x_out.append(left_x)
        y_out.append(state)
        x_out.append(right_x)
        y_out.append(state)
    return np.asarray(x_out, dtype=float), np.asarray(y_out, dtype=float)


def _suppress_short_low_digital_glitches(
    x: np.ndarray,
    digital: np.ndarray,
    max_width_s: float = 0.003,
) -> np.ndarray:
    if digital.size < 3:
        return digital

    sample_period = float(np.median(np.diff(x))) if x.size > 1 else 0.0
    if sample_period <= 0.0:
        return digital
    max_samples = max(1, int(np.ceil(max_width_s / sample_period)))

    cleaned = digital.copy()
    start = 0
    while start < cleaned.size:
        stop = start + 1
        while stop < cleaned.size and cleaned[stop] == cleaned[start]:
            stop += 1
        run_is_low = cleaned[start] < 0.5
        surrounded_by_high = (
            start > 0
            and stop < cleaned.size
            and cleaned[start - 1] >= 0.5
            and cleaned[stop] >= 0.5
        )
        if run_is_low and surrounded_by_high and stop - start <= max_samples:
            cleaned[start:stop] = 1.0
        start = stop
    return cleaned


def _analog_lick_trace_for_display(
    x: np.ndarray,
    values: np.ndarray,
    min_low_width_s: float = 0.008,
) -> np.ndarray:
    if values.size < 3:
        return values

    sample_period = float(np.median(np.diff(x))) if x.size > 1 else 0.0
    if sample_period <= 0.0:
        return values

    low_level = float(np.nanpercentile(values, 10))
    high_level = float(np.nanpercentile(values, 90))
    if not np.isfinite(low_level) or not np.isfinite(high_level):
        return values
    if high_level - low_level < 0.5:
        return values

    threshold = low_level + 0.5 * (high_level - low_level)
    high_state = values >= threshold
    min_low_samples = max(1, int(np.ceil(min_low_width_s / sample_period)))
    cleaned_state = high_state.copy()

    start = 0
    while start < cleaned_state.size:
        stop = start + 1
        while stop < cleaned_state.size and cleaned_state[stop] == cleaned_state[start]:
            stop += 1
        run_is_low = not bool(cleaned_state[start])
        surrounded_by_high = (
            start > 0
            and stop < cleaned_state.size
            and bool(cleaned_state[start - 1])
            and bool(cleaned_state[stop])
        )
        if run_is_low and surrounded_by_high and stop - start < min_low_samples:
            cleaned_state[start:stop] = True
        start = stop
    return np.where(cleaned_state, high_level, low_level)


def _combine_plot_blocks(blocks: list[AcquisitionBlock]) -> AcquisitionBlock:
    if not blocks:
        return AcquisitionBlock(np.array([]), {}, {})
    if len(blocks) == 1:
        return blocks[0]
    analog_names = list(blocks[0].analog)
    digital_names = list(blocks[0].digital)
    return AcquisitionBlock(
        t_seconds=np.concatenate([block.t_seconds for block in blocks]),
        analog={
            name: np.concatenate([block.analog[name] for block in blocks if name in block.analog])
            for name in analog_names
        },
        digital={
            name: np.concatenate([block.digital[name] for block in blocks if name in block.digital])
            for name in digital_names
        },
    )
