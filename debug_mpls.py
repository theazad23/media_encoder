import struct
from pathlib import Path

def debug_mpls(file_path):
    with open(file_path, 'rb') as f:
        data = f.read()
        
    print(f"File size: {len(data)} bytes")
    print(f"Header bytes (hex): {data[:16].hex()}")
    try:
        print(f"Header bytes (ascii): {data[:4].decode(errors='replace')}")
    except:
        print("Could not decode header as ASCII")
    
    # Try to find playlist mark start position
    if len(data) >= 12:
        try:
            playlist_start = struct.unpack('>I', data[8:12])[0]
            print(f"Playlist start position: {playlist_start}")
            
            if playlist_start < len(data):
                print(f"Data at playlist start (hex): {data[playlist_start:playlist_start+16].hex()}")
                
                # Try to get number of items
                if playlist_start + 6 <= len(data):
                    num_items = struct.unpack('>H', data[playlist_start+4:playlist_start+6])[0]
                    print(f"Number of items: {num_items}")
                    
                    # Debug first item
                    item_start = playlist_start + 6
                    if item_start + 16 <= len(data):
                        print(f"\nFirst item data (hex): {data[item_start:item_start+16].hex()}")
                        try:
                            item_length = struct.unpack('>H', data[item_start:item_start+2])[0]
                            print(f"First item length: {item_length}")
                            
                            # Try to get clip name
                            clip_info_start = item_start + 2
                            if clip_info_start + 5 <= len(data):
                                clip_name = data[clip_info_start:clip_info_start+5].hex()
                                print(f"Clip name (hex): {clip_name}")
                        except Exception as e:
                            print(f"Error parsing first item: {e}")
        except Exception as e:
            print(f"Error parsing playlist: {e}")

if __name__ == "__main__":
    # Analyze first few playlists
    mpls_dir = Path(r"C:\Users\anthony\Desktop\Toy.Story.1995\BDMV\PLAYLIST")
    print(f"Looking for MPLS files in: {mpls_dir}")
    
    if not mpls_dir.exists():
        print(f"Error: Directory {mpls_dir} does not exist!")
        exit(1)
        
    mpls_files = sorted(mpls_dir.glob("*.mpls"))
    if not mpls_files:
        print("No .mpls files found!")
        exit(1)
        
    for mpls_file in mpls_files[:3]:  # Check first 3 files
        print(f"\nAnalyzing {mpls_file.name}")
        print("-" * 50)
        debug_mpls(mpls_file)