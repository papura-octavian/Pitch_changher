"""
PitchShifter — Windows and Linux

- Load MP3/WAV/MP4
- Shift pitch by semitones (±24)
- Choose semitone or tone units (1 tone = 2 semitones)
- Export WAV/MP3 or MP4 (video remux with shifted audio)

Install in venv:
    python -m pip install --upgrade pip setuptools wheel
    pip install PySide6 librosa soundfile numpy pydub

Requires FFmpeg in PATH for MP3/MP4.
"""
from __future__ import annotations

import os
import sys
import tempfile
import traceback
from dataclasses import dataclass
from typing import Optional

import numpy as np
import librosa
import soundfile as sf
from pydub import AudioSegment

from PySide6.QtCore import Qt, QThread, Signal, Slot
from PySide6.QtGui import QDragEnterEvent, QDropEvent
from PySide6.QtWidgets import (
    QApplication,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
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

MAX_SHIFT_SEMITONES = 24


def get_ffmpeg_path() -> str:
    """Get path to ffmpeg executable, preferring bundled version."""
    import platform
    import shutil
    
    # Get the directory where this script is located
    if getattr(sys, 'frozen', False):
        # Running as compiled executable (PyInstaller)
        # sys._MEIPASS is the temporary directory where PyInstaller extracts files
        base_dir = sys._MEIPASS
    else:
        # Running as script
        base_dir = os.path.dirname(os.path.abspath(__file__))
    
    system = platform.system().lower()
    if system == "windows":
        bundled_ffmpeg = os.path.join(base_dir, "ffmpeg", "windows", "ffmpeg.exe")
    else:
        bundled_ffmpeg = os.path.join(base_dir, "ffmpeg", "linux", "ffmpeg")
    
    # Check if bundled ffmpeg exists and is executable
    if os.path.exists(bundled_ffmpeg):
        # On Windows, .exe files are always executable
        # On Linux, check if it's executable
        if system == "windows" or os.access(bundled_ffmpeg, os.X_OK):
            return bundled_ffmpeg
    
    # Fallback to system ffmpeg in PATH
    if shutil.which("ffmpeg"):
        return "ffmpeg"
    
    # Last resort: return "ffmpeg" and hope it's in PATH
    return "ffmpeg"


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
    def _process_audio(self, in_audio_path: str, out_audio_path: str) -> None:
        self.progressed.emit(10)

        # mono=False -> y is (n_channels, n_samples) or (n_samples,)
        y, sr = librosa.load(in_audio_path, sr=self.cfg.sr, mono=False)
        self.progressed.emit(30)

        if y.ndim == 1:
            y_list = [y]
        else:
            # y shape: (channels, samples)
            y_list = [y[ch, :] for ch in range(y.shape[0])]

        processed_channels = []
        for sig in y_list:
            sig = np.ascontiguousarray(sig.reshape(-1))
            n = len(sig)

            # Ensure enough samples for STFT inside pitch_shift
            if n < 2048:
                pad = 2048 - n
                sig = np.pad(sig, (0, pad))

            shifted = librosa.effects.pitch_shift(
                sig,
                sr=sr,
                n_steps=self.cfg.semitone_shift,
            )
            processed_channels.append(shifted)

        if len(processed_channels) > 1:
            # (samples, channels) for soundfile
            Y = np.stack(processed_channels, axis=1)
        else:
            Y = processed_channels[0]

        self.progressed.emit(70)

        out_ext = os.path.splitext(out_audio_path)[1].lower()
        if out_ext == ".wav":
            sf.write(out_audio_path, Y, sr)
        elif out_ext == ".mp3":
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
                tmp_path = tmp.name
            sf.write(tmp_path, Y, sr)
            AudioSegment.from_wav(tmp_path).export(out_audio_path, format="mp3")
            os.remove(tmp_path)
        else:
            if not out_audio_path.lower().endswith(".wav"):
                out_audio_path = out_audio_path + ".wav"
                self.cfg.out_path = out_audio_path
            sf.write(out_audio_path, Y, sr)

        self.progressed.emit(90)

    def _process_video(self) -> None:
        # Use ffmpeg CLI to avoid heavy Python video dependencies
        import subprocess

        self.progressed.emit(12)
        in_path = self.cfg.in_path
        out_path = self.cfg.out_path

        with tempfile.TemporaryDirectory() as td:
            temp_audio = os.path.join(td, "orig_audio.wav")
            temp_shifted = os.path.join(td, "shifted.wav")

            # 1) Extract audio to WAV (keep original rate & channels)
            ffmpeg_path = get_ffmpeg_path()
            cmd1 = [
                ffmpeg_path,
                "-y",
                "-i",
                in_path,
                "-vn",
                "-acodec",
                "pcm_s16le",
                temp_audio,
            ]
            p1 = subprocess.run(
                cmd1,
                shell=False,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            if p1.returncode != 0:
                raise RuntimeError(
                    "ffmpeg extract audio failed:\n" + p1.stderr.decode(errors="ignore")
                )
            self.progressed.emit(40)

            # 2) Process audio with librosa
            self._process_audio(temp_audio, temp_shifted)
            self.progressed.emit(70)

            # 3) Mux back shifted audio with original video stream (copy video)
            if not out_path.lower().endswith(".mp4"):
                out_path = out_path + ".mp4"
                self.cfg.out_path = out_path

            cmd2 = [
                ffmpeg_path,
                "-y",
                "-i",
                in_path,
                "-i",
                temp_shifted,
                "-c:v",
                "copy",
                "-map",
                "0:v:0",
                "-map",
                "1:a:0",
                "-shortest",
                "-c:a",
                "aac",
                out_path,
            ]
            p2 = subprocess.run(
                cmd2,
                shell=False,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            if p2.returncode != 0:
                raise RuntimeError(
                    "ffmpeg mux failed:\n" + p2.stderr.decode(errors="ignore")
                )
            self.progressed.emit(95)


class NeonFrame(QFrame):
    def __init__(self) -> None:
        super().__init__()
        self.setFrameShape(QFrame.Shape.StyledPanel)
        # Style using a Qt property so we can target it in the stylesheet
        self.setProperty("class", "neon")


class PitchShifterApp(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.setAcceptDrops(True)
        self.setWindowTitle("PitchShifter")
        self.setMinimumSize(1000, 640)

        self.in_path: Optional[str] = None
        self.thread: Optional[ProcessorThread] = None

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 24, 24, 24)
        root.setSpacing(18)

        # Top bar: Title on left, small info on right
        topbar = QHBoxLayout()

        titlebox = QVBoxLayout()
        title = QLabel("PitchShifter")
        title.setAlignment(Qt.AlignmentFlag.AlignLeft)
        title.setObjectName("title")

        subtitle = QLabel("Drop audio/video, shift pitch, export")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignLeft)
        subtitle.setObjectName("subtitle")

        titlebox.addWidget(title)
        titlebox.addWidget(subtitle)
        topbar.addLayout(titlebox, 1)

        # Right info area (no controls, just futuristic tags)
        rightbox = QVBoxLayout()
        rightbox.setSpacing(2)
        rightbox.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        tag = QLabel("FFMPEG · LIBROSA")
        tag.setObjectName("topRightTag")
        tag.setAlignment(Qt.AlignmentFlag.AlignRight)

        hint = QLabel("Drag & drop enabled")
        hint.setObjectName("topRightHint")
        hint.setAlignment(Qt.AlignmentFlag.AlignRight)

        rightbox.addWidget(tag)
        rightbox.addWidget(hint)
        topbar.addLayout(rightbox)

        # File bar
        file_bar = QHBoxLayout()
        file_bar.setSpacing(12)

        self.file_label = QLabel("Drop a file here or click Open…")
        self.file_label.setObjectName("fileLabel")

        btn_open = QPushButton("Open…")
        btn_open.setObjectName("primaryButton")
        btn_open.clicked.connect(self.choose_file)

        file_bar.addWidget(self.file_label, 1)
        file_bar.addWidget(btn_open)

        # Main control card
        ctrl_frame = NeonFrame()
        ctrl_layout = QVBoxLayout(ctrl_frame)
        ctrl_layout.setContentsMargins(18, 18, 18, 18)
        ctrl_layout.setSpacing(18)

        # Unit row
        unit_row = QHBoxLayout()
        unit_row.setSpacing(12)

        unit_caption = QLabel("Pitch units")
        unit_caption.setObjectName("sectionLabel")
        unit_row.addWidget(unit_caption)

        self.unit_combo = QComboBox()
        self.unit_combo.addItems(["Semitones", "Tones (×2)"])
        self.unit_combo.setMinimumWidth(160)
        unit_row.addWidget(self.unit_combo)
        unit_row.addStretch(1)

        # Shift row
        shift_row = QHBoxLayout()
        shift_row.setSpacing(12)

        shift_caption = QLabel("Shift amount")
        shift_caption.setObjectName("sectionLabel")
        shift_row.addWidget(shift_caption)

        self.shift_slider = QSlider(Qt.Orientation.Horizontal)
        self.shift_slider.setRange(-MAX_SHIFT_SEMITONES, MAX_SHIFT_SEMITONES)
        self.shift_slider.setSingleStep(1)
        self.shift_slider.setValue(0)
        self.shift_slider.setFixedHeight(24)

        self.shift_spin = QDoubleSpinBox()
        self.shift_spin.setRange(-float(MAX_SHIFT_SEMITONES), float(MAX_SHIFT_SEMITONES))
        self.shift_spin.setDecimals(2)
        self.shift_spin.setSingleStep(0.1)

        self.shift_slider.valueChanged.connect(
            lambda v: self.shift_spin.setValue(float(v))
        )
        self.shift_spin.valueChanged.connect(
            lambda v: self.shift_slider.setValue(int(round(v)))
        )

        shift_row.addWidget(self.shift_slider, 1)
        shift_row.addWidget(self.shift_spin)

        self.unit_label = QLabel("semitones")
        self.unit_label.setObjectName("unitLabel")
        shift_row.addWidget(self.unit_label)

        # Sample rate row
        sr_row = QHBoxLayout()
        sr_row.setSpacing(12)

        sr_caption = QLabel("Resample")
        sr_caption.setObjectName("sectionLabel")
        sr_row.addWidget(sr_caption)

        self.sr_combo = QComboBox()
        self.sr_combo.addItems(["Keep original", "44100", "48000", "96000"])
        self.sr_combo.setMinimumWidth(160)
        sr_row.addWidget(self.sr_combo)
        sr_row.addStretch(1)

        # Progress + status
        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.setFixedHeight(26)

        self.status_label = QLabel("Ready. Drop a file or click Open…")
        self.status_label.setObjectName("statusLabel")
        self.status_label.setAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )

        # Export row
        out_row = QHBoxLayout()
        self.btn_export = QPushButton("Export…")
        self.btn_export.setObjectName("primaryButton")
        self.btn_export.setEnabled(False)
        self.btn_export.clicked.connect(self.export_file)
        out_row.addStretch(1)
        out_row.addWidget(self.btn_export)

        # Build control layout
        ctrl_layout.addLayout(unit_row)
        ctrl_layout.addLayout(shift_row)
        ctrl_layout.addLayout(sr_row)
        ctrl_layout.addWidget(self.progress)
        ctrl_layout.addWidget(self.status_label)
        ctrl_layout.addLayout(out_row)

        # Assemble root layout
        root.addLayout(topbar)
        root.addLayout(file_bar)
        root.addWidget(ctrl_frame)
        root.addStretch(1)

        # Fixed dark theme + base font
        self.apply_theme()
        self.init_font()

        # Update unit label when switching combo
        self.unit_combo.currentIndexChanged.connect(
            lambda i: self.unit_label.setText("semitones" if i == 0 else "tones")
        )

    # --- UI behavior ---
    def init_font(self) -> None:
        """Set a slightly larger base font for readability."""
        f = self.font()
        f.setPointSizeF(11.0)
        app = QApplication.instance()
        if app is not None:
            app.setFont(f)

    def apply_theme(self) -> None:
        """Single dark futuristic theme."""
        bg = "#020617"      # deep navy / near-black
        fg = "#e5f4ff"
        sub = "#7ea0c8"
        accent1 = "#38bdf8"  # cyan-ish
        accent2 = "#a855f7"  # purple
        panel = "#020617"
        border = "#1f2937"

        self.setStyleSheet(
            f"""
            QWidget {{
                background: radial-gradient(circle at top left, #0b1120, {bg});
                color: {fg};
                font-family: Segoe UI, Inter, Roboto, system-ui;
            }}
            #title {{
                font-size: 34px;
                font-weight: 900;
                letter-spacing: 1px;
                color: {accent1};
            }}
            #subtitle {{
                font-size: 14px;
                color: {sub};
                margin-top: 4px;
                margin-bottom: 8px;
            }}
            #fileLabel {{
                color: {sub};
                font-size: 14px;
            }}
            #topRightTag {{
                font-size: 11px;
                color: {sub};
                font-weight: 600;
            }}
            #topRightHint {{
                font-size: 11px;
                color: {sub};
            }}
            #sectionLabel {{
                font-weight: 600;
                font-size: 14px;
            }}
            #unitLabel {{
                color: {sub};
                min-width: 70px;
            }}
            #statusLabel {{
                font-size: 12px;
                color: {sub};
                margin-top: 4px;
            }}
            QFrame[class="neon"] {{
                border: 1px solid rgba(148,163,184,0.35);
                border-radius: 18px;
                padding: 18px;
                background: qradialgradient(
                    cx:0.2, cy:0.0, radius: 1.4,
                    fx:0.1, fy:0.0,
                    stop:0 rgba(56,189,248,0.16),
                    stop:0.4 rgba(15,23,42,0.96),
                    stop:1 {panel}
                );
            }}
            QProgressBar {{
                background: rgba(15,23,42,0.7);
                border: 1px solid {border};
                border-radius: 12px;
                height: 26px;
                text-align: center;
            }}
            QProgressBar::chunk {{
                border-radius: 12px;
                background: qlineargradient(
                    x1:0, y1:0, x2:1, y2:1,
                    stop:0 {accent1}, stop:1 {accent2}
                );
            }}
            QPushButton {{
                background: qlineargradient(
                    x1:0, y1:0, x2:1, y2:1,
                    stop:0 rgba(56,189,248,0.12),
                    stop:1 rgba(168,85,247,0.16)
                );
                border: 1px solid rgba(148,163,184,0.55);
                border-radius: 14px;
                padding: 10px 18px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                border-color: {accent1};
            }}
            QPushButton#primaryButton {{
                background: qlineargradient(
                    x1:0, y1:0, x2:1, y2:1,
                    stop:0 {accent1},
                    stop:1 {accent2}
                );
                color: white;
            }}
            QPushButton#primaryButton:disabled {{
                background: rgba(30,41,59,0.9);
                color: rgba(148,163,184,0.7);
                border-color: {border};
            }}
            QComboBox, QDoubleSpinBox {{
                background: rgba(15,23,42,0.9);
                border: 1px solid rgba(148,163,184,0.4);
                border-radius: 10px;
                padding: 6px 10px;
                min-height: 30px;
            }}
            QComboBox::drop-down {{
                border: none;
                width: 18px;
            }}
            QComboBox::down-arrow {{
                width: 10px;
                height: 10px;
            }}
            QSlider::groove:horizontal {{
                height: 8px;
                background: rgba(30,64,175,0.8);
                border-radius: 4px;
                margin: 0 4px;
            }}
            QSlider::handle:horizontal {{
                width: 22px;
                height: 22px;
                margin: -7px 0;
                background: qradialgradient(
                    cx:0.3, cy:0.3, radius: 0.8,
                    fx:0.3, fy:0.3,
                    stop:0 {accent2},
                    stop:1 {accent1}
                );
                border: 1px solid {accent1};
                border-radius: 11px;
            }}
            QSlider::sub-page:horizontal {{
                background: qlineargradient(
                    x1:0, y1:0, x2:1, y2:0,
                    stop:0 {accent1}, stop:1 {accent2}
                );
                border-radius: 4px;
            }}
            QLabel {{
                font-size: 14px;
            }}
        """
        )

    # --- drag & drop ---
    def dragEnterEvent(self, event: QDragEnterEvent) -> None:  # type: ignore[override]
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            super().dragEnterEvent(event)

    def dropEvent(self, event: QDropEvent) -> None:  # type: ignore[override]
        urls = event.mimeData().urls()
        if urls:
            path = urls[0].toLocalFile()
            self.set_input_file(path)

    # --- actions ---
    def choose_file(self) -> None:
        filt = (
            "Media Files (*.wav *.mp3 *.ogg *.flac *.m4a *.aac *.mp4 *.mov *.mkv)"
        )
        path, _ = QFileDialog.getOpenFileName(
            self, "Choose media file", os.getcwd(), filt
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
        base = os.path.basename(path)
        self.file_label.setText(f"Loaded: {base}")
        self.status_label.setText(
            "File loaded. Adjust pitch settings and click Export…"
        )
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

        sr_choice = self.sr_combo.currentText()
        sr = None if sr_choice == "Keep original" else int(sr_choice)

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
        if self.thread and self.thread.isRunning():
            QMessageBox.information(
                self, "Busy", "Please wait for the current job to finish."
            )
            return
        self.progress.setValue(0)
        self.status_label.setText("Processing… please wait.")
        self.thread = ProcessorThread(cfg)
        self.thread.progressed.connect(self.on_progress)
        self.thread.finished_ok.connect(self.on_done)
        self.thread.failed.connect(self.on_fail)
        self.thread.start()

    @Slot(int)
    def on_progress(self, v: int) -> None:
        self.progress.setValue(v)

    @Slot(str)
    def on_done(self, out_path: str) -> None:
        self.progress.setValue(100)
        base = os.path.basename(out_path)
        self.status_label.setText(f"Done. Exported to: {base}")
        QMessageBox.information(self, "Done", f"Exported to:\n{out_path}")

    @Slot(str)
    def on_fail(self, msg: str) -> None:
        self.progress.setValue(0)
        self.status_label.setText("Failed. Check the error message.")
        QMessageBox.critical(self, "Failed", msg)


def main() -> None:
    app = QApplication(sys.argv)
    w = PitchShifterApp()
    w.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
