"""
Financial Normalizer Service
GAAP adjustments, one-time item removal, accounting normalization
Uses Gemini 2.5 Pro with Code Execution and File Search
"""

import os
import json
import logging
from flask import Flask, request, jsonify
from functools import wraps
from typing import Dict, Any, List
from datetime import datetime
import pandas as pd
import threading
import time

# Import Vertex AI modules for background initialization
try:
    import vertexai
    from vertexai.generative_models import GenerativeModel, Part
    from vertexai.preview import caching
    from google.oauth2 import service_account
    VERTEX_AVAILABLE = True
except ImportError:
    VERTEX_AVAILABLE = False
    logger.warning("Vertex AI modules not available")

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

SERVICE_API_KEY = os.getenv('SERVICE_API_KEY', 'dev-key')
VERTEX_PROJECT = os.getenv('PROJECT_ID') or os.getenv('VERTEX_PROJECT')
VERTEX_LOCATION = os.getenv('VERTEX_AI_LOCATION') or os.getenv('VERTEX_LOCATION', 'us-west1')
GOOGLE_CLOUD_KEY_PATH = os.getenv('GOOGLE_CLOUD_KEY_PATH') or os.getenv('GOOGLE_APPLICATION_CREDENTIALS')

class FinancialNormalizer:
    """Uses Gemini 2.5 Pro with Code Execution for financial normalization"""

    def __init__(self):
        self.model = None
        self.vertex_initialized = False

    def _ensure_initialized(self):
        """Initialize Vertex AI on first use"""
        if not self.vertex_initialized and VERTEX_PROJECT:
            try:
                # Load credentials from service account key if provided
                credentials = None
                if GOOGLE_CLOUD_KEY_PATH and os.path.exists(GOOGLE_CLOUD_KEY_PATH):
                    try:
                        credentials = service_account.Credentials.from_service_account_file(
                            GOOGLE_CLOUD_KEY_PATH
                        )
                        logger.info(f"Loaded GCP credentials from {GOOGLE_CLOUD_KEY_PATH}")
                    except Exception as cred_error:
                        logger.warning(f"Could not load credentials from file: {cred_error}")
                
                # Initialize Vertex AI with or without explicit credentials
                if credentials:
                    vertexai.init(
                        project=VERTEX_PROJECT, 
                        location=VERTEX_LOCATION,
                        credentials=credentials
                    )
                else:
                    vertexai.init(project=VERTEX_PROJECT, location=VERTEX_LOCATION)
                
                self.model = GenerativeModel(
                    'gemini-2.5-pro',
                    system_instruction="""
You are an expert financial analyst specializing in GAAP adjustments.
You have access to code execution for calculations and file search for SEC filings.

Your tasks:
1. Identify non-recurring items in financial statements
2. Calculate adjustments for SBC, M&A, restructuring, etc.
3. Generate before/after bridges with citations
4. Ensure all adjustments reconcile

Always cite specific SEC filing sections for each adjustment.
"""
                )
                self.vertex_initialized = True
                logger.info(f"✅ Vertex AI initialized successfully for project {VERTEX_PROJECT}")
            except Exception as e:
                logger.error(f"❌ Failed to initialize Vertex AI: {e}")
                self.vertex_initialized = False

    def normalize_financials(self, symbol: str, financials: dict,
                            sec_filings: list, run_cache_name: str = None) -> dict:
        """Normalize company financials using Gemini's code execution"""

        logger.info(f"Normalizing financials for {symbol}")

        # Ensure Vertex AI is initialized
        self._ensure_initialized()

        if not self.vertex_initialized or not self.model:
            error_msg = "Vertex AI not initialized - cannot perform financial normalization"
            logger.error(error_msg)
            raise RuntimeError(error_msg)

        # Convert financials to JSON-serializable format
        financials_clean = self._make_json_serializable(financials)

        # Upload SEC filings for file search
        uploaded_files = []
        for filing in sec_filings[:5]:  # Limit to 5 most recent
            try:
                content = filing.get('content', '')
                if content:
                    file = Part.from_data(
                        data=content.encode()[:100000],  # Limit size
                        mime_type='text/plain'
                    )
                    uploaded_files.append(file)
            except Exception as e:
                logger.error(f"Error uploading filing: {e}")

        # Use cached context if available
        if run_cache_name:
            try:
                cache = caching.CachedContent(name=run_cache_name)
                model = GenerativeModel.from_cached_content(cached_content=cache)
            except Exception as e:
                logger.error(f"Error using cache: {e}")
                model = self.model
        else:
            model = self.model

        prompt = f"""
Normalize the financial statements for {symbol}.

TASK: Identify and adjust for:
1. Stock-Based Compensation (SBC)
2. Acquisition-related costs
3. Restructuring charges
4. Legal settlements
5. Tax adjustments
6. Discontinued operations
7. FX impacts
8. Lease accounting (ASC 842)

PROCESS:
1. Search uploaded SEC filings for each adjustment category
2. Use code execution to calculate adjustment amounts
3. Create before/after bridges
4. Validate reconciliation
5. Cite specific sections for each adjustment

Financial Statements:
{json.dumps(financials_clean, indent=2)[:10000]}

Return structured JSON with:
- normalization_ledger (all adjustments)
- bridges (before/after reconciliation)
- citations (filing references)
- validation (reconciliation checks)
"""

        try:
            # Note: Code execution and file search tools are built-in for Gemini 2.5
            # They don't need to be explicitly declared in this SDK version
            response = model.generate_content(
                [prompt] + uploaded_files if uploaded_files else [prompt],
                generation_config={
                    'response_mime_type': 'application/json',
                    'temperature': 0.1
                }
            )

            result = json.loads(response.text)
            result['normalized_at'] = datetime.now().isoformat()
            result['symbol'] = symbol

            return result

        except Exception as e:
            logger.error(f"Error normalizing financials: {e}")
            return self._generate_basic_normalization(symbol, financials)
    
    def _make_json_serializable(self, obj):
        """Convert pandas Timestamps and other non-serializable objects to serializable format"""
        if isinstance(obj, dict):
            # Convert both keys and values to JSON-serializable format
            result = {}
            for k, v in obj.items():
                # Convert key to string if it's not a valid JSON key type
                if isinstance(k, (pd.Timestamp, datetime)):
                    key = k.isoformat() if hasattr(k, 'isoformat') else str(k)
                elif not isinstance(k, (str, int, float, bool, type(None))):
                    key = str(k)
                else:
                    key = k
                result[key] = self._make_json_serializable(v)
            return result
        elif isinstance(obj, list):
            return [self._make_json_serializable(item) for item in obj]
        elif isinstance(obj, (pd.Timestamp, datetime)):
            return obj.isoformat() if hasattr(obj, 'isoformat') else str(obj)
        elif pd.isna(obj):
            return None
        elif isinstance(obj, (int, float, str, bool, type(None))):
            return obj
        else:
            # For any other type, convert to string
            return str(obj)
    
    def _generate_mock_normalization(self, symbol: str, financials: dict) -> dict:
        """Mock normalization for deployment - returns structured response"""
        return {
            'symbol': symbol,
            'normalization_ledger': [
                {
                    'type': 'mock_adjustment',
                    'description': 'Mock GAAP adjustment for deployment',
                    'amount': 0,
                    'category': 'non-recurring'
                }
            ],
            'bridges': {
                'reported_net_income': 1000000,
                'adjusted_net_income': 1000000,
                'difference': 0
            },
            'citations': [
                {
                    'source': 'Mock SEC Filing',
                    'section': 'Item 8. Financial Statements',
                    'description': 'Mock citation for deployment'
                }
            ],
            'validation': {
                'status': 'mock',
                'reconciliation': 'passed',
                'notes': 'Vertex AI integration disabled for deployment'
            },
            'normalized_at': datetime.now().isoformat()
        }

    def _generate_basic_normalization(self, symbol: str, financials: dict) -> dict:
        """Fallback basic normalization"""
        return {
            'symbol': symbol,
            'normalization_ledger': [],
            'bridges': {},
            'citations': [],
            'validation': {'status': 'basic'},
            'normalized_at': datetime.now().isoformat()
        }

