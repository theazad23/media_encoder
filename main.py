import sys
import logging
from pathlib import Path
from typing import List

from config.encoding_config import EncodingConfig
from core.analyzer import MediaAnalyzer
from core.encoder import MediaEncoder

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

    def process_directory(self):
        """Process all media files in the input directory."""
        self.setup_logging()
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        media_files = list(self.input_dir.glob('*.mkv')) + list(self.input_dir.glob('*.mp4'))
        total_files = len(media_files)
        
        self.logger.info(f"Found {total_files} files to process")
        
        for idx, input_file in enumerate(media_files, 1):
            try:
                print(f"\nProcessing file {idx}/{total_files}: {input_file.name}")
                media_info = self.analyzer.get_media_info(input_file)
                self.encoder.encode(input_file, media_info)
            except Exception as e:
                self.logger.error(f"Failed to process {input_file.name}: {e}")

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
    if len(sys.argv) not in [3, 4]:
        print("Usage: python main.py <input_directory> <output_directory> [config_file]")
        sys.exit(1)
        
    input_dir = Path(sys.argv[1])
    output_dir = Path(sys.argv[2])
    config_path = Path(sys.argv[3]) if len(sys.argv) > 3 else Path('encoder_config.yml')
    
    # Create default config if it doesn't exist
    if not config_path.exists():
        print(f"Creating default configuration file at {config_path}")
        create_default_config(config_path)
    
    batch_encoder = BatchEncoder(input_dir, output_dir, config_path)
    batch_encoder.process_directory()

if __name__ == "__main__":
    main()