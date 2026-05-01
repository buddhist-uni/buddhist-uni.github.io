#!/bin/python3
import subprocess
from pathlib import Path
from strutils import thumbnail_path_for_file, THUMBNAIL_SIZES

def render_video_thumbnail(video_path: Path, size=128) -> bytes:
    """Uses ffmpeg to extract a frame from a video file."""
    try:
        # We try to get a frame at 1 second in.
        # -ss 5: seek to 5 seconds
        # -i: input file
        # -vf scale: resize maintaining aspect ratio
        # -vframes 1: extract 1 frame
        # -f image2pipe: output as image pipe
        # -vcodec png: encode as png
        cmd = [
            'ffmpeg',
            '-ss', '5',
            '-i', str(video_path),
            '-vf', f'thumbnail,scale={size}:-1',
            '-vframes', '1',
            '-f', 'image2pipe',
            '-vcodec', 'png',
            '-'
        ]
        # We use a short timeout and capture output
        result = subprocess.run(cmd, capture_output=True, timeout=10)
        if result.returncode == 0:
            return result.stdout
        else:
            print(f"ffmpeg error for {video_path}: {result.stderr.decode(errors='replace')}")
            return b''
    except subprocess.TimeoutExpired:
        print(f"ffmpeg timed out for {video_path}")
        return b''
    except Exception as e:
        print(f"Error rendering video thumbnail for {video_path}: {e}")
        return b''

def get_cached_video_thumbnail(video_path: Path, size='normal') -> bytes:
    """Returns the cached thumbnail bytes for a video file, or generates it if missing."""
    thumbnail_path = thumbnail_path_for_file(video_path, shared=True, size=size)
    if thumbnail_path.is_file():
        return thumbnail_path.read_bytes()
    
    # Also check non-shared cache
    alt_path = thumbnail_path_for_file(video_path, shared=False, size=size)
    if alt_path.is_file():
        return alt_path.read_bytes()

    tsize = THUMBNAIL_SIZES[size]
    thebytes = render_video_thumbnail(video_path, size=tsize)
    if thebytes:
        thumbnail_path.parent.mkdir(exist_ok=True, parents=True)
        thumbnail_path.write_bytes(thebytes)
    return thebytes
