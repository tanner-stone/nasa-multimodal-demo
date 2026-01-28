# NASA Records Multimodal Search Application

A full-stack web application for searching NASA records from the National Archives using multimodal AI. This project includes both the data pipeline for scraping and embedding NASA records, and a production-ready web application for semantic search across videos, images, and documents.

![NASA Records Search](https://img.shields.io/badge/MongoDB-Atlas-green) ![React](https://img.shields.io/badge/React-18.2-blue) ![Flask](https://img.shields.io/badge/Flask-Python-lightgrey) ![Voyage AI](https://img.shields.io/badge/Voyage%20AI-Multimodal-purple)

## 🚀 Features

### Search Application
- **Multimodal Semantic Search**: Uses Voyage AI's voyage-multimodal-3 model for intelligent search across text, images, and video
- **File Type Filtering**: Filter results by MP4 videos, JPG images, GIFs, or PDF documents
- **Reranking**: Optional Voyage AI reranker for improved result relevance
- **Dark Mode UI**: Professional retro-themed dark interface using Tailwind CSS
- **Video Playback**: HTML5 video player with automatic timestamp positioning for video chunks
- **Image Navigation**: Browse through multi-page documents with Previous/Next controls
- **Real-time Results**: Instant search results with thumbnail previews
- **Production Ready**: Kubernetes deployment with health checks and high availability

### Data Pipeline
- **NARA API Integration**: Automated scraping of NASA records from National Archives
- **Video Processing**: Splits videos into 10-second chunks with audio transcription
- **Multimodal Embeddings**: Creates embeddings combining text, audio transcripts, and visual frames
- **MongoDB Storage**: Stores embeddings in MongoDB Atlas with vector search index

## 📋 Table of Contents

- [Architecture](#architecture)
- [Prerequisites](#prerequisites)
- [Quick Start](#quick-start)
- [Data Pipeline Setup](#data-pipeline-setup)
- [Running the Application](#running-the-application)
- [Deployment](#deployment)
- [API Documentation](#api-documentation)
- [Project Structure](#project-structure)
- [Contributing](#contributing)

## 🏗️ Architecture

```
┌─────────────────┐
│   React Frontend│
│   (Vite + React)│
└────────┬────────┘
         │
         ▼
┌─────────────────┐      ┌──────────────┐
│  Flask Backend  │─────▶│  Voyage AI   │
│  (Python 3.12)  │      │  Embeddings  │
└────────┬────────┘      └──────────────┘
         │
         ▼
┌─────────────────┐
│  MongoDB Atlas  │
│  Vector Search  │
└─────────────────┘
```

**Tech Stack:**
- **Frontend**: React 18, Tailwind CSS, Vite
- **Backend**: Flask, Flask-CORS
- **Database**: MongoDB Atlas with Vector Search
- **AI/ML**: Voyage AI (multimodal-3, rerank-lite-1), OpenAI Whisper
- **Deployment**: Docker, Kubernetes, Drone CI/CD
- **Video Processing**: FFmpeg

## 📦 Prerequisites

### For Running the Application
- Python 3.8+
- Node.js 16+
- MongoDB Atlas account
- Voyage AI API key

### For Data Pipeline (Optional)
- OpenAI API key (for Whisper audio transcription)
- FFmpeg (for video processing)
- Sufficient storage for downloaded media files

## 🚀 Quick Start

### 1. Clone the Repository

```bash
git clone https://github.com/your-username/nasa-multimodal-demo.git
cd nasa-multimodal-demo
```

### 2. Install Dependencies

```bash
# Install Python dependencies
pip install -r requirements.txt

# Install Node.js dependencies
npm install
```

### 3. Configure Environment Variables

Create a `.env` file in the root directory:

```bash
MONGO_CONNECTION_STRING=mongodb+srv://username:password@cluster.mongodb.net/
VOYAGE_API_KEY=your_voyage_api_key
PORT=8080
```

### 4. Run Locally

**Option A: Development Mode (separate frontend/backend)**

```bash
# Terminal 1: Start Flask backend
python app.py

# Terminal 2: Start React frontend
npm run dev
```

**Option B: Production Mode (Docker)**

```bash
# Build and run with Docker
docker build -t nasa-multimodal-demo .
docker run -p 8080:8080 --env-file .env nasa-multimodal-demo
```

Visit `http://localhost:8080` to use the application.

## 🔧 Data Pipeline Setup

If you want to populate your own MongoDB database with NASA records, use the data pipeline scripts in the `setup/` directory.

### Overview

The pipeline consists of 4 steps:
1. **Scrape** - Download NASA records from NARA
2. **Process** - Split videos into chunks
3. **Embed Videos** - Create embeddings for video chunks
4. **Embed Images** - Create embeddings for images/PDFs

### Quick Setup

```bash
cd setup

# Install dependencies
pip install -r requirements.txt

# Configure environment (add OPENAI_API_KEY for video transcription)
# Edit your .env file in the project root

# Run the pipeline
python 01_nara_scrape.py      # Download records
python 02_mp4_processing.py   # Process videos
python 03_mp4_embedding.py    # Embed videos
python 04_image_embedding.py  # Embed images
```

### MongoDB Vector Search Index

After running the embedding scripts, create a vector search index in MongoDB Atlas:

**Index Name:** `vector_index`

**Index Definition:**
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

For detailed instructions, see [setup/README.md](setup/README.md).

## 🖥️ Running the Application

### Local Development

```bash
# Start backend
python app.py

# Start frontend (in another terminal)
npm run dev
```

- Backend: `http://localhost:8080`
- Frontend: `http://localhost:5173` (proxies to backend)

### Production Build

```bash
# Build React frontend
npm run build

# Run Flask with built frontend
python app.py
```

### Docker

```bash
# Build image
docker build -t nasa-multimodal-demo .

# Run container
docker run -p 8080:8080 --env-file .env nasa-multimodal-demo
```

## 🚢 Deployment

This application is configured for deployment to Kubernetes using Drone CI/CD.

### Kubernetes Deployment

The application uses MongoDB's web-app Helm chart with the following configuration:

**Key Features:**
- Multi-stage Docker build (Node.js + Python)
- Health and readiness probes
- Service mesh integration
- Secret management via Kubernetes secrets
- High availability with 2 replicas

### Environment Configuration

**For Kubernetes deployment:**

1. Set secrets using helm ksec:
```bash
kubectl config use-context api.staging.corp.mongodb.com
helm ksec set my-secrets MONGO_CONNECTION_STRING="mongodb+srv://..."
helm ksec set my-secrets VOYAGE_API_KEY="your_api_key"
```

2. Update `environments/staging.yaml`:
```yaml
replicaCount: 2
env:
  APP_MESSAGE: Hello, MongoDB!
  PORT: 8080
envSecrets:
  MONGO_CONNECTION_STRING: my-secrets
  VOYAGE_API_KEY: my-secrets
probes:
  enabled: true
  path: /healthz
```

3. Push to GitHub to trigger Drone CI/CD pipeline

### CI/CD Pipeline

The `.drone.yml` file configures:
- Docker image build with Kaniko
- Push to AWS ECR
- Automatic deployment to Kubernetes staging environment

## 📚 API Documentation

### POST /search

Search for NASA records using multimodal embeddings.

**Request Body:**
```json
{
  "query_text": "astronauts on the moon",
  "filter_file_types": ["mp4", "jpg"],
  "use_reranker": true
}
```

**Response:**
```json
[
  {
    "naId": "12345",
    "title": "Apollo 11 Moon Landing",
    "source_s3_path": "https://...",
    "file_type": "video_chunk",
    "start_timestamp": 120,
    "score": 0.89
  }
]
```

### GET /health

Health check endpoint.

**Response:**
```json
{
  "status": "healthy"
}
```

### GET /liveness

Kubernetes liveness probe endpoint.

**Response:**
```json
{
  "status": "alive"
}
```

## 📁 Project Structure

```
nasa-multimodal-demo/
├── app.py                      # Flask backend application
├── requirements.txt            # Python dependencies
├── package.json               # Node.js dependencies
├── Dockerfile                 # Multi-stage Docker build
├── .drone.yml                 # CI/CD pipeline configuration
├── .env.example               # Environment variables template
├── .gitignore                 # Git ignore rules
│
├── src/                       # React frontend source
│   ├── main.jsx              # React entry point
│   ├── App.jsx               # Main application component
│   └── index.css             # Global styles with Tailwind
│
├── public/                    # Static assets
│   ├── mdb-leaf.png          # MongoDB logo
│   └── favicon.png           # Site favicon
│
├── environments/              # Kubernetes deployment configs
│   └── staging.yaml          # Staging environment configuration
│
├── setup/                     # Data pipeline scripts
│   ├── README.md             # Detailed setup documentation
│   ├── requirements.txt      # Setup script dependencies
│   ├── 01_nara_scrape.py     # Download NASA records
│   ├── 02_mp4_processing.py  # Process videos into chunks
│   ├── 03_mp4_embedding.py   # Create video embeddings
│   └── 04_image_embedding.py # Create image embeddings
│
├── index.html                 # HTML entry point
├── vite.config.js            # Vite configuration
├── tailwind.config.js        # Tailwind CSS configuration
└── postcss.config.js         # PostCSS configuration
```

## 🎨 UI Features

- **Retro Dark Theme**: Neon green accents with dark background
- **File Type Icons**: Visual indicators for videos, images, and PDFs
- **Video Progress Bars**: Shows position within video chunks
- **Responsive Design**: Works on desktop and tablet devices
- **Thumbnail Previews**: Quick visual preview of search results
- **Keyboard Navigation**: Efficient browsing with keyboard shortcuts

## 🔒 Security Best Practices

- ✅ Environment variables for sensitive data
- ✅ Kubernetes secrets for production credentials
- ✅ CORS configuration for API security
- ✅ No hardcoded credentials in code
- ✅ `.gitignore` excludes sensitive files and data

## 🐛 Troubleshooting

### Common Issues

**1. "Search Failed" errors**
- Check MongoDB connection string is correct
- Verify Voyage AI API key is valid
- Ensure vector search index exists in MongoDB

**2. "No healthy upstream" in Kubernetes**
- Increase health check timeouts in `staging.yaml`
- Check pod logs: `kubectl logs <pod-name>`
- Verify secrets are set correctly

**3. Docker build fails**
- Ensure Node.js and Python base images are accessible
- Check that all dependencies are in requirements.txt
- Verify npm install completes successfully

**4. Videos don't play**
- Check S3 URLs are publicly accessible
- Verify CORS headers allow video streaming
- Ensure browser supports HTML5 video

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📄 License

This project is for demonstration purposes. NASA records are public domain, but check NARA's terms of use for specific restrictions.

## 🙏 Acknowledgments

- **National Archives and Records Administration (NARA)** - For providing public access to NASA records
- **Voyage AI** - For multimodal embedding and reranking models
- **MongoDB** - For Atlas Vector Search capabilities
- **OpenAI** - For Whisper audio transcription

## 📞 Support

For issues and questions:
- Open an issue on GitHub
- Check the [setup documentation](setup/README.md)
- Review the troubleshooting section above

---

Built with ❤️ for exploring NASA's historical archives through modern AI technology.
