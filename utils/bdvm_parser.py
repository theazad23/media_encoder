from pathlib import Path
import struct
from typing import List, NamedTuple
from dataclasses import dataclass
import logging

@dataclass
class PlaylistItem:
    filename: str
    in_time: int
    out_time: int
    relative_path: Path
    
@dataclass
class PlaylistInfo:
    items: List[PlaylistItem]
    duration: float  # in seconds
    size: int  # in bytes
    title: str

class BDMVParser:
    def __init__(self, bdmv_path: Path):
        self.bdmv_path = bdmv_path
        self.stream_path = bdmv_path / 'BDMV' / 'STREAM'
        self.playlist_path = bdmv_path / 'BDMV' / 'PLAYLIST'
        self.logger = logging.getLogger(__name__)

    def _read_mpls_header(self, mpls_data: bytes) -> tuple:
        """Read MPLS header and return (type_indicator, version, playlist_start)"""
        if len(mpls_data) < 16:
            raise ValueError("MPLS file too short")
            
        type_indicator = mpls_data[0:4].decode()
        version = f"{mpls_data[4]:02d}{mpls_data[5]:02d}{mpls_data[6]:02d}"
        playlist_start = struct.unpack('>I', mpls_data[8:12])[0]
        
        # self.logger.debug(f"MPLS Header - Type: {type_indicator}, Version: {version}, Start: {playlist_start}")
        # self.logger.debug(f"Raw header bytes: {mpls_data[:16].hex()}")
        return (type_indicator, version, playlist_start)

    def _parse_clip_info(self, data: bytes, start_pos: int) -> tuple:
        """Parse clip information block"""
        try:
            # Show the raw bytes we're working with
            # self.logger.debug(f"Parsing clip info at position {start_pos}")
            # self.logger.debug(f"Raw bytes: {data[start_pos:start_pos+32].hex()}")
            
            # Read clip info length
            clip_info_length = struct.unpack('>H', data[start_pos:start_pos+2])[0]
            # self.logger.debug(f"Clip info length: {clip_info_length}")
            
            # Read clip name (5 bytes)
            clip_name_bytes = data[start_pos+2:start_pos+7]
            # self.logger.debug(f"Clip name bytes: {clip_name_bytes.hex()}")
            
            # Parse the clip number differently - try both methods
            # Method 1: Direct ASCII interpretation
            try:
                clip_name_ascii = ''.join(chr(b) for b in clip_name_bytes if b != 0)
                # self.logger.debug(f"Clip name (ASCII): {clip_name_ascii}")
            except:
                clip_name_ascii = None
            
            # Method 2: Numeric interpretation
            clip_number = int.from_bytes(clip_name_bytes[-4:], byteorder='big')
            clip_name = f"{clip_number:05d}.m2ts"
            # self.logger.debug(f"Clip name (numeric): {clip_name}")
            
            # Read timestamps
            timestamp_pos = start_pos + 14
            if timestamp_pos + 8 <= len(data):
                in_time = struct.unpack('>I', data[timestamp_pos:timestamp_pos+4])[0]
                out_time = struct.unpack('>I', data[timestamp_pos+4:timestamp_pos+8])[0]
                # self.logger.debug(f"Timestamps - In: {in_time}, Out: {out_time}")
                
                return clip_name, clip_info_length, in_time, out_time
                
        except Exception as e:
            self.logger.error(f"Error parsing clip info: {e}")
            return None, None, None, None

    def _parse_clip_name(self, clip_name_bytes: bytes) -> str:
        """Convert raw clip name bytes to proper filename"""
        try:
            # The clip name is stored as 5 bytes in ASCII format
            ascii_str = clip_name_bytes.decode('ascii')
            # Remove any null bytes and pad with zeros to create 5-digit number
            clip_number = int(ascii_str.strip('\x00'))
            return f"{clip_number:05d}.m2ts"
        except:
            # Fallback method if ASCII decode fails
            clip_number = 0
            for b in clip_name_bytes:
                if b != 0:
                    clip_number = (clip_number * 10) + (b - ord('0'))
            return f"{clip_number:05d}.m2ts"

    def _parse_playlist_items(self, mpls_data: bytes, offset: int) -> List[PlaylistItem]:
        items = []
        try:
            playlist_length = struct.unpack('>I', mpls_data[offset:offset+4])[0]
            item_count = struct.unpack('>H', mpls_data[offset+6:offset+8])[0]
            
            # self.logger.debug(f"Playlist length: {playlist_length}, Item count: {item_count}")
            current_pos = offset + 10
            
            for i in range(item_count):
                try:
                    # Debug raw data
                    # self.logger.debug(f"Reading item {i} at position {current_pos}")
                    # self.logger.debug(f"Raw data: {mpls_data[current_pos:current_pos+32].hex()}")
                    
                    clip_info_length = struct.unpack('>H', mpls_data[current_pos:current_pos+2])[0]
                    # self.logger.debug(f"Clip info length: {clip_info_length}")
                    
                    # Get clip name (5 bytes after the length)
                    clip_name_pos = current_pos + 2
                    clip_name_bytes = mpls_data[clip_name_pos:clip_name_pos+5]
                    clip_name = self._parse_clip_name(clip_name_bytes)
                    
                    # self.logger.debug(f"Clip name bytes: {clip_name_bytes.hex()}, Clip name: {clip_name}")
                    
                    # Get timestamps
                    timestamp_pos = current_pos + 14
                    in_time = struct.unpack('>I', mpls_data[timestamp_pos:timestamp_pos+4])[0]
                    out_time = struct.unpack('>I', mpls_data[timestamp_pos+4:timestamp_pos+8])[0]
                    
                    duration = (out_time - in_time) / 45000  # Convert to seconds
                    # self.logger.debug(f"Duration: {duration:.2f} seconds")
                    
                    if duration > 30:  # Only include clips longer than 30 seconds
                        file_path = self.stream_path / clip_name
                        if file_path.exists():
                            items.append(PlaylistItem(
                                filename=clip_name,
                                in_time=in_time,
                                out_time=out_time,
                                relative_path=file_path
                            ))
                            # self.logger.debug(f"Added item: {clip_name} ({duration:.2f} seconds)")
                            # self.logger.debug(f"File exists at {file_path}")
                        else:
                            self.logger.warning(f"File not found: {file_path}")
                    
                    # Move to next item
                    current_pos += clip_info_length + 2
                    
                except Exception as e:
                    self.logger.error(f"Error parsing item {i}: {e}", exc_info=True)
                    break
                    
        except Exception as e:
            self.logger.error(f"Error parsing playlist items: {e}", exc_info=True)
            return []
            
        if items:
            total_duration = sum((item.out_time - item.in_time) / 45000 for item in items)
            # self.logger.info(f"Found {len(items)} valid items in playlist, total duration: {total_duration:.2f} seconds")
            
        return items
    
    def find_main_playlist(self) -> PlaylistInfo:
        """Find the main movie playlist and return its info."""
        longest_duration = 0
        main_playlist = None
        title = self.bdmv_path.name.replace('.', ' ').strip()
        
        for mpls_file in sorted(self.playlist_path.glob('*.mpls')):
            try:
                # self.logger.debug(f"\nProcessing playlist: {mpls_file}")
                
                with open(mpls_file, 'rb') as f:
                    mpls_data = f.read()
                
                type_indicator, version, playlist_start = self._read_mpls_header(mpls_data)
                
                if type_indicator != 'MPLS':
                    continue
                    
                items = self._parse_playlist_items(mpls_data, playlist_start)
                
                if items:
                    total_duration = sum(item.out_time - item.in_time for item in items)
                    duration_seconds = total_duration / 45000
                    
                    # self.logger.debug(f"Playlist {mpls_file.name}: {len(items)} items, {duration_seconds:.2f} seconds")
                    
                    # Feature films are typically longer than 60 minutes
                    if duration_seconds > 3600:  # 60 minutes
                        if duration_seconds > longest_duration:
                            longest_duration = duration_seconds
                            total_size = sum(item.relative_path.stat().st_size for item in items)
                            main_playlist = PlaylistInfo(
                                items=items,
                                duration=duration_seconds,
                                size=total_size,
                                title=title
                            )
                            # self.logger.info(f"Found new main playlist: {mpls_file.name}")
            
            except Exception as e:
                self.logger.error(f"Error processing {mpls_file}: {e}")
                continue
        
        if main_playlist:
            self.logger.info(f"Selected main playlist: {len(main_playlist.items)} items, "
                           f"duration: {main_playlist.duration:.2f} seconds, "
                           f"size: {main_playlist.size / (1024*1024*1024):.2f} GB")
        else:
            self.logger.warning("No valid playlists found longer than 60 minutes")
        
        return main_playlist

    def get_concatenation_file(self, playlist_items: List[PlaylistItem]) -> str:
        """Generate FFmpeg concat demuxer file content."""
        concat_content = ["ffconcat version 1.0"]
        
        for item in playlist_items:
            escaped_path = str(item.relative_path).replace('\\', '/').replace("'", "'\\''")
            concat_content.append(f"file '{escaped_path}'")
            
            if item.in_time > 0:
                concat_content.append(f"inpoint {item.in_time / 45000:.6f}")
            if item.out_time < float('inf'):
                concat_content.append(f"outpoint {item.out_time / 45000:.6f}")
        
        return "\n".join(concat_content)