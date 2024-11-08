# Media Encoder

A high-performance media encoding tool designed for transcoding Blu-ray and video content with advanced HDR preservation capabilities.

## Features

- **HDR Support**
  - Preserves HDR metadata including HDR10, HDR10+, HLG, and Dolby Vision
  - Automatic HDR format detection
  - Configurable HDR settings with format fallback options
  - Support for multiple Dolby Vision profiles (5, 8.1, 8.2, 8.4)

- **Blu-ray Processing**
  - Automatic main feature detection from BDMV structure
  - Playlist parsing and analysis
  - Handles multi-segment features
  - Preserves chapter information

- **Advanced Encoding**
  - High-quality x265 encoding with optimized presets
  - GPU acceleration support (NVENC)
  - Configurable encoding parameters
  - 10-bit color depth support
  - Multi-threaded processing

- **Audio and Subtitle Handling**
  - Intelligent audio track selection
  - Language-based track filtering
  - Subtitle preservation
  - Support for multiple audio/subtitle streams

## Prerequisites

- Python 3.7+
- FFmpeg with libx265 support
- NVIDIA GPU (optional, for NVENC support)

## Installation

1. Clone the repository:
```bash
git clone https://github.com/yourusername/media-encoder.git
cd media-encoder
```

2. Install required Python packages:
```bash
pip install -r requirements.txt
```

3. Ensure FFmpeg is installed and accessible in your system PATH or specify its location in the config file.

## Configuration

Create or modify `encode_config.yaml` with your desired settings:

```yaml
# FFmpeg Settings
ffmpeg_path: null  # Set custom FFmpeg path if needed
ffprobe_path: null

# Video Encoding Settings
video_codec: libx265
video_preset: veryslow
video_crf: 13
max_threads: 16
gpu_device: 0
copy_audio: true
copy_subtitles: true

# Language Settings
preferred_languages:
  - eng
  - jpn
  - kor
  - cmn

# HDR Settings
hdr_settings:
  preserve_hdr: true
  force_10bit: true
  preferred_format: auto
  fallback_format: hdr10
  dolby_vision_enabled: true
  dolby_vision_profile: auto
```

## Usage

Basic usage:
```bash
python main.py <input_directory> <output_directory> [config_file]
```

Example:
```bash
python main.py /path/to/bdmv/folder /path/to/output encode_config.yaml
```

The encoder will:
1. Analyze the input directory for BDMV structure
2. Detect the main feature
3. Analyze HDR metadata and video characteristics
4. Apply optimal encoding settings
5. Process the video while preserving HDR metadata
6. Save the encoded file to the output directory

## Advanced Features

### HDR Processing

The encoder supports multiple HDR formats:
- HDR10 with static metadata
- HDR10+ with dynamic metadata
- HLG (Hybrid Log-Gamma)
- Dolby Vision (profiles 5, 8.1, 8.2, 8.4)

HDR metadata is automatically detected and preserved during encoding.

### Video Encoding Options

- **x265 Presets**: Choose from ultrafast to veryslow
- **CRF Control**: Fine-tune quality vs. file size
- **10-bit Processing**: Force 10-bit encoding for better color precision
- **GPU Acceleration**: NVIDIA NVENC support for faster encoding

### Audio/Subtitle Handling

The encoder intelligently selects audio and subtitle tracks based on:
- Language preferences
- Track type (primary audio, commentary, etc.)
- Audio format quality

## Logging

Detailed logs are saved to `encoding.log` in the output directory, including:
- Input file analysis
- HDR metadata detection
- Encoding parameters
- Progress updates
- Error reporting

## Error Handling

The encoder includes robust error handling for:
- Missing or corrupt input files
- Invalid BDMV structure
- Unsupported formats
- FFmpeg processing errors
- Insufficient disk space

## Performance Optimization

- Multi-threaded processing
- GPU acceleration support
- Optimized FFmpeg parameters
- Smart memory management
- Progress tracking with ETA

## Contributing

Contributions are welcome! Please read our contributing guidelines and submit pull requests to:
- Add new features
- Fix bugs
- Improve documentation
- Optimize performance

## License

[Insert your license information here]

## Acknowledgments

- FFmpeg team for their excellent media processing framework
- x265 developers for the HEVC encoder
- Dolby Vision development team