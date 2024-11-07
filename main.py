import sys
import logging
import shutil
from pathlib import Path
from typing import List

from config.encoding_config import EncodingConfig
from core.analyzer import MediaAnalyzer
from core.encoder import MediaEncoder
from utils.bdvm_parser import BDMVParser

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

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
    def __init__(self, input_dir: Path, output_dir: Path, config_path: Path=None):
        self.input_dir = input_dir
        self.output_dir = output_dir
        self.config = EncodingConfig.from_yaml(config_path or Path('encoder_config.yml'))
        self.analyzer = MediaAnalyzer()
        self.encoder = MediaEncoder(output_dir, self.config)
        self.logger = logging.getLogger(__name__)
        self.parser = BDMVParser(input_dir)
        
    def setup_logging(self):
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(self.output_dir / 'encoding.log'),
                logging.StreamHandler()
            ]
        )

    def find_main_movie_file(self, stream_dir: Path) -> Path:
        """Find the largest M2TS file in the stream directory."""
        m2ts_files = list(stream_dir.glob('*.m2ts'))
        if not m2ts_files:
            raise ValueError(f'No .m2ts files found in {stream_dir}')
        main_movie = sorted(m2ts_files, key=lambda x: x.stat().st_size, reverse=True)[0]
        self.logger.info(f'Found main movie file: {main_movie.name} ({main_movie.stat().st_size / (1024*1024*1024):.2f} GB)')
        return main_movie

    def process_directory(self):
        self.setup_logging()
        self.output_dir.mkdir(parents=True, exist_ok=True)

        try:
            # Find main playlist first
            playlist_info = self.parser.find_main_playlist()
            
            if playlist_info and playlist_info.items and all(item.relative_path.exists() for item in playlist_info.items):
                self.logger.info(f"Found main playlist with {len(playlist_info.items)} items")
                self.logger.info(f"Movie title: {playlist_info.title}")
                self.logger.info(f"Total duration: {playlist_info.duration:.2f} seconds")
                self.logger.info(f"Total size: {playlist_info.size / (1024*1024*1024):.2f} GB")
                
                # Debug info about the selected playlist
                for item in playlist_info.items:
                    file_size = item.relative_path.stat().st_size / (1024*1024)
                    self.logger.info(f"Playlist item: {item.filename} ({(item.out_time - item.in_time)/45000:.2f} seconds)")
                    self.logger.info(f"File exists: {item.relative_path.exists()}")
                    self.logger.info(f"File size: {file_size:.2f} MB")
                
                # Create concat file
                concat_file = self.output_dir / 'concat.txt'
                concat_content = ["ffconcat version 1.0"]
                
                for item in playlist_info.items:
                    escaped_path = str(item.relative_path).replace('\\', '/').replace("'", "'\\''")
                    concat_content.append(f"file '{escaped_path}'")
                    
                    # Add trim points if needed
                    if item.in_time > 0:
                        concat_content.append(f"inpoint {item.in_time/45000:.6f}")
                    if item.out_time < float('inf'):
                        concat_content.append(f"outpoint {item.out_time/45000:.6f}")
                
                with open(concat_file, 'w') as f:
                    f.write('\n'.join(concat_content))
                
                self.logger.info(f"Created concat file: {concat_file}")
                
                # Get media info from first file
                first_file = playlist_info.items[0].relative_path
                self.logger.info(f"Analyzing first file: {first_file}")
                media_info = self.analyzer.get_media_info(first_file)
                
                # Adjust duration for all segments
                media_info.duration = playlist_info.duration
                
                # Create virtual input for FFmpeg
                virtual_input = Path(f"concat:{concat_file}")
                self.encoder.encode(virtual_input, media_info, title=playlist_info.title)
                
            else:
                # Fall back to single largest file
                stream_dir = self.input_dir / 'BDMV' / 'STREAM'
                self.logger.info(f"Falling back to single file mode. Checking {stream_dir}")
                main_movie = self.find_main_movie_file(stream_dir)
                title = self.input_dir.name.replace('.', ' ').strip()
                
                self.logger.info(f'Using largest file: {main_movie}')
                media_info = self.analyzer.get_media_info(main_movie)
                self.encoder.encode(main_movie, media_info, title=title)
                
        except Exception as e:
            self.logger.error(f'Failed to process movie: {e}')
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
