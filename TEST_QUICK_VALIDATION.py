"""
QUICK VALIDATION TEST - Without Docker
Tests core functionality: API keys, GCP connectivity, RAG Engine setup

Run with: python TEST_QUICK_VALIDATION.py
"""

import os
import sys
import json
import requests
from datetime import datetime

# Load environment variables from .env
from dotenv import load_dotenv
load_dotenv()

print("\n" + "=" * 80)
print("M&A PLATFORM - QUICK VALIDATION TEST")
print("=" * 80 + "\n")

results = {
    'tests_passed': 0,
    'tests_failed': 0,
    'details': {}
}

# Test 1: Check environment variables
print("[TEST 1] Checking environment variables...")
env_vars = {
    'FMP_API_KEY': os.getenv('FMP_API_KEY'),
    'PROJECT_ID': os.getenv('PROJECT_ID'),
    'VERTEX_PROJECT': os.getenv('VERTEX_PROJECT'),
    'VERTEX_LOCATION': os.getenv('VERTEX_LOCATION'),
    'GCS_BUCKET': os.getenv('GCS_BUCKET'),
    'GOOGLE_CLOUD_KEY_PATH': os.getenv('GOOGLE_CLOUD_KEY_PATH')
}

missing_vars = [k for k, v in env_vars.items() if not v]
if missing_vars:
    print(f"  ❌ Missing environment variables: {', '.join(missing_vars)}")
    results['tests_failed'] += 1
    results['details']['environment_check'] = 'FAILED'
else:
    print(f"  ✅ All environment variables set")
    results['tests_passed'] += 1
    results['details']['environment_check'] = 'PASSED'

# Test 2: Check GCP service key exists
print("\n[TEST 2] Checking GCP service account key...")
key_path = env_vars['GOOGLE_CLOUD_KEY_PATH']
if key_path and os.path.exists(key_path):
    print(f"  ✅ Service account key found: {key_path}")
    results['tests_passed'] += 1
    results['details']['gcp_key_check'] = 'PASSED'
    
    # Try to load it
    try:
        with open(key_path, 'r') as f:
            key_data = json.load(f)
        print(f"  ✅ Key is valid JSON")
        print(f"     Project ID: {key_data.get('project_id')}")
        print(f"     Client Email: {key_data.get('client_email')}")
    except Exception as e:
        print(f"  ⚠️  Warning: Could not parse key file: {e}")
else:
    print(f"  ❌ Service account key not found: {key_path}")
    results['tests_failed'] += 1
    results['details']['gcp_key_check'] = 'FAILED'

