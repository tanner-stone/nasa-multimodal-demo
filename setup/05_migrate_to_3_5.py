"""
Migration Script for voyage-multimodal-3.5

This script migrates documents from nasa_archive to nasa_archive_3_5 collection,
updating embeddings to use the new voyage-multimodal-3.5 model with native video support.

Key changes:
1. Video chunks: Uses Video API instead of frames + transcript
2. PDFs: Creates page-level chunks with overlapping pages
3. Adds no_clip_content field for video chunks with blank frames AND no meaningful transcript

Usage:
    python 05_migrate_to_3_5.py

Environment Variables (Required):
    MONGO_CONNECTION_STRING: MongoDB Atlas connection string
    VOYAGE_API_KEY: Voyage AI API key
    OPENAI_API_KEY: OpenAI API key (for transcription)
    
Environment Variables (Optional):
    DATA_DIR: Base directory for data storage (default: './data')
    SEARCH_TERM: The search term used for scraping (default: 'NASA')
    DB_NAME: MongoDB database name (default: 'ts_multimodal_demo')
    SOURCE_COLLECTION: Source collection name (default: 'nasa_archive')
    TARGET_COLLECTION: Target collection name (default: 'nasa_archive_3_5')
"""

import os
import json
import pathlib
import re
from io import BytesIO
from dotenv import load_dotenv
import voyageai
from voyageai.video_utils import Video
from openai import OpenAI
from pymongo import MongoClient
from PIL import Image
import fitz  # PyMuPDF
import numpy as np

# Load environment variables
load_dotenv()

# --- Configuration ---

