import os
import json
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

# Hello
def init_mongo():
    global mongo_client, db, collection
    connection_string = os.getenv('MONGO_CONNECTION_STRING')
    if not connection_string:
        print("Warning: MONGO_CONNECTION_STRING not found in environment variables")
        return False
    
    try:
        mongo_client = MongoClient(connection_string)
        db = mongo_client.ts_multimodal_demo
        collection = db.nasa_archive
        return True
    except Exception as e:
        print(f"Error connecting to MongoDB: {e}")
        return False

def get_embedding(text):
    """Generate embedding using Voyage AI multimodal model"""
    try:
        result = voyage_client.multimodal_embed(
            inputs=[[text]],
            model="voyage-multimodal-3",
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
        print(f"Query: '{query_text}', Filter: '{filter_file_types}', Reranker: {use_reranker}")
        
        # Generate embedding for the query
        print("Generating embedding...")
        embedding = get_embedding(query_text)
        if not embedding:
            print("Failed to generate embedding")
            return jsonify({'error': 'Failed to generate embedding'}), 500
        
        print(f"Generated embedding with length: {len(embedding)}")
        
        # Build aggregation pipeline
        pipeline = []
        
        # Vector search stage
        vector_search_stage = {
            "$vectorSearch": {
                "index": "vector_index",
                "path": "embedding",
                "queryVector": embedding,
                "numCandidates": 200,
                "limit": 50
            }
        }
        pipeline.append(vector_search_stage)
        
        # Add file type filter if provided
        if filter_file_types and len(filter_file_types) > 0:
            # Handle video_chunk mapping for mp4 filter
            mapped_file_types = []
            for ft in filter_file_types:
                if ft == 'mp4':
                    mapped_file_types.extend(['mp4', 'video_chunk'])
                else:
                    mapped_file_types.append(ft)
            
            match_stage = {
                "$match": {
                    "file_type": {"$in": mapped_file_types}
                }
            }
            pipeline.append(match_stage)
        
        # Project only required fields
        project_stage = {
            "$project": {
                "naId": 1,
                "title": 1,
                "source_s3_path": 1,
                "source_s3_paths": 1,
                "file_type": 1,
                "start_timestamp": 1,
                "source_file_names": 1,
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
        
        results = list(collection.aggregate(pipeline))
        print(f"Found {len(results)} results")

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

        print("Returning results")
        return jsonify(results)
        
    except Exception as e:
        print(f"Search error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/health', methods=['GET'])
def health():
    return jsonify({'status': 'healthy'})

@app.route('/liveness', methods=['GET'])
def liveness():
    return jsonify({'status': 'alive'})

if __name__ == '__main__':
    init_mongo()
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', debug=False, port=port, use_reloader=False)
