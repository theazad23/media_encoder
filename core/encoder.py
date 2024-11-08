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
        preferred_langs = self.config.preferred_languages or ['eng']
        is_foreign = all((track.language not in preferred_langs for track in media_info.audio_tracks if track.language != 'und'))
        selected_audio = []
        selected_subs = []
        
        if is_foreign:
            original_audio = next((track.index for track in media_info.audio_tracks), None)
            if original_audio is not None:
                selected_audio.append(original_audio)
            preferred_dub = next((track.index for track in media_info.audio_tracks if track.language in preferred_langs), None)
            if preferred_dub is not None:
                selected_audio.append(preferred_dub)
        else:
            preferred_audio = next((track.index for track in media_info.audio_tracks if track.language in preferred_langs), None)
            if preferred_audio is not None:
                selected_audio.append(preferred_audio)
                
        preferred_sub = next((track.index for track in media_info.subtitle_tracks if track.language in preferred_langs), None)
        if preferred_sub is not None:
            selected_subs.append(preferred_sub)
            
        return (selected_audio, selected_subs)

    def _get_hdr_params(self, hdr_metadata: HDRMetadata) -> List[str]:
        handler = HDRHandler()
        return handler.get_encoding_params(hdr_metadata, self.config.video_codec)
    
    def encode(self, input_file: Path, media_info: MediaInfo, *, title: str=None) -> Path:
        try:
            if not title:
                title = input_file.parent.parent.parent.name.replace('.', ' ').strip()
            if not title:
                title = 'output'
                
            output_file = self.output_dir / f'{title}.mkv'
            self.output_dir.mkdir(parents=True, exist_ok=True)
            
            selected_audio, selected_subs = self._select_tracks(media_info)
            
            cmd = ['ffmpeg', '-hide_banner', '-y']
            
            # Handle concat input
            if str(input_file).startswith('concat:'):
                concat_file = Path(str(input_file).replace('concat:', ''))
                if concat_file.exists():
                    self.logger.info(f'Using concat file: {concat_file}')
                    cmd.extend(['-f', 'concat', '-safe', '0'])
                    cmd.extend(['-i', str(concat_file)])
                else:
                    raise FileNotFoundError(f'Concat file not found: {concat_file}')
            else:
                cmd.extend(['-i', str(input_file)])
            
            # Map streams
            cmd.extend(['-map', '0:v:0'])
            for audio_idx in selected_audio:
                cmd.extend(['-map', f'0:{audio_idx}'])
            for sub_idx in selected_subs:
                cmd.extend(['-map', f'0:{sub_idx}'])
            
            # Video encoding parameters
            cmd.extend(['-c:v', self.config.video_codec])
            cmd.extend(['-preset', self.config.video_preset])
            
            # Combine HDR and base x265 parameters
            x265_params = []
            if media_info.hdr_metadata:
                hdr_params = self.hdr_handler.get_encoding_params(media_info.hdr_metadata, self.config.video_codec)
                if hdr_params:
                    self.logger.info(f'Applying HDR parameters for {media_info.hdr_metadata.hdr_format} content')
                    x265_params.extend(hdr_params)
                    for param in hdr_params:
                        self.logger.debug(f'HDR param: {param}')
            
            # Add base x265 parameters
            x265_params.extend(self.config.get_base_x265_params())
            
            # Add profile and bit depth settings
            if self.config.hdr_config.force_10bit:
                x265_params.extend(['profile=main10', 'high-tier=1', 'bit-depth=10'])
                
            # Add x265 parameters as a single argument
            if x265_params:
                cmd.extend(['-x265-params', ':'.join(x265_params)])
            
            # Add pixel format for 10-bit
            if self.config.hdr_config.force_10bit:
                cmd.extend(['-pix_fmt', 'yuv420p10le'])
            
            # Audio and subtitle settings
            cmd.extend(['-c:a', 'copy' if self.config.copy_audio else 'aac'])
            cmd.extend(['-c:s', 'copy' if self.config.copy_subtitles else 'srt'])
            
            # Output file
            cmd.append(str(output_file))
            
            # Log the complete command
            self.logger.info('FFmpeg command:')
            self.logger.info(' '.join(str(x) for x in cmd))
            self.logger.info(f'Starting encode of {input_file.name} to {output_file}')
            
            # Execute the command
            process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True, bufsize=1)
            
            while True:
                line = process.stderr.readline()
                if not line and process.poll() is not None:
                    break
                if 'Error' in line or 'error' in line:
                    self.logger.error(f'FFmpeg error: {line.strip()}')
                elif 'frame=' in line:
                    print(f'\r{line.strip()}', end='', flush=True)
            
            print()
            
            if process.returncode != 0:
                stderr_output = process.stderr.read()
                self.logger.error(f'FFmpeg error output:\n{stderr_output}')
                raise subprocess.CalledProcessError(process.returncode, cmd)
            
            if output_file.exists():
                self.logger.info(f'Successfully encoded {input_file.name} to {output_file}')
                if str(input_file).startswith('concat:'):
                    concat_file = Path(str(input_file).replace('concat:', ''))
                    try:
                        if concat_file.exists():
                            concat_file.unlink()
                            self.logger.debug(f'Cleaned up concat file: {concat_file}')
                    except Exception as e:
                        self.logger.warning(f'Failed to clean up concat file: {e}')
                return output_file
            else:
                raise FileNotFoundError(f'Expected output file {output_file} was not created')
                
        except Exception as e:
            self.logger.error(f'Error encoding {input_file.name}: {e}', exc_info=True)
            raise