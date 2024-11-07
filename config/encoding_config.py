from dataclasses import dataclass
from pathlib import Path
from typing import List, Dict, Optional
import yaml

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
    preserve_hdr: bool = True
    force_10bit: bool = True
    hdr_settings: Dict = None
    ffmpeg_path: Optional[str] = None
    ffprobe_path: Optional[str] = None

    @classmethod
    def from_yaml(cls, config_path: Path) -> 'EncodingConfig':
        """Load configuration from YAML file."""
        if not config_path.exists():
            return cls()
        
        with open(config_path, 'r') as f:
            config_data = yaml.safe_load(f)
            return cls(**config_data)

    def to_yaml(self, config_path: Path):
        """Save configuration to YAML file."""
        with open(config_path, 'w') as f:
            yaml.dump(self.__dict__, f, default_flow_style=False)

    def get_ffmpeg_params(self) -> List[str]:
        """Convert config to FFmpeg parameters."""
        params = []
        
        # Video codec settings
        params.extend(['-c:v', self.video_codec])
        params.extend(['-preset', self.video_preset])
        
        if self.video_codec == 'libx265':
            x265_params = [
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

            if self.force_10bit:
                x265_params.extend([
                    'profile=main10',
                    'high-tier=1',
                    'bit-depth=10'
                ])

            params.extend(['-x265-params', ':'.join(x265_params)])
            
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
                '-temporal_aq', '1',
            ])
        
        if self.force_10bit:
            params.extend(['-pix_fmt', 'yuv420p10le'])
        
        params.extend([
            '-c:a', 'copy' if self.copy_audio else 'aac',
            '-c:s', 'copy' if self.copy_subtitles else 'srt'
        ])
        
        return params