import logging
import subprocess
from pathlib import Path
from typing import List, Tuple
from models.media_info import MediaInfo
from config.encoding_config import EncodingConfig
from utils.progress import ProgressTracker

class MediaEncoder:
    def __init__(self, output_dir: Path, config: EncodingConfig):
        self.output_dir = output_dir
        self.config = config
        self.logger = logging.getLogger(__name__)
        
    def _select_tracks(self, media_info: MediaInfo) -> Tuple[List[int], List[int]]:
        """Select which audio and subtitle tracks to keep based on language preferences."""
        preferred_langs = self.config.preferred_languages or ['eng']
        
        is_foreign = all(track.language not in preferred_langs 
                        for track in media_info.audio_tracks 
                        if track.language != 'und')
        
        selected_audio = []
        selected_subs = []
        
        if is_foreign:
            original_audio = next((track.index for track in media_info.audio_tracks), None)
            if original_audio is not None:
                selected_audio.append(original_audio)
            preferred_dub = next((track.index for track in media_info.audio_tracks 
                                if track.language in preferred_langs), None)
            if preferred_dub is not None:
                selected_audio.append(preferred_dub)
        else:
            preferred_audio = next((track.index for track in media_info.audio_tracks 
                                  if track.language in preferred_langs), None)
            if preferred_audio is not None:
                selected_audio.append(preferred_audio)
        
        preferred_sub = next((track.index for track in media_info.subtitle_tracks 
                            if track.language in preferred_langs), None)
        if preferred_sub is not None:
            selected_subs.append(preferred_sub)
        
        return selected_audio, selected_subs

    def _get_hdr_params(self, media_info: MediaInfo) -> List[str]:
        """Generate HDR-specific encoding parameters."""
        params = []
        hdr = media_info.hdr_metadata
        config = self.config.hdr_settings

        # Force 10-bit encoding if requested or if source is HDR
        if self.config.force_10bit or hdr.is_hdr:
            params.extend([
                'profile=main10',
                'high-tier=1',
                'bit-depth=10'
            ])

        # Color space parameters
        if hdr.is_hdr or config['color_primaries'] != 'auto':
            primaries = config['color_primaries'] if config['color_primaries'] != 'auto' else hdr.color_primaries
            transfer = config['transfer'] if config['transfer'] != 'auto' else hdr.transfer_characteristics
            matrix = config['color_matrix'] if config['color_matrix'] != 'auto' else hdr.color_matrix
            
            params.extend([
                f'colorprim={primaries}',
                f'transfer={transfer}',
                f'colormatrix={matrix}'
            ])

        # HDR metadata
        if hdr.is_hdr and self.config.preserve_hdr:
            if hdr.max_cll and config['max_cll'] == 'preserve':
                params.append(f'max-cll={hdr.max_cll}')
            
            if hdr.master_display and config['master_display'] == 'preserve':
                params.append(f'master-display={hdr.master_display}')

            # HDR-specific tuning
            params.extend([
                'hdr-opt=1',
                'hdr10-opt=1',
                'range=limited'
            ])

        return params
    
    def encode(self, input_file: Path, media_info: MediaInfo) -> Path:
        """Encode the media file with selected settings."""
        output_file = self.output_dir / f"{input_file.stem}_encoded{input_file.suffix}"
        
        selected_audio, selected_subs = self._select_tracks(media_info)
        
        # Base FFmpeg command
        cmd = [
            'ffmpeg',
            '-i', str(input_file),
            '-progress', 'pipe:1',
            '-map', '0:v:0'  # Always map first video stream
        ]
        
        # Map selected audio tracks
        for audio_idx in selected_audio:
            cmd.extend(['-map', f'0:{audio_idx}'])
            
        # Map selected subtitle tracks
        for sub_idx in selected_subs:
            cmd.extend(['-map', f'0:{sub_idx}'])
        
        # Add encoding parameters from config
        cmd.extend(self.config.get_ffmpeg_params())
        
        # Add HDR parameters if needed
        if self.config.video_codec == 'libx265':
            x265_params = cmd[cmd.index('-x265-params') + 1].split(':')
            x265_params.extend(self._get_hdr_params(media_info))
            cmd[cmd.index('-x265-params') + 1] = ':'.join(x265_params)
        
        # Output file
        cmd.extend([str(output_file)])
        
        try:
            self.logger.info(f"Starting encode of {input_file.name}")
            
            # Set up progress tracking
            progress = ProgressTracker(media_info.duration, input_file.name)
            
            # Run FFmpeg with progress monitoring
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True
            )
            
            while True:
                line = process.stdout.readline()
                if not line:
                    break
                    
                # Parse FFmpeg progress output
                if 'out_time_ms=' in line:
                    time_ms = int(line.split('=')[1])
                    current_time = time_ms / 1000000.0
                    progress_str = progress.update(current_time)
                    if progress_str:
                        print(progress_str, end='', flush=True)
            
            process.wait()
            print()  # New line after progress
            
            if process.returncode != 0:
                raise subprocess.CalledProcessError(process.returncode, cmd)
                
            self.logger.info(f"Successfully encoded {input_file.name}")
            return output_file
            
        except subprocess.CalledProcessError as e:
            self.logger.error(f"Error encoding {input_file.name}: {e}")
            raise
