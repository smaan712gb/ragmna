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

                        # CRITICAL: Poll for completion (max 10 minutes)
                        success = self._poll_rag_operation(operation_name, access_token, max_wait_seconds=600)

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

    def _download_sec_filing(self, cik: str, accession: str, filing_info: Dict[str, Any]) -> str:
        """Download SEC filing content"""
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

            return response.text

        except Exception as e:
            logger.error(f"Error downloading SEC filing {accession}: {e}")
            return ''

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

        except Exception as e:
            logger.error(f"Error in data processing and vectorization: {e}")
            vectorization_results['error'] = str(e)

        return vectorization_results

    def _process_sec_filings_for_vectorization(self, symbol: str, sec_data: Dict[str, Any]) -> Dict[str, Any]:
        """Process SEC filings and store in vector database"""
        results = {'filings_processed': 0, 'chunks_created': 0, 'vectors_stored': 0}

        filings = sec_data.get('filings', [])
        for filing in filings:
            if 'content' in filing and filing['content']:
                # Create proper metadata with file_name
                file_identifier = f"{symbol}_{filing.get('form_type', 'filing')}_{filing.get('filing_date', 'unknown')}"
                
                metadata = {
                    'file_name': file_identifier,  # FIXED: Add file_name
                    'symbol': symbol,
                    'cik': sec_data.get('cik', ''),
                    'form_type': filing.get('form_type', ''),
                    'filing_date': filing.get('filing_date', ''),
                    'accession_number': filing.get('accession_number', ''),
                    'document_type': 'sec_filing',
                    'source': 'sec_edgar'
                }

                # Chunk and vectorize
                chunks = self._chunk_document(filing['content'], metadata)
                vector_ids = self._store_in_rag_engine(chunks, metadata)

                results['filings_processed'] += 1
                results['chunks_created'] += len(chunks)
                results['vectors_stored'] += len(vector_ids)

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
