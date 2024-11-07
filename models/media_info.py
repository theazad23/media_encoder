from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

@dataclass
class HDRMetadata:
    color_primaries: str
    transfer_characteristics: str
    color_matrix: str
    max_cll: Optional[str] = None
    master_display: Optional[str] = None
    is_hdr: bool = False
    bit_depth: int = 8

@dataclass
class MediaTrack:
    index: int
    type: str
    language: str
    codec: str
    title: Optional[str] = None

@dataclass
class MediaInfo:
    filepath: Path
    duration: float
    video_codec: str
    audio_tracks: List[MediaTrack]
    subtitle_tracks: List[MediaTrack]
    hdr_metadata: HDRMetadata