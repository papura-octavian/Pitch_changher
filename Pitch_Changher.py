"""
PitchShifter — Windows and Linux

- Load MP3/WAV/OGG/FLAC/M4A/AAC or MP4/MOV/MKV
- Shift pitch by semitones (±24) or tones (±12)
- Export WAV/MP3 (audio) or MP4 (video remux with shifted audio)

Install in venv:
    python -m pip install --upgrade pip setuptools wheel
    pip install -r requirements.txt

FFmpeg is looked up in ./ffmpeg/<os>/ next to the app, then in PATH.
Run scripts/get_ffmpeg.py to download a bundled copy.
"""
from __future__ import annotations

import os
import platform
import shutil
import subprocess
import sys
import tempfile
import traceback
from dataclasses import dataclass
from typing import Optional

import numpy as np
import librosa
import soundfile as sf

from PySide6.QtCore import Qt, QThread, Signal, Slot
from PySide6.QtGui import QColor, QDragEnterEvent, QDropEvent, QIcon, QMouseEvent, QPalette
from PySide6.QtWidgets import (
    QApplication,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QGridLayout,
    QPushButton,
    QLabel,
    QFileDialog,
    QSlider,
    QDoubleSpinBox,
    QComboBox,
    QProgressBar,
    QMessageBox,
    QFrame,
)

SUPPORTED_AUDIO_EXTS = {".wav", ".mp3", ".ogg", ".flac", ".m4a", ".aac"}
SUPPORTED_VIDEO_EXTS = {".mp4", ".mov", ".mkv"}

# Formats libsndfile can decode directly; everything else goes through ffmpeg
_DIRECT_DECODE_EXTS = {".wav", ".flac", ".ogg"}

MAX_SHIFT_SEMITONES = 24

_ffmpeg_path: Optional[str] = None


def get_ffmpeg_path() -> str:
    """Get path to ffmpeg executable, preferring a bundled copy (cached)."""
    global _ffmpeg_path
    if _ffmpeg_path is not None:
        return _ffmpeg_path

    is_windows = platform.system().lower() == "windows"
    subdir = "windows" if is_windows else "linux"
    exe = "ffmpeg.exe" if is_windows else "ffmpeg"

    candidates = []
    if getattr(sys, "frozen", False):
        exe_dir = os.path.dirname(os.path.abspath(sys.executable))
        # Installed layout: ffmpeg/ next to the executable
        candidates.append(os.path.join(exe_dir, "ffmpeg", subdir, exe))
        # AppImage layout: usr/bin/PitchShifter with ffmpeg/ in usr/
        candidates.append(os.path.join(exe_dir, "..", "ffmpeg", subdir, exe))
        # Onefile bundles extracted to _MEIPASS
        if hasattr(sys, "_MEIPASS"):
            candidates.append(os.path.join(sys._MEIPASS, "ffmpeg", subdir, exe))
    else:
        base_dir = os.path.dirname(os.path.abspath(__file__))
        candidates.append(os.path.join(base_dir, "ffmpeg", subdir, exe))

    for cand in candidates:
        cand = os.path.normpath(cand)
        if os.path.isfile(cand) and (is_windows or os.access(cand, os.X_OK)):
            _ffmpeg_path = cand
            return cand

    _ffmpeg_path = shutil.which("ffmpeg") or "ffmpeg"
    return _ffmpeg_path


def run_ffmpeg(args: list[str], action: str) -> None:
    """Run ffmpeg with the given arguments, raising on failure."""
    creationflags = 0
    if os.name == "nt":
        creationflags = subprocess.CREATE_NO_WINDOW
    proc = subprocess.run(
        [get_ffmpeg_path(), *args],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        creationflags=creationflags,
    )
    if proc.returncode != 0:
        raise RuntimeError(
            f"ffmpeg {action} failed:\n" + proc.stderr.decode(errors="ignore")
        )


@dataclass
class JobConfig:
    in_path: str
    out_path: str
    semitone_shift: float
    sr: Optional[int] = None


