import logging
from typing import Dict, List
from models.media_info import HDRMetadata

class HDRHandler:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def _format_master_display(self, display_data: str) -> str:
        try:
            coords = re.findall(r'([RGB])\((\d+),(\d+)\)', display_data)
            wp = re.findall(r'WP\((\d+),(\d+)\)', display_data)
            lum = re.findall(r'L\((\d+),(\d+)\)', display_data)
            if coords and wp and lum:
                points = []
                for color, x, y in sorted(coords):  # Sort to ensure G,B,R order
                    points.extend([x, y])
                points.extend(wp[0])
                points.extend(lum[0])
                return 'G(%s,%s)B(%s,%s)R(%s,%s)WP(%s,%s)L(%s,%s)' % tuple(points)
        except Exception as e:
            self.logger.warning(f'Error parsing master display data: {e}')
        return None

    def detect_hdr_format(self, metadata: Dict) -> HDRMetadata:
        """Detect HDR format from stream metadata"""
        transfer = metadata.get('color_transfer', '').lower()
        primaries = metadata.get('color_primaries', '').lower()
        bit_depth = int(metadata.get('bits_per_raw_sample', 8))
        
        hdr_metadata = HDRMetadata(
            color_primaries=primaries,
            transfer_characteristics=transfer,
            color_matrix=metadata.get('color_space', 'unknown'),
            bit_depth=bit_depth,
            is_hdr=False
        )
        
        # Detect HDR formats
        if any(tag.get('value', '').startswith('dovi') for tag in metadata.get('tags', [])):
            hdr_metadata.hdr_format = "dolby_vision"
            hdr_metadata.is_hdr = True
            profile_tag = next((tag for tag in metadata.get('tags', []) if tag.get('key') == 'dv_profile'), None)
            if profile_tag:
                hdr_metadata.dolby_vision_profile = profile_tag.get('value')
            hdr_metadata.dolby_vision_rpu = any('dv_rpu' in str(s) for s in metadata.get('side_data_list', []))
        elif any('dhdr' in str(s) for s in metadata.get('side_data_list', [])):
            hdr_metadata.hdr_format = "hdr10plus"
            hdr_metadata.is_hdr = True
        elif transfer == 'smpte2084' and primaries == 'bt2020':
            hdr_metadata.hdr_format = "hdr10"
            hdr_metadata.is_hdr = True
        elif transfer == 'arib-std-b67':
            hdr_metadata.hdr_format = "hlg"
            hdr_metadata.is_hdr = True
        
        # Parse HDR metadata
        for side_data in metadata.get('side_data_list', []):
            if side_data.get('side_data_type') == 'Content light level metadata':
                max_content = side_data.get('max_content', 0)
                max_average = side_data.get('max_average', 0)
                hdr_metadata.max_cll = f"{max_content},{max_average}"
            elif side_data.get('side_data_type') == 'Mastering display metadata':
                max_lum = side_data.get('max_luminance', 0)
                min_lum = side_data.get('min_luminance', 0)
                hdr_metadata.max_luminance = max_lum
                hdr_metadata.min_luminance = min_lum
                display = side_data.get('master_display_primaries', '')
                if display:
                    hdr_metadata.master_display = self._format_master_display(display)
        
        return hdr_metadata
    
    def get_encoding_params(self, hdr_metadata: HDRMetadata, encoder: str = 'libx265') -> List[str]:
        """Generate encoding parameters based on HDR format"""
        if not hdr_metadata.is_hdr:
            return []
            
        self.logger.info(f'Configuring {hdr_metadata.hdr_format} encoding parameters')
        
        params = [
            'hdr10=1',
            'repeat-headers=1',
            'range=limited',
            f'colorprim={hdr_metadata.color_primaries}',
            f'transfer={hdr_metadata.transfer_characteristics}',
            f'colormatrix={hdr_metadata.color_matrix}'
        ]
        
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