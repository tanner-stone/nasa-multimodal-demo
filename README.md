# NASA Records Multimodal Search Application

A full-stack web application for searching NASA records using multimodal AI. Built with React.js frontend and Python Flask backend, featuring dark mode UI and support for videos, images, and documents.

## Features

- **Multimodal Search**: Uses Voyage AI's voyage-multimodal-3 model for semantic search
- **File Type Filtering**: Filter results by MP4 videos, JPG images, GIFs, or PDF documents
- **Dark Mode UI**: Professional dark theme using Tailwind CSS
- **Video Playback**: HTML5 video player with automatic timestamp positioning
- **Image Navigation**: Browse through multi-page documents with Previous/Next controls
- **Real-time Results**: Instant search results with thumbnail previews

## Prerequisites

- Python 3.8+
- Node.js 16+
- MongoDB Atlas account
- Voyage AI API key

## Setup Instructions

### 1. Clone and Install Dependencies

```bash
# Install Python dependencies
pip install -r requirements.txt

# Install Node.js dependencies
npm install
```

### 2. Environment Configuration

Create a `.env` file in the root directory:

```bash
cp .env.example .env
```

Edit `.env` with your credentials:

```env
MONGO_CONNECTION_STRING=mongodb+srv://username:password@cluster.mongodb.net/nasa_records?retryWrites=true&w=majority
VOYAGE_API_KEY=your_voyage_ai_api_key_here
```

### 3. MongoDB Setup

Your MongoDB collection should have documents with the following structure:

```json
{
  "naId": "string",
  "title": "string",
  "source_s3_path": "string or array of strings",
  "file_type": "mp4|jpg|gif|pdf",
  "start_timestamp": "number (for videos)",
  "source_file_names": ["array of strings"],
  "embedding": [/* vector embedding array */]
}
```

Ensure you have a vector search index named `vector_index` on the `embedding` field.

## Running the Application

### Development Mode

1. **Start the Flask backend:**
```bash
python app.py
```
The backend will run on `http://localhost:5000`

2. **Start the React frontend:**
```bash
npm run dev
```
The frontend will run on `http://localhost:3000`

### Production Build

```bash
npm run build
npm run preview
```

## Usage

1. **Search**: Enter your query in the search bar
2. **Filter**: Optionally select a file type from the dropdown
3. **Browse**: Click on results in the sidebar to view them in the main area
4. **Navigate**: Use Previous/Next buttons for multi-page documents
5. **Watch**: Videos automatically start 3 seconds before the relevant timestamp

## API Endpoints

### POST /search

Search for NASA records using multimodal embeddings.

**Request Body:**
```json
{
  "query_text": "string (required)",
  "filter_file_type": "string (optional)"
}
```

**Response:**
```json
[
  {
    "naId": "string",
    "title": "string",
    "source_s3_path": "string or array",
    "file_type": "string",
    "start_timestamp": "number",
    "source_file_names": ["array"],
    "score": "number"
  }
]
```

### GET /health

Health check endpoint.

## Architecture

- **Frontend**: React.js with Tailwind CSS for styling
- **Backend**: Flask with CORS support
- **Database**: MongoDB Atlas with vector search
- **AI**: Voyage AI voyage-multimodal-3 for embeddings
- **Build Tool**: Vite for fast development and building

## File Structure

```
├── app.py                 # Flask backend
├── requirements.txt       # Python dependencies
├── package.json          # Node.js dependencies
├── vite.config.js        # Vite configuration
├── tailwind.config.js    # Tailwind CSS configuration
├── postcss.config.js     # PostCSS configuration
├── index.html            # HTML entry point
├── src/
│   ├── main.jsx          # React entry point
│   ├── App.jsx           # Main React component
│   └── index.css         # Global styles
└── .env.example          # Environment variables template
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

## License

MIT License - see LICENSE file for details.
