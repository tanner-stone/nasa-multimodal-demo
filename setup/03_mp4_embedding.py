"""
MP4 Video Embedding Script

This script processes video chunks, transcribes audio using OpenAI Whisper,
creates multimodal embeddings using Voyage AI, and stores them in MongoDB.

Usage:
    python 03_mp4_embedding.py

Environment Variables (Required):
    MONGO_CONNECTION_STRING: MongoDB Atlas connection string
    VOYAGE_API_KEY: Voyage AI API key
    OPENAI_API_KEY: OpenAI API key
    
Environment Variables (Optional):
    DATA_DIR: Base directory for data storage (default: './data')
    SEARCH_TERM: The search term used for scraping (default: 'NASA')
    DB_NAME: MongoDB database name (default: 'ts_multimodal_demo')
    COLLECTION_NAME: MongoDB collection name (default: 'nasa_archive')
"""

import os
import json
import pathlib
from dotenv import load_dotenv
import voyageai
from openai import OpenAI
from pymongo import MongoClient
from PIL import Image

# Load environment variables
load_dotenv()

# --- Configuration ---

# API Keys and MongoDB Connection (Required)
VOYAGE_API_KEY = os.getenv("VOYAGE_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
MONGO_CONNECTION_STRING = os.getenv("MONGO_CONNECTION_STRING")

# Directory paths
DATA_DIR = pathlib.Path(os.getenv('DATA_DIR', './data'))
SEARCH_TERM = os.getenv('SEARCH_TERM', 'NASA')

NARA_RECORDS_DIR = DATA_DIR / 'nara_records' / SEARCH_TERM / 'mp4'
NARA_CHUNKS_DIR = DATA_DIR / 'nara_video_chunks'

# MongoDB setup
DB_NAME = os.getenv('DB_NAME', 'ts_multimodal_demo')
COLLECTION_NAME = os.getenv('COLLECTION_NAME', 'nasa_archive')

# Initialize API clients
voyage_client = None
openai_client = None

try:
    if VOYAGE_API_KEY:
        voyage_client = voyageai.Client(api_key=VOYAGE_API_KEY)
except Exception as e:
    print(f"Error initializing Voyage AI client: {e}")

try:
    if OPENAI_API_KEY:
        openai_client = OpenAI(api_key=OPENAI_API_KEY)
except Exception as e:
    print(f"Error initializing OpenAI client: {e}")

def get_pil_image(image_path):
    """Opens and returns a PIL.Image object from an image file."""
    try:
        if not os.path.exists(image_path):
            print(f"File not found: {image_path}")
            return None
        
        image = Image.open(image_path)
        # Convert to RGB to ensure compatibility with various image formats
        if image.mode != 'RGB':
            image = image.convert('RGB')
        return image
    except Exception as e:
        print(f"Error opening image {image_path}: {e}")
        return None

def transcribe_audio_whisper(audio_file_path):
    """Transcribes an audio file using OpenAI's Whisper model."""
    try:
        with open(audio_file_path, "rb") as audio_file:
            transcript = openai_client.audio.transcriptions.create(
                model="whisper-1",
                file=audio_file
            )
        return transcript.text
    except Exception as e:
        print(f"Error transcribing audio {audio_file_path}: {e}")
        return None

def process_and_embed_video_files():
    """
    Orchestrates the entire process: reads metadata, transcribes audio,
    creates multimodal embeddings, and inserts documents into MongoDB.
    """
    # Validate required environment variables
    if not all([VOYAGE_API_KEY, OPENAI_API_KEY, MONGO_CONNECTION_STRING]):
        print("Error: Please set VOYAGE_API_KEY, OPENAI_API_KEY, and MONGO_CONNECTION_STRING environment variables.")
        return
    
    if not voyage_client or not openai_client:
        print("API clients failed to initialize. Cannot proceed.")
        return

    # MongoDB connection setup
    try:
        mongo_client = MongoClient(MONGO_CONNECTION_STRING)
        db = mongo_client[DB_NAME]
        collection = db[COLLECTION_NAME]
        print(f"Connected to MongoDB Atlas: {DB_NAME}.{COLLECTION_NAME}")
    except Exception as e:
        print(f"Error connecting to MongoDB: {e}")
        return

    # Check if the records directory exists
    if not NARA_RECORDS_DIR.exists():
        print(f"Error: NARA_RECORDS_DIR does not exist at {NARA_RECORDS_DIR}")
        return
    
    record_files = list(NARA_RECORDS_DIR.glob("*.json"))
    if not record_files:
        print(f"No JSON metadata files found in {NARA_RECORDS_DIR}")
        return

    print(f"Found {len(record_files)} metadata files to process.")

    # Iterate through all JSON metadata files
    for metadata_file_path in record_files:
        try:
            with open(metadata_file_path, 'r') as f:
                record_metadata = json.load(f)
        except Exception as e:
            print(f"Error reading metadata file {metadata_file_path}: {e}. Skipping.")
            continue
        
        na_id = record_metadata.get('naId')
        
        # Filter for MP4 files only
        digital_objects = [
            obj for obj in record_metadata.get('digitalObjects', [])
            if obj.get('objectFilename', '').endswith('.mp4')
        ]

        if not digital_objects:
            continue

        print(f"\nProcessing record NAID: {na_id} with {len(digital_objects)} MP4 files.")
        
        for obj in digital_objects:
            video_filename = obj['objectFilename']
            video_name = pathlib.Path(video_filename).stem
            
            # Find the corresponding chunk directory
            video_chunks_dir = NARA_CHUNKS_DIR / video_name
            if not video_chunks_dir.exists():
                print(f"  - No chunk directory found for {video_name}. Skipping.")
                continue

            # Load the chunk metadata JSON
            chunk_metadata_path = video_chunks_dir / f"{video_name}_metadata.json"
            if not chunk_metadata_path.exists():
                print(f"  - No metadata file found for {video_name}. Skipping.")
                continue

            with open(chunk_metadata_path, 'r') as f:
                video_metadata = json.load(f)

            # Loop through each chunk within the video
            for chunk_data in video_metadata['chunks']:
                chunk_id = chunk_data['chunk_id']
                
                # Check if this chunk has already been embedded and inserted
                if collection.find_one({'_id': f"{na_id}_{chunk_id}"}):
                    print(f"  - Chunk {chunk_id} already exists in DB. Skipping.")
                    continue

                print(f"  - Embedding chunk {chunk_id}...")
                
                # --- 1. Transcribe Audio ---
                audio_path = pathlib.Path(chunk_data['audio_file'])
                if not audio_path.exists():
                    print(f"    - Audio file not found at {audio_path}. Skipping chunk.")
                    continue

                transcript = transcribe_audio_whisper(audio_path)
                if not transcript:
                    print(f"    - Transcription failed for {audio_path}. Skipping chunk.")
                    continue
                print(f"    - Transcript: '{transcript[:50]}...'")

                # --- 2. Prepare Multimodal Input (Transcript + Frames) ---
                input_content = [transcript]  # Start with the text transcript
                
                # Get PIL Image objects for all frames
                for frame_path_str in chunk_data['frame_files']:
                    frame_path = pathlib.Path(frame_path_str)
                    pil_image = get_pil_image(frame_path)
                    if pil_image:
                        input_content.append(pil_image)

                # --- 3. Create Multimodal Embedding with Voyage AI ---
                if len(input_content) < 2:  # Check if there is at least a transcript and one image
                    print(f"    - Not enough content to create a multimodal embedding for {chunk_id}. Skipping.")
                    continue
                
                try:
                    result = voyage_client.multimodal_embed(
                        inputs=[input_content],
                        model="voyage-multimodal-3",
                        input_type="document"
                    )
                    embedding = result.embeddings[0]
                except Exception as e:
                    print(f"    - Voyage AI embedding failed: {e}. Skipping chunk.")
                    continue

                # --- 4. Construct MongoDB Document ---
                mongo_doc = {
                    "_id": f"{na_id}_{chunk_id}",
                    "naId": na_id,
                    "title": record_metadata.get('title'),
                    "subtitle": record_metadata.get('subtitle'),
                    "scopeAndContentNote": record_metadata.get('scopeAndContentNote'),
                    "source_file_name": video_filename,
                    "source_s3_path": obj.get('objectUrl'),
                    "file_type": "video_chunk",
                    "chunk_text_content": transcript,
                    "start_timestamp": chunk_data['start_time'],
                    "end_timestamp": chunk_data['end_time'],
                    "embedding": embedding
                }
                
                # --- 5. Insert into MongoDB ---
                try:
                    collection.insert_one(mongo_doc)
                    print(f"    - Successfully inserted chunk {chunk_id} into MongoDB.")
                except Exception as e:
                    print(f"    - Failed to insert chunk {chunk_id} into MongoDB: {e}")

    print("\n--- Video embedding complete ---")

def main():
    """Main function to run the video embedding process."""
    print("--- Starting MP4 Video Embedding ---")
    print(f"Data directory: {DATA_DIR}")
    print(f"Records directory: {NARA_RECORDS_DIR}")
    print(f"Chunks directory: {NARA_CHUNKS_DIR}")
    print(f"MongoDB: {DB_NAME}.{COLLECTION_NAME}")
    
    process_and_embed_video_files()

if __name__ == "__main__":
    main()
