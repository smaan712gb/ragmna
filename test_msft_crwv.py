"""
Real Production Test: MSFT Acquiring CRWV
Demonstrates live RAG vectorization with real data
"""
import requests
import os
import json
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()

headers = {'X-API-Key': os.getenv('SERVICE_API_KEY')}

print('\n' + '='*80)
print('🎯 LIVE PRODUCTION TEST: MSFT Acquiring CRWV')
print('='*80 + '\n')

# Ingest CRWV (Target)
print('📥 Ingesting CRWV (Target) - Fetching real data from FMP API...')
r1 = requests.post(
    'http://localhost:8001/ingest/comprehensive',
    json={'symbol': 'CRWV', 'data_sources': ['analyst_reports', 'news']},
    headers=headers,
    timeout=300
)

d1 = r1.json()
vec1 = d1.get('vectorization_results', {})
print(f'✅ CRWV Status: HTTP {r1.status_code}')
print(f'   Vectors Stored in RAG: {vec1.get("vectors_stored", 0)}')
print(f'   Documents Processed: {vec1.get("total_documents", 0)}')
if vec1.get('error'):
    print(f'   Error: {vec1.get("error")[:100]}')
print()

# Ingest MSFT (Acquirer)
print('📥 Ingesting MSFT (Acquirer) - Fetching real data from FMP API...')
r2 = requests.post(
    'http://localhost:8001/ingest/comprehensive',
    json={'symbol': 'MSFT', 'data_sources': ['analyst_reports']},
    headers=headers,
    timeout=300
)

d2 = r2.json()
vec2 = d2.get('vectorization_results', {})
print(f'✅ MSFT Status: HTTP {r2.status_code}')
print(f'   Vectors Stored in RAG: {vec2.get("vectors_stored", 0)}')
print(f'   Documents Processed: {vec2.get("total_documents", 0)}')
if vec2.get('error'):
    print(f'   Error: {vec2.get("error")[:100]}')
print()

# Summary
total_vectors = vec1.get('vectors_stored', 0) + vec2.get('vectors_stored', 0)
print('='*80)
print(f'🎉 TOTAL VECTORS STORED IN VERTEX AI RAG ENGINE: {total_vectors}')
print(f'✅ RAG Authentication Status: {"WORKING WITH ACCESS TOKENS ✓" if total_vectors > 0 else "FAILED"}')
print(f'📊 Project: amadds102025')
print(f'🌍 Region: us-west1')
print(f'🔑 Auth Method: gcloud auth print-access-token')
print('='*80)

# Save results
results = {
    'timestamp': datetime.now().isoformat(),
    'scenario': 'MSFT_acquires_CRWV',
    'target': {'symbol': 'CRWV', 'vectors': vec1.get('vectors_stored', 0), 'status': r1.status_code},
    'acquirer': {'symbol': 'MSFT', 'vectors': vec2.get('vectors_stored', 0), 'status': r2.status_code},
    'total_vectors': total_vectors,
    'auth_working': total_vectors > 0
}

filename = f'MSFT_CRWV_TEST_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json'
with open(filename, 'w') as f:
    json.dump(results, f, indent=2)

print(f'\n📁 Results saved to: {filename}')
