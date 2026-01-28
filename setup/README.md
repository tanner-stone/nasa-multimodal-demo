# NASA Multimodal Demo - Data Setup Scripts

This directory contains scripts for scraping, processing, and embedding NASA records from the National Archives and Records Administration (NARA) into MongoDB Atlas with multimodal embeddings.

## Overview

The setup process consists of 4 main steps:

1. **Scrape** - Download NASA records and media files from NARA
2. **Process** - Split MP4 videos into chunks with audio and frames
3. **Embed Videos** - Create multimodal embeddings for video chunks
4. **Embed Images** - Create multimodal embeddings for images and PDFs

## Prerequisites

### System Requirements
- Python 3.8+
- ffmpeg (for video processing)

### Python Dependencies

Install required packages:

```bash
pip install -r requirements.txt
```

Required packages:
- `requests` - HTTP requests for API calls
- `python-dotenv` - Environment variable management
- `voyageai` - Voyage AI multimodal embeddings
- `openai` - OpenAI Whisper for audio transcription
- `pymongo` - MongoDB client
- `Pillow` - Image processing
- `ffmpeg-python` - Video processing
- `PyMuPDF` - PDF processing

### API Keys and Configuration

Create a `.env` file in the project root with the following variables:

```bash
# Required for all scripts
MONGO_CONNECTION_STRING=mongodb+srv://username:password@cluster.mongodb.net/
VOYAGE_API_KEY=your_voyage_api_key

# Required for video embedding (script 03)
OPENAI_API_KEY=your_openai_api_key

# Optional configuration
SEARCH_TERM=NASA
DATA_DIR=./data
DB_NAME=ts_multimodal_demo
COLLECTION_NAME=nasa_archive
```

## Usage

### Step 1: Scrape NASA Records

Downloads media files and metadata from NARA:

```bash
cd setup
python 01_nara_scrape.py
```

**What it does:**
- Searches NARA API for NASA-related records
- Downloads MP4, MP3, JPG, PDF, GIF, MOV, and ASCII files
- Saves metadata as JSON files
- Organizes files by media type

**Output:**
- `data/nara_downloads/NASA/` - Downloaded media files
- `data/nara_records/NASA/` - Metadata JSON files

### Step 2: Process MP4 Videos

Splits videos into 10-second chunks with audio and frames:

```bash
python 02_mp4_processing.py
```

**What it does:**
- Processes all MP4 files from step 1
- Extracts 10-second audio clips (MP3)
- Extracts 5 frames per chunk (JPG)
- Creates metadata linking chunks to source videos

**Output:**
- `data/nara_video_chunks/` - Video chunks with audio and frames

**Configuration:**
- `CHUNK_DURATION` - Chunk length in seconds (default: 10)
- `FRAMES_PER_CHUNK` - Number of frames per chunk (default: 5)

### Step 3: Embed Video Chunks

Creates multimodal embeddings for video chunks:

```bash
python 03_mp4_embedding.py
```

**What it does:**
- Transcribes audio using OpenAI Whisper
- Combines transcript with video frames
- Creates multimodal embeddings with Voyage AI
- Stores embeddings in MongoDB

**Output:**
- MongoDB documents with embeddings for each video chunk

**Requirements:**
- OpenAI API key (for Whisper transcription)
- Voyage AI API key
- MongoDB connection string

### Step 4: Embed Images and PDFs

Creates multimodal embeddings for images and PDFs:

```bash
python 04_image_embedding.py
```

**What it does:**
- Processes JPG, GIF, and PDF files
- Converts PDF pages to images
- Resizes images to max 2048px
- Creates multimodal embeddings with Voyage AI
- Stores embeddings in MongoDB

**Output:**
- MongoDB documents with embeddings for each image/PDF record

**Configuration:**
- `MAX_IMAGE_DIM` - Maximum image dimension (default: 2048)

## Data Structure

### Directory Layout