class ProcessorThread(QThread):
    progressed = Signal(int)
    finished_ok = Signal(str)
    failed = Signal(str)

    def __init__(self, cfg: JobConfig):
        super().__init__()
        self.cfg = cfg

    def run(self) -> None:  # type: ignore[override]
        try:
            self.progressed.emit(5)
            ext = os.path.splitext(self.cfg.in_path)[1].lower()
            if ext in SUPPORTED_VIDEO_EXTS:
                self._process_video()
            elif ext in SUPPORTED_AUDIO_EXTS:
                self._process_audio(self.cfg.in_path, self.cfg.out_path)
            else:
                raise RuntimeError(f"Unsupported file extension: {ext}")
            self.progressed.emit(100)
            self.finished_ok.emit(self.cfg.out_path)
        except Exception as e:
            tb = traceback.format_exc()
            self.failed.emit(f"Error: {e}\n\n{tb}")

    # --- helpers ---
    def _load_audio(self, in_audio_path: str) -> tuple[np.ndarray, int]:
        """Load audio as (channels, samples), decoding via ffmpeg when needed."""
        ext = os.path.splitext(in_audio_path)[1].lower()
        tmp_decoded = None
        src = in_audio_path
        if ext not in _DIRECT_DECODE_EXTS:
            # Decode compressed formats with the bundled ffmpeg so we don't
            # depend on system codecs being installed
            fd, tmp_decoded = tempfile.mkstemp(suffix=".wav")
            os.close(fd)
            run_ffmpeg(
                ["-y", "-i", in_audio_path, "-vn", "-acodec", "pcm_s16le", tmp_decoded],
                "decode audio",
            )
            src = tmp_decoded
        try:
            y, sr = librosa.load(src, sr=self.cfg.sr, mono=False)
        finally:
            if tmp_decoded:
                os.remove(tmp_decoded)
        return np.atleast_2d(y), int(sr)

    def _process_audio(self, in_audio_path: str, out_audio_path: str) -> None:
        self.progressed.emit(10)

        y, sr = self._load_audio(in_audio_path)
        self.progressed.emit(30)

        # Pad very short signals so the STFT inside pitch_shift has enough
        # samples, then trim back to the original length
        n = y.shape[1]
        if n < 2048:
            y = np.pad(y, ((0, 0), (0, 2048 - n)))

        shifted = librosa.effects.pitch_shift(
            y, sr=sr, n_steps=self.cfg.semitone_shift
        )
        shifted = shifted[:, :n]
        Y = shifted.T if shifted.shape[0] > 1 else shifted[0]

        self.progressed.emit(70)

        out_ext = os.path.splitext(out_audio_path)[1].lower()
        if out_ext == ".mp3":
            fd, tmp_path = tempfile.mkstemp(suffix=".wav")
            os.close(fd)
            try:
                sf.write(tmp_path, Y, sr)
                run_ffmpeg(
                    ["-y", "-i", tmp_path, "-codec:a", "libmp3lame", "-q:a", "2",
                     out_audio_path],
                    "encode mp3",
                )
            finally:
                os.remove(tmp_path)
        else:
            if out_ext != ".wav":
                out_audio_path = out_audio_path + ".wav"
                self.cfg.out_path = out_audio_path
            sf.write(out_audio_path, Y, sr)

        self.progressed.emit(90)

    def _process_video(self) -> None:
        self.progressed.emit(12)
        in_path = self.cfg.in_path
        out_path = self.cfg.out_path

        with tempfile.TemporaryDirectory() as td:
            temp_audio = os.path.join(td, "orig_audio.wav")
            temp_shifted = os.path.join(td, "shifted.wav")

            # 1) Extract audio to WAV (keep original rate & channels)
            run_ffmpeg(
                ["-y", "-i", in_path, "-vn", "-acodec", "pcm_s16le", temp_audio],
                "extract audio",
            )
            self.progressed.emit(40)

            # 2) Process audio with librosa
            self._process_audio(temp_audio, temp_shifted)
            self.progressed.emit(70)

            # 3) Mux back shifted audio with original video stream (copy video)
            if not out_path.lower().endswith(".mp4"):
                out_path = out_path + ".mp4"
                self.cfg.out_path = out_path

            run_ffmpeg(
                ["-y", "-i", in_path, "-i", temp_shifted,
                 "-c:v", "copy", "-map", "0:v:0", "-map", "1:a:0",
                 "-shortest", "-c:a", "aac", out_path],
                "mux",
            )
            self.progressed.emit(95)


def resource_path(*parts: str) -> str:
    """Path to a bundled resource, working both frozen and from source."""
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        base = sys._MEIPASS
    else:
        base = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base, *parts)


def _asset_url(name: str) -> str:
    """Forward-slash path for use inside the Qt stylesheet."""
    return resource_path("assets", name).replace("\\", "/")


