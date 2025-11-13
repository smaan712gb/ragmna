"""
Data Ingestion Service - ENHANCED
Multi-source data integration with qualitative extraction

Data Sources:
1. FMP API - Financials, company profiles, analyst reports
2. yfinance - Shares outstanding, market data, institutional holders
3. SEC Edgar - Official filings with qualitative extraction (MD&A, footnotes, projections)
4. News APIs - Company news and press releases
5. Social Media - Twitter, Reddit sentiment
"""

import os
import json
import logging
import time
import re
from flask import Flask, request, jsonify
from functools import wraps
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from google.cloud import storage, pubsub_v1
from google.api_core.exceptions import GoogleAPIError
import requests
import yfinance as yf
from bs4 import BeautifulSoup
from collections import deque
from threading import Lock

app = Flask(__name__)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Service configurations
SERVICE_API_KEY = os.getenv('SERVICE_API_KEY')
PROJECT_ID = os.getenv('PROJECT_ID', 'your-gcp-project')
RAG_ENGINE_URL = os.getenv('RAG_ENGINE_URL', 'https://LOCATION-aiplatform.googleapis.com/v1beta1')
VERTEX_PROJECT = os.getenv('VERTEX_PROJECT')
VERTEX_LOCATION = os.getenv('VERTEX_LOCATION')

class YFinanceRateLimiter:
    """Rate limiter for yfinance API calls to prevent hitting rate limits"""
    
    def __init__(self, max_calls_per_minute=10):
        """
        Initialize rate limiter
        Args:
            max_calls_per_minute: Maximum number of API calls allowed per minute
        """
        self.max_calls_per_minute = max_calls_per_minute
        self.call_times = deque()
        self.lock = Lock()
        logger.info(f"🔒 YFinance rate limiter initialized: max {max_calls_per_minute} calls/minute")
    
    def wait_if_needed(self):
        """Wait if necessary to stay within rate limits"""
        with self.lock:
            now = time.time()
            
            # Remove calls older than 1 minute
            while self.call_times and (now - self.call_times[0]) > 60:
                self.call_times.popleft()
            
            # If at limit, wait until oldest call is >60s old
            if len(self.call_times) >= self.max_calls_per_minute:
                sleep_time = 60 - (now - self.call_times[0]) + 0.1  # Add 0.1s buffer
                if sleep_time > 0:
                    logger.info(f"⏳ Rate limit: {len(self.call_times)}/{self.max_calls_per_minute} calls in last minute. Waiting {sleep_time:.1f}s...")
                    time.sleep(sleep_time)
                    # Clean up old calls after waiting
                    now = time.time()
                    while self.call_times and (now - self.call_times[0]) > 60:
                        self.call_times.popleft()
            
            # Record this call
            self.call_times.append(now)
            logger.debug(f"📊 Rate limiter: {len(self.call_times)}/{self.max_calls_per_minute} calls in last minute")

# Global yfinance rate limiter - limit to 10 calls per minute (conservative)
yf_rate_limiter = YFinanceRateLimiter(max_calls_per_minute=10)