```
data/
├── nara_downloads/          # Downloaded media files
│   └── NASA/
│       ├── mp4/
│       ├── jpg/
│       ├── gif/
│       ├── pdf/
│       └── ...
├── nara_records/            # Metadata JSON files
│   └── NASA/
│       ├── mp4/
│       ├── jpg/
│       └── ...
└── nara_video_chunks/       # Processed video chunks
    ├── video-name-1/
    │   ├── video-name-1_chunk_000/
    │   │   ├── video-name-1_chunk_000.mp3
    │   │   ├── video-name-1_chunk_000_frame_1.jpg
    │   │   └── ...
    │   └── video-name-1_metadata.json
    └── ...
```

### MongoDB Document Schema

**Video Chunks:**
```json
{
  "_id": "naId_chunk_id",
  "naId": "12345",
  "title": "Apollo 11 Launch",
  "subtitle": "...",
  "scopeAndContentNote": "...",
  "source_file_name": "apollo-11.mp4",
  "source_s3_path": "https://...",
  "file_type": "video_chunk",
  "chunk_text_content": "Transcript of audio...",
  "start_timestamp": 0,
  "end_timestamp": 10,
  "embedding": [0.123, 0.456, ...]
}
```

**Images/PDFs:**
```json
{
  "_id": "naId",
  "naId": "12345",
  "title": "Moon Landing Photo",
  "subtitle": "...",
  "scopeAndContentNote": "...",
  "source_file_names": ["photo1.jpg", "photo2.jpg"],
  "source_s3_paths": ["https://...", "https://..."],
  "file_type": "jpg",
  "embedding": [0.123, 0.456, ...]
}
```

## MongoDB Vector Search Index

After running the embedding scripts, create a vector search index in MongoDB Atlas:

```json
{
  "fields": [
    {
      "type": "vector",
      "path": "embedding",
      "numDimensions": 1024,
      "similarity": "cosine"
    }
  ]
}
```

Index name: `vector_index`

## Environment Variables Reference

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `MONGO_CONNECTION_STRING` | Yes | - | MongoDB Atlas connection string |
| `VOYAGE_API_KEY` | Yes | - | Voyage AI API key |
| `OPENAI_API_KEY` | Yes (script 03) | - | OpenAI API key for Whisper |
| `SEARCH_TERM` | No | `NASA` | Search term for NARA API |
| `DATA_DIR` | No | `./data` | Base directory for data storage |
| `DB_NAME` | No | `ts_multimodal_demo` | MongoDB database name |
| `COLLECTION_NAME` | No | `nasa_archive` | MongoDB collection name |
| `CHUNK_DURATION` | No | `10` | Video chunk duration (seconds) |
| `FRAMES_PER_CHUNK` | No | `5` | Frames to extract per chunk |
| `MAX_IMAGE_DIM` | No | `2048` | Maximum image dimension (pixels) |

## Troubleshooting

### Common Issues

**1. ffmpeg not found**
```bash
# macOS
brew install ffmpeg

# Ubuntu/Debian
sudo apt-get install ffmpeg

# Windows
# Download from https://ffmpeg.org/download.html
```

**2. MongoDB connection failed**
- Verify your connection string is correct
- Check that your IP is whitelisted in MongoDB Atlas
- Ensure database user has read/write permissions

**3. API rate limits**
- NARA API: Add delays between requests (already implemented)
- Voyage AI: Check your API quota
- OpenAI: Monitor your usage limits

**4. Out of memory**
- Reduce `MAX_IMAGE_DIM` for image processing
- Process files in smaller batches
- Increase system memory allocation

## Notes

- **Data files are excluded from git** - The `data/` directory is in `.gitignore`
- **Idempotent operations** - Scripts skip already processed files
- **Resume capability** - Can safely restart scripts after interruption
- **Cost considerations** - Be aware of API costs for Voyage AI and OpenAI

## License

This project is for demonstration purposes. NASA records are public domain, but check NARA's terms of use for specific restrictions.