_ARROW_DOWN = _asset_url("arrow-down.svg")
_ARROW_UP = _asset_url("arrow-up.svg")


# ---------------------------------------------------------------------------
# Theme
#
# The look is locked to this dark palette no matter what theme the OS uses:
#  - Fusion style (ignores platform theme engines)
#  - a complete QPalette, including Disabled roles
#  - an application-wide stylesheet (also covers QMessageBox and popups)
#  - the Qt color scheme is forced to Dark where supported (title bar)
# ---------------------------------------------------------------------------

C_BG = "#0a0f1e"          # window background
C_CARD = "#0f172a"        # card / input background
C_CARD_2 = "#111c33"      # slightly lighter card
C_BORDER = "#24324d"      # subtle borders
C_TEXT = "#e8f2ff"        # main text
C_SUB = "#8aa3c4"         # secondary text
C_MUTED = "#5b7294"       # muted text
C_ACCENT = "#38bdf8"      # cyan
C_ACCENT_2 = "#a855f7"    # purple
C_DISABLED = "#64748b"

STYLESHEET = f"""
QWidget {{
    background-color: {C_BG};
    color: {C_TEXT};
    font-family: "Segoe UI", "Inter", "Roboto", sans-serif;
    font-size: 14px;
}}
#title {{
    font-size: 30px;
    font-weight: 800;
    letter-spacing: 1px;
    color: {C_TEXT};
    background: transparent;
}}
#titleAccent {{
    font-size: 30px;
    font-weight: 800;
    letter-spacing: 1px;
    color: {C_ACCENT};
    background: transparent;
}}
#subtitle {{
    font-size: 13px;
    color: {C_SUB};
    background: transparent;
}}
#topRightTag {{
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 2px;
    color: {C_MUTED};
    background: transparent;
}}
#topRightHint {{
    font-size: 11px;
    color: {C_MUTED};
    background: transparent;
}}

/* --- drop zone ------------------------------------------------------- */
#dropZone {{
    border: 2px dashed {C_BORDER};
    border-radius: 16px;
    background-color: {C_CARD};
}}
#dropZone:hover {{
    border-color: {C_ACCENT};
    background-color: {C_CARD_2};
}}
#dropZone[dragOver="true"] {{
    border: 2px dashed {C_ACCENT};
    background-color: rgba(56, 189, 248, 0.10);
}}
#dropZone[loaded="true"] {{
    border: 2px solid {C_BORDER};
}}
#dropIcon {{
    font-size: 30px;
    background: transparent;
}}
#dropTitle {{
    font-size: 15px;
    font-weight: 600;
    color: {C_TEXT};
    background: transparent;
}}
#dropHint {{
    font-size: 12px;
    color: {C_MUTED};
    background: transparent;
}}

/* --- control card ----------------------------------------------------- */
QFrame[class="card"] {{
    border: 1px solid {C_BORDER};
    border-radius: 16px;
    background: qlineargradient(
        x1:0, y1:0, x2:1, y2:1,
        stop:0 {C_CARD_2},
        stop:1 {C_CARD}
    );
}}
#sectionLabel {{
    font-weight: 600;
    font-size: 13px;
    color: {C_SUB};
    background: transparent;
}}
#unitSuffix {{
    color: {C_MUTED};
    font-size: 13px;
    background: transparent;
}}
#statusLabel {{
    font-size: 12px;
    color: {C_SUB};
    background: transparent;
}}
#divider {{
    background-color: {C_BORDER};
    max-height: 1px;
    border: none;
}}

/* --- buttons ----------------------------------------------------------- */
QPushButton {{
    background-color: {C_CARD_2};
    border: 1px solid {C_BORDER};
    border-radius: 10px;
    padding: 9px 20px;
    font-weight: 600;
    color: {C_TEXT};
}}
QPushButton:hover {{
    border-color: {C_ACCENT};
    background-color: #16233f;
}}
QPushButton:pressed {{
    background-color: {C_CARD};
}}
QPushButton:disabled {{
    color: {C_DISABLED};
    border-color: {C_BORDER};
    background-color: {C_CARD};
}}
QPushButton#primaryButton {{
    background: qlineargradient(
        x1:0, y1:0, x2:1, y2:1,
        stop:0 {C_ACCENT}, stop:1 {C_ACCENT_2}
    );
    border: none;
    color: #06121f;
    font-weight: 700;
    padding: 10px 26px;
}}
QPushButton#primaryButton:hover {{
    background: qlineargradient(
        x1:0, y1:0, x2:1, y2:1,
        stop:0 #5ecbfa, stop:1 #bb75f9
    );
}}
QPushButton#primaryButton:pressed {{
    background: qlineargradient(
        x1:0, y1:0, x2:1, y2:1,
        stop:0 #2da8e0, stop:1 #9445dd
    );
}}
QPushButton#primaryButton:disabled {{
    background: {C_CARD_2};
    color: {C_DISABLED};
    border: 1px solid {C_BORDER};
}}

/* --- inputs ------------------------------------------------------------ */
QComboBox, QDoubleSpinBox {{
    background-color: {C_CARD};
    border: 1px solid {C_BORDER};
    border-radius: 10px;
    padding: 6px 12px;
    min-height: 30px;
    selection-background-color: rgba(56, 189, 248, 0.35);
    selection-color: {C_TEXT};
}}
QComboBox:hover, QDoubleSpinBox:hover {{
    border-color: {C_ACCENT};
}}
QComboBox:disabled, QDoubleSpinBox:disabled {{
    color: {C_DISABLED};
}}
QComboBox::drop-down {{
    border: none;
    width: 26px;
}}
QComboBox::down-arrow {{
    image: url("{_ARROW_DOWN}");
    width: 12px;
    height: 12px;
    margin-right: 8px;
}}
QComboBox QAbstractItemView {{
    background-color: {C_CARD_2};
    border: 1px solid {C_BORDER};
    border-radius: 8px;
    padding: 4px;
    outline: none;
    selection-background-color: rgba(56, 189, 248, 0.25);
    selection-color: {C_TEXT};
}}
QDoubleSpinBox::up-button, QDoubleSpinBox::down-button {{
    background: transparent;
    border: none;
    width: 20px;
}}
QDoubleSpinBox::up-arrow {{
    image: url("{_ARROW_UP}");
    width: 10px;
    height: 10px;
}}
QDoubleSpinBox::down-arrow {{
    image: url("{_ARROW_DOWN}");
    width: 10px;
    height: 10px;
}}

/* --- slider ------------------------------------------------------------ */
QSlider::groove:horizontal {{
    height: 6px;
    background: {C_BORDER};
    border-radius: 3px;
    margin: 0 2px;
}}
QSlider::handle:horizontal {{
    width: 20px;
    height: 20px;
    margin: -7px 0;
    background: qradialgradient(
        cx:0.4, cy:0.4, radius: 0.9,
        fx:0.4, fy:0.4,
        stop:0 #e8f2ff, stop:0.35 {C_ACCENT}, stop:1 {C_ACCENT_2}
    );
    border: 2px solid {C_BG};
    border-radius: 10px;
}}
QSlider::handle:horizontal:hover {{
    background: qradialgradient(
        cx:0.4, cy:0.4, radius: 0.9,
        fx:0.4, fy:0.4,
        stop:0 #ffffff, stop:0.35 #5ecbfa, stop:1 #bb75f9
    );
}}
QSlider::sub-page:horizontal {{
    background: qlineargradient(
        x1:0, y1:0, x2:1, y2:0,
        stop:0 {C_ACCENT}, stop:1 {C_ACCENT_2}
    );
    border-radius: 3px;
}}

/* --- progress ----------------------------------------------------------- */
QProgressBar {{
    background-color: {C_CARD};
    border: 1px solid {C_BORDER};
    border-radius: 9px;
    height: 18px;
    text-align: center;
    font-size: 11px;
    font-weight: 600;
    color: {C_TEXT};
}}
QProgressBar::chunk {{
    border-radius: 8px;
    background: qlineargradient(
        x1:0, y1:0, x2:1, y2:0,
        stop:0 {C_ACCENT}, stop:1 {C_ACCENT_2}
    );
}}

/* --- dialogs / misc ------------------------------------------------------ */
QMessageBox {{
    background-color: {C_CARD_2};
}}
QMessageBox QLabel {{
    background: transparent;
    color: {C_TEXT};
}}
QToolTip {{
    background-color: {C_CARD_2};
    color: {C_TEXT};
    border: 1px solid {C_ACCENT};
    padding: 4px 8px;
}}
QScrollBar:vertical {{
    background: {C_CARD};
    width: 10px;
    border-radius: 5px;
}}
QScrollBar::handle:vertical {{
    background: {C_BORDER};
    border-radius: 5px;
    min-height: 24px;
}}
QScrollBar::handle:vertical:hover {{
    background: {C_MUTED};
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0;
}}
"""