class DataIngestionService:
    """Handles data ingestion and processing pipeline"""

    def __init__(self):
        # GCP credentials: Support both service account and Application Default Credentials (ADC)
        google_cloud_key_path = os.getenv('GOOGLE_CLOUD_KEY_PATH')
        
        if not PROJECT_ID or PROJECT_ID == 'your-gcp-project':
            raise ValueError("❌ PROJECT_ID environment variable is REQUIRED and must be configured")
        
        # Initialize GCS client with appropriate credentials
        try:
            from google.oauth2 import service_account
            from google.auth import default

            # Always try Application Default Credentials first (user's gcloud auth)
            # This is more reliable than service account files
            logger.info("🔑 Using Application Default Credentials for GCS")
            try:
                self.storage_client = storage.Client(project=PROJECT_ID)
                logger.info(f"✅ GCS client initialized with Application Default Credentials, project: {PROJECT_ID}")
            except Exception as adc_error:
                logger.warning(f"ADC failed for GCS, trying service account: {adc_error}")
                if google_cloud_key_path and os.path.exists(google_cloud_key_path):
                    # Fallback to service account credentials
                    logger.info("🔑 Falling back to service account credentials for GCS")
                    credentials = service_account.Credentials.from_service_account_file(google_cloud_key_path)
                    self.storage_client = storage.Client(credentials=credentials, project=PROJECT_ID)
                    logger.info(f"✅ GCS client initialized with service account, project: {PROJECT_ID}")
                else:
                    raise ValueError("No valid credentials found for GCS")
        except Exception as e:
            raise ValueError(f"❌ FAILED to initialize GCS client: {e}. Check credentials and permissions.")

        # Initialize PubSub client
        try:
            # Always try Application Default Credentials first
            logger.info("🔑 Using Application Default Credentials for PubSub")
            try:
                self.publisher = pubsub_v1.PublisherClient()
                logger.info(f"✅ PubSub client initialized with Application Default Credentials")
            except Exception as adc_error:
                logger.warning(f"ADC failed for PubSub, trying service account: {adc_error}")
                if google_cloud_key_path and os.path.exists(google_cloud_key_path):
                    # Fallback to service account credentials
                    logger.info("🔑 Falling back to service account credentials for PubSub")
                    credentials = service_account.Credentials.from_service_account_file(google_cloud_key_path)
                    self.publisher = pubsub_v1.PublisherClient(credentials=credentials)
                    logger.info(f"✅ PubSub client initialized with service account")
                else:
                    raise ValueError("No valid credentials found for PubSub")
            self.topic_path = self.publisher.topic_path(PROJECT_ID, 'rag-ingestion-data-processing-topic')
        except Exception as e:
            raise ValueError(f"❌ FAILED to initialize PubSub client: {e}. Check credentials and permissions.")

    def process_sec_filing(self, bucket_name: str, file_name: str) -> Dict[str, Any]:
        """Process uploaded SEC filing"""

        logger.info(f"Processing SEC filing: {bucket_name}/{file_name}")

        try:
            # Download file from Cloud Storage
            bucket = self.storage_client.bucket(bucket_name)
            blob = bucket.blob(file_name)

            if not blob.exists():
                raise FileNotFoundError(f"File {file_name} not found in bucket {bucket_name}")

            content = blob.download_as_text()

            # Extract metadata
            metadata = self._extract_filing_metadata(file_name, content)

            # Chunk document
            chunks = self._chunk_document(content, metadata)

            # Store in vector database via RAG Engine
            vector_ids = self._store_in_rag_engine(chunks, metadata)

            # Publish processing completion
            self._publish_completion_event(metadata, vector_ids)

            return {
                'status': 'success',
                'file_processed': file_name,
                'chunks_created': len(chunks),
                'vectors_stored': len(vector_ids),
                'metadata': metadata
            }

        except Exception as e:
            logger.error(f"Error processing SEC filing {file_name}: {e}")
            return {
                'status': 'error',
                'file_processed': file_name,
                'error': str(e)
            }

    def _extract_filing_metadata(self, file_name: str, content: str) -> Dict[str, Any]:
        """Extract metadata from SEC filing"""

        metadata = {
            'file_name': file_name,
            'processing_date': datetime.now().isoformat(),
            'filing_type': 'unknown',
            'company_cik': 'unknown',
            'company_name': 'unknown',
            'filing_date': 'unknown',
            'document_type': 'sec_filing'
        }

        # Extract filing type from filename
        if '10-K' in file_name.upper():
            metadata['filing_type'] = '10-K'
        elif '10-Q' in file_name.upper():
            metadata['filing_type'] = '10-Q'
        elif '8-K' in file_name.upper():
            metadata['filing_type'] = '8-K'

        # Extract CIK from filename (typically in format: cik-formtype-date.txt)
        try:
            cik = file_name.split('-')[0]
            if cik.isdigit():
                metadata['company_cik'] = cik
        except:
            pass

        # Extract company name from content (basic parsing)
        try:
            # Look for company name in header
            lines = content.split('\n')[:50]  # First 50 lines
            for line in lines:
                if 'COMPANY CONFORMED NAME:' in line.upper():
                    metadata['company_name'] = line.split(':', 1)[1].strip()
                    break
        except:
            pass

        return metadata

    def _chunk_document(self, content: str, metadata: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Chunk document for vector storage"""

        # Simple chunking strategy - split by sections and limit size
        max_chunk_size = 1000  # characters
        overlap = 200  # characters

        # Split content into sections (basic approach)
        sections = content.split('\n\n')  # Split by double newlines

        chunks = []
        current_chunk = ""
        chunk_id = 0

        for section in sections:
            if len(current_chunk + section) > max_chunk_size and current_chunk:
                # Create chunk
                chunks.append({
                    'id': f"{metadata['file_name']}_chunk_{chunk_id}",
                    'content': current_chunk.strip(),
                    'metadata': {
                        **metadata,
                        'chunk_number': chunk_id,
                        'start_position': len(''.join([c['content'] for c in chunks])),
                        'end_position': len(''.join([c['content'] for c in chunks] + [current_chunk]))
                    }
                })
                chunk_id += 1

                # Start new chunk with overlap
                overlap_text = current_chunk[-overlap:] if len(current_chunk) > overlap else current_chunk
                current_chunk = overlap_text + section
            else:
                current_chunk += "\n\n" + section if current_chunk else section

        # Add final chunk
        if current_chunk.strip():
            chunks.append({
                'id': f"{metadata['file_name']}_chunk_{chunk_id}",
                'content': current_chunk.strip(),
                'metadata': {
                    **metadata,
                    'chunk_number': chunk_id,
                    'start_position': len(''.join([c['content'] for c in chunks[:-1]])),
                    'end_position': len(''.join([c['content'] for c in chunks]))
                }
            })

        return chunks

    def _poll_rag_operation(self, operation_name: str, access_token: str, max_wait_seconds: int = 600) -> bool:
        """Poll RAG import operation until completion

        Args:
            operation_name: Full operation name from RAG import response
            access_token: OAuth2 access token for API calls
            max_wait_seconds: Maximum time to wait (default 10 minutes)

        Returns:
            True if operation succeeded, False otherwise
        """
        import time

        poll_interval = 10  # Check every 10 seconds
        max_polls = max_wait_seconds // poll_interval

        logger.info(f"⏳ Polling RAG operation (max {max_wait_seconds}s): {operation_name}")

        for attempt in range(max_polls):
            try:
                # Get operation status
                url = f"https://aiplatform.googleapis.com/v1beta1/{operation_name}"
                headers = {
                    'Authorization': f'Bearer {access_token}',
                    'Content-Type': 'application/json'
                }

                response = requests.get(url, headers=headers, timeout=30)

                if response.status_code == 200:
                    operation = response.json()

                    # Check if done
                    if operation.get('done', False):
                        # Check for errors
                        if 'error' in operation:
                            error = operation['error']
                            logger.error(f"❌ RAG operation failed: {error.get('message', 'Unknown error')}")
                            return False
                        else:
                            logger.info(f"✅ RAG vectorization completed successfully after {(attempt + 1) * poll_interval}s")
                            return True
                    else:
                        # Still in progress
                        logger.info(f"   ⏳ RAG vectorization in progress... ({(attempt + 1) * poll_interval}s elapsed)")
                        time.sleep(poll_interval)
                else:
                    logger.warning(f"⚠️ Failed to poll operation status: {response.status_code}")
                    return False

            except Exception as e:
                logger.warning(f"⚠️ Error polling RAG operation: {e}")
                return False

        # Timeout reached
        logger.warning(f"⚠️ RAG operation timeout after {max_wait_seconds}s - vectors may not be ready yet")
        return False

    def _store_in_rag_engine(self, chunks: List[Dict[str, Any]], metadata: Dict[str, Any]) -> List[str]:
        """Store document chunks in Vertex AI RAG Engine via Import API with completion polling"""

        vector_ids = []

        try:
            import requests as req_lib
            from google.cloud import storage
            import tempfile

            # Get access token using gcloud command (most reliable method)
            import subprocess
            try:
                result = subprocess.run(
                    ['gcloud', 'auth', 'print-access-token'],
                    capture_output=True,
                    text=True,
                    check=True,
                    timeout=30
                )
                access_token = result.stdout.strip()
                if not access_token or len(access_token) < 100:
                    raise ValueError(f"Invalid access token from gcloud: {access_token[:50] if access_token else 'empty'}")
                logger.info(f"✅ RAG: Access token from gcloud (length: {len(access_token)})")
            except Exception as gcloud_error:
                logger.warning(f"⚠️ gcloud command failed: {gcloud_error}, trying service account directly")

                # Fallback: Use service account with requests library directly
                google_cloud_key_path = os.getenv('GOOGLE_APPLICATION_CREDENTIALS')
                if not google_cloud_key_path or not os.path.exists(google_cloud_key_path):
                    raise ValueError(f"❌ Service account key not found at: {google_cloud_key_path}")

                # Load service account and manually get OAuth2 token
                import json
                with open(google_cloud_key_path, 'r') as f:
                    sa_info = json.load(f)

                # Use google.auth with explicit token request
                from google.oauth2 import service_account
                from google.auth.transport.requests import Request

                credentials = service_account.Credentials.from_service_account_info(
                    sa_info,
                    scopes=['https://www.googleapis.com/auth/cloud-platform']
                )
                credentials.refresh(Request())
                access_token = credentials.token

                if not access_token:
                    raise ValueError("❌ Failed to get access token from service account")

                logger.info(f"✅ RAG: Access token from service account (length: {len(access_token)})")

            # Get RAG corpus configuration
            vertex_project = os.getenv('VERTEX_PROJECT', PROJECT_ID)
            vertex_location = os.getenv('VERTEX_LOCATION')
            rag_corpus_id = os.getenv('RAG_CORPUS_ID')
            gcs_bucket = os.getenv('GCS_BUCKET')

            if not all([vertex_project, vertex_location, rag_corpus_id, gcs_bucket]):
                raise ValueError("❌ VERTEX_PROJECT, VERTEX_LOCATION, RAG_CORPUS_ID, and GCS_BUCKET must all be configured")

            # Create temporary file with chunks content
            temp_file_path = None
            try:
                # Combine chunks into single document
                combined_content = "\n\n".join([chunk['content'] for chunk in chunks])

                # Create temp file
                with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8') as tf:
                    tf.write(combined_content)
                    temp_file_path = tf.name

                # Upload to GCS first (required by RAG Engine Import API) - reuse existing client
                bucket = self.storage_client.bucket(gcs_bucket)

                # Create blob name from metadata
                file_name = metadata.get('file_name', 'unknown')
                blob_name = f"rag-uploads/{file_name}.txt"
                blob = bucket.blob(blob_name)
                blob.upload_from_filename(temp_file_path)

                gcs_uri = f"gs://{gcs_bucket}/{blob_name}"
                logger.info(f"📤 Uploaded to GCS: {gcs_uri}")

                # Import to RAG Engine using Import API
                url = f"https://{vertex_location}-aiplatform.googleapis.com/v1beta1/projects/{vertex_project}/locations/{vertex_location}/ragCorpora/{rag_corpus_id}/ragFiles:import"

                payload = {
                    "import_rag_files_config": {
                        "gcs_source": {
                            "uris": [gcs_uri]
                        },
                        "rag_file_chunking_config": {
                            "chunk_size": int(os.getenv('RAG_CHUNK_SIZE', 1000)),
                            "chunk_overlap": int(os.getenv('RAG_CHUNK_OVERLAP', 200))
                        },
                        "max_embedding_requests_per_min": int(os.getenv('MAX_EMBEDDING_QPM', 1000))
                    }
                }

                # Use Bearer token with ACCESS token from ADC
                headers = {
                    'Authorization': f'Bearer {access_token}',
                    'Content-Type': 'application/json'
                }

                logger.info(f"🔑 RAG: Making authenticated request to Vertex AI RAG Engine")

                # SYNCHRONOUS RAG Import with operation polling
                # CRITICAL: Wait for vectorization to complete before continuing workflow
                try:
                    response = requests.post(url, json=payload, headers=headers, timeout=60)

                    if response.status_code == 200:
                        operation = response.json()
                        operation_name = operation.get('name', 'unknown')
                        logger.info(f"✅ RAG import started: {operation_name}")

                        # CRITICAL: Poll for completion (max 20 minutes for comprehensive vectorization)
                        success = self._poll_rag_operation(operation_name, access_token, max_wait_seconds=1200)

                        if not success:
                            logger.warning(f"⚠️ RAG vectorization did not complete - vectors may not be available for analysis")

                    elif response.status_code == 400:
                        error_data = response.json()
                        error_msg = error_data.get('error', {}).get('message', '')
                        if 'other operations running' in error_msg.lower():
                            logger.warning(f"⚠️ RAG corpus busy - document queued for later processing")
                        else:
                            logger.warning(f"⚠️ RAG import issue: {error_msg[:200]} - continuing without RAG")
                    else:
                        logger.warning(f"⚠️ RAG returned {response.status_code} - continuing without RAG")
                except Exception as e:
                    logger.warning(f"⚠️ RAG import failed: {str(e)[:200]} - continuing without RAG")

                # Track chunk IDs
                for chunk in chunks:
                    vector_ids.append(chunk['id'])

                return vector_ids

            finally:
                # Cleanup temp file
                if temp_file_path and os.path.exists(temp_file_path):
                    os.unlink(temp_file_path)

        except Exception as e:
            logger.error(f"❌ Error storing in Vertex AI RAG Engine: {e}")
            raise ValueError(f"Failed to store in RAG Engine: {e}")

    def _publish_completion_event(self, metadata: Dict[str, Any], vector_ids: List[str]):
        """Publish processing completion event"""

        event_data = {
            'event_type': 'sec_filing_processed',
            'metadata': metadata,
            'vectors_created': len(vector_ids),
            'processing_timestamp': datetime.now().isoformat()
        }

        try:
            future = self.publisher.publish(
                self.topic_path,
                json.dumps(event_data).encode('utf-8'),
                event_type='sec_filing_processed'
            )
            logger.info(f"Published completion event: {future.result()}")
        except Exception as e:
            logger.error(f"Error publishing completion event: {e}")

    def fetch_company_data(self, symbol: str, data_sources: List[str] = None) -> Dict[str, Any]:
        """Fetch comprehensive company data from multiple sources"""

        if data_sources is None:
            data_sources = ['sec_filings', 'analyst_reports', 'news', 'social_media']

        logger.info(f"Fetching comprehensive data for {symbol} from sources: {data_sources}")

        results = {
            'symbol': symbol,
            'data_sources': data_sources,
            'fetched_data': {},
            'processing_timestamp': datetime.now().isoformat()
        }

        try:
            # Get company info first
            company_info = self._get_company_info(symbol)
            results['company_info'] = company_info

            # Store for vectorization (instance variable)
            self.last_company_info = company_info

            # Fetch data from each source
            for source in data_sources:
                if source == 'sec_filings':
                    results['fetched_data']['sec_filings'] = self._fetch_sec_filings(symbol, company_info)
                elif source == 'analyst_reports':
                    results['fetched_data']['analyst_reports'] = self._fetch_analyst_reports(symbol)
                elif source == 'news':
                    results['fetched_data']['news'] = self._fetch_news_data(symbol)
                elif source == 'social_media':
                    results['fetched_data']['social_media'] = self._fetch_social_media_data(symbol)

            # Process and vectorize all collected data
            vectorization_results = self._process_and_vectorize_data(symbol, results['fetched_data'])

            results['vectorization_results'] = vectorization_results
            results['status'] = 'success'

        except Exception as e:
            logger.error(f"Error fetching comprehensive data for {symbol}: {e}")
            results['status'] = 'error'
            results['error'] = str(e)

        return results

    def _get_company_info(self, symbol: str) -> Dict[str, Any]:
        """Get comprehensive company information from multiple sources"""
        
        company_info = {'symbol': symbol}
        
        try:
            # SOURCE 1: FMP API for company profile and financials
            fmp_api_key = os.getenv('FMP_API_KEY')
            if not fmp_api_key:
                logger.error(f"❌ FMP_API_KEY not configured - cannot fetch FMP data for {symbol}")
            else:
                logger.info(f"📥 FMP: Fetching company profile for {symbol}...")
                try:
                    # Get company profile
                    url = f"https://financialmodelingprep.com/api/v3/profile/{symbol}"
                    params = {'apikey': fmp_api_key}
                    
                    response = requests.get(url, params=params, timeout=30)
                    if response.status_code == 200:
                        data = response.json()
                        if data and isinstance(data, list) and len(data) > 0:
                            fmp_profile = data[0]
                            company_info.update(fmp_profile)
                            logger.info(f"✅ FMP: Retrieved company profile for {symbol}")

                            # Debug: Log all available fields
                            logger.info(f"   - Available FMP fields: {list(fmp_profile.keys())}")

                            # Log key metrics
                            logger.info(f"   - Market Cap: ${fmp_profile.get('mktCap', 0)/1e9:.1f}B")
                            logger.info(f"   - Price: ${fmp_profile.get('price', 0):.2f}")
                            logger.info(f"   - Industry: {fmp_profile.get('industry', 'N/A')}")
                        else:
                            logger.warning(f"⚠️  FMP returned empty data for {symbol}")
                    else:
                        logger.error(f"❌ FMP API returned status {response.status_code} for {symbol}")
                except Exception as e:
                    logger.error(f"❌ Error fetching FMP profile for {symbol}: {e}")
                
                # Get financial statements from FMP
                logger.info(f"📥 FMP: Fetching income statements for {symbol}...")
                income_url = f"https://financialmodelingprep.com/api/v3/income-statement/{symbol}"
                params = {'apikey': fmp_api_key, 'limit': 5}
                response = requests.get(income_url, params=params, timeout=30)
                if response.status_code == 200:
                    income_data = response.json()
                    company_info['income_statements'] = income_data
                    logger.info(f"✅ FMP: Retrieved {len(income_data)} income statements")
                
                # Get balance sheets
                logger.info(f"📥 FMP: Fetching balance sheets for {symbol}...")
                balance_url = f"https://financialmodelingprep.com/api/v3/balance-sheet-statement/{symbol}"
                params = {'apikey': fmp_api_key, 'limit': 5}
                response = requests.get(balance_url, params=params, timeout=30)
                if response.status_code == 200:
                    balance_data = response.json()
                    company_info['balance_sheets'] = balance_data
                    logger.info(f"✅ FMP: Retrieved {len(balance_data)} balance sheets")
                
                # Get cash flow statements
                logger.info(f"📥 FMP: Fetching cash flow statements for {symbol}...")
                cf_url = f"https://financialmodelingprep.com/api/v3/cash-flow-statement/{symbol}"
                params = {'apikey': fmp_api_key, 'limit': 5}
                response = requests.get(cf_url, params=params, timeout=30)
                if response.status_code == 200:
                    cf_data = response.json()
                    company_info['cash_flow_statements'] = cf_data
                    logger.info(f"✅ FMP: Retrieved {len(cf_data)} cash flow statements")
                
                # Get enterprise values - for shares outstanding ONLY (mktCap is already in profile)
                logger.info(f"📥 FMP: Fetching enterprise values for {symbol}...")
                enterprise_url = f"https://financialmodelingprep.com/api/v3/enterprise-values/{symbol}"
                params = {'apikey': fmp_api_key, 'limit': 5}
                response = requests.get(enterprise_url, params=params, timeout=30)
                if response.status_code == 200:
                    enterprise_data = response.json()
                    company_info['enterprise_values'] = enterprise_data
                    logger.info(f"✅ FMP: Retrieved {len(enterprise_data)} periods of enterprise values")

                    # Extract shares outstanding ONLY (mktCap should come from profile for current value)
                    if enterprise_data and len(enterprise_data) > 0:
                        latest_enterprise = enterprise_data[0]  # Most recent
                        shares_outstanding = latest_enterprise.get('numberOfShares', 0)
                        logger.info(f"   - Shares outstanding from enterprise values: {shares_outstanding}")
                        if shares_outstanding and shares_outstanding > 0:
                            company_info['sharesOutstanding'] = shares_outstanding
                            logger.info(f"✅ Retrieved shares outstanding from FMP enterprise values: {shares_outstanding:,.0f}")
                
                # Get financial ratios
                logger.info(f"📥 FMP: Fetching financial ratios for {symbol}...")
                ratios_url = f"https://financialmodelingprep.com/api/v3/ratios/{symbol}"
                params = {'apikey': fmp_api_key, 'limit': 5}
                response = requests.get(ratios_url, params=params, timeout=30)
                if response.status_code == 200:
                    ratios_data = response.json()
                    company_info['financial_ratios'] = ratios_data
                    logger.info(f"✅ FMP: Retrieved {len(ratios_data)} periods of financial ratios")
            
            # Shares outstanding is now fetched from key-metrics endpoint above
            
            # SOURCE 2: yfinance for additional market data (optional, with robust rate limit handling)
            logger.info(f"📥 Fetching yfinance data for {symbol}...")
            yf_info = {}  # Initialize to avoid scope issues
            try:
                # Proactive rate limiting - wait if needed before making API call
                yf_rate_limiter.wait_if_needed()
                
                # Robust retry logic for yfinance rate limiting
                max_retries = 3
                retry_delay = 2  # seconds
                
                for attempt in range(max_retries):
                    try:
                        if attempt > 0:
                            wait_time = retry_delay * (2 ** attempt)  # Exponential backoff
                            logger.info(f"⏳ yfinance retry attempt {attempt + 1}/{max_retries}, waiting {wait_time}s...")
                            time.sleep(wait_time)
                        
                        ticker = yf.Ticker(symbol)
                        yf_info = ticker.info
                        logger.info(f"✅ Retrieved yfinance data for {symbol}")
                        break  # Success, exit retry loop
                        
                    except Exception as yf_error:
                        error_msg = str(yf_error)
                        if '429' in error_msg or 'Too Many Requests' in error_msg:
                            if attempt < max_retries - 1:
                                logger.warning(f"⚠️  yfinance rate limit hit for {symbol}, retrying...")
                                continue
                            else:
                                logger.warning(f"⚠️  yfinance rate limit exceeded after {max_retries} attempts for {symbol}")
                                raise
                        else:
                            # Non-rate-limit error, don't retry
                            raise
                
                # Use yfinance shares only if FMP calculation failed
                if not company_info.get('sharesOutstanding'):
                    shares_outstanding = yf_info.get('sharesOutstanding', 0)
                    if shares_outstanding and shares_outstanding > 0:
                        company_info['sharesOutstanding'] = shares_outstanding
                        logger.info(f"✅ Retrieved shares outstanding from yfinance: {shares_outstanding:,.0f}")
                
                # Additional yfinance data (only if yfinance succeeded)
                company_info['yfinance_data'] = {
                    'market_cap': yf_info.get('marketCap'),
                    'current_price': yf_info.get('currentPrice', yf_info.get('regularMarketPrice')),
                    'beta': yf_info.get('beta'),
                    'forward_pe': yf_info.get('forwardPE'),
                    'trailing_pe': yf_info.get('trailingPE'),
                    'dividend_yield': yf_info.get('dividendYield'),
                    'peg_ratio': yf_info.get('pegRatio'),
                    '52_week_high': yf_info.get('fiftyTwoWeekHigh'),
                    '52_week_low': yf_info.get('fiftyTwoWeekLow'),
                    'avg_volume': yf_info.get('averageVolume'),
                    'float_shares': yf_info.get('floatShares')
                }
            except Exception as e:
                logger.warning(f"⚠️  yfinance temporarily unavailable for {symbol}: {str(e)[:100]}")
                # Continue processing - we have FMP data
                company_info['yfinance_data'] = {}  # Empty dict if yfinance fails
            
            # Institutional holders (for DD)
            try:
                institutional = ticker.institutional_holders
                if institutional is not None and not institutional.empty:
                    company_info['institutional_holders'] = institutional.to_dict('records')
                    logger.info(f"Retrieved {len(institutional)} institutional holders")
            except:
                pass
            
            # Insider transactions (for DD)
            try:
                insider_purchases = ticker.insider_purchases
                if insider_purchases is not None and not insider_purchases.empty:
                    company_info['insider_transactions'] = insider_purchases.to_dict('records')
            except:
                pass
                
            # Get financials from yfinance as backup
            try:
                financials = ticker.financials
                if financials is not None and not financials.empty:
                    company_info['financials'] = financials.to_dict()
                    
                balance_sheet = ticker.balance_sheet
                if balance_sheet is not None and not balance_sheet.empty:
                    company_info['balance_sheet'] = balance_sheet.to_dict()
                    
                cashflow = ticker.cashflow
                if cashflow is not None and not cashflow.empty:
                    company_info['cash_flow'] = cashflow.to_dict()
            except:
                pass
            
            logger.info(f"Successfully integrated yfinance data for {symbol}")

        except Exception as e:
            logger.error(f"Error getting company info for {symbol}: {e}")
            company_info['error'] = str(e)

        # CRITICAL: Validate required fields before returning
        required_fields = {
            'companyName': 'Company name',
            'price': 'Current stock price',
            'mktCap': 'Market capitalization',
            'sharesOutstanding': 'Shares outstanding'
        }

        missing_fields = []
        zero_fields = []

        for field, description in required_fields.items():
            value = company_info.get(field)
            if not value:
                # Check if yfinance has the data as fallback
                if field == 'companyName':
                    yf_name = company_info.get('yfinance_data', {}).get('longName') or company_info.get('yfinance_data', {}).get('shortName')
                    if yf_name:
                        company_info['companyName'] = yf_name
                        logger.info(f"✅ Using yfinance company name: {yf_name}")
                    else:
                        missing_fields.append(f"{description} ({field})")
                elif field == 'price':
                    yf_price = company_info.get('yfinance_data', {}).get('current_price')
                    if yf_price and yf_price > 0:
                        company_info['price'] = yf_price
                        logger.info(f"✅ Using yfinance price: ${yf_price:.2f}")
                    else:
                        missing_fields.append(f"{description} ({field})")
                elif field == 'mktCap':
                    yf_mcap = company_info.get('yfinance_data', {}).get('market_cap')
                    if yf_mcap and yf_mcap > 0:
                        company_info['mktCap'] = yf_mcap
                        logger.info(f"✅ Using yfinance market cap: ${yf_mcap/1e9:.2f}B")
                    else:
                        missing_fields.append(f"{description} ({field})")
                else:
                    missing_fields.append(f"{description} ({field})")
            elif isinstance(value, (int, float)) and value == 0:
                # Try fallback for zero values
                if field == 'price':
                    yf_price = company_info.get('yfinance_data', {}).get('current_price')
                    if yf_price and yf_price > 0:
                        company_info['price'] = yf_price
                        logger.info(f"✅ Replaced zero price with yfinance: ${yf_price:.2f}")
                    else:
                        zero_fields.append(f"{description} ({field})")
                elif field == 'mktCap':
                    yf_mcap = company_info.get('yfinance_data', {}).get('market_cap')
                    if yf_mcap and yf_mcap > 0:
                        company_info['mktCap'] = yf_mcap
                        logger.info(f"✅ Replaced zero market cap with yfinance: ${yf_mcap/1e9:.2f}B")
                    else:
                        zero_fields.append(f"{description} ({field})")
                else:
                    zero_fields.append(f"{description} ({field})")

        if missing_fields:
            error_msg = f"Missing required data for {symbol}: {', '.join(missing_fields)}"
            logger.error(f"❌ {error_msg}")
            raise ValueError(error_msg)

        if zero_fields:
            error_msg = f"Zero values in critical fields for {symbol}: {', '.join(zero_fields)}"
            logger.error(f"❌ {error_msg}")
            raise ValueError(error_msg)

        logger.info(f"✅ Data validation passed for {symbol}:")
        logger.info(f"   - Company: {company_info.get('companyName')}")
        logger.info(f"   - Price: ${company_info.get('price'):.2f}")
        logger.info(f"   - Market Cap: ${company_info.get('mktCap')/1e9:.2f}B")
        logger.info(f"   - Shares Outstanding: {company_info.get('sharesOutstanding'):,.0f}")

        return company_info

    def _fetch_sec_filings(self, symbol: str, company_info: Dict[str, Any]) -> Dict[str, Any]:
        """Fetch SEC filings from EDGAR"""
        cik = company_info.get('cik', '')

        if not cik:
            # Try to get CIK from symbol search
            cik = self._get_cik_from_symbol(symbol)

        if not cik:
            return {'error': 'CIK not found', 'filings': []}

        logger.info(f"Fetching SEC filings for {symbol} (CIK: {cik})")

        try:
            # SEC EDGAR API for recent filings
            base_url = "https://www.sec.gov/Archives/edgar/data"
            filings_url = f"https://data.sec.gov/submissions/CIK{cik.zfill(10)}.json"

            headers = {
                'User-Agent': 'Company Research Tool (contact@example.com)',
                'Accept-Encoding': 'gzip, deflate',
                'Host': 'data.sec.gov'
            }

            response = requests.get(filings_url, headers=headers, timeout=30)
            response.raise_for_status()

            data = response.json()

            # Extract recent filings (last 2 years)
            filings = []
            recent_filings = data.get('filings', {}).get('recent', {})

            if recent_filings:
                form_types = recent_filings.get('form', [])
                filing_dates = recent_filings.get('filingDate', [])
                accession_numbers = recent_filings.get('accessionNumber', [])
                primary_docs = recent_filings.get('primaryDocument', [])

                # Get 10-K, 10-Q, 8-K filings from last 2 years
                for i, form_type in enumerate(form_types):
                    if form_type in ['10-K', '10-Q', '8-K'] and i < len(filing_dates):
                        filing_date = filing_dates[i]
                        if self._is_recent_filing(filing_date):
                            accession = accession_numbers[i].replace('-', '')

                            filing_info = {
                                'form_type': form_type,
                                'filing_date': filing_date,
                                'accession_number': accession,
                                'primary_document': primary_docs[i] if i < len(primary_docs) else '',
                                'url': f"{base_url}/{cik}/{accession}/index.json"
                            }

                            # Download filing content
                            filing_content = self._download_sec_filing(cik, accession, filing_info)
                            if filing_content:
                                filing_info['content'] = filing_content
                                filings.append(filing_info)

            return {
                'cik': cik,
                'filings_count': len(filings),
                'filings': filings
            }

        except Exception as e:
            logger.error(f"Error fetching SEC filings for {symbol}: {e}")
            return {'error': str(e), 'filings': []}

    def _get_cik_from_symbol(self, symbol: str) -> str:
        """Get CIK from stock symbol"""
        try:
            fmp_api_key = os.getenv('FMP_API_KEY')
            url = "https://financialmodelingprep.com/api/v3/search-cik"
            params = {'query': symbol, 'apikey': fmp_api_key}

            response = requests.get(url, params=params, timeout=30)
            response.raise_for_status()

            data = response.json()
            if data:
                return str(data[0].get('cik', ''))
        except Exception as e:
            logger.error(f"Error getting CIK for {symbol}: {e}")
        return ''

    def _is_recent_filing(self, filing_date: str) -> bool:
        """Check if filing is from last 2 years"""
        try:
            filing_dt = datetime.strptime(filing_date, '%Y-%m-%d')
            two_years_ago = datetime.now() - timedelta(days=730)
            return filing_dt >= two_years_ago
        except:
            return False

    def _parse_sec_filing_html(self, html_content: str, filing_type: str) -> Dict[str, Any]:
        """Parse SEC filing HTML to extract financial data and business information"""

        logger.info(f"🔍 Parsing {filing_type} filing HTML content")

        parsed_data = {
            'filing_type': filing_type,
            'financial_statements': {},
            'business_description': '',
            'mda_section': '',
            'risk_factors': '',
            'executive_compensation': '',
            'corporate_governance': '',
            'legal_proceedings': '',
            'footnotes': [],
            'exhibits': [],
            'extraction_timestamp': datetime.now().isoformat()
        }

        try:
            # Parse HTML with BeautifulSoup
            soup = BeautifulSoup(html_content, 'html.parser')

            # Remove script and style elements
            for script in soup(["script", "style"]):
                script.decompose()

            # Get text content
            text_content = soup.get_text()

            # Extract different sections based on filing type
            if filing_type == '10-K':
                parsed_data.update(self._parse_10k_filing(text_content))
            elif filing_type == '10-Q':
                parsed_data.update(self._parse_10q_filing(text_content))
            elif filing_type == '8-K':
                parsed_data.update(self._parse_8k_filing(text_content))

            # Extract financial statements from tables
            financial_tables = self._extract_financial_tables(soup)
            if financial_tables:
                parsed_data['financial_statements'] = financial_tables

            # Extract key metrics and ratios if available in tables
            key_metrics = self._extract_key_metrics(soup)
            if key_metrics:
                parsed_data['key_metrics'] = key_metrics

            logger.info(f"✅ Successfully parsed {filing_type} filing with {len(parsed_data.get('financial_statements', {}))} financial statements")

        except Exception as e:
            logger.error(f"❌ Error parsing SEC filing HTML: {e}")
            parsed_data['parsing_error'] = str(e)

        return parsed_data

    def _parse_10k_filing(self, text_content: str) -> Dict[str, Any]:
        """Parse 10-K filing content"""

        sections = {}

        # Extract Business Description (Item 1)
        business_match = re.search(r'ITEM\s+1\.?\s+BUSINESS(.*?)ITEM\s+1A', text_content, re.IGNORECASE | re.DOTALL)
        if business_match:
            sections['business_description'] = business_match.group(1).strip()[:50000]  # Limit size

        # Extract Risk Factors (Item 1A)
        risk_match = re.search(r'ITEM\s+1A\.?\s+RISK\s+FACTORS(.*?)ITEM\s+1B', text_content, re.IGNORECASE | re.DOTALL)
        if risk_match:
            sections['risk_factors'] = risk_match.group(1).strip()[:30000]

        # Extract MD&A (Item 7)
        mda_match = re.search(r'ITEM\s+7\.?\s+MANAGEMENT.?S\s+DISCUSSION\s+AND\s+ANALYSIS(.*?)ITEM\s+7A', text_content, re.IGNORECASE | re.DOTALL)
        if mda_match:
            sections['mda_section'] = mda_match.group(1).strip()[:50000]

        # Extract Executive Compensation (Item 11 - often in proxy statement, but check 10-K)
        comp_match = re.search(r'ITEM\s+11\.?\s+EXECUTIVE\s+COMPENSATION(.*?)ITEM\s+12', text_content, re.IGNORECASE | re.DOTALL)
        if comp_match:
            sections['executive_compensation'] = comp_match.group(1).strip()[:20000]

        # Extract Legal Proceedings (Item 3)
        legal_match = re.search(r'ITEM\s+3\.?\s+LEGAL\s+PROCEEDINGS(.*?)ITEM\s+4', text_content, re.IGNORECASE | re.DOTALL)
        if legal_match:
            sections['legal_proceedings'] = legal_match.group(1).strip()[:20000]

        return sections

    def _parse_10q_filing(self, text_content: str) -> Dict[str, Any]:
        """Parse 10-Q filing content"""

        sections = {}

        # Extract MD&A (Item 2)
        mda_match = re.search(r'ITEM\s+2\.?\s+MANAGEMENT.?S\s+DISCUSSION\s+AND\s+ANALYSIS(.*?)ITEM\s+3', text_content, re.IGNORECASE | re.DOTALL)
        if mda_match:
            sections['mda_section'] = mda_match.group(1).strip()[:50000]

        # Extract Controls and Procedures (Item 4)
        controls_match = re.search(r'ITEM\s+4\.?\s+CONTROLS\s+AND\s+PROCEDURES(.*?)ITEM\s+5', text_content, re.IGNORECASE | re.DOTALL)
        if controls_match:
            sections['controls_and_procedures'] = controls_match.group(1).strip()[:20000]

        # Extract Legal Proceedings (Item 1)
        legal_match = re.search(r'ITEM\s+1\.?\s+LEGAL\s+PROCEEDINGS(.*?)ITEM\s+1A', text_content, re.IGNORECASE | re.DOTALL)
        if legal_match:
            sections['legal_proceedings'] = legal_match.group(1).strip()[:20000]

        # Extract Risk Factors (Item 1A)
        risk_match = re.search(r'ITEM\s+1A\.?\s+RISK\s+FACTORS(.*?)ITEM\s+2', text_content, re.IGNORECASE | re.DOTALL)
        if risk_match:
            sections['risk_factors'] = risk_match.group(1).strip()[:30000]

        return sections

    def _parse_8k_filing(self, text_content: str) -> Dict[str, Any]:
        """Parse 8-K filing content"""

        sections = {}

        # 8-K filings are event-driven, extract key items
        items = re.findall(r'ITEM\s+(\d+\.\d+).*?(?=ITEM\s+\d+\.\d+|$)', text_content, re.IGNORECASE | re.DOTALL)

        for item_match in items:
            item_num = item_match[0]
            item_content = item_match[1].strip()[:20000]  # Limit size

            if '2.02' in item_num:
                sections['results_of_operations'] = item_content
            elif '5.02' in item_num:
                sections['departure_of_directors'] = item_content
            elif '8.01' in item_num:
                sections['other_events'] = item_content
            elif '9.01' in item_num:
                sections['financial_statements'] = item_content

        return sections

    def _extract_financial_tables(self, soup) -> Dict[str, Any]:
        """Extract financial data from HTML tables in SEC filings using XBRL-aware parsing"""

        financial_data = {}

        try:
            # Find all tables
            tables = soup.find_all('table')

            logger.info(f"Found {len(tables)} tables in SEC filing")

            # SEC filings use XBRL - look for XBRL tags first
            xbrl_elements = soup.find_all(attrs={'name': True})
            logger.info(f"Found {len(xbrl_elements)} elements with 'name' attribute")

            # Group XBRL elements by financial statement type
            xbrl_by_statement = {
                'balance_sheet': [],
                'income_statement': [],
                'cash_flow_statement': []
            }

            xbrl_count = 0
            for elem in xbrl_elements:
                name = elem.get('name', '').lower()
                if 'us-gaap' in name:
                    xbrl_count += 1
                    if any(keyword in name for keyword in ['balancesheet', 'assets', 'liabilities', 'equity']):
                        xbrl_by_statement['balance_sheet'].append(elem)
                    elif any(keyword in name for keyword in ['incomestatement', 'revenue', 'income', 'expenses']):
                        xbrl_by_statement['income_statement'].append(elem)
                    elif any(keyword in name for keyword in ['cashflow', 'cashflows']):
                        xbrl_by_statement['cash_flow_statement'].append(elem)

            logger.info(f"Found {xbrl_count} XBRL us-gaap elements")
            logger.info(f"XBRL breakdown - BS: {len(xbrl_by_statement['balance_sheet'])}, IS: {len(xbrl_by_statement['income_statement'])}, CF: {len(xbrl_by_statement['cash_flow_statement'])}")

            # Extract data from XBRL elements
            for statement_type, elements in xbrl_by_statement.items():
                if elements:
                    logger.info(f"Processing {len(elements)} XBRL elements for {statement_type}")
                    table_data = self._extract_xbrl_financial_data(elements, statement_type)
                    if table_data and table_data.get('data'):
                        financial_data[statement_type] = table_data
                        logger.info(f"✅ Extracted {statement_type} from XBRL data with {len(table_data['data'])} rows")
                    else:
                        logger.warning(f"❌ XBRL extraction for {statement_type} returned no data")

            # Fallback: Traditional table parsing if XBRL extraction failed
            if not financial_data:
                logger.info("XBRL extraction failed or returned no data, falling back to traditional table parsing")

                for i, table in enumerate(tables):
                    table_type = None
                    confidence_score = 0

                    # Strategy 1: Check for XBRL tags in table
                    xbrl_tags = table.find_all(attrs={'name': True})
                    for tag in xbrl_tags:
                        tag_name = tag.get('name', '').lower()
                        if 'us-gaap' in tag_name:
                            if any(keyword in tag_name for keyword in ['balancesheet', 'statementoffinancialposition']):
                                table_type = 'balance_sheet'
                                confidence_score = 95
                                break
                            elif any(keyword in tag_name for keyword in ['incomestatement', 'statementofoperations', 'statementofearnings']):
                                table_type = 'income_statement'
                                confidence_score = 95
                                break
                            elif any(keyword in tag_name for keyword in ['cashflow', 'statementofcashflows']):
                                table_type = 'cash_flow_statement'
                                confidence_score = 95
                                break

                    # Strategy 2: Enhanced table caption detection
                    if not table_type:
                        caption = table.find('caption')
                        if caption:
                            caption_text = caption.get_text().lower()
                            if any(term in caption_text for term in ['balance sheet', 'statement of financial position', 'consolidated balance sheets']):
                                table_type = 'balance_sheet'
                                confidence_score = 90
                            elif any(term in caption_text for term in ['income statement', 'statement of operations', 'statement of earnings', 'consolidated statements of income']):
                                table_type = 'income_statement'
                                confidence_score = 90
                            elif any(term in caption_text for term in ['cash flow', 'statement of cash flows', 'consolidated statements of cash flows']):
                                table_type = 'cash_flow_statement'
                                confidence_score = 90

                    # Strategy 3: Look for preceding headers and context (expanded search)
                    if not table_type:
                        prev_text = ""
                        # Look much further back for context in SEC filings
                        for prev_elem in table.find_previous_siblings(['p', 'div', 'span', 'h1', 'h2', 'h3', 'h4', 'h5', 'strong', 'b'], limit=10):
                            prev_text += prev_elem.get_text().strip() + " "
                            if len(prev_text) > 1000:  # Allow longer search
                                break

                        prev_lower = prev_text.lower()
                        if any(term in prev_lower for term in ['balance sheet', 'statement of financial position', 'consolidated balance sheets']):
                            table_type = 'balance_sheet'
                            confidence_score = 85
                        elif any(term in prev_lower for term in ['income statement', 'statement of operations', 'statement of earnings', 'consolidated statements of income']):
                            table_type = 'income_statement'
                            confidence_score = 85
                        elif any(term in prev_lower for term in ['cash flow', 'statement of cash flows', 'consolidated statements of cash flows']):
                            table_type = 'cash_flow_statement'
                            confidence_score = 85

                    # Strategy 4: Enhanced content analysis with SEC-specific keywords
                    if not table_type:
                        table_text = table.get_text().lower()

                        # SEC-specific financial keywords
                        bs_keywords = ['total assets', 'total liabilities', 'stockholders equity', 'retained earnings', 'current assets', 'current liabilities', 'total equity']
                        is_keywords = ['revenue', 'net income', 'operating income', 'gross profit', 'cost of revenue', 'net sales', 'total operating expenses']
                        cf_keywords = ['cash flows', 'operating activities', 'investing activities', 'financing activities', 'net cash', 'cash and cash equivalents']

                        bs_score = sum(1 for keyword in bs_keywords if keyword in table_text)
                        is_score = sum(1 for keyword in is_keywords if keyword in table_text)
                        cf_score = sum(1 for keyword in cf_keywords if keyword in table_text)

                        max_score = max(bs_score, is_score, cf_score)
                        if max_score >= 1:  # Lower threshold for SEC filings
                            if bs_score == max_score:
                                table_type = 'balance_sheet'
                                confidence_score = 75
                            elif is_score == max_score:
                                table_type = 'income_statement'
                                confidence_score = 75
                            elif cf_score == max_score:
                                table_type = 'cash_flow_statement'
                                confidence_score = 75

                    # Strategy 5: Monetary value detection with SEC formatting
                    if not table_type:
                        cells = table.find_all(['td', 'th'])
                        monetary_cells = 0
                        total_cells = len(cells)

                        for cell in cells:
                            cell_text = cell.get_text().strip()
                            # SEC monetary patterns: $123,456 or (123,456) or 123,456 or $ (123,456)
                            if re.search(r'[\$]?\(?\d{1,3}(?:,\d{3})*(?:\.\d+)?\)?|\(\d{1,3}(?:,\d{3})*(?:\.\d+)?\)', cell_text):
                                monetary_cells += 1

                        # SEC tables often have 20-40% monetary cells
                        if total_cells > 0 and (monetary_cells / total_cells) > 0.2:
                            table_text = table.get_text().lower()
                            if any(keyword in table_text for keyword in ['assets', 'liabilities', 'equity', 'stockholders']):
                                table_type = 'balance_sheet'
                                confidence_score = 65
                            elif any(keyword in table_text for keyword in ['revenue', 'income', 'expenses', 'earnings']):
                                table_type = 'income_statement'
                                confidence_score = 65
                            elif any(keyword in table_text for keyword in ['cash', 'flow', 'activities', 'operating', 'investing', 'financing']):
                                table_type = 'cash_flow_statement'
                                confidence_score = 65

                    # Parse table if we identified a type with sufficient confidence
                    if table_type and confidence_score >= 60:
                        parsed_table = self._parse_financial_table(table)
                        if parsed_table and parsed_table.get('data') and len(parsed_table['data']) > 1:
                            if table_type not in financial_data:  # Don't overwrite XBRL data
                                financial_data[table_type] = parsed_table
                                logger.info(f"✅ Extracted {table_type} (confidence: {confidence_score}%) with {len(parsed_table.get('data', []))} rows")
                            elif confidence_score > 80:  # Overwrite only if much more confident
                                financial_data[table_type] = parsed_table
                                logger.info(f"✅ Updated {table_type} (confidence: {confidence_score}%) with {len(parsed_table.get('data', []))} rows")

        except Exception as e:
            logger.warning(f"Error extracting financial tables: {e}")

        logger.info(f"Total financial statements extracted: {len(financial_data)}")
        return financial_data

    def _parse_financial_table(self, table) -> Dict[str, Any]:
        """Parse a financial statement table"""

        table_data = {}

        try:
            rows = table.find_all('tr')

            # Extract headers (usually first 1-2 rows)
            headers = []
            for row in rows[:2]:  # Check first 2 rows for headers
                header_cells = row.find_all(['th', 'td'])
                if header_cells:
                    header_row = [cell.get_text().strip() for cell in header_cells]
                    headers.append(header_row)

            # Extract data rows
            data_rows = []
            for row in rows[2:]:  # Skip header rows
                cells = row.find_all(['td', 'th'])
                if cells and len(cells) > 1:  # Must have at least account name + 1 value
                    row_data = [cell.get_text().strip() for cell in cells]
                    data_rows.append(row_data)

            table_data = {
                'headers': headers,
                'data': data_rows,
                'rows_count': len(data_rows),
                'columns_count': len(headers[0]) if headers else 0
            }

        except Exception as e:
            logger.warning(f"Error parsing financial table: {e}")

        return table_data

    def _extract_xbrl_financial_data(self, xbrl_elements: List, statement_type: str) -> Dict[str, Any]:
        """Extract financial data from XBRL elements in SEC filings"""

        logger.info(f"🔍 Extracting XBRL data for {statement_type} with {len(xbrl_elements)} elements")

        table_data = {
            'headers': [['Account', 'Value']],
            'data': [],
            'rows_count': 0,
            'columns_count': 2
        }

        try:
            # Group XBRL elements by context (period)
            contexts = {}
            for elem in xbrl_elements:
                context_ref = elem.get('contextref', '')
                name = elem.get('name', '').lower()
                unit_ref = elem.get('unitref', '')
                content = elem.get_text().strip()

                # Parse the context to get period information
                if context_ref:
                    if context_ref not in contexts:
                        contexts[context_ref] = {}

                    # Extract financial value
                    try:
                        # Remove commas and convert to float
                        value = float(content.replace(',', '').replace('$', ''))
                        contexts[context_ref][name] = value
                    except (ValueError, AttributeError):
                        # If not numeric, store as string
                        contexts[context_ref][name] = content

            # Convert contexts to table format
            if contexts:
                # Get all unique account names
                all_accounts = set()
                for context_data in contexts.values():
                    all_accounts.update(context_data.keys())

                # Create rows for each account
                for account in sorted(all_accounts):
                    row = [account]  # Account name

                    # Add values for each context (period)
                    for context_ref in sorted(contexts.keys()):
                        context_data = contexts[context_ref]
                        value = context_data.get(account, '')
                        if isinstance(value, float):
                            # Format large numbers
                            if abs(value) >= 1e9:
                                row.append(f"${value/1e9:.2f}B")
                            elif abs(value) >= 1e6:
                                row.append(f"${value/1e6:.1f}M")
                            elif abs(value) >= 1e3:
                                row.append(f"${value/1e3:.0f}K")
                            else:
                                row.append(f"${value:.2f}")
                        else:
                            row.append(str(value))

                    table_data['data'].append(row)

                table_data['rows_count'] = len(table_data['data'])
                table_data['columns_count'] = len(table_data['data'][0]) if table_data['data'] else 2

                logger.info(f"✅ Extracted {table_data['rows_count']} XBRL accounts for {statement_type}")

        except Exception as e:
            logger.warning(f"Error extracting XBRL data: {e}")

        return table_data

    def _extract_key_metrics(self, soup) -> Dict[str, Any]:
        """Extract key financial metrics and ratios from the filing"""

        metrics = {}

        try:
            # Look for common financial metrics in text
            text_content = soup.get_text()

            # Revenue patterns
            revenue_matches = re.findall(r'(?:total\s+)?revenue[^\d]*\$?([\d,]+(?:\.\d+)?)\s*(?:million|billion|m|b)', text_content, re.IGNORECASE)
            if revenue_matches:
                metrics['revenue_mentions'] = revenue_matches[:5]  # Limit to 5 mentions

            # Net income patterns
            net_income_matches = re.findall(r'net\s+(?:income|loss|earnings)[^\d]*\$?([\d,]+(?:\.\d+)?)\s*(?:million|billion|m|b)', text_content, re.IGNORECASE)
            if net_income_matches:
                metrics['net_income_mentions'] = net_income_matches[:5]

            # EPS patterns
            eps_matches = re.findall(r'(?:earnings|eps)[^\d]*\$?([\d.]+)\s*(?:per\s+share)?', text_content, re.IGNORECASE)
            if eps_matches:
                metrics['eps_mentions'] = eps_matches[:5]

            # Market cap or valuation mentions
            market_cap_matches = re.findall(r'market\s+cap(?:italization)?[^\d]*\$?([\d,]+(?:\.\d+)?)\s*(?:million|billion|m|b)', text_content, re.IGNORECASE)
            if market_cap_matches:
                metrics['market_cap_mentions'] = market_cap_matches[:3]

        except Exception as e:
            logger.warning(f"Error extracting key metrics: {e}")

        return metrics

    def _download_sec_filing(self, cik: str, accession: str, filing_info: Dict[str, Any]) -> Dict[str, Any]:
        """Download and parse SEC filing content to extract financial data and business information"""
        try:
            base_url = "https://www.sec.gov/Archives/edgar/data"
            filing_url = f"{base_url}/{cik}/{accession}/{filing_info.get('primary_document', '')}"

            headers = {
                'User-Agent': 'Company Research Tool (contact@example.com)',
                'Accept-Encoding': 'gzip, deflate',
                'Host': 'www.sec.gov'
            }

            response = requests.get(filing_url, headers=headers, timeout=60)
            response.raise_for_status()

            html_content = response.text

            # Parse the HTML content to extract structured financial data
            parsed_data = self._parse_sec_filing_html(html_content, filing_info.get('form_type', ''))

            return {
                'raw_html': html_content,
                'parsed_data': parsed_data,
                'filing_type': filing_info.get('form_type', ''),
                'accession_number': accession
            }

        except Exception as e:
            logger.error(f"Error downloading SEC filing {accession}: {e}")
            return {
                'error': str(e),
                'filing_type': filing_info.get('form_type', ''),
                'accession_number': accession
            }

    def extract_sec_qualitative_data(self, filing_content: str, filing_type: str) -> Dict[str, Any]:
        """
        Extract qualitative sections from SEC filings
        Extracts: MD&A, Risk Factors, Footnotes, Management Projections, Business Description
        """
        
        logger.info(f"Extracting qualitative data from {filing_type}")
        
        qualitative_data = {
            'mda': '',  # Management Discussion & Analysis
            'risk_factors': '',
            'business_description': '',
            'footnotes': [],
            'management_projections': [],
            'forward_looking_statements': []
        }
        
        try:
            # Parse HTML if needed
            if '<html' in filing_content.lower():
                soup = BeautifulSoup(filing_content, 'html.parser')
                text_content = soup.get_text()
            else:
                text_content = filing_content
            
            # Extract MD&A (Item 7 in 10-K, Item 2 in 10-Q)
            mda_section = self._extract_mda_section(text_content, filing_type)
            if mda_section:
                qualitative_data['mda'] = mda_section
                logger.info(f"Extracted MD&A section: {len(mda_section)} characters")
            
            # Extract Risk Factors (Item 1A)
            risk_factors = self._extract_risk_factors(text_content)
            if risk_factors:
                qualitative_data['risk_factors'] = risk_factors
                logger.info(f"Extracted Risk Factors: {len(risk_factors)} characters")
            
            # Extract Business Description (Item 1)
            business_desc = self._extract_business_description(text_content)
            if business_desc:
                qualitative_data['business_description'] = business_desc
                logger.info(f"Extracted Business Description: {len(business_desc)} characters")
            
            # Extract Forward-Looking Statements
            forward_looking = self._extract_forward_looking_statements(text_content)
            if forward_looking:
                qualitative_data['forward_looking_statements'] = forward_looking
                logger.info(f"Found {len(forward_looking)} forward-looking statements")
            
            # Extract Financial Footnotes
            footnotes = self._extract_financial_footnotes(text_content)
            if footnotes:
                qualitative_data['footnotes'] = footnotes
                logger.info(f"Extracted {len(footnotes)} financial footnotes")
            
            # Extract Management Projections/Guidance
            projections = self._extract_management_projections(text_content)
            if projections:
                qualitative_data['management_projections'] = projections
                logger.info(f"Found {len(projections)} management projections/guidance")
                
        except Exception as e:
            logger.error(f"Error extracting qualitative data: {e}")
            qualitative_data['extraction_error'] = str(e)
        
        return qualitative_data
    
    def _extract_mda_section(self, content: str, filing_type: str) -> str:
        """Extract Management Discussion & Analysis section"""
        
        if filing_type == '10-K':
            # Look for Item 7
            patterns = [
                r'ITEM\s+7\.?\s+MANAGEMENT.?S\s+DISCUSSION\s+AND\s+ANALYSIS(.*?)ITEM\s+8',
                r'Item\s+7\.?\s+Management.?s\s+Discussion\s+and\s+Analysis(.*?)Item\s+8'
            ]
        elif filing_type == '10-Q':
            # Look for Item 2
            patterns = [
                r'ITEM\s+2\.?\s+MANAGEMENT.?S\s+DISCUSSION\s+AND\s+ANALYSIS(.*?)ITEM\s+3',
                r'Item\s+2\.?\s+Management.?s\s+Discussion\s+and\s+Analysis(.*?)Item\s+3'
            ]
        else:
            return ''
        
        for pattern in patterns:
            match = re.search(pattern, content, re.IGNORECASE | re.DOTALL)
            if match:
                mda = match.group(1).strip()
                return mda[:50000]  # Limit to 50k characters
        
        return ''
    
    def _extract_risk_factors(self, content: str) -> str:
        """Extract Risk Factors section (Item 1A)"""
        
        patterns = [
            r'ITEM\s+1A\.?\s+RISK\s+FACTORS(.*?)ITEM\s+1B',
            r'Item\s+1A\.?\s+Risk\s+Factors(.*?)Item\s+1B',
            r'ITEM\s+1A\.?\s+RISK\s+FACTORS(.*?)ITEM\s+2'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, content, re.IGNORECASE | re.DOTALL)
            if match:
                risks = match.group(1).strip()
                return risks[:30000]  # Limit to 30k characters
        
        return ''
    
    def _extract_business_description(self, content: str) -> str:
        """Extract Business Description section (Item 1)"""
        
        patterns = [
            r'ITEM\s+1\.?\s+BUSINESS(.*?)ITEM\s+1A',
            r'Item\s+1\.?\s+Business(.*?)Item\s+1A'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, content, re.IGNORECASE | re.DOTALL)
            if match:
                business = match.group(1).strip()
                return business[:30000]  # Limit to 30k characters
        
        return ''
    
    def _extract_forward_looking_statements(self, content: str) -> List[str]:
        """Extract forward-looking statements and projections"""
        
        forward_looking = []
        
        # Keywords that indicate forward-looking statements
        keywords = [
            'expect', 'anticipate', 'intend', 'plan', 'believe',
            'estimate', 'project', 'forecast', 'will', 'may',
            'should', 'could', 'would', 'likely', 'potential'
        ]
        
        # Find sentences with forward-looking keywords
        sentences = re.split(r'[.!?]+', content)
        
        for sentence in sentences:
            sentence = sentence.strip()
            if len(sentence) > 50 and len(sentence) < 500:  # Reasonable sentence length
                for keyword in keywords:
                    if re.search(r'\b' + keyword + r'\b', sentence, re.IGNORECASE):
                        # Check if contains numeric projections
                        if re.search(r'\d+%|\$\d+|\d+\s+(million|billion|thousand)', sentence, re.IGNORECASE):
                            forward_looking.append(sentence)
                            break
        
        # Deduplicate and limit
        return list(set(forward_looking))[:50]
    
    def _extract_financial_footnotes(self, content: str) -> List[Dict[str, str]]:
        """Extract financial statement footnotes"""
        
        footnotes = []
        
        # Look for footnote sections
        footnote_patterns = [
            r'NOTES?\s+TO\s+(?:CONSOLIDATED\s+)?FINANCIAL\s+STATEMENTS(.*?)(?:ITEM\s+\d+|SIGNATURES)',
            r'Notes?\s+to\s+(?:Consolidated\s+)?Financial\s+Statements(.*?)(?:Item\s+\d+|Signatures)'
        ]
        
        for pattern in footnote_patterns:
            match = re.search(pattern, content, re.IGNORECASE | re.DOTALL)
            if match:
                footnotes_text = match.group(1).strip()
                
                # Try to split into individual notes
                note_sections = re.split(r'NOTE\s+\d+[:\.]?|Note\s+\d+[:\.]?', footnotes_text)
                
                for i, note in enumerate(note_sections[1:21], 1):  # Limit to 20 notes
                    if note.strip():
                        footnotes.append({
                            'note_number': i,
                            'content': note.strip()[:5000]  # Limit each note
                        })
                
                break
        
        return footnotes
    
    def _extract_management_projections(self, content: str) -> List[Dict[str, Any]]:
        """Extract management guidance and projections"""
        
        projections = []
        
        # Look for guidance sections
        guidance_patterns = [
            r'(?:GUIDANCE|OUTLOOK|PROJECTIONS?|FORECAST)\s*[:\-]?\s*(.*?)(?:\n\n|\Z)',
            r'(?:we|management)\s+(?:expect|anticipate|project|estimate).*?(?:revenue|earnings|ebitda|margin).*?(?:\$[\d,.]+ (?:million|billion)|[\d.]+%)',
        ]
        
        for pattern in guidance_patterns:
            matches = re.finditer(pattern, content, re.IGNORECASE | re.DOTALL)
            for match in matches:
                projection_text = match.group(0).strip()
                if len(projection_text) > 20 and len(projection_text) < 1000:
                    # Extract numeric values
                    numbers = re.findall(r'\$?[\d,.]+ ?(?:million|billion|%|percent)', projection_text, re.IGNORECASE)
                    
                    if numbers:
                        projections.append({
                            'text': projection_text,
                            'values': numbers
                        })
        
        # Deduplicate and limit
        unique_projections = []
        seen_texts = set()
        for proj in projections:
            if proj['text'] not in seen_texts:
                unique_projections.append(proj)
                seen_texts.add(proj['text'])
                if len(unique_projections) >= 20:
                    break
        
        return unique_projections

    def _fetch_analyst_reports(self, symbol: str) -> Dict[str, Any]:
        """Fetch analyst reports and estimates"""
        try:
            fmp_api_key = os.getenv('FMP_API_KEY')

            # Get analyst estimates
            estimates_url = f"https://financialmodelingprep.com/api/v3/analyst-estimates/{symbol}"
            params = {'apikey': fmp_api_key, 'limit': 20}

            response = requests.get(estimates_url, params=params, timeout=30)
            response.raise_for_status()

            estimates = response.json()

            # Get analyst recommendations
            grades_url = f"https://financialmodelingprep.com/api/v3/grades/{symbol}"
            params = {'apikey': fmp_api_key, 'limit': 20}

            response = requests.get(grades_url, params=params, timeout=30)
            response.raise_for_status()

            grades = response.json()

            # Get price targets
            targets_url = f"https://financialmodelingprep.com/api/v3/price-target/{symbol}"
            params = {'apikey': fmp_api_key}

            response = requests.get(targets_url, params=params, timeout=30)
            response.raise_for_status()

            targets = response.json()

            return {
                'estimates': estimates,
                'grades': grades,
                'price_targets': targets,
                'total_reports': len(estimates) + len(grades)
            }

        except Exception as e:
            logger.error(f"Error fetching analyst reports for {symbol}: {e}")
            return {'error': str(e)}

    def _fetch_news_data(self, symbol: str) -> Dict[str, Any]:
        """Fetch news articles and press releases"""
        try:
            fmp_api_key = os.getenv('FMP_API_KEY')

            # Get stock news
            news_url = f"https://financialmodelingprep.com/api/v3/stock_news"
            params = {'tickers': symbol, 'limit': 50, 'apikey': fmp_api_key}

            response = requests.get(news_url, params=params, timeout=30)
            response.raise_for_status()

            news = response.json()

            # Get press releases
            press_url = f"https://financialmodelingprep.com/api/v3/press-releases/{symbol}"
            params = {'apikey': fmp_api_key, 'limit': 20}

            response = requests.get(press_url, params=params, timeout=30)
            response.raise_for_status()

            press_releases = response.json()

            return {
                'news_articles': news,
                'press_releases': press_releases,
                'total_items': len(news) + len(press_releases)
            }

        except Exception as e:
            logger.error(f"Error fetching news data for {symbol}: {e}")
            return {'error': str(e)}

    def _fetch_social_media_data(self, symbol: str) -> Dict[str, Any]:
        """Fetch social media sentiment and mentions"""
        # Note: This would typically integrate with social media APIs
        # For now, return placeholder structure

        return {
            'twitter_mentions': [],
            'reddit_posts': [],
            'sentiment_score': 0.0,
            'total_mentions': 0,
            'note': 'Social media integration requires API keys for Twitter, Reddit, etc.'
        }

    def _process_and_vectorize_data(self, symbol: str, fetched_data: Dict[str, Any]) -> Dict[str, Any]:
        """Process all fetched data and create vector embeddings"""

        logger.info(f"Processing and vectorizing data for {symbol}")

        vectorization_results = {
            'total_documents': 0,
            'chunks_created': 0,
            'vectors_stored': 0,
            'processing_details': {}
        }

        try:
            # Get CIK from SEC filings for unified corpus
            cik = fetched_data.get('sec_filings', {}).get('cik', symbol)
            logger.info(f"Using CIK for vectorization: {cik}")

            # Get company_info from results (passed from fetch_company_data)
            company_info = self.last_company_info  # Will be set in fetch_company_data

            # Process SEC filings
            if 'sec_filings' in fetched_data:
                sec_results = self._process_sec_filings_for_vectorization(symbol, fetched_data['sec_filings'])
                vectorization_results['processing_details']['sec_filings'] = sec_results
                vectorization_results['total_documents'] += sec_results.get('filings_processed', 0)
                vectorization_results['chunks_created'] += sec_results.get('chunks_created', 0)
                vectorization_results['vectors_stored'] += sec_results.get('vectors_stored', 0)

            # Process analyst reports - PASS CIK
            if 'analyst_reports' in fetched_data:
                analyst_results = self._process_analyst_data_for_vectorization(symbol, fetched_data['analyst_reports'], cik)
                vectorization_results['processing_details']['analyst_reports'] = analyst_results
                vectorization_results['total_documents'] += 1  # Treat as single document
                vectorization_results['chunks_created'] += analyst_results.get('chunks_created', 0)
                vectorization_results['vectors_stored'] += analyst_results.get('vectors_stored', 0)

            # Process news data - PASS CIK
            if 'news' in fetched_data:
                news_results = self._process_news_data_for_vectorization(symbol, fetched_data['news'], cik)
                vectorization_results['processing_details']['news'] = news_results
                vectorization_results['total_documents'] += news_results.get('articles_processed', 0)
                vectorization_results['chunks_created'] += news_results.get('chunks_created', 0)
                vectorization_results['vectors_stored'] += news_results.get('vectors_stored', 0)

            # NEW: Process FMP financial data (income, balance, cash flow, ratios)
            if company_info:
                fmp_results = self._process_fmp_financials_for_vectorization(symbol, company_info, cik)
                vectorization_results['processing_details']['fmp_financials'] = fmp_results
                vectorization_results['total_documents'] += 1  # Treat as single document
                vectorization_results['chunks_created'] += fmp_results.get('chunks_created', 0)
                vectorization_results['vectors_stored'] += fmp_results.get('vectors_stored', 0)

            # NEW: Process yfinance data (market data, institutional holders, etc.)
            if company_info and company_info.get('yfinance_data'):
                yf_results = self._process_yfinance_data_for_vectorization(symbol, company_info['yfinance_data'], cik)
                vectorization_results['processing_details']['yfinance'] = yf_results
                vectorization_results['total_documents'] += 1  # Treat as single document
                vectorization_results['chunks_created'] += yf_results.get('chunks_created', 0)
                vectorization_results['vectors_stored'] += yf_results.get('vectors_stored', 0)

            # NEW: Process social media data
            if 'social_media' in fetched_data:
                social_results = self._process_social_media_for_vectorization(symbol, fetched_data['social_media'], cik)
                vectorization_results['processing_details']['social_media'] = social_results
                vectorization_results['total_documents'] += social_results.get('items_processed', 0)
                vectorization_results['chunks_created'] += social_results.get('chunks_created', 0)
                vectorization_results['vectors_stored'] += social_results.get('vectors_stored', 0)

        except Exception as e:
            logger.error(f"Error in data processing and vectorization: {e}")
            vectorization_results['error'] = str(e)

        return vectorization_results

    def _process_fmp_financials_for_vectorization(self, symbol: str, company_info: Dict[str, Any], cik: str = None) -> Dict[str, Any]:
        """Process FMP financial statements and ratios for vectorization"""

        logger.info(f"📊 Processing FMP financial data for vectorization: {symbol}")

        content_parts = []

        # Process income statements (last 5 periods)
        if 'income_statements' in company_info and company_info['income_statements']:
            content_parts.append("=== INCOME STATEMENTS (Historical) ===\n")
            for stmt in company_info['income_statements'][:5]:
                content_parts.append(
                    f"\nPeriod: {stmt.get('date', 'Unknown')}\n"
                    f"Revenue: ${stmt.get('revenue', 0)/1e9:.2f}B\n"
                    f"Cost of Revenue: ${stmt.get('costOfRevenue', 0)/1e9:.2f}B\n"
                    f"Gross Profit: ${stmt.get('grossProfit', 0)/1e9:.2f}B\n"
                    f"Gross Profit Margin: {stmt.get('grossProfitRatio', 0)*100:.1f}%\n"
                    f"Operating Expenses: ${stmt.get('operatingExpenses', 0)/1e9:.2f}B\n"
                    f"Operating Income: ${stmt.get('operatingIncome', 0)/1e9:.2f}B\n"
                    f"Operating Margin: {stmt.get('operatingIncomeRatio', 0)*100:.1f}%\n"
                    f"EBITDA: ${stmt.get('ebitda', 0)/1e9:.2f}B\n"
                    f"EBITDA Margin: {stmt.get('ebitdaratio', 0)*100:.1f}%\n"
                    f"Net Income: ${stmt.get('netIncome', 0)/1e9:.2f}B\n"
                    f"Net Profit Margin: {stmt.get('netIncomeRatio', 0)*100:.1f}%\n"
                    f"EPS: ${stmt.get('eps', 0):.2f}\n"
                    f"EPS Diluted: ${stmt.get('epsdiluted', 0):.2f}\n"
                )

        # Process balance sheets (last 5 periods)
        if 'balance_sheets' in company_info and company_info['balance_sheets']:
            content_parts.append("\n=== BALANCE SHEETS (Historical) ===\n")
            for bs in company_info['balance_sheets'][:5]:
                content_parts.append(
                    f"\nPeriod: {bs.get('date', 'Unknown')}\n"
                    f"Total Assets: ${bs.get('totalAssets', 0)/1e9:.2f}B\n"
                    f"Current Assets: ${bs.get('totalCurrentAssets', 0)/1e9:.2f}B\n"
                    f"Cash and Equivalents: ${bs.get('cashAndCashEquivalents', 0)/1e9:.2f}B\n"
                    f"Accounts Receivable: ${bs.get('netReceivables', 0)/1e9:.2f}B\n"
                    f"Inventory: ${bs.get('inventory', 0)/1e9:.2f}B\n"
                    f"Total Liabilities: ${bs.get('totalLiabilities', 0)/1e9:.2f}B\n"
                    f"Current Liabilities: ${bs.get('totalCurrentLiabilities', 0)/1e9:.2f}B\n"
                    f"Total Debt: ${bs.get('totalDebt', 0)/1e9:.2f}B\n"
                    f"Long-term Debt: ${bs.get('longTermDebt', 0)/1e9:.2f}B\n"
                    f"Total Equity: ${bs.get('totalEquity', 0)/1e9:.2f}B\n"
                    f"Retained Earnings: ${bs.get('retainedEarnings', 0)/1e9:.2f}B\n"
                    f"Book Value per Share: ${bs.get('totalEquity', 0) / bs.get('commonStock', 1):.2f}\n"
                )

        # Process cash flow statements (last 5 periods)
        if 'cash_flow_statements' in company_info and company_info['cash_flow_statements']:
            content_parts.append("\n=== CASH FLOW STATEMENTS (Historical) ===\n")
            for cf in company_info['cash_flow_statements'][:5]:
                content_parts.append(
                    f"\nPeriod: {cf.get('date', 'Unknown')}\n"
                    f"Operating Cash Flow: ${cf.get('operatingCashFlow', 0)/1e9:.2f}B\n"
                    f"Capital Expenditures: ${cf.get('capitalExpenditure', 0)/1e9:.2f}B\n"
                    f"Free Cash Flow: ${cf.get('freeCashFlow', 0)/1e9:.2f}B\n"
                    f"Investing Cash Flow: ${cf.get('netCashUsedForInvestingActivites', 0)/1e9:.2f}B\n"
                    f"Financing Cash Flow: ${cf.get('netCashUsedProvidedByFinancingActivities', 0)/1e9:.2f}B\n"
                    f"Dividends Paid: ${cf.get('dividendsPaid', 0)/1e9:.2f}B\n"
                    f"Stock Repurchased: ${cf.get('commonStockRepurchased', 0)/1e9:.2f}B\n"
                    f"Debt Repayment: ${cf.get('debtRepayment', 0)/1e9:.2f}B\n"
                    f"Net Change in Cash: ${cf.get('netChangeInCash', 0)/1e9:.2f}B\n"
                )

        # Process financial ratios (last 5 periods)
        if 'financial_ratios' in company_info and company_info['financial_ratios']:
            content_parts.append("\n=== FINANCIAL RATIOS (Historical) ===\n")
            for ratios in company_info['financial_ratios'][:5]:
                content_parts.append(
                    f"\nPeriod: {ratios.get('date', 'Unknown')}\n"
                    f"Current Ratio: {ratios.get('currentRatio', 0):.2f}\n"
                    f"Quick Ratio: {ratios.get('quickRatio', 0):.2f}\n"
                    f"Debt to Equity: {ratios.get('debtEquityRatio', 0):.2f}\n"
                    f"Debt to Assets: {ratios.get('debtRatio', 0):.2f}\n"
                    f"Return on Assets (ROA): {ratios.get('returnOnAssets', 0)*100:.1f}%\n"
                    f"Return on Equity (ROE): {ratios.get('returnOnEquity', 0)*100:.1f}%\n"
                    f"Return on Capital (ROIC): {ratios.get('returnOnCapitalEmployed', 0)*100:.1f}%\n"
                    f"Asset Turnover: {ratios.get('assetTurnover', 0):.2f}\n"
                    f"Inventory Turnover: {ratios.get('inventoryTurnover', 0):.2f}\n"
                    f"Receivables Turnover: {ratios.get('receivablesTurnover', 0):.2f}\n"
                    f"Days Sales Outstanding: {ratios.get('daysOfSalesOutstanding', 0):.0f} days\n"
                    f"Price to Earnings (P/E): {ratios.get('priceEarningsRatio', 0):.2f}\n"
                    f"Price to Book (P/B): {ratios.get('priceToBookRatio', 0):.2f}\n"
                    f"Price to Sales (P/S): {ratios.get('priceToSalesRatio', 0):.2f}\n"
                    f"EV to Sales: {ratios.get('enterpriseValueMultiple', 0):.2f}\n"
                )

        if not content_parts:
            logger.warning(f"⚠️ No FMP financial data available for vectorization: {symbol}")
            return {'chunks_created': 0, 'vectors_stored': 0}

        content = "\n".join(content_parts)

        file_identifier = f"{symbol}_fmp_financials_{datetime.now().strftime('%Y%m%d')}"

        metadata = {
            'file_name': file_identifier,
            'symbol': symbol,
            'company_cik': cik or symbol,
            'document_type': 'financial_statements',
            'source': 'fmp_api',
            'periods_included': len(company_info.get('income_statements', []))
        }

        chunks = self._chunk_document(content, metadata)
        vector_ids = self._store_in_rag_engine(chunks, metadata)

        logger.info(f"✅ Vectorized FMP financials: {len(chunks)} chunks, {len(vector_ids)} vectors")

        return {
            'chunks_created': len(chunks),
            'vectors_stored': len(vector_ids)
        }

    def _process_yfinance_data_for_vectorization(self, symbol: str, yf_data: Dict[str, Any], cik: str = None) -> Dict[str, Any]:
        """Process yfinance market data for vectorization"""

        logger.info(f"📈 Processing yfinance data for vectorization: {symbol}")

        content_parts = []

        # Market data
        if yf_data:
            content_parts.append("=== MARKET DATA (yfinance) ===\n")
            content_parts.append(
                f"Market Cap: ${yf_data.get('market_cap', 0)/1e9:.2f}B\n"
                f"Current Price: ${yf_data.get('current_price', 0):.2f}\n"
                f"Beta: {yf_data.get('beta', 0):.2f}\n"
                f"Forward P/E: {yf_data.get('forward_pe', 0):.2f}\n"
                f"Trailing P/E: {yf_data.get('trailing_pe', 0):.2f}\n"
                f"PEG Ratio: {yf_data.get('peg_ratio', 0):.2f}\n"
                f"Dividend Yield: {yf_data.get('dividend_yield', 0)*100:.2f}%\n"
                f"52-Week High: ${yf_data.get('52_week_high', 0):.2f}\n"
                f"52-Week Low: ${yf_data.get('52_week_low', 0):.2f}\n"
                f"Average Volume: {yf_data.get('avg_volume', 0):,.0f}\n"
                f"Float Shares: {yf_data.get('float_shares', 0):,.0f}\n"
            )

        if not content_parts:
            logger.warning(f"⚠️ No yfinance data available for vectorization: {symbol}")
            return {'chunks_created': 0, 'vectors_stored': 0}

        content = "\n".join(content_parts)

        file_identifier = f"{symbol}_yfinance_{datetime.now().strftime('%Y%m%d')}"

        metadata = {
            'file_name': file_identifier,
            'symbol': symbol,
            'company_cik': cik or symbol,
            'document_type': 'market_data',
            'source': 'yfinance'
        }

        chunks = self._chunk_document(content, metadata)
        vector_ids = self._store_in_rag_engine(chunks, metadata)

        logger.info(f"✅ Vectorized yfinance data: {len(chunks)} chunks, {len(vector_ids)} vectors")

        return {
            'chunks_created': len(chunks),
            'vectors_stored': len(vector_ids)
        }

    def _process_sec_filings_for_vectorization(self, symbol: str, sec_data: Dict[str, Any]) -> Dict[str, Any]:
        """Process SEC filings and store in vector database"""
        results = {'filings_processed': 0, 'chunks_created': 0, 'vectors_stored': 0}

        filings = sec_data.get('filings', [])
        for filing in filings:
            if 'parsed_data' in filing and filing['parsed_data']:
                parsed_data = filing['parsed_data']

                # Create proper metadata with file_name
                file_identifier = f"{symbol}_{filing.get('form_type', 'filing')}_{filing.get('filing_date', 'unknown')}"

                metadata = {
                    'file_name': file_identifier,
                    'symbol': symbol,
                    'cik': sec_data.get('cik', ''),
                    'form_type': filing.get('form_type', ''),
                    'filing_date': filing.get('filing_date', ''),
                    'accession_number': filing.get('accession_number', ''),
                    'document_type': 'sec_filing',
                    'source': 'sec_edgar'
                }

                # Build comprehensive content from parsed data
                content_parts = []

                # Add filing header
                content_parts.append(f"=== SEC {filing.get('form_type', 'Unknown')} FILING ===\n")
                content_parts.append(f"Company: {symbol}")
                content_parts.append(f"CIK: {sec_data.get('cik', 'Unknown')}")
                content_parts.append(f"Filing Date: {filing.get('filing_date', 'Unknown')}")
                content_parts.append(f"Accession Number: {filing.get('accession_number', 'Unknown')}\n")

                # Add business description
                if parsed_data.get('business_description'):
                    content_parts.append("=== BUSINESS DESCRIPTION ===\n")
                    content_parts.append(parsed_data['business_description'][:10000])  # Limit size
                    content_parts.append("")

                # Add MD&A section
                if parsed_data.get('mda_section'):
                    content_parts.append("=== MANAGEMENT DISCUSSION & ANALYSIS (MD&A) ===\n")
                    content_parts.append(parsed_data['mda_section'][:15000])  # Limit size
                    content_parts.append("")

                # Add risk factors
                if parsed_data.get('risk_factors'):
                    content_parts.append("=== RISK FACTORS ===\n")
                    content_parts.append(parsed_data['risk_factors'][:10000])  # Limit size
                    content_parts.append("")

                # Add financial statements data
                if parsed_data.get('financial_statements'):
                    financials = parsed_data['financial_statements']

                    if 'income_statement' in financials and financials['income_statement'].get('data'):
                        content_parts.append("=== INCOME STATEMENT DATA ===\n")
                        income_data = financials['income_statement']['data'][:10]  # First 10 rows
                        for row in income_data:
                            if len(row) >= 2:
                                account = row[0]
                                values = row[1:]
                                content_parts.append(f"{account}: {', '.join(str(v) for v in values)}")
                        content_parts.append("")

                    if 'balance_sheet' in financials and financials['balance_sheet'].get('data'):
                        content_parts.append("=== BALANCE SHEET DATA ===\n")
                        bs_data = financials['balance_sheet']['data'][:15]  # First 15 rows
                        for row in bs_data:
                            if len(row) >= 2:
                                account = row[0]
                                values = row[1:]
                                content_parts.append(f"{account}: {', '.join(str(v) for v in values)}")
                        content_parts.append("")

                    if 'cash_flow_statement' in financials and financials['cash_flow_statement'].get('data'):
                        content_parts.append("=== CASH FLOW STATEMENT DATA ===\n")
                        cf_data = financials['cash_flow_statement']['data'][:10]  # First 10 rows
                        for row in cf_data:
                            if len(row) >= 2:
                                account = row[0]
                                values = row[1:]
                                content_parts.append(f"{account}: {', '.join(str(v) for v in values)}")
                        content_parts.append("")

                # Add key metrics
                if parsed_data.get('key_metrics'):
                    content_parts.append("=== KEY FINANCIAL METRICS ===\n")
                    metrics = parsed_data['key_metrics']
                    if metrics.get('revenue_mentions'):
                        content_parts.append(f"Revenue Mentions: {', '.join(metrics['revenue_mentions'][:3])}")
                    if metrics.get('net_income_mentions'):
                        content_parts.append(f"Net Income Mentions: {', '.join(metrics['net_income_mentions'][:3])}")
                    if metrics.get('eps_mentions'):
                        content_parts.append(f"EPS Mentions: {', '.join(metrics['eps_mentions'][:3])}")
                    content_parts.append("")

                # Add other sections
                if parsed_data.get('executive_compensation'):
                    content_parts.append("=== EXECUTIVE COMPENSATION ===\n")
                    content_parts.append(parsed_data['executive_compensation'][:5000])
                    content_parts.append("")

                if parsed_data.get('legal_proceedings'):
                    content_parts.append("=== LEGAL PROCEEDINGS ===\n")
                    content_parts.append(parsed_data['legal_proceedings'][:5000])
                    content_parts.append("")

                if parsed_data.get('corporate_governance'):
                    content_parts.append("=== CORPORATE GOVERNANCE ===\n")
                    content_parts.append(parsed_data['corporate_governance'][:5000])
                    content_parts.append("")

                # Add footnotes summary
                if parsed_data.get('footnotes'):
                    content_parts.append("=== FINANCIAL STATEMENT FOOTNOTES ===\n")
                    footnotes = parsed_data['footnotes'][:5]  # First 5 footnotes
                    for footnote in footnotes:
                        content_parts.append(f"Note {footnote.get('note_number', '?')}: {footnote.get('content', '')[:1000]}...")
                    content_parts.append("")

                # Combine all content
                content = "\n".join(content_parts)

                # Skip if content is too short (likely parsing failed)
                if len(content) < 500:
                    logger.warning(f"⚠️ SEC filing content too short for {symbol}, skipping vectorization")
                    continue

                # Chunk and vectorize the structured content
                chunks = self._chunk_document(content, metadata)
                vector_ids = self._store_in_rag_engine(chunks, metadata)

                results['filings_processed'] += 1
                results['chunks_created'] += len(chunks)
                results['vectors_stored'] += len(vector_ids)

                logger.info(f"✅ Vectorized SEC filing {filing.get('form_type')} for {symbol}: {len(chunks)} chunks")

        return results

    def _process_analyst_data_for_vectorization(self, symbol: str, analyst_data: Dict[str, Any], cik: str = None) -> Dict[str, Any]:
        """Process analyst data and store in vector database"""
        # Combine all analyst data into a single document
        content_parts = []

        if 'estimates' in analyst_data:
            content_parts.append(f"Analyst Estimates:\n{json.dumps(analyst_data['estimates'], indent=2)}")

        if 'grades' in analyst_data:
            content_parts.append(f"Analyst Grades:\n{json.dumps(analyst_data['grades'], indent=2)}")

        if 'price_targets' in analyst_data:
            content_parts.append(f"Price Targets:\n{json.dumps(analyst_data['price_targets'], indent=2)}")

        content = "\n\n".join(content_parts)

        file_identifier = f"{symbol}_analyst_reports_{datetime.now().strftime('%Y%m%d')}"
        
        metadata = {
            'file_name': file_identifier,
            'symbol': symbol,
            'company_cik': cik or symbol,  # FIXED: Include CIK from SEC
            'document_type': 'analyst_reports',
            'source': 'fmp_api',
            'total_reports': analyst_data.get('total_reports', 0)
        }

        chunks = self._chunk_document(content, metadata)
        vector_ids = self._store_in_rag_engine(chunks, metadata)

        return {
            'chunks_created': len(chunks),
            'vectors_stored': len(vector_ids)
        }

    def _process_news_data_for_vectorization(self, symbol: str, news_data: Dict[str, Any], cik: str = None) -> Dict[str, Any]:
        """Process news data and store in vector database"""
        results = {'articles_processed': 0, 'chunks_created': 0, 'vectors_stored': 0}

        # Process news articles
        articles = news_data.get('news_articles', [])
        for idx, article in enumerate(articles[:20]):  # Limit to 20 articles
            content = f"Title: {article.get('title', '')}\n\nSummary: {article.get('text', '')}\n\nPublished: {article.get('publishedDate', '')}"

            file_identifier = f"{symbol}_news_{idx}_{article.get('publishedDate', 'unknown')}"
            
            metadata = {
                'file_name': file_identifier,
                'symbol': symbol,
                'company_cik': cik or symbol,  # FIXED: Include CIK from SEC
                'document_type': 'news_article',
                'source': 'fmp_news',
                'title': article.get('title', ''),
                'published_date': article.get('publishedDate', ''),
                'sentiment': article.get('sentiment', 'neutral')
            }

            chunks = self._chunk_document(content, metadata)
            vector_ids = self._store_in_rag_engine(chunks, metadata)

            results['articles_processed'] += 1
            results['chunks_created'] += len(chunks)
            results['vectors_stored'] += len(vector_ids)

        return results

    def _process_social_media_for_vectorization(self, symbol: str, social_data: Dict[str, Any], cik: str = None) -> Dict[str, Any]:
        """Process social media data for vectorization"""
        
        logger.info(f"📱 Processing social media data for vectorization: {symbol}")
        
        results = {'items_processed': 0, 'chunks_created': 0, 'vectors_stored': 0}
        
        # Check if social media data is available
        twitter_mentions = social_data.get('twitter_mentions', [])
        reddit_posts = social_data.get('reddit_posts', [])
        sentiment_score = social_data.get('sentiment_score', 0.0)
        total_mentions = social_data.get('total_mentions', 0)
        
        # If no actual data, create a placeholder document for future use
        if not twitter_mentions and not reddit_posts and total_mentions == 0:
            logger.info(f"ℹ️  No social media data available for {symbol} - creating placeholder")
            content = f"""
Social Media Monitoring for {symbol}

Sentiment Score: {sentiment_score}
Total Mentions: {total_mentions}

Note: {social_data.get('note', 'Social media integration pending API configuration')}

This document serves as a placeholder for future social media sentiment analysis.
"""
        else:
            # Process actual social media data
            content_parts = [f"=== SOCIAL MEDIA ANALYSIS FOR {symbol} ===\n"]
            
            # Add sentiment summary
            content_parts.append(f"Overall Sentiment Score: {sentiment_score:.2f}")
            content_parts.append(f"Total Mentions: {total_mentions}\n")
            
            # Process Twitter mentions
            if twitter_mentions:
                content_parts.append("=== TWITTER MENTIONS ===\n")
                for idx, mention in enumerate(twitter_mentions[:50], 1):
                    content_parts.append(f"{idx}. {mention.get('text', '')} (Date: {mention.get('date', 'Unknown')})\n")
                content_parts.append("")
            
            # Process Reddit posts
            if reddit_posts:
                content_parts.append("=== REDDIT DISCUSSIONS ===\n")
                for idx, post in enumerate(reddit_posts[:50], 1):
                    content_parts.append(f"{idx}. {post.get('title', '')} - {post.get('text', '')} (Date: {post.get('date', 'Unknown')})\n")
            
            content = "\n".join(content_parts)
        
        file_identifier = f"{symbol}_social_media_{datetime.now().strftime('%Y%m%d')}"
        
        metadata = {
            'file_name': file_identifier,
            'symbol': symbol,
            'company_cik': cik or symbol,
            'document_type': 'social_media',
            'source': 'social_media_apis',
            'sentiment_score': sentiment_score,
            'total_mentions': total_mentions
        }
        
        chunks = self._chunk_document(content, metadata)
        vector_ids = self._store_in_rag_engine(chunks, metadata)
        
        logger.info(f"✅ Vectorized social media data: {len(chunks)} chunks, {len(vector_ids)} vectors")
        
        results['items_processed'] = len(twitter_mentions) + len(reddit_posts) if (twitter_mentions or reddit_posts) else 1
        results['chunks_created'] = len(chunks)
        results['vectors_stored'] = len(vector_ids)
        
        return results

    def update_company_data(self, symbol: str, data_type: str) -> Dict[str, Any]:
        """Update company data from external sources (legacy method)"""
        return self.fetch_company_data(symbol, [data_type] if data_type != 'all' else None)

# Global data ingestion service instance
data_ingestion = DataIngestionService()

def require_api_key(f):
    """Decorator to require API key"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        api_key = request.headers.get('X-API-Key')
        if not api_key or api_key != SERVICE_API_KEY:
            return jsonify({'error': 'Invalid API key'}), 401
        return f(*args, **kwargs)
    return decorated_function

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'service': 'data-ingestion',
        'version': '1.0.0'
    })

