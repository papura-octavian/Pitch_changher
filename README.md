# PitchShifter

PitchShifter is a small desktop app (Windows & Linux) for quick pitch shifting of audio and video files.

- Load **MP3 / WAV / OGG / FLAC / M4A / AAC / MP4 / MOV / MKV**
- Shift pitch by **±24 semitones** (or **±12 tones**)
- Make quiet tracks louder: volume in **dB** or **auto-normalize**, without clipping
- Export as **WAV / MP3** (for audio) or **MP4** (for video, with remuxed video stream)
- Simple, drag-and-drop friendly UI built with **PySide6**

---

## Features

- 🎛 **Pitch control**
  - Slider and numeric input for precise control (fractional values supported)
  - Switch between **Semitones** and **Tones (1 tone = 2 semitones)**
- 🎵 **Audio formats**
  - Input: `.wav`, `.mp3`, `.ogg`, `.flac`, `.m4a`, `.aac`
  - Output: `.wav`, `.mp3`
- 🎬 **Video formats**
  - Input: `.mp4`, `.mov`, `.mkv`
  - Output: `.mp4` — video stream is copied; only the audio is pitch-shifted and remuxed
- 🎚 **Resampling**
  - Keep the original sample rate or convert to `44100`, `48000`, or `96000` Hz
- 🔊 **Volume**
  - Raise or lower the volume from **−12 to +24 dB**
  - **Auto-normalize** brings any file to a standard loudness (−14 LUFS)
  - A true-peak limiter keeps peaks under −1 dB, so boosting never clips or distorts
  - Works on audio and video, together with a pitch shift or on its own
- 🖱 **User interface**
  - Dark, modern UI with drag & drop support
  - Progress bar + status messages during processing

---

## Installation

### 🚀 Quick Install (Recommended)

Download the pre-built Windows installer from the [Releases](https://github.com/papura-octavian/Pitch_changher/releases) page:

- **Windows**: Download `PitchShifter-Setup-*.exe` and run it.
- **Linux**: build from source (see below) or run `./build_appimage.sh` to create an AppImage locally.

FFmpeg is bundled with the installer — no separate installation needed.

---

### 🔧 Running from Source

1. **Clone this repository**

   ```bash
   git clone https://github.com/papura-octavian/Pitch_changher.git
   cd Pitch_changher
   ```

2. **Create and activate a virtual environment**

   ```bash
   python -m venv .venv
   # Windows
   .venv\Scripts\activate
   # Linux / macOS
   source .venv/bin/activate
   ```

3. **Install dependencies**

   ```bash
   python -m pip install --upgrade pip setuptools wheel
   pip install -r requirements.txt
   ```

4. **Get FFmpeg** (one of the two):

   ```bash
   # Option A: download a bundled copy into ffmpeg/<os>/
   python scripts/get_ffmpeg.py

   # Option B: install FFmpeg system-wide and make sure it's in PATH
   ```

5. **Run the app**

   ```bash
   python Pitch_Changher.py
   ```

---

## Building Installers

See [BUILD.md](BUILD.md) for full instructions.

- **Windows**: `build_installer_windows.bat` (requires [Inno Setup](https://jrsoftware.org/isdl.php)) → `installer/PitchShifter-Setup-*.exe`
- **Linux**: `./build_appimage.sh [version]` → `PitchShifter-[version]-x86_64.AppImage`

### Automated Builds (GitHub Actions)

The Windows installer is built automatically when you push a version tag:

```bash
git tag v1.2.1
git push origin v1.2.1
```

The **Build Installers** workflow builds the Windows installer and attaches it to the GitHub Release for that tag. You can also trigger it manually from the **Actions** tab (artifact only, no release).

---

## Usage

1. **Load a file** — drag & drop into the window, or click **Open…**
2. **Adjust pitch** — use the slider or the numeric box:
   - Positive values → higher pitch, negative → lower
   - Units: **Semitones** (±24) or **Tones** (±12, 1 tone = 2 semitones)
3. **Set resample (optional)** — keep original or convert to 44100/48000/96000 Hz
4. **Export** — click **Export…**, choose name and format, wait for the progress bar to finish

---

## How it Works (Technical Overview)

- Input audio is decoded to WAV via **FFmpeg** (bundled copy preferred, PATH as fallback), then loaded with **librosa** (all channels preserved, optional resampling).
- The whole multi-channel signal is processed with `librosa.effects.pitch_shift`.
- Output is written with **soundfile** (WAV) or encoded to MP3 via FFmpeg (`libmp3lame`).
- For video: FFmpeg extracts the audio → it is pitch-shifted → FFmpeg muxes it back with the original (copied) video stream into a new `.mp4`.

---

## Troubleshooting

- **"ffmpeg … failed"** — run `python scripts/get_ffmpeg.py` to download a bundled FFmpeg, or install FFmpeg and check `ffmpeg -version` works in a terminal.
- **Windows Defender blocks the installer** — unsigned installers can trigger SmartScreen; choose "More info" → "Run anyway", or build from source.
- **AppImage doesn't run** — make sure it's executable (`chmod +x`) and `libfuse2` is installed (`sudo apt install libfuse2`).
- **No sound or strange output** — check the input file is valid and not DRM-protected; try **Keep original** resample and a smaller shift (extreme values sound unnatural).

---

## Roadmap / Ideas

- Presets for common pitch shifts (e.g. +3, +5, -3 semitones)
- A simple waveform or level meter
- Batch processing for multiple files

---

Happy pitch-shifting! 🎧