def make_dark_palette() -> QPalette:
    """Complete fixed palette so no widget falls back to the OS theme."""
    p = QPalette()
    roles = {
        QPalette.ColorRole.Window: C_BG,
        QPalette.ColorRole.WindowText: C_TEXT,
        QPalette.ColorRole.Base: C_CARD,
        QPalette.ColorRole.AlternateBase: C_CARD_2,
        QPalette.ColorRole.Text: C_TEXT,
        QPalette.ColorRole.Button: C_CARD_2,
        QPalette.ColorRole.ButtonText: C_TEXT,
        QPalette.ColorRole.BrightText: "#ffffff",
        QPalette.ColorRole.Highlight: C_ACCENT,
        QPalette.ColorRole.HighlightedText: "#06121f",
        QPalette.ColorRole.ToolTipBase: C_CARD_2,
        QPalette.ColorRole.ToolTipText: C_TEXT,
        QPalette.ColorRole.Link: C_ACCENT,
        QPalette.ColorRole.LinkVisited: C_ACCENT_2,
        QPalette.ColorRole.PlaceholderText: C_MUTED,
    }
    for role, color in roles.items():
        p.setColor(role, QColor(color))
    # Disabled group — keep it consistent instead of inheriting OS greys
    for role in (QPalette.ColorRole.WindowText, QPalette.ColorRole.Text,
                 QPalette.ColorRole.ButtonText):
        p.setColor(QPalette.ColorGroup.Disabled, role, QColor(C_DISABLED))
    p.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Base, QColor(C_CARD))
    p.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Button, QColor(C_CARD))
    return p


