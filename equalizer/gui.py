"""PyQt6 dark-mode GUI for MetalEQ."""
from PyQt6.QtCore import QPointF, Qt, QTimer
from PyQt6.QtGui import (
    QAction,
    QColor,
    QKeySequence,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
)
from PyQt6.QtWidgets import (
    QComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QSlider,
    QSystemTrayIcon,
    QVBoxLayout,
    QWidget,
)

from . import presets as preset_store
from .icon import load_app_icon
from .theme import ACCENT, BORDER
from .audio_engine import (
    BAND_LABELS,
    BAND_MAX_DB,
    BAND_MIN_DB,
    BAND_Q_DEFAULT,
    BAND_Q_MAX,
    BAND_Q_MIN,
    BASS_BOOST_OFFSETS,
    PREAMP_MAX_DB,
    PREAMP_MIN_DB,
    AudioEngine,
    AudioEngineError,
)

CUSTOM_LABEL = "Custom"
FLAT_LABEL = "Flat"
BAND_GRID_COLUMNS = 10
COLUMN_WIDTH = 58


def _format_db(value):
    return f"{value:+.1f}"


def _format_percent(value):
    return f"{int(round(value))}%"


class GainSlider(QWidget):
    """A slider + labels representing one EQ band, the preamp, or an
    effect intensity (0-100%)."""

    def __init__(
        self,
        label,
        min_value,
        max_value,
        on_change,
        orientation="vertical",
        scale=10,
        fmt=_format_db,
        parent=None,
    ):
        super().__init__(parent)
        self._on_change = on_change
        self._suppress = False
        self.orientation = orientation
        self.scale = scale
        self.fmt = fmt

        if orientation == "vertical":
            self._build_vertical(label, min_value, max_value)
        else:
            self._build_horizontal(label, min_value, max_value)

    def _build_vertical(self, label, min_value, max_value):
        self.setFixedWidth(COLUMN_WIDTH)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(2, 2, 2, 2)
        layout.setSpacing(4)

        self.gain_label = QLabel(self.fmt(0))
        self.gain_label.setObjectName("bandGain")
        self.gain_label.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        layout.addWidget(self.gain_label)

        self.slider = QSlider(Qt.Orientation.Vertical)
        self.slider.setMinimum(int(min_value * self.scale))
        self.slider.setMaximum(int(max_value * self.scale))
        self.slider.setValue(0)
        self.slider.setMinimumHeight(240)
        self.slider.setSizePolicy(
            QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding
        )
        self.slider.valueChanged.connect(self._handle_change)
        layout.addWidget(self.slider, alignment=Qt.AlignmentFlag.AlignHCenter)
        # The frequency label lives in its own row/frame below the whole
        # slider grid (see _build_band_panel), not stacked in this widget.

    def _build_horizontal(self, label, min_value, max_value):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(2, 2, 2, 2)
        layout.setSpacing(8)

        name_label = QLabel(label)
        name_label.setObjectName("bandFreq")
        layout.addWidget(name_label)

        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setMinimum(int(min_value * self.scale))
        self.slider.setMaximum(int(max_value * self.scale))
        self.slider.setValue(0)
        self.slider.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )
        self.slider.valueChanged.connect(self._handle_change)
        layout.addWidget(self.slider, stretch=1)

        self.gain_label = QLabel(self.fmt(0))
        self.gain_label.setObjectName("bandGain")
        self.gain_label.setMinimumWidth(40)
        layout.addWidget(self.gain_label)

    def _handle_change(self, raw_value):
        value = raw_value / self.scale
        self.gain_label.setText(self.fmt(value))
        if not self._suppress:
            self._on_change(value)

    def set_value(self, value, notify=False):
        self._suppress = not notify
        self.slider.setValue(int(round(value * self.scale)))
        self._suppress = False
        self.gain_label.setText(self.fmt(value))

    # Backwards-compatible alias used by band/preamp sliders.
    set_db = set_value


