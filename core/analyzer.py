import json
import logging
import subprocess
import re
from pathlib import Path
from typing import Dict, Any
from models.media_info import MediaInfo, MediaTrack, HDRMetadata
from core.hdr_handler import HDRHandler

class MediaAnalyzer:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.hdr_handler = HDRHandler()

    def _parse_hdr_metadata(self, stream_data: Dict[str, Any]) -> HDRMetadata:
        handler = HDRHandler()
        return handler.detect_hdr_format(stream_data)

    def _format_master_display(self, display_data: str) -> str:
        """Format master display metadata for x265."""
        try:
            coords = re.findall(r'([RGB])\((\d+),(\d+)\)', display_data)
            wp = re.findall(r'WP\((\d+),(\d+)\)', display_data)
            lum = re.findall(r'L\((\d+),(\d+)\)', display_data)
            
            if coords and wp and lum:
                points = []
                for color, x, y in coords:
                    points.extend([x, y])
                points.extend(wp[0])
                points.extend(lum[0])
                return 'G(%s,%s)B(%s,%s)R(%s,%s)WP(%s,%s)L(%s,%s)' % tuple(points)
        except Exception as e:
            self.logger.warning(f"Error parsing master display data: {e}")
        return None

    def get_media_info(self, input_file: Path) -> MediaInfo:
        cmd = ['ffprobe', '-v', 'quiet', '-print_format', 'json', 
               '-show_format', '-show_streams', '-show_frames', 
               '-read_intervals', '%+#1', #Only read first frame for HDR metadata
               '-show_entries', 'frame=color_space,color_primaries,color_transfer,side_data',
               str(input_file)]
        
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            data = json.loads(result.stdout)
            
            video_stream = next((s for s in data['streams'] if s['codec_type'] == 'video'), None)
            if not video_stream:
                raise ValueError('No video stream found')

            # Get HDR metadata from both stream and first frame
            frame_data = data.get('frames', [{}])[0]
            stream_hdr_data = {
                'color_transfer': video_stream.get('color_transfer'),
                'color_primaries': video_stream.get('color_primaries'),
                'color_space': video_stream.get('color_space'),
                'bits_per_raw_sample': video_stream.get('bits_per_raw_sample'),
                'side_data_list': video_stream.get('side_data_list', []),
                'tags': video_stream.get('tags', {})
            }
            
            # Merge frame data with stream data for complete HDR info
            if frame_data:
                stream_hdr_data.update({
                    'color_transfer': frame_data.get('color_transfer', stream_hdr_data['color_transfer']),
                    'color_primaries': frame_data.get('color_primaries', stream_hdr_data['color_primaries']),
                    'color_space': frame_data.get('color_space', stream_hdr_data['color_space']),
                    'side_data_list': frame_data.get('side_data_list', []) + stream_hdr_data['side_data_list']
                })

            hdr_metadata = self.hdr_handler.detect_hdr_format(stream_hdr_data)
            
            if hdr_metadata.is_hdr:
                self.logger.info(f"Detected {hdr_metadata.hdr_format} content with {hdr_metadata.bit_depth}-bit depth")
                if hdr_metadata.max_cll:
                    self.logger.info(f"MaxCLL: {hdr_metadata.max_cll}")
                if hdr_metadata.master_display:
                    self.logger.info(f"Master Display: {hdr_metadata.master_display}")

            audio_tracks = []
            subtitle_tracks = []
            
            for idx, stream in enumerate(data['streams']):
                if stream['codec_type'] == 'audio':
                    language = stream.get('tags', {}).get('language', 'und')
                    audio_tracks.append(
                        MediaTrack(
                            index=idx,
                            type='audio',
                            language=language,
                            codec=stream['codec_name'],
                            title=stream.get('tags', {}).get('title')
                        )
                    )
                elif stream['codec_type'] == 'subtitle':
                    language = stream.get('tags', {}).get('language', 'und')
                    subtitle_tracks.append(
                        MediaTrack(
                            index=idx,
                            type='subtitle',
                            language=language,
                            codec=stream['codec_name'],
                            title=stream.get('tags', {}).get('title')
                        )
                    )

            return MediaInfo(
                filepath=input_file,
                duration=float(data['format']['duration']),
                video_codec=video_stream['codec_name'],
                audio_tracks=audio_tracks,
                subtitle_tracks=subtitle_tracks,
                hdr_metadata=hdr_metadata
            )
            
        except subprocess.CalledProcessError as e:
            self.logger.error(f'Error analyzing media file: {e}')
            raise