def force_dark_title_bar(widget: QWidget) -> None:
    """Keep the Windows title bar dark even when the OS uses a light theme."""
    if sys.platform != "win32":
        return
    try:
        import ctypes
        hwnd = int(widget.winId())
        value = ctypes.c_int(1)
        for attr in (20, 19):  # DWMWA_USE_IMMERSIVE_DARK_MODE (19 on older builds)
            res = ctypes.windll.dwmapi.DwmSetWindowAttribute(
                hwnd, attr, ctypes.byref(value), ctypes.sizeof(value)
            )
            if res == 0:
                break
    except Exception:
        pass


class DropZone(QFrame):
    """Clickable drop target that highlights while a file is dragged over."""

    clicked = Signal()

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("dropZone")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumHeight(110)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 18, 16, 18)
        layout.setSpacing(4)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.icon_label = QLabel("🎧")
        self.icon_label.setObjectName("dropIcon")
        self.icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.title_label = QLabel("Drop your audio or video file here")
        self.title_label.setObjectName("dropTitle")
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.hint_label = QLabel("or click to browse · wav mp3 ogg flac m4a aac · mp4 mov mkv")
        self.hint_label.setObjectName("dropHint")
        self.hint_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        layout.addWidget(self.icon_label)
        layout.addWidget(self.title_label)
        layout.addWidget(self.hint_label)

    def mousePressEvent(self, event: QMouseEvent) -> None:  # type: ignore[override]
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)

    def set_drag_over(self, on: bool) -> None:
        self.setProperty("dragOver", "true" if on else "false")
        self.style().unpolish(self)
        self.style().polish(self)

    def set_loaded(self, filename: Optional[str]) -> None:
        if filename:
            self.icon_label.setText("🎵")
            self.title_label.setText(filename)
            self.hint_label.setText("Click to choose a different file")
            self.setProperty("loaded", "true")
        else:
            self.icon_label.setText("🎧")
            self.title_label.setText("Drop your audio or video file here")
            self.hint_label.setText(
                "or click to browse · wav mp3 ogg flac m4a aac · mp4 mov mkv"
            )
            self.setProperty("loaded", "false")
        self.style().unpolish(self)
        self.style().polish(self)


