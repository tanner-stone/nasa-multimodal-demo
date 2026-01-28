"""
Image and PDF Embedding Script

This script processes image files (JPG, GIF) and PDF documents,
creates multimodal embeddings using Voyage AI, and stores them in MongoDB.

Usage:
    python 04_image_embedding.py

Environment Variables (Required):
    MONGO_CONNECTION_STRING: MongoDB Atlas connection string
    VOYAGE_API_KEY: Voyage AI API key
    
Environment Variables (Optional):
    DATA_DIR: Base directory for data storage (default: './data')
    SEARCH_TERM: The search term used for scraping (default: 'NASA')
    DB_NAME: MongoDB database name (default: 'ts_multimodal_demo')
    COLLECTION_NAME: MongoDB collection name (default: 'nasa_archive')
    MAX_IMAGE_DIM: Maximum dimension for image resizing (default: 2048)

Requirements:
    - PyMuPDF (fitz) for PDF processing
"""

import os
import json
import pathlib
from dotenv import load_dotenv
import voyageai
from pymongo import MongoClient
from PIL import Image
import fitz  # PyMuPDF

# Load environment variables
load_dotenv()

# --- Configuration ---

# API Keys and MongoDB Connection (Required)
VOYAGE_API_KEY = os.getenv("VOYAGE_API_KEY")
MONGO_CONNECTION_STRING = os.getenv("MONGO_CONNECTION_STRING")

# Directory paths
DATA_DIR = pathlib.Path(os.getenv('DATA_DIR', './data'))
SEARCH_TERM = os.getenv('SEARCH_TERM', 'NASA')

NARA_RECORDS_DIR = DATA_DIR / 'nara_records' / SEARCH_TERM
NARA_DOWNLOADS_DIR = DATA_DIR / 'nara_downloads' / SEARCH_TERM

# MongoDB setup
DB_NAME = os.getenv('DB_NAME', 'ts_multimodal_demo')
COLLECTION_NAME = os.getenv('COLLECTION_NAME', 'nasa_archive')

# Image resizing parameters
MAX_IMAGE_DIM = int(os.getenv('MAX_IMAGE_DIM', '2048'))

# Initialize API client
voyage_client = None

try:
    if VOYAGE_API_KEY:
        voyage_client = voyageai.Client(api_key=VOYAGE_API_KEY)
except Exception as e:
    print(f"Error initializing Voyage AI client: {e}")

def resize_image(image: Image.Image, max_dim: int) -> Image.Image:
    """
    Resizes an image to a maximum dimension while maintaining aspect ratio.
    """
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

def get_pil_image_from_path(image_path):
    """
    Opens and returns a resized PIL.Image object from an image file path.
    """
    try:
        if not os.path.exists(image_path):
            print(f"  - File not found: {image_path}")
            return None
        
        image = Image.open(image_path)
        if image.mode != 'RGB':
            image = image.convert('RGB')
            
        # Resize the image before returning
        resized_image = resize_image(image, MAX_IMAGE_DIM)
        return resized_image
    except Exception as e:
        print(f"  - Error opening image {image_path}: {e}")
        return None

def get_pil_images_from_pdf(pdf_path):
    """
    Converts each page of a PDF into a resized PIL.Image object.
    """
    try:
        if not os.path.exists(pdf_path):
            print(f"  - PDF file not found: {pdf_path}")
            return None
            
        doc = fitz.open(pdf_path)
        images = []
        for page_num in range(doc.page_count):
            pix = doc[page_num].get_pixmap()
            img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
            
            # Resize the image before appending
            resized_img = resize_image(img, MAX_IMAGE_DIM)
            images.append(resized_img)
        doc.close()
        return images
    except Exception as e:
        print(f"  - Error processing PDF {pdf_path}: {e}")
        return None