@app.route('/data/vectors/<symbol>', methods=['GET'])
@require_api_key
def get_vectors(symbol):
    """
    Get vectorized data for a symbol from RAG
    This endpoint retrieves all RAG vectors for due diligence analysis
    """
    try:
        import sys
        import os
        sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
        from shared.rag_helper import rag_helper

        # Get vectors from RAG
        vectors = rag_helper.get_vectors_by_symbol(symbol)

        if vectors.get('contexts_retrieved', 0) == 0:
            logger.warning(f"⚠️ No vectors found for {symbol}")
            return jsonify({
                'symbol': symbol,
                'vectors': {},
                'contexts_retrieved': 0,
                'message': f'No vectorized data found for {symbol}. Data may not have been ingested yet.'
            }), 200  # 200 instead of 404 so DD agent doesn't error

        logger.info(f"✅ Retrieved {vectors['contexts_retrieved']} vectors for {symbol}")

        return jsonify({
            'symbol': symbol,
            'vectors': vectors,
            'contexts_retrieved': vectors.get('contexts_retrieved', 0),
            'retrieved_at': datetime.now().isoformat()
        })

    except Exception as e:
        logger.error(f"Error retrieving vectors for {symbol}: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return jsonify({
            'error': str(e),
            'symbol': symbol,
            'contexts_retrieved': 0
        }), 500