class PitchShifterApp(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.setAcceptDrops(True)
        self.setWindowTitle("PitchShifter")
        self.setMinimumSize(720, 560)
        self.resize(880, 620)

        self.in_path: Optional[str] = None
        self.worker: Optional[ProcessorThread] = None
        self._unit_index = 0

        root = QVBoxLayout(self)
        root.setContentsMargins(28, 24, 28, 24)
        root.setSpacing(18)

        # --- header ---
        topbar = QHBoxLayout()

        titlebox = QVBoxLayout()
        titlebox.setSpacing(2)

        title_row = QHBoxLayout()
        title_row.setSpacing(0)
        title_a = QLabel("Pitch")
        title_a.setObjectName("titleAccent")
        title_b = QLabel("Shifter")
        title_b.setObjectName("title")
        title_row.addWidget(title_a)
        title_row.addWidget(title_b)
        title_row.addStretch(1)

        subtitle = QLabel("Drop audio/video · shift pitch · export")
        subtitle.setObjectName("subtitle")

        titlebox.addLayout(title_row)
        titlebox.addWidget(subtitle)
        topbar.addLayout(titlebox, 1)

        rightbox = QVBoxLayout()
        rightbox.setSpacing(2)
        rightbox.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        tag = QLabel("FFMPEG · LIBROSA")
        tag.setObjectName("topRightTag")
        tag.setAlignment(Qt.AlignmentFlag.AlignRight)

        hint = QLabel("drag & drop enabled")
        hint.setObjectName("topRightHint")
        hint.setAlignment(Qt.AlignmentFlag.AlignRight)

        rightbox.addWidget(tag)
        rightbox.addWidget(hint)
        topbar.addLayout(rightbox)

        # --- drop zone ---
        self.drop_zone = DropZone()
        self.drop_zone.clicked.connect(self.choose_file)

        # --- control card ---
        card = QFrame()
        card.setProperty("class", "card")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(22, 22, 22, 22)
        card_layout.setSpacing(16)

        grid = QGridLayout()
        grid.setHorizontalSpacing(16)
        grid.setVerticalSpacing(14)
        grid.setColumnStretch(1, 1)

        # Row 0: shift amount
        shift_caption = QLabel("Shift amount")
        shift_caption.setObjectName("sectionLabel")

        self.shift_slider = QSlider(Qt.Orientation.Horizontal)
        self.shift_slider.setRange(-MAX_SHIFT_SEMITONES, MAX_SHIFT_SEMITONES)
        self.shift_slider.setSingleStep(1)
        self.shift_slider.setValue(0)
        self.shift_slider.setFixedHeight(24)

        self.shift_spin = QDoubleSpinBox()
        self.shift_spin.setRange(-float(MAX_SHIFT_SEMITONES), float(MAX_SHIFT_SEMITONES))
        self.shift_spin.setDecimals(2)
        self.shift_spin.setSingleStep(0.1)
        self.shift_spin.setFixedWidth(96)

        self.unit_label = QLabel("semitones")
        self.unit_label.setObjectName("unitSuffix")

        self.shift_slider.valueChanged.connect(self._slider_moved)
        self.shift_spin.valueChanged.connect(self._spin_changed)

        shift_box = QHBoxLayout()
        shift_box.setSpacing(12)
        shift_box.addWidget(self.shift_slider, 1)
        shift_box.addWidget(self.shift_spin)
        shift_box.addWidget(self.unit_label)

        grid.addWidget(shift_caption, 0, 0)
        grid.addLayout(shift_box, 0, 1)

        # Row 1: units
        unit_caption = QLabel("Pitch units")
        unit_caption.setObjectName("sectionLabel")

        self.unit_combo = QComboBox()
        self.unit_combo.addItems(["Semitones", "Tones (1 tone = 2 semitones)"])
        self.unit_combo.setMinimumWidth(220)

        unit_box = QHBoxLayout()
        unit_box.addWidget(self.unit_combo)
        unit_box.addStretch(1)

        grid.addWidget(unit_caption, 1, 0)
        grid.addLayout(unit_box, 1, 1)

        # Row 2: resample
        sr_caption = QLabel("Resample")
        sr_caption.setObjectName("sectionLabel")

        self.sr_combo = QComboBox()
        self.sr_combo.addItems(["Keep original", "44100 Hz", "48000 Hz", "96000 Hz"])
        self.sr_combo.setMinimumWidth(220)

        sr_box = QHBoxLayout()
        sr_box.addWidget(self.sr_combo)
        sr_box.addStretch(1)

        grid.addWidget(sr_caption, 2, 0)
        grid.addLayout(sr_box, 2, 1)

        card_layout.addLayout(grid)

        divider = QFrame()
        divider.setObjectName("divider")
        divider.setFrameShape(QFrame.Shape.HLine)
        divider.setFixedHeight(1)
        card_layout.addWidget(divider)

        # Progress + status
        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.setFixedHeight(18)

        self.status_label = QLabel("Ready. Drop a file or click the box above.")
        self.status_label.setObjectName("statusLabel")

        # Buttons row
        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)

        self.btn_reset = QPushButton("Reset")
        self.btn_reset.clicked.connect(self.reset_shift)

        self.btn_export = QPushButton("Export…")
        self.btn_export.setObjectName("primaryButton")
        self.btn_export.setEnabled(False)
        self.btn_export.clicked.connect(self.export_file)

        btn_row.addWidget(self.status_label, 1)
        btn_row.addWidget(self.btn_reset)
        btn_row.addWidget(self.btn_export)

        card_layout.addWidget(self.progress)
        card_layout.addLayout(btn_row)

        # --- assemble ---
        root.addLayout(topbar)
        root.addWidget(self.drop_zone)
        root.addWidget(card)
        root.addStretch(1)

        self.init_font()
        self.unit_combo.currentIndexChanged.connect(self._unit_changed)

    # --- UI behavior ---
    def init_font(self) -> None:
        """Set a slightly larger base font for readability."""
        f = self.font()
        f.setPointSizeF(10.5)
        app = QApplication.instance()
        if app is not None:
            app.setFont(f)

    # --- slider/spin sync (block signals so fractional values survive) ---
    def _slider_moved(self, v: int) -> None:
        self.shift_spin.blockSignals(True)
        self.shift_spin.setValue(float(v))
        self.shift_spin.blockSignals(False)

    def _spin_changed(self, v: float) -> None:
        self.shift_slider.blockSignals(True)
        self.shift_slider.setValue(int(round(v)))
        self.shift_slider.blockSignals(False)

    def _unit_changed(self, index: int) -> None:
        """Convert the current value and keep ±MAX_SHIFT_SEMITONES effective."""
        value = self.shift_spin.value()
        if index == self._unit_index:
            return
        if index == 0:
            limit = MAX_SHIFT_SEMITONES
            value *= 2.0  # tones -> semitones
            self.unit_label.setText("semitones")
        else:
            limit = MAX_SHIFT_SEMITONES // 2
            value /= 2.0  # semitones -> tones
            self.unit_label.setText("tones")
        self._unit_index = index

        self.shift_slider.blockSignals(True)
        self.shift_spin.blockSignals(True)
        self.shift_slider.setRange(-limit, limit)
        self.shift_spin.setRange(-float(limit), float(limit))
        self.shift_spin.setValue(value)
        self.shift_slider.setValue(int(round(value)))
        self.shift_spin.blockSignals(False)
        self.shift_slider.blockSignals(False)

    def reset_shift(self) -> None:
        self.shift_spin.setValue(0.0)

    # --- drag & drop ---
    def dragEnterEvent(self, event: QDragEnterEvent) -> None:  # type: ignore[override]
        urls = event.mimeData().urls()
        if urls:
            ext = os.path.splitext(urls[0].toLocalFile())[1].lower()
            if ext in (SUPPORTED_AUDIO_EXTS | SUPPORTED_VIDEO_EXTS):
                self.drop_zone.set_drag_over(True)
                event.acceptProposedAction()
                return
        super().dragEnterEvent(event)

    def dragLeaveEvent(self, event) -> None:  # type: ignore[override]
        self.drop_zone.set_drag_over(False)
        super().dragLeaveEvent(event)

    def dropEvent(self, event: QDropEvent) -> None:  # type: ignore[override]
        self.drop_zone.set_drag_over(False)
        urls = event.mimeData().urls()
        if urls:
            path = urls[0].toLocalFile()
            self.set_input_file(path)

    # --- actions ---
    def choose_file(self) -> None:
        filt = (
            "Media Files (*.wav *.mp3 *.ogg *.flac *.m4a *.aac *.mp4 *.mov *.mkv)"
        )
        start_dir = os.path.dirname(self.in_path) if self.in_path else os.path.expanduser("~")
        path, _ = QFileDialog.getOpenFileName(
            self, "Choose media file", start_dir, filt
        )
        if path:
            self.set_input_file(path)

    def set_input_file(self, path: str) -> None:
        ext = os.path.splitext(path)[1].lower()
        if ext not in (SUPPORTED_AUDIO_EXTS | SUPPORTED_VIDEO_EXTS):
            QMessageBox.warning(
                self, "Unsupported file", f"File type not supported: {ext}"
            )
            return
        self.in_path = path
        self.drop_zone.set_loaded(os.path.basename(path))
        self.status_label.setText("File loaded. Adjust pitch and click Export…")
        self.progress.setValue(0)
        self.btn_export.setEnabled(True)

    def export_file(self) -> None:
        if not self.in_path:
            return

        in_ext = os.path.splitext(self.in_path)[1].lower()
        if in_ext in SUPPORTED_VIDEO_EXTS:
            filt = "MP4 Video (*.mp4)"
            default_suffix = ".mp4"
        else:
            filt = "Audio (*.wav *.mp3)"
            default_suffix = ".wav"

        out_path, _ = QFileDialog.getSaveFileName(
            self,
            "Export processed file",
            self.suggest_out_name(default_suffix),
            filt,
        )
        if not out_path:
            return

        semis = float(self.shift_spin.value())
        if self.unit_combo.currentIndex() == 1:
            # Tones → semitones
            semis *= 2.0

        sr_text = self.sr_combo.currentText()
        sr = None if sr_text == "Keep original" else int(sr_text.split()[0])

        cfg = JobConfig(
            in_path=self.in_path,
            out_path=out_path,
            semitone_shift=semis,
            sr=sr,
        )
        self.run_job(cfg)

    def suggest_out_name(self, default_suffix: str) -> str:
        assert self.in_path
        stem, _ = os.path.splitext(self.in_path)
        sign = "+" if self.shift_spin.value() >= 0 else "-"
        amt = abs(self.shift_spin.value())
        unit = "semi" if self.unit_combo.currentIndex() == 0 else "tone"
        return f"{stem}_pitch{sign}{amt:g}{unit}{default_suffix}"

    def run_job(self, cfg: JobConfig) -> None:
        if self.worker and self.worker.isRunning():
            QMessageBox.information(
                self, "Busy", "Please wait for the current job to finish."
            )
            return
        self.progress.setValue(0)
        self.status_label.setText("Processing… please wait.")
        self._set_busy(True)
        self.worker = ProcessorThread(cfg)
        self.worker.progressed.connect(self.on_progress)
        self.worker.finished_ok.connect(self.on_done)
        self.worker.failed.connect(self.on_fail)
        self.worker.start()

    def _set_busy(self, busy: bool) -> None:
        self.btn_export.setEnabled(not busy and self.in_path is not None)
        self.btn_reset.setEnabled(not busy)
        self.drop_zone.setEnabled(not busy)

    def closeEvent(self, event) -> None:  # type: ignore[override]
        if self.worker and self.worker.isRunning():
            QMessageBox.information(
                self, "Busy", "Please wait for the current job to finish before closing."
            )
            event.ignore()
            return
        super().closeEvent(event)

    @Slot(int)
    def on_progress(self, v: int) -> None:
        self.progress.setValue(v)

    @Slot(str)
    def on_done(self, out_path: str) -> None:
        self.progress.setValue(100)
        self._set_busy(False)
        base = os.path.basename(out_path)
        self.status_label.setText(f"Done. Exported to: {base}")
        QMessageBox.information(self, "Done", f"Exported to:\n{out_path}")

    @Slot(str)
    def on_fail(self, msg: str) -> None:
        self.progress.setValue(0)
        self._set_busy(False)
        self.status_label.setText("Failed. Check the error message.")
        QMessageBox.critical(self, "Failed", msg)


def main() -> None:
    app = QApplication(sys.argv)

    # Lock the look: Fusion style ignores the platform theme engine, and the
    # fixed palette + app-wide stylesheet keep every widget (including
    # dialogs and popups) on our dark theme regardless of the OS theme.
    app.setStyle("Fusion")
    app.setPalette(make_dark_palette())
    app.setStyleSheet(STYLESHEET)

    # Qt 6.8+: force the dark color scheme (also darkens window frames)
    hints = app.styleHints()
    if hasattr(hints, "setColorScheme") and hasattr(Qt, "ColorScheme"):
        try:
            hints.setColorScheme(Qt.ColorScheme.Dark)
        except Exception:
            pass

    icon_path = resource_path("icons", "icon.png")
    if os.path.exists(icon_path):
        app.setWindowIcon(QIcon(icon_path))

    w = PitchShifterApp()
    w.show()
    force_dark_title_bar(w)
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
