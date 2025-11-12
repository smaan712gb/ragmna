import requests
import os
from dotenv import load_dotenv

load_dotenv()

print('Testing Data Ingestion with Fixed Auth...')
r = requests.post(
    'http://localhost:8001/ingest/comprehensive', 
    json={'symbol': 'NVDA', 'data_sources': ['analyst_reports']}, 
    headers={'X-API-Key': os.getenv('SERVICE_API_KEY')}, 
    timeout=180
)

result = r.json()
print(f'Status: {r.status_code}')

if 'vectorization_results' in result:
    vec_results = result['vectorization_results']
    error = vec_results.get('error', 'No error')
    vectors_stored = vec_results.get('vectors_stored', 0)
    
    print(f'Vectorization Error: {error}')
    print(f'Vectors Stored: {vectors_stored}')
    
    if vectors_stored > 0:
        print('✅ SUCCESS! RAG vectorization is working with ACCESS tokens!')
    elif 'id_token' in str(error).lower():
        print('❌ STILL GETTING ID TOKENS - Authentication fix not working')
    else:
        print(f'❌ OTHER ERROR: {error}')
else:
    print('No vectorization results')
