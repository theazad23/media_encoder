from dataclasses import dataclass
from pathlib import Path
from typing import List, Dict, Optional
import yaml
import logging

@dataclass
class HDRConfig:
    preserve_hdr: bool = True
    force_10bit: bool = True
    preferred_format: str = "auto"
    fallback_format: str = "hdr10"
    dolby_vision_enabled: bool = True
    dolby_vision_profile: str = "auto"

@dataclass
class EncodingConfig:
    video_codec: str = 'libx265'
    video_preset: str = 'veryslow'
    video_crf: int = 14
    max_threads: int = 16
    gpu_device: int = 0
    copy_audio: bool = True
    copy_subtitles: bool = True
    preferred_languages: List[str] = None
    hdr_config: HDRConfig = None
    ffmpeg_path: Optional[str] = None
    ffprobe_path: Optional[str] = None

    def __post_init__(self):
        if self.hdr_config is None:
            self.hdr_config = HDRConfig()
        if self.preferred_languages is None:
            self.preferred_languages = ['eng']
        self.logger = logging.getLogger(__name__)

    @classmethod
    def from_yaml(cls, config_path: Path) -> 'EncodingConfig':
        if not config_path.exists():
            return cls()
        with open(config_path, 'r') as f:
            config_data = yaml.safe_load(f)
            hdr_config_data = config_data.pop('hdr_settings', {})
            config_data['hdr_config'] = HDRConfig(**hdr_config_data)
            return cls(**config_data)

    def to_yaml(self, config_path: Path):
        config_dict = self.__dict__.copy()
        config_dict['hdr_settings'] = config_dict.pop('hdr_config').__dict__
        config_dict.pop('logger', None)  # Remove logger before saving
        with open(config_path, 'w') as f:
            yaml.dump(config_dict, f, default_flow_style=False)

    def get_base_x265_params(self) -> List[str]:
        """Get base x265 encoding parameters"""
        return [
            f'crf={self.video_crf}',
            'pools=+,-',
            f'frame-threads={self.max_threads}',
            'rd=4',
            'psy-rd=2.0',
            'psy-rdoq=2.0',
            'aq-mode=3',
            'aq-strength=0.8',
            'deblock=-1:-1',
            'me=star',
            'subme=7',
            'ref=6',
            'rc-lookahead=60',
            'b-adapt=2',
            'bframes=8',
            'keyint=250',
            'min-keyint=23',
            'merange=57',
            'weightp=2',
            'weightb=1',
            'strong-intra-smoothing=0'
        ]

    def get_ffmpeg_params(self, hdr_params: List[str] = None) -> List[str]:
        """Get FFmpeg encoding parameters"""
        params = []
        params.extend(['-c:v', self.video_codec])
        params.extend(['-preset', self.video_preset])
        
        if self.video_codec == 'libx265':
            # Combine all x265 parameters
            x265_params = []
            
            # Add HDR parameters first if they exist
            if hdr_params:
                x265_params.extend(hdr_params)
            
            # Add base encoding parameters
            x265_params.extend(self.get_base_x265_params())
            
            # Add 10-bit parameters if needed
            if self.hdr_config.force_10bit:
                x265_params.extend(['profile=main10', 'high-tier=1', 'bit-depth=10'])
            
            # Join all parameters with colons
            params.extend(['-x265-params', ':'.join(x265_params)])
            
            self.logger.debug(f"Final x265 parameters: {':'.join(x265_params)}")
            
        elif self.video_codec == 'hevc_nvenc':
            params.extend([
                '-gpu', str(self.gpu_device),
                '-rc:v', 'vbr',
                '-cq', str(self.video_crf),
                '-qmin', str(self.video_crf),
                '-qmax', str(self.video_crf + 2),
                '-profile:v', 'main10',
                '-preset', 'p7',
                '-rc-lookahead', '32',
                '-spatial_aq', '1',
                '-temporal_aq', '1'
            ])
            
        if self.hdr_config.force_10bit:
            params.extend(['-pix_fmt', 'yuv420p10le'])
            
        params.extend([
            '-c:a', 'copy' if self.copy_audio else 'aac',
            '-c:s', 'copy' if self.copy_subtitles else 'srt'
        ])
        
        return params