def process_and_embed_media_files():
    """
    Reads metadata, creates multimodal embeddings for media files (PDF, JPG, GIF),
    and inserts documents into MongoDB.
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
        collection = db[COLLECTION_NAME]
        print(f"Connected to MongoDB Atlas: {DB_NAME}.{COLLECTION_NAME}")
    except Exception as e:
        print(f"Error connecting to MongoDB: {e}")
        return
    
    # Check if the records directory exists
    if not NARA_RECORDS_DIR.exists():
        print(f"Error: NARA_RECORDS_DIR does not exist at {NARA_RECORDS_DIR}")
        return
    
    # Iterate through all media types (subdirectories) in the records directory
    # Skip the mov, mp3, and mp4 directories as they are handled by other scripts
    processed_count = 0
    for media_type_dir in NARA_RECORDS_DIR.iterdir():
        if not media_type_dir.is_dir() or media_type_dir.name in ['mp4', 'mov', 'mp3', 'ascii']:
            continue
            
        file_extension = media_type_dir.name.lower()
        print(f"\n--- Processing '{file_extension}' files ---")
        
        metadata_files = list(media_type_dir.glob("*.json"))
        if not metadata_files:
            print(f"  - No metadata files found in {media_type_dir}")
            continue
            
        for metadata_file_path in metadata_files:
            with open(metadata_file_path, 'r') as f:
                record_metadata = json.load(f)
            
            na_id = record_metadata.get('naId')
            
            # Check if a document for this NAID already exists to avoid re-embedding
            if collection.find_one({'naId': na_id, 'file_type': {'$in': ['pdf', 'jpg', 'gif']}}):
                print(f"  - Document for NAID {na_id} already exists in DB. Skipping.")
                continue
            
            print(f"  - Processing record NAID: {na_id}")
            
            digital_objects = record_metadata.get('digitalObjects', [])
            if not digital_objects:
                print(f"  - No digital objects found for NAID {na_id}. Skipping.")
                continue

            # --- Prepare Multimodal Input (Images) ---
            pil_images = []
            
            for obj in digital_objects:
                filename = obj.get('objectFilename')
                
                # Normalize extension to lowercase for path matching
                if filename:
                    local_file_path = NARA_DOWNLOADS_DIR / file_extension / filename
                    
                    if filename.lower().endswith('.pdf'):
                        images_from_pdf = get_pil_images_from_pdf(local_file_path)
                        if images_from_pdf:
                            pil_images.extend(images_from_pdf)
                    elif filename.lower().endswith(('.jpg', '.jpeg', '.gif')):
                        image = get_pil_image_from_path(local_file_path)
                        if image:
                            pil_images.append(image)

            if not pil_images:
                print(f"  - No valid images found for embedding for NAID {na_id}. Skipping.")
                continue
            
            print(f"  - Preparing to embed {len(pil_images)} image(s) for NAID {na_id}.")
            
            # --- Create Multimodal Embedding with Voyage AI ---
            try:
                # The input is a list of PIL.Image objects
                result = voyage_client.multimodal_embed(
                    inputs=[pil_images], 
                    model="voyage-multimodal-3",
                    input_type="document"
                )
                embedding = result.embeddings[0]
            except Exception as e:
                print(f"  - Voyage AI embedding failed: {e}. Skipping record.")
                continue

            # --- Construct MongoDB Document ---
            # Create a single document for the entire record's media files
            mongo_doc = {
                "_id": f"{na_id}",
                "naId": na_id,
                "title": record_metadata.get('title'),
                "subtitle": record_metadata.get('subtitle'),
                "scopeAndContentNote": record_metadata.get('scopeAndContentNote'),
                "source_file_names": [obj.get('objectFilename') for obj in digital_objects],
                "source_s3_paths": [obj.get('objectUrl') for obj in digital_objects],
                "file_type": file_extension,
                "embedding": embedding
            }
            
            # --- Insert into MongoDB ---
            try:
                collection.insert_one(mongo_doc)
                print(f"  - Successfully inserted multimodal document for NAID {na_id}.")
                processed_count += 1
            except Exception as e:
                print(f"  - Failed to insert document for NAID {na_id} into MongoDB: {e}")

    print(f"\n--- Image embedding complete. Processed {processed_count} documents. ---")

def main():
    """Main function to run the image embedding process."""
    print("--- Starting Image and PDF Embedding ---")
    print(f"Data directory: {DATA_DIR}")
    print(f"Records directory: {NARA_RECORDS_DIR}")
    print(f"Downloads directory: {NARA_DOWNLOADS_DIR}")
    print(f"MongoDB: {DB_NAME}.{COLLECTION_NAME}")
    print(f"Max image dimension: {MAX_IMAGE_DIM}px")
    
    process_and_embed_media_files()

if __name__ == "__main__":
    main()