class FrequencyCurve(QWidget):
    """Live frequency-response curve above the band sliders -- the visual
    signature of a professional parametric EQ."""

    def __init__(self, num_bands, min_db, max_db, parent=None):
        super().__init__(parent)
        self.num_bands = num_bands
        self.min_db = min_db
        self.max_db = max_db
        self.values = [0.0] * num_bands
        self.setMinimumHeight(48)
        self.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )

    def set_values(self, values):
        self.values = list(values)
        self.update()

    def _value_to_y(self, value):
        span = self.max_db - self.min_db
        frac = (value - self.min_db) / span if span else 0.5
        frac = max(0.0, min(1.0, frac))
        top_pad, bottom_pad = 6, 6
        usable = self.height() - top_pad - bottom_pad
        return self.height() - bottom_pad - frac * usable

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        width = self.width()
        height = self.height()
        if self.num_bands < 2 or width <= 0:
            return

        zero_y = self._value_to_y(0.0)
        zero_pen = QPen(QColor(BORDER))
        zero_pen.setStyle(Qt.PenStyle.DashLine)
        painter.setPen(zero_pen)
        painter.drawLine(0, int(zero_y), width, int(zero_y))

        points = [
            QPointF(width * i / (self.num_bands - 1), self._value_to_y(v))
            for i, v in enumerate(self.values)
        ]

        curve = QPainterPath()
        curve.moveTo(points[0])
        for i in range(len(points) - 1):
            p0, p1 = points[i], points[i + 1]
            mid_x = (p0.x() + p1.x()) / 2
            curve.cubicTo(QPointF(mid_x, p0.y()), QPointF(mid_x, p1.y()), p1)

        fill = QPainterPath(curve)
        fill.lineTo(points[-1].x(), height)
        fill.lineTo(points[0].x(), height)
        fill.closeSubpath()

        gradient = QLinearGradient(0, 0, 0, height)
        top_color = QColor(ACCENT)
        top_color.setAlpha(80)
        bottom_color = QColor(ACCENT)
        bottom_color.setAlpha(0)
        gradient.setColorAt(0, top_color)
        gradient.setColorAt(1, bottom_color)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(gradient)
        painter.drawPath(fill)

        line_pen = QPen(QColor(ACCENT))
        line_pen.setWidthF(2.0)
        painter.setPen(line_pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPath(curve)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("MetalEQ")
        self.setMinimumSize(660, 618)
        self.resize(700, 668)

        self.engine = AudioEngine()
        self.band_values = [0.0] * 10
        self.preamp_value = 0.0
        self.bass_boost_level = 0
        self.vocal_norm_level = 0
        self.active_preset_name = None
        self._really_quit = False
        self._tray_hint_shown = False

        self.error_timer = QTimer(self)
        self.error_timer.setInterval(500)
        self.error_timer.timeout.connect(self._check_engine_errors)

        AudioEngine.recover_stale_state()

        self._build_ui()
        self._build_tray_icon()

        quit_shortcut = QAction(self)
        quit_shortcut.setShortcut(QKeySequence("Ctrl+Q"))
        quit_shortcut.triggered.connect(self._quit_app)
        self.addAction(quit_shortcut)

        self._refresh_devices()
        self._refresh_presets()
        self._select_preset_by_name(preset_store.get_default_preset())

        if preset_store.get_engine_enabled():
            self.enable_btn.setChecked(True)

    # ------------------------------------------------------------------- UI
    def _build_ui(self):
        root = QWidget()
        root_layout = QVBoxLayout(root)
        root_layout.setContentsMargins(12, 10, 12, 10)
        root_layout.setSpacing(8)

        root_layout.addWidget(self._build_device_panel())
        root_layout.addWidget(self._build_toggle_panel())
        root_layout.addWidget(self._build_band_panel(), stretch=1)
        root_layout.addWidget(self._build_preset_panel())

        self.setCentralWidget(root)

    def _build_device_panel(self):
        panel = QFrame()
        panel.setObjectName("panel")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(8)

        device_header = QLabel("Output device:")
        device_header.setObjectName("sectionHeader")
        layout.addWidget(device_header)

        self.device_combo = QComboBox()
        layout.addWidget(self.device_combo)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)
        btn_row.addStretch(1)

        refresh_btn = QPushButton("Refresh")
        refresh_btn.clicked.connect(self._refresh_devices)
        btn_row.addWidget(refresh_btn)

        self.enable_btn = QPushButton("Equalizer: Off")
        self.enable_btn.setObjectName("enableButton")
        self.enable_btn.setCheckable(True)
        self.enable_btn.setMinimumWidth(170)
        self.enable_btn.setSizePolicy(
            QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed
        )
        self.enable_btn.toggled.connect(self._on_enable_toggled)
        btn_row.addWidget(self.enable_btn)

        layout.addLayout(btn_row)
        return panel

    def _build_toggle_panel(self):
        panel = QFrame()
        panel.setObjectName("panel")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(10)

        self.bass_boost_slider = GainSlider(
            "Bass Boost",
            0,
            100,
            self._on_bass_boost_changed,
            orientation="horizontal",
            scale=1,
            fmt=_format_percent,
        )
        layout.addWidget(self.bass_boost_slider)

        self.vocal_norm_slider = GainSlider(
            "Vocal Normalize",
            0,
            100,
            self._on_vocal_norm_changed,
            orientation="horizontal",
            scale=1,
            fmt=_format_percent,
        )
        layout.addWidget(self.vocal_norm_slider)

        return panel

    def _build_band_panel(self):
        panel = QFrame()
        panel.setObjectName("panel")
        outer = QVBoxLayout(panel)
        outer.setContentsMargins(12, 10, 12, 10)
        outer.setSpacing(10)

        self.preamp_slider = GainSlider(
            "Preamp", PREAMP_MIN_DB, PREAMP_MAX_DB, self._on_preamp_changed,
            orientation="horizontal",
        )
        outer.addWidget(self.preamp_slider)

        divider = QFrame()
        divider.setFrameShape(QFrame.Shape.HLine)
        divider.setStyleSheet("color: #3a3d47;")
        outer.addWidget(divider)

        self.frequency_curve = FrequencyCurve(len(BAND_LABELS), BAND_MIN_DB, BAND_MAX_DB)
        outer.addWidget(self.frequency_curve)

        grid = QGridLayout()
        grid.setHorizontalSpacing(8)
        grid.setVerticalSpacing(6)

        self.band_sliders = []
        for i, label in enumerate(BAND_LABELS):
            slider = GainSlider(
                f"{label}Hz",
                BAND_MIN_DB,
                BAND_MAX_DB,
                lambda db, idx=i: self._on_band_changed(idx, db),
                orientation="vertical",
            )
            self.band_sliders.append(slider)
            row, col = divmod(i, BAND_GRID_COLUMNS)
            grid.addWidget(slider, row, col)

        outer.addLayout(grid, stretch=1)

        freq_frame = QFrame()
        freq_frame.setObjectName("freqRow")
        freq_layout = QHBoxLayout(freq_frame)
        freq_layout.setContentsMargins(0, 5, 0, 5)
        freq_layout.setSpacing(8)

        self.band_q_sliders = []
        self.band_q_values = [BAND_Q_DEFAULT] * len(BAND_LABELS)
        for i, label in enumerate(BAND_LABELS):
            column = QVBoxLayout()
            column.setSpacing(2)

            freq_label = QLabel(f"{label}Hz")
            freq_label.setObjectName("bandFreq")
            freq_label.setFixedWidth(COLUMN_WIDTH)
            freq_label.setAlignment(Qt.AlignmentFlag.AlignHCenter)
            column.addWidget(freq_label)

            q_slider = QSlider(Qt.Orientation.Horizontal)
            q_slider.setObjectName("qSlider")
            q_slider.setFixedWidth(COLUMN_WIDTH)
            q_slider.setMinimum(int(BAND_Q_MIN * 10))
            q_slider.setMaximum(int(BAND_Q_MAX * 10))
            q_slider.setValue(int(BAND_Q_DEFAULT * 10))
            q_slider.setToolTip(f"Q {BAND_Q_DEFAULT:.1f} (narrow ↔ wide)")
            q_slider.valueChanged.connect(
                lambda raw, idx=i: self._on_band_q_changed(idx, raw / 10.0)
            )
            self.band_q_sliders.append(q_slider)
            column.addWidget(q_slider)

            freq_layout.addLayout(column)
        outer.addWidget(freq_frame)

        return panel

    def _build_preset_panel(self):
        panel = QFrame()
        panel.setObjectName("panel")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(8)

        header_row = QHBoxLayout()
        header_row.setSpacing(8)

        preset_header = QLabel("Preset:")
        preset_header.setObjectName("sectionHeader")
        header_row.addWidget(preset_header)
        header_row.addStretch(1)

        self.default_preset_label = QLabel()
        self.default_preset_label.setObjectName("status")
        header_row.addWidget(self.default_preset_label)

        layout.addLayout(header_row)

        self.preset_combo = QComboBox()
        self.preset_combo.activated.connect(self._on_preset_selected)
        layout.addWidget(self.preset_combo)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)

        save_btn = QPushButton("Save")
        save_btn.clicked.connect(self._save_current)
        btn_row.addWidget(save_btn)

        save_as_btn = QPushButton("Save As...")
        save_as_btn.clicked.connect(self._save_preset)
        btn_row.addWidget(save_as_btn)

        delete_btn = QPushButton("Delete")
        delete_btn.clicked.connect(self._delete_preset)
        btn_row.addWidget(delete_btn)

        reset_btn = QPushButton("Reset")
        reset_btn.clicked.connect(self._reset_bands)
        btn_row.addWidget(reset_btn)

        btn_row.addStretch(1)

        set_default_btn = QPushButton("Set as Default")
        set_default_btn.clicked.connect(self._set_default_preset)
        btn_row.addWidget(set_default_btn)

        layout.addLayout(btn_row)
        self._refresh_default_preset_label()

        return panel

    # ------------------------------------------------------------------ tray
    def _build_tray_icon(self):
        icon = load_app_icon()
        self.tray_icon = QSystemTrayIcon(icon, self)
        self.tray_icon.setToolTip("MetalEQ")

        menu = QMenu()

        self.tray_show_action = QAction("Show MetalEQ", self)
        self.tray_show_action.triggered.connect(self._show_window)
        menu.addAction(self.tray_show_action)

        menu.addSeparator()

        self.tray_enable_action = QAction("Enable Equalizer", self)
        self.tray_enable_action.setCheckable(True)
        self.tray_enable_action.toggled.connect(self._on_tray_enable_toggled)
        menu.addAction(self.tray_enable_action)

        self.tray_preset_menu = QMenu("Preset", menu)
        menu.addMenu(self.tray_preset_menu)

        menu.addSeparator()

        quit_action = QAction("Quit", self)
        quit_action.triggered.connect(self._quit_app)
        menu.addAction(quit_action)

        self.tray_icon.setContextMenu(menu)
        self.tray_icon.activated.connect(self._on_tray_activated)
        self.tray_icon.show()

    def _refresh_tray_preset_menu(self):
        self.tray_preset_menu.clear()
        names = [FLAT_LABEL] + list(preset_store.BUILTIN_EXTRA_PRESETS)
        reserved_names = {FLAT_LABEL} | set(preset_store.BUILTIN_EXTRA_PRESETS)
        custom_names = sorted(
            n for n in preset_store.load_custom_presets().keys()
            if n not in reserved_names
        )
        for name in names + custom_names:
            action = QAction(name, self)
            action.triggered.connect(lambda checked=False, n=name: self._select_preset_by_name(n))
            self.tray_preset_menu.addAction(action)

    def _show_window(self):
        self.showNormal()
        self.raise_()
        self.activateWindow()

    def _on_tray_activated(self, reason):
        if reason in (
            QSystemTrayIcon.ActivationReason.Trigger,
            QSystemTrayIcon.ActivationReason.DoubleClick,
        ):
            if self.isVisible():
                self.hide()
            else:
                self._show_window()

    def _on_tray_enable_toggled(self, checked):
        if self.enable_btn.isChecked() != checked:
            self.enable_btn.setChecked(checked)

    def _quit_app(self):
        self._really_quit = True
        self.close()

    # --------------------------------------------------------------- devices
    def _refresh_devices(self):
        current = self.device_combo.currentData()
        self.device_combo.clear()
        for name, description in AudioEngine.list_output_sinks():
            self.device_combo.addItem(description, userData=name)

        target = current or AudioEngine.get_system_default_sink()
        if target:
            index = self.device_combo.findData(target)
            if index >= 0:
                self.device_combo.setCurrentIndex(index)

    # --------------------------------------------------------------- presets
    def _refresh_presets(self):
        current_text = self.preset_combo.currentText()
        self.preset_combo.blockSignals(True)
        self.preset_combo.clear()
        self.preset_combo.addItem(CUSTOM_LABEL)
        for name in preset_store.BUILTIN_EXTRA_PRESETS:
            self.preset_combo.addItem(name)
        self.preset_combo.addItem(FLAT_LABEL)
        reserved_names = {FLAT_LABEL} | set(preset_store.BUILTIN_EXTRA_PRESETS)
        custom_names = sorted(
            name
            for name in preset_store.load_custom_presets().keys()
            if name not in reserved_names
        )
        if custom_names:
            self.preset_combo.insertSeparator(self.preset_combo.count())
            for name in custom_names:
                self.preset_combo.addItem(name)
        index = self.preset_combo.findText(current_text)
        self.preset_combo.setCurrentIndex(index if index >= 0 else 0)
        self.preset_combo.blockSignals(False)
        self._refresh_tray_preset_menu()

    def _on_preset_selected(self, index):
        name = self.preset_combo.itemText(index)
        if name == CUSTOM_LABEL:
            self.active_preset_name = None
            return
        self._apply_preset_values(name)

    def _apply_preset_values(self, name):
        if name == CUSTOM_LABEL:
            return
        self.active_preset_name = name
        custom = preset_store.load_custom_presets()
        if name in custom:
            # A saved override always wins over the built-in starting point.
            entry = custom[name]
            bands = entry["bands"]
            q_values = entry["q"]
            bass_boost = entry["bass_boost"]
            vocal_norm = entry["vocal_norm"]
            preamp = entry["preamp"]
        elif name == FLAT_LABEL:
            bands = [0.0] * 10
            q_values = [BAND_Q_DEFAULT] * 10
            bass_boost, vocal_norm, preamp = 0, 0, 0.0
        elif name in preset_store.BUILTIN_EXTRA_PRESETS:
            bands = preset_store.BUILTIN_EXTRA_PRESETS[name]
            q_values = [BAND_Q_DEFAULT] * 10
            bass_boost, vocal_norm, preamp = 0, 0, 0.0
        else:
            bands = [0.0] * 10
            q_values = [BAND_Q_DEFAULT] * 10
            bass_boost, vocal_norm, preamp = 0, 0, 0.0
        self._apply_band_values(bands)
        self._apply_band_q_values(q_values)
        self._apply_fx_levels(bass_boost, vocal_norm)
        self._apply_preamp(preamp)

    def _select_preset_by_name(self, name):
        index = self.preset_combo.findText(name)
        if index < 0:
            return
        self.preset_combo.setCurrentIndex(index)
        self._apply_preset_values(name)

    # ------------------------------------------------------------- bands/fx
    def _effective_band_value(self, index):
        frac = self.bass_boost_level / 100.0
        value = self.band_values[index] + BASS_BOOST_OFFSETS[index] * frac
        return max(BAND_MIN_DB, min(BAND_MAX_DB, value))

    def _push_band_to_engine(self, index):
        if self.engine.running:
            self.engine.set_band(index, self._effective_band_value(index))

    def _push_all_bands_to_engine(self):
        for i in range(10):
            self._push_band_to_engine(i)
        self.frequency_curve.set_values(
            [self._effective_band_value(i) for i in range(10)]
        )

    def _apply_band_values(self, values):
        self.band_values = list(values)
        for slider, value in zip(self.band_sliders, values):
            slider.set_db(value)
        self._push_all_bands_to_engine()

    def _on_band_changed(self, index, db_value):
        self.band_values[index] = db_value
        self._push_band_to_engine(index)
        self.frequency_curve.set_values(
            [self._effective_band_value(i) for i in range(10)]
        )

    def _on_band_q_changed(self, index, q_value):
        self.band_q_values[index] = q_value
        self.band_q_sliders[index].setToolTip(f"Q {q_value:.1f} (narrow ↔ wide)")
        if self.engine.running:
            self.engine.set_band_q(index, q_value)

    def _on_preamp_changed(self, db_value):
        self.preamp_value = db_value
        if self.engine.running:
            self.engine.set_preamp_db(db_value)

    def _on_bass_boost_changed(self, level):
        self.bass_boost_level = level
        self._push_all_bands_to_engine()

    def _on_vocal_norm_changed(self, level):
        self.vocal_norm_level = level
        if self.engine.running:
            self.engine.set_vocal_normalization(level)

    def _apply_fx_levels(self, bass_boost, vocal_norm):
        self.bass_boost_level = bass_boost
        self.vocal_norm_level = vocal_norm
        self.bass_boost_slider.set_value(bass_boost)
        self.vocal_norm_slider.set_value(vocal_norm)
        self._push_all_bands_to_engine()
        if self.engine.running:
            self.engine.set_vocal_normalization(vocal_norm)

    def _apply_preamp(self, db_value):
        self.preamp_value = db_value
        self.preamp_slider.set_db(db_value)
        if self.engine.running:
            self.engine.set_preamp_db(db_value)

    def _apply_band_q_values(self, q_values):
        self.band_q_values = list(q_values)
        for slider, q_value in zip(self.band_q_sliders, q_values):
            slider.blockSignals(True)
            slider.setValue(int(round(q_value * 10)))
            slider.blockSignals(False)
            slider.setToolTip(f"Q {q_value:.1f} (narrow ↔ wide)")
        if self.engine.running:
            for i, q_value in enumerate(q_values):
                self.engine.set_band_q(i, q_value)

    def _reset_bands(self):
        self._apply_band_values([0.0] * 10)
        self._apply_band_q_values([BAND_Q_DEFAULT] * 10)
        self._apply_fx_levels(0, 0)
        self._apply_preamp(0.0)
        self.active_preset_name = FLAT_LABEL
        self.preset_combo.blockSignals(True)
        self.preset_combo.setCurrentIndex(self.preset_combo.findText(FLAT_LABEL))
        self.preset_combo.blockSignals(False)

    def _save_current(self):
        name = self.active_preset_name
        if not name:
            self._save_preset()
            return
        preset_store.add_preset(
            name,
            self.band_values,
            self.bass_boost_level,
            self.vocal_norm_level,
            self.preamp_value,
            self.band_q_values,
        )
        self._refresh_presets()
        index = self.preset_combo.findText(name)
        if index >= 0:
            self.preset_combo.blockSignals(True)
            self.preset_combo.setCurrentIndex(index)
            self.preset_combo.blockSignals(False)

    def _save_preset(self):
        name, ok = QInputDialog.getText(self, "Save Preset", "Preset name:")
        name = name.strip()
        if not ok or not name:
            return
        reserved = {CUSTOM_LABEL, FLAT_LABEL} | set(preset_store.BUILTIN_EXTRA_PRESETS)
        if name in reserved:
            QMessageBox.warning(self, "Invalid name", "That name is reserved.")
            return
        preset_store.add_preset(
            name,
            self.band_values,
            self.bass_boost_level,
            self.vocal_norm_level,
            self.preamp_value,
            self.band_q_values,
        )
        self._refresh_presets()
        index = self.preset_combo.findText(name)
        if index >= 0:
            self.preset_combo.setCurrentIndex(index)

    def _delete_preset(self):
        name = self.preset_combo.currentText()
        custom = preset_store.load_custom_presets()
        if name not in custom:
            QMessageBox.information(
                self, "Can't delete", "Only custom presets can be deleted."
            )
            return
        preset_store.delete_preset(name)
        self._refresh_presets()
        if self.preset_combo.currentText() == name:
            # Reload now that the override is gone (falls back to the
            # built-in default, Flat, or stays Custom).
            self._apply_preset_values(name)

    def _refresh_default_preset_label(self):
        self.default_preset_label.setText(
            f"Default profile: {preset_store.get_default_preset()}"
        )

    def _set_default_preset(self):
        name = self.preset_combo.currentText()
        if name == CUSTOM_LABEL:
            QMessageBox.information(
                self,
                "Can't set default",
                "Save this as a named preset first, then set it as default.",
            )
            return
        preset_store.set_default_preset(name)
        self._refresh_default_preset_label()

    # ---------------------------------------------------------------- engine
    def _on_enable_toggled(self, checked):
        if checked:
            self._start_engine()
        else:
            self._stop_engine()
        actually_on = self.enable_btn.isChecked()
        self.enable_btn.setText("Equalizer: On" if actually_on else "Equalizer: Off")
        preset_store.set_engine_enabled(actually_on)
        self._sync_tray_enable(actually_on)

    def _start_engine(self):
        sink_name = self.device_combo.currentData()
        if not sink_name:
            QMessageBox.warning(self, "No device", "No output device selected.")
            self._set_enabled_checked(False)
            return
        try:
            self.engine.start(sink_name)
        except AudioEngineError as exc:
            QMessageBox.critical(self, "Failed to start", str(exc))
            self._set_enabled_checked(False)
            return

        self._push_all_bands_to_engine()
        for i, q_value in enumerate(self.band_q_values):
            self.engine.set_band_q(i, q_value)
        self.engine.set_preamp_db(self.preamp_value)
        self.engine.set_vocal_normalization(self.vocal_norm_level)

        self.device_combo.setEnabled(False)
        self.error_timer.start()

    def _stop_engine(self):
        self.error_timer.stop()
        self.engine.stop()
        self.device_combo.setEnabled(True)

    def _set_enabled_checked(self, checked):
        self.enable_btn.blockSignals(True)
        self.enable_btn.setChecked(checked)
        self.enable_btn.blockSignals(False)
        self.enable_btn.setText("Equalizer: On" if checked else "Equalizer: Off")
        preset_store.set_engine_enabled(checked)
        self._sync_tray_enable(checked)

    def _sync_tray_enable(self, checked):
        self.tray_enable_action.blockSignals(True)
        self.tray_enable_action.setChecked(checked)
        self.tray_enable_action.blockSignals(False)
        self.tray_icon.setToolTip(f"MetalEQ — {'On' if checked else 'Off'}")

    def _check_engine_errors(self):
        error = self.engine.poll_errors()
        if error:
            self._stop_engine()
            self._set_enabled_checked(False)
            QMessageBox.critical(self, "Audio Error", error)

    def closeEvent(self, event):
        if self._really_quit:
            if self.engine.running:
                self.engine.stop()
            event.accept()
            return

        event.ignore()
        self.hide()
        if not self._tray_hint_shown:
            self._tray_hint_shown = True
            self.tray_icon.showMessage(
                "MetalEQ",
                "Still running in the tray. Right-click the icon to quit, "
                "or press Ctrl+Q while the window is open.",
                QSystemTrayIcon.MessageIcon.Information,
                3000,
            )
