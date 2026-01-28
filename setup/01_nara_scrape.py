"""
NASA Records Scraper

This script scrapes NASA records from the National Archives and Records Administration (NARA)
Catalog API. It downloads media files and saves metadata for further processing.

Usage:
    python 01_nara_scrape.py

Environment Variables:
    SEARCH_TERM: The search term to use (default: 'NASA')
    DATA_DIR: Base directory for data storage (default: './data')
"""

import requests
import os
import time
import json
from pathlib import Path

# --- Configuration ---

# Search term for NARA API
SEARCH_TERM = os.getenv('SEARCH_TERM', 'NASA')

# Base URL for the NARA Catalog API
NARA_CATALOG_API_URL = "https://catalog.archives.gov/proxy/records/search"

# The number of records to retrieve per API call
LIMIT = 50

# Base directory for data storage
DATA_DIR = Path(os.getenv('DATA_DIR', './data'))

# The parent directory for all downloads and metadata
DOWNLOAD_BASE_DIR = DATA_DIR / 'nara_downloads'
RECORDS_BASE_DIR = DATA_DIR / 'nara_records'

# Create base directories if they don't exist
DOWNLOAD_BASE_DIR.mkdir(parents=True, exist_ok=True)
RECORDS_BASE_DIR.mkdir(parents=True, exist_ok=True)

# The specific data types to search for
MEDIA_TYPES = [
    'mp4',
    'mp3',
    'jpg',
    'pdf',
    'ascii',
    'mov',
    'gif',
]

# --- Helper Functions ---

def download_file_requests(url, file_path):
    """
    Downloads a file from a given URL to a specified path using requests.
    This function is robust and handles direct file transfers.
    
    Args:
        url (str): The URL of the file to download.
        file_path (Path): The local path to save the file.
    """
    try:
        with requests.get(url, stream=True, timeout=30) as r:
            r.raise_for_status()
            with open(file_path, 'wb') as f:
                for chunk in r.iter_content(chunk_size=8192):
                    f.write(chunk)
        print(f"Downloaded: {file_path.name}")
    except requests.exceptions.RequestException as e:
        print(f"Error downloading {url}: {e}")

def main():
    """
    Main function to orchestrate the API scraping and downloading process.
    """
    print("--- Starting NARA API Scraper ---")
    print(f"Search term: {SEARCH_TERM}")
    print(f"Data directory: {DATA_DIR}")
    
    # Create a sub-directory for the search term in both download and records folders
    download_term_dir = DOWNLOAD_BASE_DIR / SEARCH_TERM.replace(' ', '_')
    records_term_dir = RECORDS_BASE_DIR / SEARCH_TERM.replace(' ', '_')
    
    download_term_dir.mkdir(parents=True, exist_ok=True)
    records_term_dir.mkdir(parents=True, exist_ok=True)

    # Iterate through each media type
    for media_type in MEDIA_TYPES:
        print(f"\n--- Searching for '{media_type}' files ---")
        
        # Create a specific directory for the current media type
        download_type_dir = download_term_dir / media_type
        records_type_dir = records_term_dir / media_type

        download_type_dir.mkdir(parents=True, exist_ok=True)
        records_type_dir.mkdir(parents=True, exist_ok=True)
        
        # Construct the API URL with search parameters
        params = {
            'q': SEARCH_TERM,
            'objectType': media_type,
            'limit': LIMIT
        }
        
        try:
            # Make the API call
            response = requests.get(NARA_CATALOG_API_URL, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()
            
            # Navigate the JSON structure to get the records
            hits = data.get('body', {}).get('hits', {}).get('hits', [])
            
            if not hits:
                print(f"No records found for '{media_type}'.")
                continue
            
            print(f"Found {len(hits)} records for '{media_type}'.")
            
            found_downloads = False
            for record in hits:
                record_source = record.get('_source', {}).get('record', {})
                na_id = record_source.get('naId')

                # Check for existing metadata file before processing this record
                records_file_path = records_type_dir / f"{na_id}.json"
                if records_file_path.exists():
                    print(f"Metadata file already exists for NAID {na_id}. Skipping record.")
                    continue
                
                digital_objects = record_source.get('digitalObjects', [])

                if not digital_objects:
                    continue

                # Prepare the metadata dictionary for this record
                record_data = {
                    'naId': na_id,
                    'title': record_source.get('title'),
                    'subtitle': record_source.get('subtitle'),
                    'scopeAndContentNote': record_source.get('scopeAndContentNote'),
                    'useRestrictionNote': record_source.get('useRestriction', {}).get('note'),
                    'digitalObjects': []
                }
                
                # Check for digital objects and download them
                for obj in digital_objects:
                    obj_url = obj.get('objectUrl')
                    obj_filename = obj.get('objectFilename')
                    
                    if obj_url and obj_filename:
                        # Add object metadata to our dictionary
                        record_data['digitalObjects'].append({
                            'objectUrl': obj_url,
                            'objectFilename': obj_filename,
                            'objectType': obj.get('objectType'),
                            'objectFileSize': obj.get('objectFileSize')
                        })

                        # Define the file path for downloading
                        file_path = download_type_dir / obj_filename
                        
                        # Only download if the file doesn't already exist
                        if not file_path.exists():
                            download_file_requests(obj_url, file_path)
                            found_downloads = True
                            # Add a small delay between downloads
                            time.sleep(0.5)
                        else:
                            print(f"File already exists: {file_path}. Skipping download.")

                # Save the metadata to a JSON file
                if na_id:
                    with open(records_file_path, 'w') as f:
                        json.dump(record_data, f, indent=4)
                    print(f"Saved metadata to: {records_file_path}")

            if not found_downloads:
                print(f"No new downloadable files found for '{media_type}' within the returned records.")
                
        except requests.exceptions.RequestException as e:
            print(f"Error making API call for '{media_type}': {e}")
        except json.JSONDecodeError as e:
            print(f"Error decoding JSON response for '{media_type}': {e}")
            
        # Add a longer delay between different media type searches
        time.sleep(2)
            
    print("\n--- Scraping complete ---")

if __name__ == "__main__":
    main()
