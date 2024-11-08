import logging
import subprocess
from pathlib import Path
from typing import List, Tuple
from models.media_info import HDRMetadata, MediaInfo
from config.encoding_config import EncodingConfig
from utils.progress import ProgressTracker
from core.hdr_handler import HDRHandler

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

    def _get_hdr_params(self, hdr_metadata: HDRMetadata) -> List[str]:
        handler = HDRHandler()
        return handler.get_encoding_params(hdr_metadata, self.config.video_codec)
    
    def encode(self, input_file: Path, media_info: MediaInfo, *, title: str = None) -> Path:
        try:
            if not title:
                title = input_file.parent.parent.parent.name.replace('.', ' ').strip()
            if not title:
                title = "output"

            output_file = self.output_dir / f"{title}.mkv"
            self.output_dir.mkdir(parents=True, exist_ok=True)

            selected_audio, selected_subs = self._select_tracks(media_info)
            
            # Build FFmpeg command
            cmd = ['ffmpeg', '-hide_banner', '-y']
            
            # Handle concat input
            if str(input_file).startswith('concat:'):
                concat_file = Path(str(input_file).replace('concat:', ''))
                if concat_file.exists():
                    self.logger.info(f"Using concat file: {concat_file}")
                    cmd.extend(['-f', 'concat', '-safe', '0'])
                    cmd.extend(['-i', str(concat_file)])
                else:
                    raise FileNotFoundError(f"Concat file not found: {concat_file}")
            else:
                cmd.extend(['-i', str(input_file)])
            
            # Add stream mapping
            cmd.extend(['-map', '0:v:0'])  # First video stream
            for audio_idx in selected_audio:
                cmd.extend(['-map', f'0:{audio_idx}'])
            for sub_idx in selected_subs:
                cmd.extend(['-map', f'0:{sub_idx}'])
            
            # Get base encoding parameters
            params = self.config.get_ffmpeg_params()
            
            # Add HDR parameters if present
            if hasattr(media_info, 'hdr_metadata') and media_info.hdr_metadata:
                # Find the x265-params in the existing parameters
                for i, param in enumerate(params):
                    if param.startswith('x265-params'):
                        # Get the existing x265 params
                        x265_params = param.split(':')[1:]
                        # Add HDR parameters
                        x265_params.extend(self._get_hdr_params(media_info.hdr_metadata))
                        # Update the parameter
                        params[i] = 'x265-params=' + ':'.join(x265_params)
                        break
            
            # Add encoding parameters
            cmd.extend(params)
            cmd.append(str(output_file))
            
            self.logger.info("FFmpeg command:")
            self.logger.info(' '.join(str(x) for x in cmd))
            
            self.logger.info(f'Starting encode of {input_file.name} to {output_file}')
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True,
                bufsize=1
            )
            
            while True:
                line = process.stderr.readline()
                if not line and process.poll() is not None:
                    break
                
                # Log FFmpeg output for debugging
                if 'Error' in line or 'error' in line:
                    self.logger.error(f"FFmpeg error: {line.strip()}")
                elif 'frame=' in line:
                    # Regular progress update
                    print(f"\r{line.strip()}", end='', flush=True)
            
            print()  # New line after progress
            
            if process.returncode != 0:
                stderr_output = process.stderr.read()
                self.logger.error(f"FFmpeg error output:\n{stderr_output}")
                raise subprocess.CalledProcessError(process.returncode, cmd)
                
            if output_file.exists():
                self.logger.info(f'Successfully encoded {input_file.name} to {output_file}')
                
                # Clean up concat file if it was used
                if str(input_file).startswith('concat:'):
                    concat_file = Path(str(input_file).replace('concat:', ''))
                    try:
                        if concat_file.exists():
                            concat_file.unlink()
                            self.logger.debug(f"Cleaned up concat file: {concat_file}")
                    except Exception as e:
                        self.logger.warning(f"Failed to clean up concat file: {e}")
                
                return output_file
            else:
                raise FileNotFoundError(f"Expected output file {output_file} was not created")
                
        except Exception as e:
            self.logger.error(f'Error encoding {input_file.name}: {e}', exc_info=True)
            raise