@app.route('/ingest/sec-filing', methods=['POST'])
@require_api_key
def ingest_sec_filing():
    """Ingest SEC filing from Cloud Storage"""
    try:
        data = request.get_json()
        bucket_name = data.get('bucket_name')
        file_name = data.get('file_name')

        if not bucket_name or not file_name:
            return jsonify({'error': 'bucket_name and file_name are required'}), 400

        result = data_ingestion.process_sec_filing(bucket_name, file_name)

        return jsonify(result)

    except Exception as e:
        logger.error(f"Error ingesting SEC filing: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/ingest/company-data', methods=['POST'])
@require_api_key
def update_company_data():
    """Update company data"""
    try:
        data = request.get_json()
        symbol = data.get('symbol')
        data_type = data.get('data_type', 'all')

        if not symbol:
            return jsonify({'error': 'symbol is required'}), 400

        result = data_ingestion.update_company_data(symbol, data_type)

        return jsonify(result)

    except Exception as e:
        logger.error(f"Error updating company data: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/ingest/batch', methods=['POST'])
@require_api_key
def batch_ingest():
    """Batch ingest multiple files"""
    try:
        data = request.get_json()
        files = data.get('files', [])

        if not files:
            return jsonify({'error': 'files array is required'}), 400

        results = []
        for file_info in files:
            bucket_name = file_info.get('bucket_name')
            file_name = file_info.get('file_name')

            if bucket_name and file_name:
                result = data_ingestion.process_sec_filing(bucket_name, file_name)
                results.append(result)

        return jsonify({
            'batch_results': results,
            'total_processed': len(results),
            'successful': len([r for r in results if r.get('status') == 'success']),
            'failed': len([r for r in results if r.get('status') == 'error'])
        })

    except Exception as e:
        logger.error(f"Error in batch ingestion: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/ingest/comprehensive', methods=['POST'])
@require_api_key
def comprehensive_ingest():
    """Fetch and ingest comprehensive company data from all sources"""
    try:
        data = request.get_json()
        symbol = data.get('symbol')
        data_sources = data.get('data_sources')  # Optional: specify which sources to fetch

        if not symbol:
            return jsonify({'error': 'symbol is required'}), 400

        result = data_ingestion.fetch_company_data(symbol, data_sources)

        return jsonify(result)

    except Exception as e:
        logger.error(f"Error in comprehensive ingestion: {e}")
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    port = int(os.getenv('PORT', 8080))
    app.run(host='0.0.0.0', port=port, debug=False)
