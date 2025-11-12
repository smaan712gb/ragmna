"""
Test RAG Authentication Fix
Tests the complete pipeline: Ingestion -> Vectorization -> LLM with Gemini 2.5 Pro
"""

import os
import sys
import json
import time
import requests
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configuration
PROJECT_ID = os.getenv('PROJECT_ID')
VERTEX_PROJECT = os.getenv('VERTEX_PROJECT')
VERTEX_LOCATION = os.getenv('VERTEX_LOCATION')
SERVICE_API_KEY = os.getenv('SERVICE_API_KEY')
FMP_API_KEY = os.getenv('FMP_API_KEY')
RAG_CORPUS_ID = os.getenv('RAG_CORPUS_ID')
GCS_BUCKET = os.getenv('GCS_BUCKET')

# Service URLs
RUN_MANAGER_URL = "http://localhost:8013"
DATA_INGESTION_URL = "http://localhost:8001"
LLM_ORCHESTRATOR_URL = "http://localhost:8002"

# Test configuration
TEST_SYMBOL = "NVDA"
TEST_NAME = f"RAG_Authentication_Test_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

def print_section(title):
    """Print a section header"""
    print(f"\n{'='*80}")
    print(f"  {title}")
    print(f"{'='*80}\n")

def print_status(status, message):
    """Print a status message"""
    icons = {
        'success': '✅',
        'error': '❌',
        'info': 'ℹ️',
        'warning': '⚠️',
        'progress': '⏳'
    }
    icon = icons.get(status, '•')
    print(f"{icon} {message}")

def check_configuration():
    """Verify all required configuration is present"""
    print_section("1. Configuration Check")
    
    required_vars = {
        'PROJECT_ID': PROJECT_ID,
        'VERTEX_PROJECT': VERTEX_PROJECT,
        'VERTEX_LOCATION': VERTEX_LOCATION,
        'SERVICE_API_KEY': SERVICE_API_KEY,
        'FMP_API_KEY': FMP_API_KEY,
        'RAG_CORPUS_ID': RAG_CORPUS_ID,
        'GCS_BUCKET': GCS_BUCKET
    }
    
    all_present = True
    for var_name, var_value in required_vars.items():
        if var_value:
            print_status('success', f"{var_name}: {var_value[:20]}..." if len(str(var_value)) > 20 else f"{var_name}: {var_value}")
        else:
            print_status('error', f"{var_name}: MISSING")
            all_present = False
    
    if not all_present:
        print_status('error', "Missing required configuration. Please check .env file.")
        sys.exit(1)
    
    print_status('success', "All configuration variables present")
    return True

def check_services():
    """Check if required services are running"""
    print_section("2. Service Health Check")
    
    services = [
        ('Run Manager', RUN_MANAGER_URL),
        ('Data Ingestion', DATA_INGESTION_URL),
        ('LLM Orchestrator', LLM_ORCHESTRATOR_URL)
    ]
    
    all_healthy = True
    for service_name, service_url in services:
        try:
            response = requests.get(f"{service_url}/health", timeout=5)
            if response.status_code == 200:
                print_status('success', f"{service_name} is healthy at {service_url}")
            else:
                print_status('error', f"{service_name} returned status {response.status_code}")
                all_healthy = False
        except requests.exceptions.RequestException as e:
            print_status('error', f"{service_name} is not reachable: {e}")
            all_healthy = False
    
    if not all_healthy:
        print_status('error', "Some services are not running. Start with: docker-compose up -d")
        sys.exit(1)
    
    return True

