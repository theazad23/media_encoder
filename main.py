import sys
import logging
import shutil
from pathlib import Path
from typing import List

from config.encoding_config import EncodingConfig
from core.analyzer import MediaAnalyzer
from core.encoder import MediaEncoder

def check_ffmpeg():
    """Check if FFmpeg and FFprobe are available in the system."""
    if not (shutil.which('ffmpeg') and shutil.which('ffprobe')):
        print("Error: FFmpeg and/or FFprobe not found!")
        print("\nPlease ensure FFmpeg is installed and in your system PATH:")
        print("1. Download FFmpeg from https://www.gyan.dev/ffmpeg/builds/")
        print("2. Extract the archive")
        print("3. Add the bin folder to your system PATH")
        print("\nOr specify the FFmpeg path in the config file.")
        sys.exit(1)
        
class BatchEncoder:
    def __init__(self, input_dir: Path, output_dir: Path, config_path: Path = None):
        self.input_dir = input_dir
        self.output_dir = output_dir
        self.config = EncodingConfig.from_yaml(config_path or Path('encoder_config.yml'))
        self.analyzer = MediaAnalyzer()
        self.encoder = MediaEncoder(output_dir, self.config)
        self.logger = logging.getLogger(__name__)
        
    def setup_logging(self):
        """Configure logging for the encoding process."""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(self.output_dir / 'encoding.log'),
                logging.StreamHandler()
            ]
        )

    def find_main_movie_file(self, stream_dir: Path) -> Path:
        """
        Find the main movie file in a BDMV/STREAM directory.
        Usually the largest .m2ts file is the main movie.
        """
        m2ts_files = list(stream_dir.glob('*.m2ts'))
        if not m2ts_files:
            raise ValueError(f"No .m2ts files found in {stream_dir}")
            
        # Sort by file size, largest first
        main_movie = sorted(m2ts_files, key=lambda x: x.stat().st_size, reverse=True)[0]
        self.logger.info(f"Found main movie file: {main_movie.name} "
                        f"({main_movie.stat().st_size / (1024*1024*1024):.2f} GB)")
        return main_movie

    def process_directory(self):
        """Process Blu-ray directory structure."""
        self.setup_logging()
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Look for BDMV/STREAM directory
        stream_dir = self.input_dir / 'BDMV' / 'STREAM'
        if not stream_dir.exists():
            self.logger.error(f"Could not find BDMV/STREAM directory in {self.input_dir}")
            return
        
        try:
            # Find and process main movie file
            main_movie = self.find_main_movie_file(stream_dir)
            self.logger.info(f"Processing main movie file: {main_movie}")
            
            media_info = self.analyzer.get_media_info(main_movie)
            self.encoder.encode(main_movie, media_info)
            
        except Exception as e:
            self.logger.error(f"Failed to process movie: {e}")
            raise

def create_default_config(config_path: Path):
    """Create a default configuration file."""
    config = EncodingConfig(
        video_codec='libx265',
        video_preset='veryslow',
        video_crf=14,
        max_threads=16,
        gpu_device=0,
        copy_audio=True,
        copy_subtitles=True,
        preferred_languages=['eng'],
        preserve_hdr=True,
        force_10bit=True,
        hdr_settings={
            'color_primaries': 'auto',
            'transfer': 'auto',
            'color_matrix': 'auto',
            'max_cll': 'preserve',
            'master_display': 'preserve'
        }
    )
    config.to_yaml(config_path)
    return config

def main():
    # Check for FFmpeg first
    check_ffmpeg()

    if len(sys.argv) not in [3, 4]:
        print("Usage: python main.py <input_directory> <output_directory> [config_file]")
        sys.exit(1)
        
    input_dir = Path(sys.argv[1])
    output_dir = Path(sys.argv[2])
    config_path = Path(sys.argv[3]) if len(sys.argv) > 3 else Path('encoder_config.yml')
    
    if not input_dir.exists():
        print(f"Error: Input directory '{input_dir}' does not exist")
        sys.exit(1)
    
    bdmv_dir = input_dir / 'BDMV'
    if not bdmv_dir.exists():
        print(f"Error: No BDMV directory found in '{input_dir}'")
        sys.exit(1)
    
    # Create default config if it doesn't exist
    if not config_path.exists():
        print(f"Creating default configuration file at {config_path}")
        create_default_config(config_path)
    
    batch_encoder = BatchEncoder(input_dir, output_dir, config_path)
    batch_encoder.process_directory()

if __name__ == "__main__":
    main()