normalizer = FinancialNormalizer()

def require_api_key(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if request.headers.get('X-API-Key') != SERVICE_API_KEY:
            return jsonify({'error': 'Invalid API key'}), 401
        return f(*args, **kwargs)
    return decorated

@app.route('/health', methods=['GET'])
def health():
    return jsonify({'status': 'healthy', 'service': 'financial-normalizer', 'version': '1.0.0'})

@app.route('/normalize', methods=['POST'])
@require_api_key
def normalize():
    try:
        data = request.get_json()
        result = normalizer.normalize_financials(
            symbol=data.get('symbol'),
            financials=data.get('financials', {}),
            sec_filings=data.get('sec_filings', []),
            run_cache_name=data.get('run_cache_name')
        )
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error: {e}")
        return jsonify({'error': str(e)}), 500

def initialize_vertex_ai_background():
    """Initialize Vertex AI in background thread"""
    def init_worker():
        time.sleep(2)  # Wait a bit for Flask to start
        logger.info("Starting Vertex AI initialization in background...")
        normalizer._ensure_initialized()
        logger.info("Vertex AI background initialization completed")

    thread = threading.Thread(target=init_worker, daemon=True)
    thread.start()

if __name__ == '__main__':
    # Start Vertex AI initialization in background
    initialize_vertex_ai_background()

    # Start Flask app immediately
    app.run(host='0.0.0.0', port=int(os.getenv('PORT', 8080)))
