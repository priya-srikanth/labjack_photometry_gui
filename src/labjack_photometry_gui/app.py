from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

import numpy as np
from PySide6 import QtCore, QtWidgets
import pyqtgraph as pg

from labjack_photometry_gui.config_file import load_gui_config, save_gui_config
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
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.name = name
        self.channel = channel
        self.is_digital = is_digital
        self.x_values: list[float] = []
        self.y_values: list[float] = []
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
        self.x_values.clear()
        self.y_values.clear()
        self.curve.setData([], [])
        self.value_label.setText("--")

    def push(self, t_seconds: np.ndarray, values: np.ndarray, display_seconds: float) -> None:
        if t_seconds.size == 0 or values.size == 0:
            return

        if self.is_digital:
            values = (values >= 0.5).astype(float)
        else:
            values = values.astype(float)

        self.x_values.extend(t_seconds.tolist())
        self.y_values.extend(values.tolist())

        cutoff = float(t_seconds[-1] - display_seconds)
        while self.x_values and self.x_values[0] < cutoff:
            self.x_values.pop(0)
            self.y_values.pop(0)

        x = np.asarray(self.x_values, dtype=float)
        y = np.asarray(self.y_values, dtype=float)
        if x.size == 0:
            return

        relative_x = x - x[-1]
        self.curve.setData(relative_x, y)
        self.plot.setXRange(-display_seconds, 0.0, padding=0)
        if not self.is_digital and y.size:
            y_min = float(np.nanmin(y))
            y_max = float(np.nanmax(y))
            if y_min == y_max:
                y_min -= 0.5
                y_max += 0.5
            span = y_max - y_min
            self.plot.setYRange(y_min - 0.08 * span, y_max + 0.08 * span, padding=0)

        if self.is_digital:
            self.value_label.setText(str(int(round(float(y[-1])))))
        else:
            self.value_label.setText(f"{float(y[-1]):.3f}")


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
        self.display_seconds_spin = QtWidgets.QDoubleSpinBox()
        self.display_seconds_spin.setRange(1.0, 300.0)
        self.display_seconds_spin.setDecimals(0)
        self.display_seconds_spin.setValue(20.0)
        self.display_seconds_spin.setSuffix(" s")
        self.save_check = QtWidgets.QCheckBox("Save HDF5")
        self.save_check.setChecked(True)
        self.session_name_edit = QtWidgets.QLineEdit(
            f"photometry_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        )
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
        backend_layout.addRow("Display", self.display_seconds_spin)
        backend_layout.addRow("Session", self.session_name_edit)
        backend_layout.addRow("Output", output_row)
        backend_layout.addRow(self.save_check)
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
            frequency.setRange(1.0, 2_000.0)
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

        controls_layout.addWidget(modulation_group)

        map_tabs = QtWidgets.QTabWidget()
        map_tabs.addTab(self._build_channel_table("analog"), "Analog In")
        map_tabs.addTab(self._build_channel_table("digital"), "Digital In")
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
        table.setColumnCount(3)
        table.setHorizontalHeaderLabels(["On", "Name", "Channel"])
        table.verticalHeader().setVisible(False)
        table.horizontalHeader().setStretchLastSection(True)
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

    def _populate_channel_table(
        self,
        table: QtWidgets.QTableWidget,
        channels: tuple[AnalogInputChannel, ...] | tuple[DigitalInputChannel, ...],
    ) -> None:
        table.setRowCount(0)
        for channel in channels:
            self._add_channel_row(table, channel.name, channel.channel, channel.enabled)
        table.resizeColumnsToContents()

    def _add_channel_row(
        self,
        table: QtWidgets.QTableWidget,
        name: str = "",
        channel: str = "",
        enabled: bool = True,
    ) -> None:
        row = table.rowCount()
        table.insertRow(row)
        self._set_row_values(table, row, enabled, name, channel)

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

    def _row_values(self, table: QtWidgets.QTableWidget, row: int) -> tuple[bool, str, str]:
        enabled_item = table.item(row, 0)
        name_item = table.item(row, 1)
        channel_item = table.item(row, 2)
        enabled = enabled_item.checkState() == QtCore.Qt.CheckState.Checked
        name = name_item.text() if name_item is not None else ""
        channel = channel_item.text() if channel_item is not None else ""
        return enabled, name, channel

    def _set_row_values(
        self,
        table: QtWidgets.QTableWidget,
        row: int,
        enabled: bool,
        name: str,
        channel: str,
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

    def _apply_channel_map_preview(self) -> None:
        try:
            self.config = self._config_from_controls()
        except ValueError as exc:
            QtWidgets.QMessageBox.warning(self, "Invalid channel map", str(exc))
            return
        self._rebuild_strip_charts()
        self.statusBar().showMessage("Applied channel map")

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
            AnalogInputChannel(name=name, channel=channel, enabled=enabled)
            for enabled, name, channel in self._table_rows(self.analog_table)
        )
        digital_inputs = tuple(
            DigitalInputChannel(name=name, channel=channel, enabled=enabled)
            for enabled, name, channel in self._table_rows(self.digital_table)
        )
        _validate_unique_enabled_names(analog_inputs, digital_inputs)

        return RigConfig(
            sample_rate_hz=self.sample_rate_spin.value(),
            backend=BackendKind(self.backend_combo.currentText()),
            modulations=tuple(mods),
            analog_inputs=analog_inputs,
            digital_inputs=digital_inputs,
        )

    def _table_rows(self, table: QtWidgets.QTableWidget) -> list[tuple[bool, str, str]]:
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
            rows.append((enabled, name, channel))
        return rows

    def _toggle_start(self) -> None:
        if self.timer.isActive():
            self._stop_recording()
            self.start_button.setText("Start")
            self.statusBar().showMessage("Stopped")
            return

        self.config = self._config_from_controls()
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

        self.backend.start()
        runtime_metadata = {
            "actual_sample_rate_hz": getattr(
                self.backend,
                "actual_scan_rate_hz",
                self.config.sample_rate_hz,
            ),
            "waveforms": getattr(self.backend, "waveform_info", []),
        }

        if self.save_check.isChecked():
            session = SessionConfig(
                output_dir=Path(self.output_dir_edit.text()),
                session_name=self.session_name_edit.text().strip() or "photometry_session",
                save_h5=True,
            )
            self.recorder = H5Recorder(session, self.config, runtime_metadata=runtime_metadata)
            self.recorder.open()
        else:
            self.recorder = None

        self.timer.start()
        self.start_button.setText("Stop")
        self.statusBar().showMessage(
            f"Recording {self.config.backend.value} at {runtime_metadata['actual_sample_rate_hz']:.1f} Hz"
        )

    def _stop_recording(self) -> None:
        self.timer.stop()
        try:
            self.backend.stop()
        finally:
            self.backend.disconnect()
        if self.recorder is not None:
            self.recorder.close()
            self.recorder = None

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
                "session_name": self.session_name_edit.text(),
                "save_h5": self.save_check.isChecked(),
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
        self.display_seconds_spin.setValue(float(ui.get("display_seconds", 20.0)))
        self.output_dir_edit.setText(str(ui.get("output_dir", Path.cwd() / "data")))
        self.session_name_edit.setText(
            str(ui.get("session_name", f"photometry_{datetime.now().strftime('%Y%m%d_%H%M%S')}"))
        )
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
        self._rebuild_strip_charts()

    def _rebuild_strip_charts(self) -> None:
        while self.chart_layout.count() > 0:
            item = self.chart_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

        self.strip_charts.clear()
        color_index = 0
        for channel in self.config.analog_inputs:
            if not channel.enabled:
                continue
            chart = SignalStripChart(
                name=channel.name,
                channel=channel.channel,
                color=pg.intColor(color_index).name(),
                is_digital=False,
            )
            self.strip_charts[channel.name] = chart
            self.chart_layout.addWidget(chart)
            color_index += 1

        for channel in self.config.digital_inputs:
            if not channel.enabled:
                continue
            chart = SignalStripChart(
                name=channel.name,
                channel=channel.channel,
                color=pg.intColor(color_index).name(),
                is_digital=True,
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
        block = self.backend.read()
        if block.t_seconds.size == 0:
            return
        if self.recorder is not None:
            self.recorder.append(block)

        display_seconds = self.display_seconds_spin.value()
        for name, values in block.analog.items():
            if name in self.strip_charts:
                self.strip_charts[name].push(block.t_seconds, values, display_seconds)
        for name, values in block.digital.items():
            if name in self.strip_charts:
                self.strip_charts[name].push(block.t_seconds, values, display_seconds)
        self.sample_count_label.setText(f"Samples: {int(block.t_seconds[-1] * self.config.sample_rate_hz):,}")


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
