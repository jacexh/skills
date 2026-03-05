#!/usr/bin/env python3
import argparse
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

VIDEO_EXTENSIONS = {'.mp4', '.mkv', '.avi', '.mov', '.flv', '.wmv', '.m4v'}


def get_video_files(directory: str) -> list[str]:
    """Get all video files from a directory."""
    return [str(f) for f in Path(directory).iterdir() if f.suffix.lower() in VIDEO_EXTENSIONS]


def natural_sort_key(s: str) -> list[int | str]:
    """Key function for natural sorting (e.g., 1.mp4, 2.mp4, 10.mp4)."""
    return [int(text) if text.isdigit() else text.lower()
            for text in re.split(r'([0-9]+)', s)]


def merge_videos(input_files: list[str], output_file: str, reencode: bool = False) -> bool:
    """Merge multiple video files into one using ffmpeg."""
    if not input_files:
        print("Error: No input files provided.")
        return False

    try:
        if not reencode:
            # Concat demuxer method (fastest, requires matching stream parameters)
            with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
                for video in input_files:
                    # Use absolute path and escape single quotes for ffmpeg concat file
                    abs_path = os.path.abspath(video).replace("'", "'\\''")
                    f.write(f"file '{abs_path}'\n")
                temp_file_path = f.name

            try:
                cmd = [
                    'ffmpeg', '-y', '-f', 'concat', '-safe', '0',
                    '-i', temp_file_path, '-c', 'copy', output_file
                ]
                print(f"Executing: {' '.join(cmd)}")
                subprocess.run(
                    cmd, check=True,
                    stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True,
                )
                print(f"Successfully merged {len(input_files)} videos to {output_file}")
                return True
            except subprocess.CalledProcessError as e:
                print("Error: Fast merge (copy) failed. Fallback to re-encoding might be needed.")
                print(f"ffmpeg stderr: {e.stderr}")
                return False
            finally:
                Path(temp_file_path).unlink(missing_ok=True)
        else:
            print("Re-encoding merge not yet implemented.")
            return False

    except OSError as e:
        print(f"An unexpected error occurred: {e}")
        return False


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Merge multiple video files into one using ffmpeg."
    )
    parser.add_argument("inputs", nargs="*", help="Input video files in order.")
    parser.add_argument("-d", "--dir", help="Directory containing video files to merge.")
    parser.add_argument("-o", "--output", default="merged_output.mp4", help="Output video file name.")
    parser.add_argument(
        "-s", "--sort", choices=['name', 'time'], default='name',
        help="Sort order for directory files (default: name).",
    )

    args = parser.parse_args()

    input_list = []
    if args.dir:
        if not os.path.isdir(args.dir):
            print(f"Error: {args.dir} is not a directory.")
            sys.exit(1)

        input_list = get_video_files(args.dir)
        if args.sort == 'name':
            input_list.sort(key=natural_sort_key)
        elif args.sort == 'time':
            input_list.sort(key=os.path.getmtime)

        print(f"Found {len(input_list)} video files in directory: {args.dir}")
    else:
        input_list = args.inputs

    if not input_list:
        print("Error: No input files or directory specified.")
        parser.print_help()
        sys.exit(1)

    if merge_videos(input_list, args.output):
        sys.exit(0)
    else:
        sys.exit(1)
