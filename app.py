import os
import json
import time
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from pymongo import MongoClient
import voyageai
from bson import ObjectId
from dotenv import load_dotenv
import requests

# Load environment variables from .env file
load_dotenv()

app = Flask(__name__, static_folder='dist', static_url_path='')
CORS(app)

# Initialize Voyage AI client
voyage_client = voyageai.Client(api_key=os.getenv('VOYAGE_API_KEY'))

# MongoDB connection
mongo_client = None
db = None
collection = None

# Collection configuration - use environment variable to switch between collections
COLLECTION_NAME = os.getenv('COLLECTION_NAME', 'nasa_archive_3_5')

def init_mongo():
    global mongo_client, db, collection
    connection_string = os.getenv('MONGO_CONNECTION_STRING')
    if not connection_string:
        print("Warning: MONGO_CONNECTION_STRING not found in environment variables")
        return False
    
    try:
        mongo_client = MongoClient(connection_string)
        db = mongo_client.ts_multimodal_demo
        collection = db[COLLECTION_NAME]
        print(f"Connected to collection: {COLLECTION_NAME}")
        return True
    except Exception as e:
        print(f"Error connecting to MongoDB: {e}")
        return False

# Model configuration - use environment variable to switch between models
VOYAGE_MODEL = os.getenv('VOYAGE_MODEL', 'voyage-multimodal-3.5')

def get_embedding(text):
    """Generate embedding using Voyage AI multimodal model"""
    try:
        result = voyage_client.multimodal_embed(
            inputs=[[text]],
            model=VOYAGE_MODEL,
            input_type="query"
        )
        return result.embeddings[0]
    except Exception as e:
        print(f"Error generating embedding: {e}")
        return None

@app.route('/')
def index():
    return send_from_directory(app.static_folder, 'index.html')

@app.route('/<path:path>')
def serve_static(path):
    if os.path.exists(os.path.join(app.static_folder, path)):
        return send_from_directory(app.static_folder, path)
    else:
        return send_from_directory(app.static_folder, 'index.html')

# Available vector search indexes with their configurations
VECTOR_INDEXES = {
    'float32': {
        'name': 'vector_index_float32',
        'quantization': None,
        'storage_estimate': '~47 MB',  # 1024 dims * 4 bytes * 11634 docs
        'description': 'Full precision (32-bit float)'
    },
    'scalar': {
        'name': 'vector_index_scalar',
        'quantization': 'scalar',
        'storage_estimate': '~12 MB',  # 1024 dims * 1 byte * 11634 docs
        'description': 'Scalar quantization (8-bit int)'
    },
    'binary': {
        'name': 'vector_index_binary',
        'quantization': 'binary',
        'storage_estimate': '~1.5 MB',  # 1024 dims / 8 bits * 11634 docs
        'description': 'Binary quantization (1-bit)'
    }
}

@app.route('/api/indexes', methods=['GET'])
def get_indexes():
    """Return available vector search indexes with their metadata"""
    return jsonify(VECTOR_INDEXES)

@app.route('/api/document/<doc_id>', methods=['GET'])
def get_document(doc_id):
    """Fetch a full document by its _id"""
    try:
        if collection is None:
            if not init_mongo():
                return jsonify({'error': 'Database connection failed'}), 500
        
        # Find the document by _id (stored as string in this collection)
        document = collection.find_one({'_id': doc_id})
        
        if not document:
            return jsonify({'error': 'Document not found'}), 404
        
        # Remove the embedding field as it's large and not needed for display
        if 'embedding' in document:
            document['embedding'] = f"[{len(document['embedding'])} dimensions - hidden for display]"
        
        # Convert any ObjectId fields to strings
        for key, value in document.items():
            if isinstance(value, ObjectId):
                document[key] = str(value)
        
        return jsonify(document)
    except Exception as e:
        print(f"Error fetching document: {e}")
        return jsonify({'error': 'Failed to fetch document'}), 500

