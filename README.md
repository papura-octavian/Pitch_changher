```markdown
# PitchShifter

PitchShifter is a small desktop app (Windows & Linux) for quick pitch shifting of audio and video files.

- Load **MP3 / WAV / OGG / FLAC / M4A / AAC / MP4 / MOV / MKV**
- Shift pitch by **±24 semitones** (or tones, if you prefer)
- Choose **semitones** or **tones (1 tone = 2 semitones)**
- Export as **WAV / MP3** (for audio) or **MP4** (for video, with remuxed video stream)
- Simple, drag-and-drop friendly UI built with **PySide6**

---

## Features

- 🎛 **Pitch control**
  - Slider and numeric input for precise control (±24 semitones)
  - Switch between **Semitones** and **Tones (×2)** units
- 🎵 **Audio formats**
  - Input: `.wav`, `.mp3`, `.ogg`, `.flac`, `.m4a`, `.aac`
  - Output: `.wav`, `.mp3`
- 🎬 **Video formats**
  - Input: `.mp4`, `.mov`, `.mkv`
  - Output: `.mp4`
  - Video stream is copied; only the audio is pitch-shifted and remuxed
- 🎚 **Resampling (sample rate)**
  - Option to keep the original sample rate or convert to `44100`, `48000`, or `96000` Hz
- 🖱 **User interface**
  - Dark, modern, “futuristic” UI
  - Drag & drop support for quick loading
  - Progress bar + status messages during processing

---

## Requirements

- **Python**: 3.9+ (recommended)
- **OS**: Windows or Linux
- **FFmpeg**:
  - Required and must be available in your `PATH`
  - Used for extracting audio from video and remuxing processed audio back into MP4

### Python Dependencies

Install these with `pip`:

- `PySide6` – GUI framework
- `librosa` – audio processing (pitch shifting)
- `soundfile` – reading/writing audio files
- `numpy` – numerical operations
- `pydub` – exporting MP3 via ffmpeg

---

## Installation

1. **Clone this repository**

   ```bash
   git clone https://github.com/<your-username>/pitchshifter.git
   cd pitchshifter
````

2. **Create and activate a virtual environment (recommended)**

   ```bash
   python -m venv .venv
   # Windows
   .venv\Scripts\activate
   # Linux / macOS
   source .venv/bin/activate
   ```

3. **Upgrade basic tooling**

   ```bash
   python -m pip install --upgrade pip setuptools wheel
   ```

4. **Install dependencies**

   ```bash
   pip install PySide6 librosa soundfile numpy pydub
   ```

5. **Install FFmpeg**

   * **Windows**: Download from the official FFmpeg site, extract it, and add the `bin` directory to your `PATH`.
   * **Linux**: Usually available via package manager, for example:

     ```bash
     sudo apt install ffmpeg
     ```

   You should be able to run:

   ```bash
   ffmpeg -version
   ```

   from a terminal/command prompt.

---

## Running the App

From the project folder, run:

```bash
python pitchshifter.py
```

(or whatever the main script file is named in your repo).

The PitchShifter window should appear.

---

## Usage

1. **Load a file**

   * Drag & drop an audio/video file into the window, **or**
   * Click **“Open…”** and select a supported file.

2. **Adjust pitch**

   * Use the **slider** or **numeric box** to set the pitch shift:

     * Positive values → higher pitch
     * Negative values → lower pitch
   * Choose **Semitones** or **Tones (×2)** in the **Pitch units** dropdown:

     * 1 tone = 2 semitones
     * Example: `+2 tones` = `+4 semitones`

3. **Set resample (optional)**

   * **Keep original**: keeps the original sample rate of the file.
   * `44100 / 48000 / 96000`: audio will be resampled to the selected rate before processing and export.
   * This does **not** change the amount of pitch shift, only the sample rate of the processed audio.

4. **Export**

   * Click **“Export…”**
   * Choose an output file name and format:

     * For audio inputs: `.wav` or `.mp3`
     * For video inputs: `.mp4`
   * Wait for the progress bar to reach 100% and the “Done” dialog to appear.

---

## How it Works (Technical Overview)

* Audio is loaded using **librosa**:

  * Mono or multi-channel (stereo, etc.) is supported.
  * When resample is set (44100, 48000, 96000), librosa resamples to that sample rate.
* For each channel:

  * The signal is padded if necessary and processed with
    `librosa.effects.pitch_shift` to apply `n_steps` semitones.
* Audio is written using **soundfile**:

  * For `.wav`, the processed multi-channel array is saved directly.
  * For `.mp3`, a temporary `.wav` is created and then converted via **pydub** (which uses ffmpeg under the hood).
* For video:

  1. `ffmpeg` extracts the original audio to a temporary `.wav`.
  2. The temp `.wav` is processed the same as a normal audio file.
  3. `ffmpeg` muxes the processed audio back together with the original video stream into a new `.mp4`.

---

## Troubleshooting

* **Unknown property ...** in the console
  Qt style sheets are CSS-like but not full CSS. If you add unsupported properties, Qt will log warnings. The shipped version of the app only uses supported properties.

* **“ffmpeg extract audio failed” / “ffmpeg mux failed”**

  * Check that `ffmpeg` is installed and accessible in `PATH`.
  * Try running `ffmpeg -version` in a terminal.

* **No sound or strange output**

  * Check the input file is valid and not DRM-protected.
  * Try leaving **Resample** on **Keep original**.
  * Try a smaller pitch shift (extreme values can sometimes sound unnatural).

---

## License

Add your license of choice here, for example:

* MIT, Apache-2.0, etc.

---

## Roadmap / Ideas

* Presets for common pitch shifts (e.g. +3, +5, -3 semitones)
* A simple waveform or level meter
* Batch processing for multiple files

---

Happy pitch-shifting! 🎧
