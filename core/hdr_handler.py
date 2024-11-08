import logging
import re
from typing import Dict, List, Optional, Union
from fractions import Fraction
from models.media_info import HDRMetadata

class HDRHandler:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def _get_stream_value(self, metadata: Dict, *keys: str, default: str = "unknown") -> str:
        for key in keys:
            value = metadata.get(key)
            if value:
                return str(value).lower()
        return default

    def _safe_int(self, value, default: int = 8) -> int:
        if value is None:
            return default
        try:
            return int(value)
        except (ValueError, TypeError):
            return default

    def _safe_float(self, value, default: float = 0.0) -> float:
        """Safely convert value to float, handling fraction strings"""
        if value is None:
            return default
        try:
            if isinstance(value, (int, float)):
                return float(value)
            # Handle fraction strings like "0/10000"
            if '/' in str(value):
                return float(Fraction(value))
            return float(value)
        except (ValueError, TypeError):
            self.logger.warning(f"Could not convert {value} to float, using default {default}")
            return default

    def _format_master_display(self, display_data: str) -> Optional[str]:
        try:
            coords = re.findall(r'([RGB])\((\d+),(\d+)\)', display_data)
            wp = re.findall(r'WP\((\d+),(\d+)\)', display_data)
            lum = re.findall(r'L\((\d+),(\d+)\)', display_data)
            
            if coords and wp and lum:
                points = []
                coords = sorted(coords, key=lambda x: x[0])
                for _, x, y in coords:
                    points.extend([x, y])
                points.extend(wp[0])
                points.extend(lum[0])
                return 'G(%s,%s)B(%s,%s)R(%s,%s)WP(%s,%s)L(%s,%s)' % tuple(points)
            return None
        except Exception as e:
            self.logger.warning(f'Error parsing master display data: {e}')
            return None

    def detect_hdr_format(self, metadata: Dict) -> HDRMetadata:
        transfer = self._get_stream_value(metadata, 'color_transfer', 'transfer_characteristics')
        primaries = self._get_stream_value(metadata, 'color_primaries')
        color_matrix = self._get_stream_value(metadata, 'color_space', 'color_matrix')
        bit_depth = self._safe_int(metadata.get('bits_per_raw_sample'))
        
        self.logger.debug(f"Detected color values - Transfer: {transfer}, Primaries: {primaries}, Matrix: {color_matrix}, Bit depth: {bit_depth}")
        
        hdr_metadata = HDRMetadata(
            color_primaries=primaries,
            transfer_characteristics=transfer,
            color_matrix=color_matrix,
            bit_depth=bit_depth,
            is_hdr=False
        )
        
        # Check for Dolby Vision
        tags = metadata.get('tags', {})
        if isinstance(tags, dict):
            dovi_flag = any(str(v).startswith('dovi') for v in tags.values())
        else:
            dovi_flag = any(str(getattr(tag, 'value', '')).startswith('dovi') for tag in tags)
            
        if dovi_flag:
            hdr_metadata.hdr_format = "dolby_vision"
            hdr_metadata.is_hdr = True
            if isinstance(tags, dict):
                profile = next((str(v) for k, v in tags.items() if 'dv_profile' in str(k)), None)
            else:
                profile = next((str(getattr(tag, 'value', '')) for tag in tags 
                              if 'dv_profile' in str(getattr(tag, 'key', ''))), None)
            if profile:
                hdr_metadata.dolby_vision_profile = profile
            hdr_metadata.dolby_vision_rpu = any('dv_rpu' in str(s) for s in metadata.get('side_data_list', []))
        
        # Check for HDR10+
        elif any('dhdr' in str(s) for s in metadata.get('side_data_list', [])):
            hdr_metadata.hdr_format = "hdr10plus"
            hdr_metadata.is_hdr = True
        
        # Check for HDR10
        elif transfer == 'smpte2084' and primaries == 'bt2020':
            hdr_metadata.hdr_format = "hdr10"
            hdr_metadata.is_hdr = True
        
        # Check for HLG
        elif transfer == 'arib-std-b67':
            hdr_metadata.hdr_format = "hlg"
            hdr_metadata.is_hdr = True
        
        # Parse HDR metadata from side data
        for side_data in metadata.get('side_data_list', []):
            if isinstance(side_data, dict):
                data_type = side_data.get('side_data_type', '')
                
                if data_type == 'Content light level metadata':
                    max_content = self._safe_int(side_data.get('max_content'), 0)
                    max_average = self._safe_int(side_data.get('max_average'), 0)
                    hdr_metadata.max_cll = f"{max_content},{max_average}"
                    
                elif data_type == 'Mastering display metadata':
                    hdr_metadata.max_luminance = self._safe_int(side_data.get('max_luminance'), 0)
                    hdr_metadata.min_luminance = self._safe_float(side_data.get('min_luminance', 0))
                    display = side_data.get('master_display_primaries', '')
                    if display:
                        hdr_metadata.master_display = self._format_master_display(display)
        
        if hdr_metadata.is_hdr:
            self.logger.info(f"Detected {hdr_metadata.hdr_format} content with {hdr_metadata.bit_depth}-bit depth")
            if hdr_metadata.max_cll:
                self.logger.info(f"MaxCLL: {hdr_metadata.max_cll}")
            if hdr_metadata.master_display:
                self.logger.info(f"Master Display: {hdr_metadata.master_display}")
        else:
            self.logger.info("No HDR format detected, treating as SDR content")
            
        return hdr_metadata

    def get_encoding_params(self, hdr_metadata: HDRMetadata, encoder: str = 'libx265') -> List[str]:
        if not hdr_metadata.is_hdr:
            return []
            
        self.logger.info(f'Configuring {hdr_metadata.hdr_format} encoding parameters')
        
        params = [
            'hdr10=1',
            'repeat-headers=1',
            'range=limited'
        ]
        
        if hdr_metadata.color_primaries != "unknown":
            params.append(f'colorprim={hdr_metadata.color_primaries}')
        if hdr_metadata.transfer_characteristics != "unknown":
            params.append(f'transfer={hdr_metadata.transfer_characteristics}')
        if hdr_metadata.color_matrix != "unknown":
            params.append(f'colormatrix={hdr_metadata.color_matrix}')
        
        if encoder == 'libx265':
            if hdr_metadata.hdr_format == "hdr10":
                params.extend([
                    'hdr10-opt=1',
                    'annexb=1'
                ])
                if hdr_metadata.master_display:
                    params.append(f'master-display={hdr_metadata.master_display}')
                if hdr_metadata.max_cll:
                    params.append(f'max-cll={hdr_metadata.max_cll}')
                    
            elif hdr_metadata.hdr_format == "hdr10plus":
                params.extend([
                    'hdr10-opt=1',
                    'dhdr10-info=metadata',
                    'annexb=1'
                ])
                
            elif hdr_metadata.hdr_format == "hlg":
                params.extend([
                    'hdr10=0',
                    'repeat-headers=1',
                    'range=limited'
                ])
                
            elif hdr_metadata.hdr_format == "dolby_vision":
                profile = hdr_metadata.dolby_vision_profile
                if profile in ['5', '8.1', '8.2', '8.4']:
                    params.extend([
                        'hdr10-opt=1',
                        'annexb=1',
                        f'dolby-vision-profile={profile}'
                    ])
                    if hdr_metadata.dolby_vision_rpu:
                        params.append('dolby-vision-rpu=metadata')
        
        elif encoder == 'hevc_nvenc':
            params.extend([
                'strict_gop=1',
                'ref=6',
                'b_ref_mode=middle',
                'nonref_p=1'
            ])
            
        self.logger.debug(f'Generated HDR parameters: {params}')
        return params