# API Keys and MongoDB Connection (Required)
VOYAGE_API_KEY = os.getenv("VOYAGE_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
MONGO_CONNECTION_STRING = os.getenv("MONGO_CONNECTION_STRING")

# Directory paths - data is now in ./setup/data
SCRIPT_DIR = pathlib.Path(__file__).parent
DATA_DIR = pathlib.Path(os.getenv('DATA_DIR', SCRIPT_DIR / 'data'))
SEARCH_TERM = os.getenv('SEARCH_TERM', 'NASA')

NARA_RECORDS_DIR = DATA_DIR / 'nara_records' / SEARCH_TERM
NARA_DOWNLOADS_DIR = DATA_DIR / 'nara_downloads' / SEARCH_TERM
NARA_CHUNKS_DIR = DATA_DIR / 'nara_video_chunks'

# MongoDB setup
DB_NAME = os.getenv('DB_NAME', 'ts_multimodal_demo')
SOURCE_COLLECTION = os.getenv('SOURCE_COLLECTION', 'nasa_archive')
TARGET_COLLECTION = os.getenv('TARGET_COLLECTION', 'nasa_archive_3_5')

# Model configuration
MODEL_NAME = "voyage-multimodal-3.5"

# Image resizing parameters
MAX_IMAGE_DIM = int(os.getenv('MAX_IMAGE_DIM', '2048'))

# PDF chunking parameters
PDF_PAGES_PER_CHUNK = 2  # Overlapping chunks of 2 pages each
PDF_OVERLAP = 1  # 1 page overlap between chunks

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


# --- Utility Functions ---

def is_blank_frame(image: Image.Image, threshold: float = 0.95) -> bool:
    """
    Detects if an image is essentially blank (mostly single color).
    
    Args:
        image: PIL Image object
        threshold: Percentage of pixels that must be similar to consider blank
        
    Returns:
        True if the image is considered blank
    """
    try:
        # Convert to RGB if needed
        if image.mode != 'RGB':
            image = image.convert('RGB')
        
        # Resize to small size for faster processing
        small = image.resize((50, 50), Image.Resampling.LANCZOS)
        
        # Convert to numpy array
        arr = np.array(small)
        
        # Calculate the standard deviation of pixel values
        # Low std dev means mostly uniform color (blank)
        std_dev = np.std(arr)
        
        # Also check if it's very dark (black screen)
        mean_brightness = np.mean(arr)
        
        # Consider blank if:
        # 1. Very low variation (uniform color) - std dev < 15
        # 2. OR very dark (black screen) - mean brightness < 10
        is_uniform = std_dev < 15
        is_dark = mean_brightness < 10
        
        return is_uniform or is_dark
    except Exception as e:
        print(f"    - Error checking blank frame: {e}")
        return False


def is_meaningless_transcript(text: str) -> bool:
    """
    Checks if a transcript is meaningless (no real content).
    
    Args:
        text: The transcript text
        
    Returns:
        True if the transcript has no meaningful content
    """
    if not text:
        return True
    
    # Normalize text
    text = text.strip().lower()
    
    # Empty or very short
    if len(text) < 3:
        return True
    
    # Common meaningless patterns
    meaningless_patterns = [
        r'^you$',  # Just "you" (common Whisper artifact)
        r'^\.+\s*$',  # Just dots
        r'^[♪♫]+$',  # Just music symbols
        r'^thank you\.?$',
        r'^thanks\.?$',
        r'^thank you for watching\.?!?$',
        r'^thanks for watching\.?!?$',
        r'^thank you very much\.?$',
        r'^[\s\.]+$',  # Just whitespace and dots
        r'^©.*$',  # Copyright notices
        r'^subtitles.*$',  # Subtitle credits
        r'^ご視聴ありがとうございました$',  # Japanese "thank you for watching"
        r'^diolch.*$',  # Welsh thank you
        r'^субтитры.*$',  # Russian subtitles
    ]
    
    for pattern in meaningless_patterns:
        if re.match(pattern, text, re.IGNORECASE):
            return True
    
    return False


def resize_image(image: Image.Image, max_dim: int) -> Image.Image:
    """Resizes an image to a maximum dimension while maintaining aspect ratio."""
    width, height = image.size
    if width > max_dim or height > max_dim:
        if width > height:
            new_width = max_dim
            new_height = int(height * (max_dim / width))
        else:
            new_height = max_dim
            new_width = int(width * (max_dim / height))
        return image.resize((new_width, new_height), Image.Resampling.LANCZOS)
    return image


def get_pil_image(image_path):
    """Opens and returns a PIL.Image object from an image file."""
    try:
        if not os.path.exists(image_path):
            print(f"File not found: {image_path}")
            return None
        
        image = Image.open(image_path)
        if image.mode != 'RGB':
            image = image.convert('RGB')
        return resize_image(image, MAX_IMAGE_DIM)
    except Exception as e:
        print(f"Error opening image {image_path}: {e}")
        return None


def get_pil_images_from_pdf(pdf_path):
    """Converts each page of a PDF into a resized PIL.Image object."""
    try:
        if not os.path.exists(pdf_path):
            print(f"  - PDF file not found: {pdf_path}")
            return None
            
        doc = fitz.open(pdf_path)
        images = []
        for page_num in range(doc.page_count):
            pix = doc[page_num].get_pixmap()
            img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
            resized_img = resize_image(img, MAX_IMAGE_DIM)
            images.append(resized_img)
        doc.close()
        return images
    except Exception as e:
        print(f"  - Error processing PDF {pdf_path}: {e}")
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


# --- Video Chunk Migration ---

def migrate_video_chunks(source_collection, target_collection):
    """
    Migrates video chunks using voyage-multimodal-3.5 Video API.
    Also detects and flags no_clip_content for blank/silent clips.
    """
    print("\n=== Migrating Video Chunks ===")
    
    # Get all unique video files from source collection
    video_docs = list(source_collection.find(
        {"file_type": "video_chunk"},
        {"naId": 1, "source_file_name": 1}
    ).distinct("source_file_name"))
    
    # Actually, let's get the metadata files from the chunks directory
    if not NARA_CHUNKS_DIR.exists():
        print(f"Error: Video chunks directory not found at {NARA_CHUNKS_DIR}")
        return
    
    # Get all video metadata files
    video_dirs = [d for d in NARA_CHUNKS_DIR.iterdir() if d.is_dir()]
    print(f"Found {len(video_dirs)} video directories to process.")
    
    # Get the NARA records for metadata
    mp4_records_dir = NARA_RECORDS_DIR / 'mp4'
    
    for video_dir in video_dirs:
        video_name = video_dir.name
        metadata_path = video_dir / f"{video_name}_metadata.json"
        
        if not metadata_path.exists():
            print(f"  - No metadata file for {video_name}. Skipping.")
            continue
        
        with open(metadata_path, 'r') as f:
            video_metadata = json.load(f)
        
        # Find the corresponding NARA record
        record_metadata = None
        na_id = None
        obj_data = None
        
        for record_file in mp4_records_dir.glob("*.json"):
            with open(record_file, 'r') as f:
                record = json.load(f)
            
            for obj in record.get('digitalObjects', []):
                if obj.get('objectFilename', '').replace('.mp4', '') == video_name:
                    record_metadata = record
                    na_id = record.get('naId')
                    obj_data = obj
                    break
            
            if record_metadata:
                break
        
        if not record_metadata:
            print(f"  - No NARA record found for {video_name}. Skipping.")
            continue
        
        print(f"\nProcessing video: {video_name} (NAID: {na_id})")
        
        # Process each chunk
        for chunk_data in video_metadata['chunks']:
            chunk_id = chunk_data['chunk_id']
            doc_id = f"{na_id}_{chunk_id}"
            
            # Check if already migrated
            if target_collection.find_one({'_id': doc_id}):
                print(f"  - Chunk {chunk_id} already exists in target. Skipping.")
                continue
            
            print(f"  - Processing chunk {chunk_id}...")
            
            # --- 1. Check for blank frames ---
            frame_paths = chunk_data.get('frame_files', [])
            blank_frame_count = 0
            total_frames = len(frame_paths)
            
            for frame_path in frame_paths:
                pil_image = get_pil_image(frame_path)
                if pil_image and is_blank_frame(pil_image):
                    blank_frame_count += 1
            
            frames_are_blank = (blank_frame_count / total_frames) >= 0.8 if total_frames > 0 else True
            
            # --- 2. Get transcript ---
            audio_path = pathlib.Path(chunk_data['audio_file'])
            transcript = ""
            if audio_path.exists():
                transcript = transcribe_audio_whisper(audio_path) or ""
            
            transcript_is_meaningless = is_meaningless_transcript(transcript)
            
            # --- 3. Determine no_clip_content ---
            no_clip_content = frames_are_blank and transcript_is_meaningless
            
            if no_clip_content:
                print(f"    - Flagged as no_clip_content (blank frames: {frames_are_blank}, meaningless transcript: '{transcript[:30]}...')")
            
            # --- 4. Create Video object and embed ---
            # Find the chunk MP4 file (we need to create it or use the original with timestamp)
            # For now, we'll use the original video with the Video API
            # The Video.from_path method can handle the full video, but we want just the chunk
            
            # Actually, we need to create a temporary chunk file or use the frames
            # Let's use the chunk's MP4 if it exists, otherwise fall back to frames
            chunk_mp4_path = video_dir / chunk_id / f"{chunk_id}.mp4"
            
            try:
                if chunk_mp4_path.exists():
                    # Use the Video API with the chunk file
                    video_obj = Video.from_path(str(chunk_mp4_path), model=MODEL_NAME)
                    
                    # Create multimodal input with video and transcript
                    if transcript and not transcript_is_meaningless:
                        input_content = [video_obj, transcript]
                    else:
                        input_content = [video_obj]
                    
                    result = voyage_client.multimodal_embed(
                        inputs=[input_content],
                        model=MODEL_NAME,
                        input_type="document"
                    )
                    embedding = result.embeddings[0]
                else:
                    # Fall back to using frames + transcript (like before but with 3.5)
                    print(f"    - No chunk MP4 found, using frames instead")
                    input_content = []
                    
                    if transcript and not transcript_is_meaningless:
                        input_content.append(transcript)
                    
                    for frame_path in frame_paths:
                        pil_image = get_pil_image(frame_path)
                        if pil_image:
                            input_content.append(pil_image)
                    
                    if not input_content:
                        print(f"    - No content to embed for {chunk_id}. Skipping.")
                        continue
                    
                    result = voyage_client.multimodal_embed(
                        inputs=[input_content],
                        model=MODEL_NAME,
                        input_type="document"
                    )
                    embedding = result.embeddings[0]
                    
            except Exception as e:
                print(f"    - Voyage AI embedding failed: {e}. Skipping chunk.")
                continue
            
            # --- 5. Construct MongoDB Document ---
            mongo_doc = {
                "_id": doc_id,
                "naId": na_id,
                "title": record_metadata.get('title'),
                "subtitle": record_metadata.get('subtitle'),
                "scopeAndContentNote": record_metadata.get('scopeAndContentNote'),
                "source_file_name": obj_data.get('objectFilename'),
                "source_s3_path": obj_data.get('objectUrl'),
                "file_type": "video_chunk",
                "chunk_text_content": transcript,
                "start_timestamp": chunk_data['start_time'],
                "end_timestamp": chunk_data['end_time'],
                "no_clip_content": no_clip_content,
                "embedding": embedding
            }
            
            # --- 6. Insert into target collection ---
            try:
                target_collection.insert_one(mongo_doc)
                print(f"    - Successfully inserted chunk {chunk_id}.")
            except Exception as e:
                print(f"    - Failed to insert chunk {chunk_id}: {e}")


# --- PDF Migration with Page-Level Chunking ---

def migrate_pdfs(source_collection, target_collection):
    """
    Migrates PDF documents with page-level chunking.
    Creates overlapping chunks of pages for better retrieval.
    """
    print("\n=== Migrating PDFs with Page-Level Chunking ===")
    
    pdf_records_dir = NARA_RECORDS_DIR / 'pdf'
    if not pdf_records_dir.exists():
        print(f"No PDF records directory found at {pdf_records_dir}")
        return
    
    metadata_files = list(pdf_records_dir.glob("*.json"))
    print(f"Found {len(metadata_files)} PDF metadata files to process.")
    
    for metadata_file_path in metadata_files:
        with open(metadata_file_path, 'r') as f:
            record_metadata = json.load(f)
        
        na_id = record_metadata.get('naId')
        print(f"\nProcessing PDF record NAID: {na_id}")
        
        digital_objects = record_metadata.get('digitalObjects', [])
        
        for obj in digital_objects:
            filename = obj.get('objectFilename')
            if not filename or not filename.lower().endswith('.pdf'):
                continue
            
            local_file_path = NARA_DOWNLOADS_DIR / 'pdf' / filename
            
            # Get all pages as images
            page_images = get_pil_images_from_pdf(local_file_path)
            if not page_images:
                print(f"  - Could not extract pages from {filename}. Skipping.")
                continue
            
            total_pages = len(page_images)
            print(f"  - PDF has {total_pages} pages. Creating overlapping chunks...")
            
            # Create overlapping page chunks
            chunk_num = 0
            page_start = 0
            
            while page_start < total_pages:
                page_end = min(page_start + PDF_PAGES_PER_CHUNK, total_pages)
                chunk_pages = page_images[page_start:page_end]
                
                doc_id = f"{na_id}_page_{page_start + 1}_to_{page_end}"
                
                # Check if already migrated
                if target_collection.find_one({'_id': doc_id}):
                    print(f"    - Chunk {doc_id} already exists. Skipping.")
                    page_start += PDF_PAGES_PER_CHUNK - PDF_OVERLAP
                    chunk_num += 1
                    continue
                
                print(f"    - Creating chunk for pages {page_start + 1}-{page_end}...")
                
                # Create embedding for this page chunk
                try:
                    result = voyage_client.multimodal_embed(
                        inputs=[chunk_pages],
                        model=MODEL_NAME,
                        input_type="document"
                    )
                    embedding = result.embeddings[0]
                except Exception as e:
                    print(f"    - Voyage AI embedding failed: {e}. Skipping chunk.")
                    page_start += PDF_PAGES_PER_CHUNK - PDF_OVERLAP
                    chunk_num += 1
                    continue
                
                # Construct MongoDB Document
                mongo_doc = {
                    "_id": doc_id,
                    "naId": na_id,
                    "title": record_metadata.get('title'),
                    "subtitle": record_metadata.get('subtitle'),
                    "scopeAndContentNote": record_metadata.get('scopeAndContentNote'),
                    "source_file_names": [filename],
                    "source_s3_paths": [obj.get('objectUrl')],
                    "file_type": "pdf",
                    "page_start": page_start + 1,  # 1-indexed for display
                    "page_end": page_end,
                    "total_pages": total_pages,
                    "embedding": embedding
                }
                
                # Insert into target collection
                try:
                    target_collection.insert_one(mongo_doc)
                    print(f"    - Successfully inserted chunk for pages {page_start + 1}-{page_end}.")
                except Exception as e:
                    print(f"    - Failed to insert chunk: {e}")
                
                # Move to next chunk with overlap
                page_start += PDF_PAGES_PER_CHUNK - PDF_OVERLAP
                chunk_num += 1


# --- Image Migration (JPG, GIF) ---

def migrate_images(source_collection, target_collection):
    """
    Migrates image documents (JPG, GIF) with voyage-multimodal-3.5.
    """
    print("\n=== Migrating Images (JPG, GIF) ===")
    
    for file_type in ['jpg', 'gif']:
        records_dir = NARA_RECORDS_DIR / file_type
        if not records_dir.exists():
            print(f"No {file_type} records directory found at {records_dir}")
            continue
        
        metadata_files = list(records_dir.glob("*.json"))
        print(f"\nFound {len(metadata_files)} {file_type.upper()} metadata files to process.")
        
        for metadata_file_path in metadata_files:
            with open(metadata_file_path, 'r') as f:
                record_metadata = json.load(f)
            
            na_id = record_metadata.get('naId')
            doc_id = str(na_id)
            
            # Check if already migrated
            if target_collection.find_one({'_id': doc_id}):
                print(f"  - Document {doc_id} already exists. Skipping.")
                continue
            
            print(f"  - Processing {file_type.upper()} record NAID: {na_id}")
            
            digital_objects = record_metadata.get('digitalObjects', [])
            pil_images = []
            
            for obj in digital_objects:
                filename = obj.get('objectFilename')
                if not filename:
                    continue
                
                local_file_path = NARA_DOWNLOADS_DIR / file_type / filename
                image = get_pil_image(local_file_path)
                if image:
                    pil_images.append(image)
            
            if not pil_images:
                print(f"    - No valid images found. Skipping.")
                continue
            
            # Create embedding
            try:
                result = voyage_client.multimodal_embed(
                    inputs=[pil_images],
                    model=MODEL_NAME,
                    input_type="document"
                )
                embedding = result.embeddings[0]
            except Exception as e:
                print(f"    - Voyage AI embedding failed: {e}. Skipping.")
                continue
            
            # Construct MongoDB Document
            mongo_doc = {
                "_id": doc_id,
                "naId": na_id,
                "title": record_metadata.get('title'),
                "subtitle": record_metadata.get('subtitle'),
                "scopeAndContentNote": record_metadata.get('scopeAndContentNote'),
                "source_file_names": [obj.get('objectFilename') for obj in digital_objects],
                "source_s3_paths": [obj.get('objectUrl') for obj in digital_objects],
                "file_type": file_type,
                "embedding": embedding
            }
            
            # Insert into target collection
            try:
                target_collection.insert_one(mongo_doc)
                print(f"    - Successfully inserted document for NAID {na_id}.")
            except Exception as e:
                print(f"    - Failed to insert document: {e}")


# --- Main Migration Function ---

def run_migration():
    """
    Main function to run the full migration from nasa_archive to nasa_archive_3_5.
    """
    # Validate required environment variables
    if not all([VOYAGE_API_KEY, MONGO_CONNECTION_STRING]):
        print("Error: Please set VOYAGE_API_KEY and MONGO_CONNECTION_STRING environment variables.")
        return
    
    if not voyage_client:
        print("Voyage AI client failed to initialize. Cannot proceed.")
        return
    
    # MongoDB connection setup
    try:
        mongo_client = MongoClient(MONGO_CONNECTION_STRING)
        db = mongo_client[DB_NAME]
        source_collection = db[SOURCE_COLLECTION]
        target_collection = db[TARGET_COLLECTION]
        print(f"Connected to MongoDB Atlas")
        print(f"Source: {DB_NAME}.{SOURCE_COLLECTION}")
        print(f"Target: {DB_NAME}.{TARGET_COLLECTION}")
    except Exception as e:
        print(f"Error connecting to MongoDB: {e}")
        return
    
    # Run migrations
    migrate_video_chunks(source_collection, target_collection)
    migrate_pdfs(source_collection, target_collection)
    migrate_images(source_collection, target_collection)
    
    # Print summary
    source_count = source_collection.count_documents({})
    target_count = target_collection.count_documents({})
    print(f"\n=== Migration Summary ===")
    print(f"Source collection documents: {source_count}")
    print(f"Target collection documents: {target_count}")
    
    # Count by file type in target
    pipeline = [{"$group": {"_id": "$file_type", "count": {"$sum": 1}}}]
    type_counts = list(target_collection.aggregate(pipeline))
    print(f"\nTarget collection by file type:")
    for tc in type_counts:
        print(f"  - {tc['_id']}: {tc['count']}")
    
    # Count no_clip_content
    no_content_count = target_collection.count_documents({"no_clip_content": True})
    print(f"\nDocuments flagged as no_clip_content: {no_content_count}")


def main():
    """Main entry point."""
    print("=" * 60)
    print("NASA Archive Migration to voyage-multimodal-3.5")
    print("=" * 60)
    print(f"\nConfiguration:")
    print(f"  Data directory: {DATA_DIR}")
    print(f"  Records directory: {NARA_RECORDS_DIR}")
    print(f"  Downloads directory: {NARA_DOWNLOADS_DIR}")
    print(f"  Chunks directory: {NARA_CHUNKS_DIR}")
    print(f"  Model: {MODEL_NAME}")
    print(f"  PDF pages per chunk: {PDF_PAGES_PER_CHUNK}")
    print(f"  PDF overlap: {PDF_OVERLAP}")
    
    run_migration()
    
    print("\n--- Migration complete ---")


if __name__ == "__main__":
    main()