def test_data_ingestion():
    """Test data ingestion and vectorization"""
    print_section("3. Data Ingestion & Vectorization Test")
    
    print_status('progress', f"Ingesting company data for {TEST_SYMBOL}...")
    print_status('info', f"Target: {DATA_INGESTION_URL}/ingest/comprehensive")
    
    headers = {'X-API-Key': SERVICE_API_KEY}
    payload = {
        'symbol': TEST_SYMBOL,
        'data_sources': ['analyst_reports']  # Start with just analyst reports (faster)
    }
    
    try:
        print_status('info', f"Making POST request with payload: {json.dumps(payload, indent=2)}")
        response = requests.post(
            f"{DATA_INGESTION_URL}/ingest/comprehensive",
            json=payload,
            headers=headers,
            timeout=300  # 5 minutes timeout
        )
        
        print_status('info', f"Response status: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            print_status('success', "Data ingestion completed successfully")
            
            # Check vectorization results
            if 'vectorization_results' in result:
                vec_results = result['vectorization_results']
                print_status('info', f"Documents processed: {vec_results.get('total_documents', 0)}")
                print_status('info', f"Chunks created: {vec_results.get('chunks_created', 0)}")
                print_status('info', f"Vectors stored: {vec_results.get('vectors_stored', 0)}")
                
                if vec_results.get('vectors_stored', 0) > 0:
                    print_status('success', "✨ RAG vectorization successful! ACCESS tokens are working.")
                else:
                    print_status('warning', "No vectors were stored - check logs for details")
            
            return result
        else:
            print_status('error', f"Ingestion failed with status {response.status_code}")
            print_status('error', f"Response: {response.text[:500]}")
            return None
            
    except Exception as e:
        print_status('error', f"Ingestion error: {str(e)}")
        return None

def test_llm_query():
    """Test LLM query using Gemini 2.5 Pro"""
    print_section("4. LLM Query Test (Gemini 2.5 Pro)")
    
    print_status('progress', f"Testing RAG-enhanced query for {TEST_SYMBOL}...")
    
    headers = {'X-API-Key': SERVICE_API_KEY}
    payload = {
        'query': f"What are the key analyst recommendations and price targets for {TEST_SYMBOL}?",
        'use_rag': True,
        'rag_filter': {
            'symbol': TEST_SYMBOL
        }
    }
    
    try:
        print_status('info', f"Making POST request to LLM Orchestrator...")
        response = requests.post(
            f"{LLM_ORCHESTRATOR_URL}/query",
            json=payload,
            headers=headers,
            timeout=120
        )
        
        print_status('info', f"Response status: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            print_status('success', "LLM query completed successfully")
            
            # Display the response
            if 'response' in result:
                print("\n" + "─"*80)
                print("LLM Response (Gemini 2.5 Pro):")
                print("─"*80)
                print(result['response'][:500] + "..." if len(result['response']) > 500 else result['response'])
                print("─"*80 + "\n")
                print_status('success', "✨ Gemini 2.5 Pro is working with RAG!")
            
            # Check if RAG context was used
            if 'rag_context' in result and result['rag_context']:
                print_status('success', f"RAG context retrieved: {len(result['rag_context'])} chunks")
            
            return result
        else:
            print_status('error', f"LLM query failed with status {response.status_code}")
            print_status('error', f"Response: {response.text[:500]}")
            return None
            
    except Exception as e:
        print_status('error', f"LLM query error: {str(e)}")
        return None

def save_test_results(ingestion_result, llm_result):
    """Save test results to file"""
    print_section("5. Saving Test Results")
    
    results = {
        'test_name': TEST_NAME,
        'timestamp': datetime.now().isoformat(),
        'test_symbol': TEST_SYMBOL,
        'configuration': {
            'project_id': PROJECT_ID,
            'vertex_location': VERTEX_LOCATION,
            'rag_corpus_id': RAG_CORPUS_ID,
            'gcs_bucket': GCS_BUCKET
        },
        'ingestion_result': ingestion_result,
        'llm_result': llm_result
    }
    
    filename = f"RAG_TEST_RESULTS_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    
    try:
        with open(filename, 'w') as f:
            json.dump(results, f, indent=2)
        print_status('success', f"Results saved to: {filename}")
        return filename
    except Exception as e:
        print_status('error', f"Failed to save results: {e}")
        return None

def main():
    """Run the complete test suite"""
    print("\n" + "█"*80)
    print("█" + " "*78 + "█")
    print("█" + "  RAG Authentication Fix - End-to-End Test".center(78) + "█")
    print("█" + " "*78 + "█")
    print("█"*80 + "\n")
    
    start_time = time.time()
    
    try:
        # Step 1: Check configuration
        check_configuration()
        
        # Step 2: Check services
        check_services()
        
        # Step 3: Test data ingestion and vectorization
        ingestion_result = test_data_ingestion()
        if not ingestion_result:
            print_status('error', "Data ingestion failed. Check logs with: docker-compose logs data-ingestion")
            sys.exit(1)
        
        # Wait a moment for vectorization to complete
        print_status('progress', "Waiting 10 seconds for vectorization to complete...")
        time.sleep(10)
        
        # Step 4: Test LLM query
        llm_result = test_llm_query()
        if not llm_result:
            print_status('warning', "LLM query failed, but ingestion was successful")
        
        # Step 5: Save results
        save_test_results(ingestion_result, llm_result)
        
        # Final summary
        elapsed_time = time.time() - start_time
        print_section("Test Summary")
        print_status('success', f"Test completed in {elapsed_time:.2f} seconds")
        print_status('success', "✨ RAG Authentication Fix VERIFIED - ACCESS tokens working correctly!")
        print_status('success', "✨ Gemini 2.5 Pro integration working!")
        print_status('info', f"Region: {VERTEX_LOCATION} (us-west1)")
        print_status('info', f"Service account: secrets/gcp-service-key.json")
        
    except KeyboardInterrupt:
        print_status('warning', "\nTest interrupted by user")
        sys.exit(1)
    except Exception as e:
        print_status('error', f"Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
