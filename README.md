**Media Encoder**

A Python-based video encoding and processing tool that utilizes FFmpeg to encode videos from input files. The tool also provides features such as language support, HDR settings, and error handling.

**Features:**

*   **Video Encoding:** Utilizes FFmpeg to encode videos at high quality with customizable settings.
*   **Language Support:** Supports multiple languages for subtitles and audio.
*   **HDR Settings:** Allows users to customize HDR settings for optimal video quality.
*   **Error Handling:** Provides error handling capabilities to ensure smooth operation.

**Usage:**

1.  Clone the repository: `git clone https://github.com/theazad23/media_encoder.git`
2.  Install required dependencies: `pip install -r requirements.txt`
3.  Run the application using Python: `python main.py`

**Configuring Encoding Settings:**

You can configure encoding settings by creating a YAML configuration file (`encoding_config.yaml`) with the following structure:
```yaml
video_codec: libx265
video_preset: veryslow
video_crf: 14
max_threads: 16
gpu_device: 0
copy_audio: True
copy_subtitles: True
preferred_languages: ["en", "fr"]
preserve_hdr: True
force_10bit: True
hdr_settings:
  ...
ffmpeg_path: /path/to/ffmpeg
ffprobe_path: /path/to/ffprobe
```
**Example Output File Path:**

The output file will be generated at the specified path, e.g., `/path/to/output/file.mkv`.