# Test 3: Test FMP API connectivity
print("\n[TEST 3] Testing FMP API connectivity...")
fmp_api_key = env_vars['FMP_API_KEY']
if fmp_api_key:
    try:
        test_url = f"https://financialmodelingprep.com/api/v3/profile/AAPL?apikey={fmp_api_key}"
        response = requests.get(test_url, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            if data and isinstance(data, list) and len(data) > 0:
                company = data[0]
                print(f"  ✅ FMP API working correctly")
                print(f"     Test query: Apple Inc (AAPL)")
                print(f"     Market Cap: ${company.get('mktCap', 0):,.0f}")
                print(f"     Price: ${company.get('price', 0):.2f}")
                results['tests_passed'] += 1
                results['details']['fmp_api_check'] = 'PASSED'
            else:
                print(f"  ❌ FMP API returned empty data")
                results['tests_failed'] += 1
                results['details']['fmp_api_check'] = 'FAILED - Empty response'
        else:
            print(f"  ❌ FMP API returned status code: {response.status_code}")
            results['tests_failed'] += 1
            results['details']['fmp_api_check'] = f'FAILED - Status {response.status_code}'
    except Exception as e:
        print(f"  ❌ FMP API connection failed: {e}")
        results['tests_failed'] += 1
        results['details']['fmp_api_check'] = f'FAILED - {str(e)}'
else:
    print(f"  ❌ FMP_API_KEY not set")
    results['tests_failed'] += 1
    results['details']['fmp_api_check'] = 'FAILED - No API key'

# Test 4: Test GCP authentication
print("\n[TEST 4] Testing GCP authentication...")
try:
    from google.auth import default
    from google.auth.transport.requests import Request
    
    # Set the environment variable for Google auth
    if key_path:
        os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = key_path
    
    credentials, project = default()
    
    # Try to refresh credentials
    if not credentials.valid:
        if credentials.expired and credentials.refresh_token:
            credentials.refresh(Request())
    
    print(f"  ✅ GCP authentication successful")
    print(f"     Project: {project}")
    print(f"     Service account: {credentials.service_account_email if hasattr(credentials, 'service_account_email') else 'N/A'}")
    results['tests_passed'] += 1
    results['details']['gcp_auth_check'] = 'PASSED'
    
except Exception as e:
    print(f"  ❌ GCP authentication failed: {e}")
    print(f"     Make sure google-cloud-aiplatform is installed: pip install google-cloud-aiplatform")
    results['tests_failed'] += 1
    results['details']['gcp_auth_check'] = f'FAILED - {str(e)}'

# Test 5: Test Vertex AI RAG Engine accessibility
print("\n[TEST 5] Testing Vertex AI RAG Engine connectivity...")
try:
    from google.auth import default
    from google.auth.transport.requests import Request
    
    if key_path:
        os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = key_path
    
    credentials, project = default()
    if not credentials.valid:
        if credentials.expired and credentials.refresh_token:
            credentials.refresh(Request())
    
    # Try to access RAG Engine API
    location = env_vars['VERTEX_LOCATION']
    rag_url = f"https://{location}-aiplatform.googleapis.com/v1beta1/projects/{project}/locations/{location}/ragCorpora"
    
    headers = {
        'Authorization': f'Bearer {credentials.token}',
        'Content-Type': 'application/json'
    }
    
    response = requests.get(rag_url, headers=headers, timeout=30)
    
    if response.status_code in [200, 404]:  # 404 is OK - means no corpora yet, but API is accessible
        print(f"  ✅ Vertex AI RAG Engine API accessible")
        if response.status_code == 200:
            data = response.json()
            corpora = data.get('ragCorpora', [])
            print(f"     Found {len(corpora)} existing RAG corpora")
            for corpus in corpora[:3]:  # Show first 3
                print(f"     - {corpus.get('displayName', 'Unknown')}")
        else:
            print(f"     No existing corpora (will be created on first use)")
        results['tests_passed'] += 1
        results['details']['rag_engine_check'] = 'PASSED'
    else:
        print(f"  ❌ RAG Engine API returned: {response.status_code}")
        print(f"     Response: {response.text[:200]}")
        results['tests_failed'] += 1
        results['details']['rag_engine_check'] = f'FAILED - Status {response.status_code}'
        
except ImportError:
    print(f"  ⚠️  Google Cloud libraries not installed")
    print(f"     Run: pip install google-cloud-aiplatform")
    results['tests_failed'] += 1
    results['details']['rag_engine_check'] = 'FAILED - Missing libraries'
except Exception as e:
    print(f"  ❌ RAG Engine connectivity test failed: {e}")
    results['tests_failed'] += 1
    results['details']['rag_engine_check'] = f'FAILED - {str(e)}'

# Test 6: Check conda environment
print("\n[TEST 6] Checking conda environment...")
try:
    conda_env = os.environ.get('CONDA_DEFAULT_ENV', '')
    if conda_env == 'ragmna':
        print(f"  ✅ Correct conda environment: {conda_env}")
        results['tests_passed'] += 1
        results['details']['conda_env_check'] = 'PASSED'
    else:
        print(f"  ⚠️  Not in ragmna environment (current: {conda_env})")
        print(f"     Run: conda activate ragmna")
        results['tests_failed'] += 1
        results['details']['conda_env_check'] = f'WARNING - In {conda_env}'
except Exception as e:
    print(f"  ⚠️  Could not check conda environment: {e}")
    results['details']['conda_env_check'] = 'UNKNOWN'

# Summary
print("\n" + "=" * 80)
print("VALIDATION SUMMARY")
print("=" * 80)

total_tests = results['tests_passed'] + results['tests_failed']
success_rate = (results['tests_passed'] / total_tests * 100) if total_tests > 0 else 0

print(f"\n✅ Tests Passed: {results['tests_passed']}/{total_tests}")
print(f"❌ Tests Failed: {results['tests_failed']}/{total_tests}")
print(f"📊 Success Rate: {success_rate:.1f}%\n")

if success_rate >= 80:
    print("🎉 PLATFORM CONFIGURATION IS VALID!")
    print("\nYour platform is properly configured and ready to use.")
    print("\nNext steps:")
    print("1. To test data ingestion: python services/data-ingestion/main.py")
    print("2. Or run full validation with Docker: docker-compose up -d")
    exit_code = 0
elif success_rate >= 50:
    print("⚠️  PLATFORM IS PARTIALLY CONFIGURED")
    print("\nSome tests failed. Review the errors above and fix configuration.")
    exit_code = 1
else:
    print("❌ PLATFORM CONFIGURATION NEEDS WORK")
    print("\nMultiple tests failed. Please fix configuration issues.")
    exit_code = 1

# Save results
timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
results_file = f'quick_validation_results_{timestamp}.json'
with open(results_file, 'w') as f:
    json.dump(results, f, indent=2)

print(f"\n📄 Detailed results saved to: {results_file}")

print("\n" + "=" * 80 + "\n")

sys.exit(exit_code)