@app.route('/search', methods=['POST'])
def search():
    try:
        print(f"Received search request")
        data = request.get_json()
        print(f"Request data: {data}")
        
        if not data or 'query_text' not in data:
            return jsonify({'error': 'query_text is required'}), 400
        
        query_text = data['query_text']
        filter_file_types = data.get('filter_file_types')
        use_reranker = data.get('use_reranker', True) # Default to True if not provided
        exclude_no_content = data.get('exclude_no_content', True)  # Default to True - filter out blank clips
        vector_index = data.get('vector_index', 'float32')  # Default to float32 index
        print(f"Query: '{query_text}', Filter: '{filter_file_types}', Reranker: {use_reranker}, ExcludeNoContent: {exclude_no_content}, Index: {vector_index}")
        
        # Generate embedding for the query
        print("Generating embedding...")
        embedding = get_embedding(query_text)
        if not embedding:
            print("Failed to generate embedding")
            return jsonify({'error': 'Failed to generate embedding'}), 500
        
        print(f"Generated embedding with length: {len(embedding)}")
        
        # Build filter conditions for vector search pre-filtering
        filter_conditions = {}
        
        # Add file type filter if provided
        if filter_file_types and len(filter_file_types) > 0:
            # Handle video_chunk mapping for mp4 filter
            mapped_file_types = []
            for ft in filter_file_types:
                if ft == 'mp4':
                    mapped_file_types.extend(['mp4', 'video_chunk'])
                else:
                    mapped_file_types.append(ft)
            filter_conditions["file_type"] = {"$in": mapped_file_types}
        
        # Filter out no_clip_content documents if requested (default: True)
        if exclude_no_content:
            filter_conditions["no_clip_content"] = {"$ne": True}
        
        # Get the selected index configuration
        index_config = VECTOR_INDEXES.get(vector_index, VECTOR_INDEXES['float32'])
        index_name = index_config['name']
        
        # Build aggregation pipeline
        pipeline = []
        
        # Vector search stage with pre-filtering
        vector_search_stage = {
            "$vectorSearch": {
                "index": index_name,
                "path": "embedding",
                "queryVector": embedding,
                "numCandidates": 200,
                "limit": 50
            }
        }
        
        # Add filter to vector search if there are any conditions
        if filter_conditions:
            vector_search_stage["$vectorSearch"]["filter"] = filter_conditions
        
        pipeline.append(vector_search_stage)
        
        # Project only required fields (including page info for PDFs)
        project_stage = {
            "$project": {
                "naId": 1,
                "title": 1,
                "source_s3_path": 1,
                "source_s3_paths": 1,
                "file_type": 1,
                "start_timestamp": 1,
                "source_file_names": 1,
                "page_start": 1,
                "page_end": 1,
                "total_pages": 1,
                "score": {"$meta": "vectorSearchScore"}
            }
        }
        pipeline.append(project_stage)
        
        # Execute search
        if collection is None:
            print("Initializing MongoDB connection...")
            if not init_mongo():
                print("MongoDB connection failed")
                return jsonify({'error': 'Database connection failed'}), 500
        
        print("Executing MongoDB aggregation...")
        
        # Debug: Check if collection has any documents
        total_docs = collection.count_documents({})
        print(f"Total documents in collection: {total_docs}")
        
        # Debug: Check if any documents have embeddings
        docs_with_embeddings = collection.count_documents({"embedding": {"$exists": True}})
        print(f"Documents with embeddings: {docs_with_embeddings}")
        
        # Debug: Show the aggregation pipeline
        print(f"Aggregation pipeline: {pipeline}")
        
        # Track query execution time
        search_start_time = time.time()
        results = list(collection.aggregate(pipeline))
        search_latency_ms = (time.time() - search_start_time) * 1000
        print(f"Found {len(results)} results in {search_latency_ms:.2f}ms")

        # Rerank results using Voyage reranker if enabled and there are at least 2 results
        if use_reranker and len(results) > 1:
            print("Reranking results with Voyage reranker...")
            # Use the chunk_text_content or title as the text for reranking
            texts = []
            for r in results:
                # Prefer chunk_text_content, fallback to title
                text = r.get("chunk_text_content") or r.get("title") or ""
                texts.append(text)
            try:
                rerank_response = voyage_client.rerank(
                    query=query_text,
                    documents=texts,
                    model="rerank-lite-1"
                )
                # rerank_response.results is a list of RerankingResult objects, sorted by relevance
                reranked = [results[r.index] for r in rerank_response.results]
                results = reranked
                print("Reranking complete.")
            except Exception as e:
                print(f"Reranking failed: {e}")
        elif not use_reranker:
            print("Reranking disabled by user.")

        # Debug: Show the structure of the first result
        if results:
            print("First result structure:")
            first_result = results[0]
            for key, value in first_result.items():
                if key == 'source_s3_path':
                    print(f"  {key}: {type(value)} = {value}")
                else:
                    print(f"  {key}: {type(value)}")

        # Convert ObjectId to string for JSON serialization
        for result in results:
            if '_id' in result:
                result['_id'] = str(result['_id'])

        # Create a sanitized version of the pipeline for display (replace embedding with placeholder)
        display_pipeline = json.loads(json.dumps(pipeline))
        if display_pipeline and '$vectorSearch' in display_pipeline[0]:
            display_pipeline[0]['$vectorSearch']['queryVector'] = '[1024-dimensional embedding vector]'

        print("Returning results")
        return jsonify({
            'results': results,
            'metadata': {
                'latency_ms': round(search_latency_ms, 2),
                'index_used': index_name,
                'index_type': vector_index,
                'result_count': len(results),
                'pipeline': display_pipeline
            }
        })
        
    except Exception as e:
        print(f"Search error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/health', methods=['GET'])
def health():
    return jsonify({'status': 'healthy'})

@app.route('/healthz', methods=['GET'])
def healthz():
    return jsonify({'status': 'healthy'})

@app.route('/liveness', methods=['GET'])
def liveness():
    return jsonify({'status': 'alive'})

if __name__ == '__main__':
    init_mongo()
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', debug=False, port=port, use_reloader=False)
