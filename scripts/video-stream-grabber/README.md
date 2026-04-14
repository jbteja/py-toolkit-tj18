# Video Stream Grabber

## 🚀 Why This Script?

Downloading modern web streams isn't as simple as "Right-click -> Save As." Most platforms use HLS (HTTP Live Streaming), where the video is delivered via an .m3u8 playlist.

An .m3u8 file doesn't actually contain video; it is a manifest that points to hundreds of small .ts (Transport Stream) chunks. To download these manually, you would have to:

- Download every individual segment.
- Decrypt them (if needed).
- Stitch them together in the correct order.

This script automates that entire headache. By leveraging ffmpeg, it handles the parsing, segment downloading, and seamless merging of these streams into a single, high-quality video file.

## ✨ Features

1. Dual-Mode Processing:
    - Raw Capture: Fast, lossless capture saved as .ts.
    - Transcoding: High-efficiency encoding using libx265 for smaller file sizes.

2. Environment Safety: Built-in system checks for dependencies and directory structures.

3. Filtered Logging: Clean console output that skips FFmpeg "noise" and only shows critical HTTP errors.

## 🛠 Prerequisites

Preferably, Always open the project using devcontainer in VSCode to ensure all dependencies are properly installed and configured.

When not using a devcontainer, make sure you have Python 3.12+ installed along with pip. You can create a virtual environment and install the required dependencies.

### Install FFmpeg (Ubuntu/Debian)

```bash
$ sudo apt update
$ sudo apt install ffmpeg -y
```

## ⚙️ Configuration

The configuration is stored in `config.yaml`. Here you can specify the transcoding options and the list of videos to process. Each video entry consists of a title and a corresponding URL (either direct video URL or m3u8 playlist).

## 📺 Usage

1. Add your links to config.yaml.

2. Run the script:

    ```bash
    python app.py
    ```

3. Check your downloads/ folder for the finished files.

## 📋 Logs

### Positive case -> Successful download and transcoding

```bash
$ python app.py

2026-04-14 14:04:55 | INFO     | __main__:check_binary:29 - Binary verified and available: ffmpeg
2026-04-14 14:04:55 | INFO     | __main__:main:179 - Output directory is ready: /workspaces/py-toolkit-tj18/scripts/downloads
2026-04-14 14:04:55 | INFO     | __main__:run_command:56 - Starting task: Transcoding 'Push-ups in a Gym' to .mp4
2026-04-14 14:04:13 | INFO     | __main__:run_command:61 - Completed: Transcoding 'Push-ups in a Gym' to .mp4

$ ls ../downloads               
'Push-ups in a Gym.mp4'
```

### Negative case (invalid URL) -> Failed download with HTTP errors

```bash
$ python app.py

2026-04-14 14:04:37 | INFO     | __main__:check_binary:29 - Binary verified and available: ffmpeg
2026-04-14 14:04:37 | INFO     | __main__:main:179 - Output directory is ready: /workspaces/py-toolkit-tj18/scripts/downloads
2026-04-14 14:04:37 | INFO     | __main__:run_command:56 - Starting task: Capturing raw stream for 'Drone Landscape'
2026-04-14 14:04:37 | WARNING  | __main__:run_command:64 - Failed: Capturing raw stream for 'Drone Landscape'
2026-04-14 14:04:37 | ERROR    | __main__:run_command:79 - Errors found:
[https @ 0x561ca71e2c40] HTTP error 403 Forbidden
Server returned 403 Forbidden (access denied)
2026-04-14 14:04:37 | WARNING  | __main__:process_video_library:146 - Skipping 'Drone Landscape' due to processing error.

2026-04-14 14:04:37 | INFO     | __main__:run_command:56 - Starting task: Capturing raw stream for 'Mindset Roadmap'
2026-04-14 14:04:37 | WARNING  | __main__:run_command:64 - Failed: Capturing raw stream for 'Mindset Roadmap'
2026-04-14 14:04:37 | ERROR    | __main__:run_command:79 - Errors found:
[https @ 0x5602905e3c40] HTTP error 404 Not Found
Server returned 404 Not Found
2026-04-14 14:04:37 | WARNING  | __main__:process_video_library:146 - Skipping 'Mindset Roadmap' due to processing error.
```
