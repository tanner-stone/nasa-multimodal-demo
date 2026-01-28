"""
MP4 Video Processing Script

This script processes MP4 video files by splitting them into chunks with audio and video frames.
Each chunk is 10 seconds long with 5 extracted frames and an MP3 audio file.

Usage:
    python 02_mp4_processing.py

Environment Variables:
    DATA_DIR: Base directory for data storage (default: './data')
    SEARCH_TERM: The search term used for scraping (default: 'NASA')
    CHUNK_DURATION: Duration of each chunk in seconds (default: 10)
    FRAMES_PER_CHUNK: Number of frames to extract per chunk (default: 5)

Requirements:
    - ffmpeg-python
    - ffmpeg binary installed on system
"""

import os
import pathlib
import ffmpeg
import json

# --- Configuration ---

# Base directory for data storage
DATA_DIR = pathlib.Path(os.getenv('DATA_DIR', './data'))
SEARCH_TERM = os.getenv('SEARCH_TERM', 'NASA')

# The root directory containing your downloaded MP4 files
SOURCE_DIR = DATA_DIR / 'nara_downloads' / SEARCH_TERM / 'mp4'

# The root directory where the new video chunks will be saved
OUTPUT_DIR = DATA_DIR / 'nara_video_chunks'

# Chunk processing parameters
CHUNK_DURATION = int(os.getenv('CHUNK_DURATION', '10'))
FRAMES_PER_CHUNK = int(os.getenv('FRAMES_PER_CHUNK', '5'))

# Create the output directory if it doesn't exist
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

def process_video_chunks(source_dir, output_dir, chunk_duration=10, frames_per_chunk=5):
    """
    Processes all MP4 files in a source directory by splitting them into
    chunks with audio and video frames. Each chunk will have a corresponding MP3
    file and JPG frames. A JSON metadata file is created to link the
    chunks back to the original file.

    Args:
        source_dir (pathlib.Path): The directory with the source MP4 files.
        output_dir (pathlib.Path): The directory to save the output chunks.
        chunk_duration (int): The duration in seconds of each chunk.
        frames_per_chunk (int): The number of frames to extract per chunk.
    """
    if not source_dir.exists():
        print(f"Source directory not found: {source_dir}. Exiting.")
        return

    mp4_files = list(source_dir.glob("*.mp4"))
    if not mp4_files:
        print(f"No MP4 files found in {source_dir}. Exiting.")
        return

    print(f"Found {len(mp4_files)} MP4 files to process.")

    # Loop through all MP4 files in the source directory
    for video_file_path in mp4_files:
        original_filename = video_file_path.name
        video_name = video_file_path.stem
        
        print(f"\n--- Processing video: {original_filename} ---")
        
        # Create a specific sub-directory for this video's chunks
        video_output_path = output_dir / video_name
        video_output_path.mkdir(parents=True, exist_ok=True)
        
        # Get the total duration of the video
        try:
            probe = ffmpeg.probe(str(video_file_path))
            duration = float(probe['format']['duration'])
        except ffmpeg.Error as e:
            print(f"Error probing video duration for {original_filename}: {e.stderr.decode('utf8')}")
            continue

        # Calculate the interval for frame extraction
        frame_interval = chunk_duration / frames_per_chunk

        # Process the video in chunks
        chunk_metadata = {
            "source_file": str(video_file_path),
            "duration_seconds": duration,
            "chunks": []
        }
        
        for i, start_time in enumerate(range(0, int(duration), chunk_duration)):
            end_time = start_time + chunk_duration
            if end_time > duration:
                end_time = duration
                
            chunk_name = f"{video_name}_chunk_{i:03d}"
            chunk_output_path = video_output_path / chunk_name
            chunk_output_path.mkdir(parents=True, exist_ok=True)

            print(f"  - Creating chunk {i+1} from {start_time:.2f}s to {end_time:.2f}s")
            
            # --- Extract Audio Snippet ---
            audio_output_path = chunk_output_path / f"{chunk_name}.mp3"
            if not audio_output_path.exists():
                try:
                    stream = ffmpeg.input(str(video_file_path), ss=start_time, t=chunk_duration)
                    stream = ffmpeg.output(stream, str(audio_output_path))
                    ffmpeg.run(stream, capture_stdout=True, capture_stderr=True, overwrite_output=True)
                    print(f"    -> Extracted audio to {audio_output_path.name}")
                except ffmpeg.Error as e:
                    print(f"    -> Error extracting audio: {e.stderr.decode('utf8')}")
                    
            # --- Extract Video Frames ---
            frame_paths = []
            for j in range(frames_per_chunk):
                frame_time = start_time + (j * frame_interval)
                frame_output_path = chunk_output_path / f"{chunk_name}_frame_{j+1}.jpg"
                frame_paths.append(str(frame_output_path))

                if not frame_output_path.exists():
                    try:
                        stream = ffmpeg.input(str(video_file_path), ss=frame_time)
                        stream = ffmpeg.output(stream, str(frame_output_path), vframes=1)
                        ffmpeg.run(stream, capture_stdout=True, capture_stderr=True, overwrite_output=True)
                        print(f"    -> Extracted frame {j+1} at {frame_time:.2f}s")
                    except ffmpeg.Error as e:
                        print(f"    -> Error extracting frame: {e.stderr.decode('utf8')}")
            
            # Save chunk metadata
            chunk_metadata["chunks"].append({
                "chunk_id": chunk_name,
                "start_time": start_time,
                "end_time": end_time,
                "audio_file": str(audio_output_path),
                "frame_files": frame_paths
            })
            
        # Save the full video's metadata JSON file
        metadata_path = video_output_path / f"{video_name}_metadata.json"
        with open(metadata_path, "w") as f:
            json.dump(chunk_metadata, f, indent=4)
        print(f"\nSaved metadata for {original_filename}")

def main():
    """Main function to run the video processing."""
    print("--- Starting MP4 Video Processing ---")
    print(f"Source directory: {SOURCE_DIR}")
    print(f"Output directory: {OUTPUT_DIR}")
    print(f"Chunk duration: {CHUNK_DURATION} seconds")
    print(f"Frames per chunk: {FRAMES_PER_CHUNK}")
    
    process_video_chunks(SOURCE_DIR, OUTPUT_DIR, CHUNK_DURATION, FRAMES_PER_CHUNK)
    
    print("\n--- Video processing complete ---")

if __name__ == "__main__":
    main()
