"""
Create Vertex AI RAG Corpus via REST API
Run this once to create the RAG corpus, then add the corpus ID to .env
"""

import os
import json
import requests
from google.oauth2 import service_account
from google.auth.transport.requests import Request

# Load environment
from dotenv import load_dotenv
load_dotenv()

def create_rag_corpus():
    """Create RAG corpus via Vertex AI API"""
    
    # Get configuration
    project_id = os.getenv('PROJECT_ID', 'amadds102025')
    location = os.getenv('VERTEX_LOCATION', 'us-central1')
    key_path = os.getenv('GOOGLE_CLOUD_KEY_PATH', 'secrets/gcp-service-key.json')
    
    print(f"Creating RAG corpus in project: {project_id}, location: {location}")
    
    # Load credentials
    scopes = [
        'https://www.googleapis.com/auth/cloud-platform',
        'https://www.googleapis.com/auth/aiplatform'
    ]
    
    credentials = service_account.Credentials.from_service_account_file(
        key_path,
        scopes=scopes
    )
    
    credentials.refresh(Request())
    
    # Create corpus
    url = f"https://{location}-aiplatform.googleapis.com/v1beta1/projects/{project_id}/locations/{location}/ragCorpora"
    
    payload = {
        "display_name": "ma-analysis",
        "description": "M&A Analysis Platform - Document corpus for SEC filings, analyst reports, and news"
    }
    
    headers = {
        'Authorization': f'Bearer {credentials.token}',
        'Content-Type': 'application/json'
    }
    
    try:
        response = requests.post(url, json=payload, headers=headers, timeout=60)
        response.raise_for_status()
        
        result = response.json()
        corpus_name = result.get('name', '')
        
        # Extract corpus ID from name (format: projects/.../ragCorpora/CORPUS_ID)
        corpus_id = corpus_name.split('/')[-1] if corpus_name else ''
        
        print(f"\n✅ RAG Corpus Created Successfully!")
        print(f"   Full name: {corpus_name}")
        print(f"   Corpus ID: {corpus_id}")
        print(f"\n📝 Add this to your .env file:")
        print(f"   RAG_CORPUS_ID={corpus_id}")
        
        return corpus_id
        
    except requests.exceptions.HTTPError as e:
        error_detail = e.response.text if hasattr(e.response, 'text') else str(e)
        print(f"\n❌ Error creating RAG corpus: {e.response.status_code}")
        print(f"   Details: {error_detail}")
        return None
    except Exception as e:
        print(f"\n❌ Error: {e}")
        return None

if __name__ == '__main__':
    create_rag_corpus()
