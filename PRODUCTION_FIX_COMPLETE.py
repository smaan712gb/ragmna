"""
Complete Production Fix Script
Fixes all critical issues for commercial deployment:
1. OAuth scope errors with Vertex AI RAG Engine API
2. Division by zero in merger model (shares outstanding)
3. Data ingestion not running (scraping, analyst reports, news, SEC filings)
4. DD agents not running end-to-end
5. Removes all hardcoded fallbacks

This script will apply fixes to all affected services.
"""

import os
import json
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ProductionFixer:
    """Fixes all production issues"""
    
    def __init__(self, base_dir: str = "."):
        self.base_dir = Path(base_dir)
        self.services_dir = self.base_dir / "services"
        
    def fix_llm_orchestrator_oauth(self):
        """Fix OAuth scopes in LLM orchestrator for Vertex AI RAG Engine API"""
        logger.info("Fixing LLM orchestrator OAuth scopes...")
        
        llm_orchestrator_file = self.services_dir / "llm-orchestrator" / "main.py"
        
        # Read current content
        with open(llm_orchestrator_file, 'r') as f:
            content = f.read()
        
        # Fix 1: Update _get_auth_headers to use correct scopes
        old_auth_headers = '''    def _get_auth_headers(self) -> Dict[str, str]:
        """Get authentication headers for Vertex AI API calls"""
        if GOOGLE_CLOUD_KEY_PATH:
            credentials = service_account.Credentials.from_service_account_file(GOOGLE_CLOUD_KEY_PATH)
        else:
            credentials, _ = google.auth.default()

        credentials.refresh(Request())
        return {
            'Authorization': f'Bearer {credentials.token}',
            'Content-Type': 'application/json'
        }'''
        
        new_auth_headers = '''    def _get_auth_headers(self) -> Dict[str, str]:
        """Get authentication headers for Vertex AI RAG Engine API calls"""
        try:
            # Define required scopes for Vertex AI RAG Engine
            scopes = [
                'https://www.googleapis.com/auth/cloud-platform',
                'https://www.googleapis.com/auth/aiplatform'
            ]
            
            if GOOGLE_CLOUD_KEY_PATH:
                credentials = service_account.Credentials.from_service_account_file(
                    GOOGLE_CLOUD_KEY_PATH,
                    scopes=scopes
                )
            else:
                credentials, _ = google.auth.default(scopes=scopes)

            if not credentials.valid:
                credentials.refresh(Request())
            
            return {
                'Authorization': f'Bearer {credentials.token}',
                'Content-Type': 'application/json'
            }
        except Exception as e:
            logger.error(f"❌ Failed to get authentication headers: {e}")
            raise ValueError(f"Authentication failed - check GCP credentials and IAM permissions: {e}")'''
        
        content = content.replace(old_auth_headers, new_auth_headers)
        
        # Fix 2: Update retrieve_contexts to use correct RAG Engine API format
        old_retrieve = '''    async def retrieve_contexts(self, query: str, top_k: int = 10,
                              vector_distance_threshold: float = None) -> Dict[str, Any]:
        """Retrieve relevant contexts from RAG corpus"""
        if not self.corpus_id:
            logger.warning("RAG_CORPUS_ID not configured, skipping retrieval")
            return {'contexts': []}

        url = f"{self.base_url}/projects/{self.project}/locations/{self.location}:retrieveContexts"

        payload = {
            'vertex_rag_store': {
                'rag_resources': {
                    'rag_corpus': f'projects/{self.project}/locations/{self.location}/ragCorpora/{self.corpus_id}'
                }
            },
            'query': {
                'text': query,
                'similarity_top_k': top_k
            }
        }

        if vector_distance_threshold:
            payload['vertex_rag_store']['vector_distance_threshold'] = vector_distance_threshold

        try:
            headers = self._get_auth_headers()
            response = requests.post(url, json=payload, headers=headers, timeout=60)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Error retrieving contexts: {e}")
            return {'contexts': []}'''
        
        new_retrieve = '''    async def retrieve_contexts(self, query: str, top_k: int = 10,
                              vector_distance_threshold: float = None) -> Dict[str, Any]:
        """Retrieve relevant contexts from Vertex AI RAG Engine"""
        if not self.corpus_id:
            raise ValueError("❌ RAG_CORPUS_ID not configured. Set RAG_CORPUS_ID environment variable.")
        
        if not self.project or not self.location:
            raise ValueError("❌ VERTEX_PROJECT and VERTEX_LOCATION must be configured.")

        # Vertex AI RAG Engine API endpoint
        url = f"{self.base_url}/projects/{self.project}/locations/{self.location}:retrieveContexts"

        # Proper RAG Engine API payload format
        payload = {
            'vertex_rag_store': {
                'rag_resources': {
                    'rag_corpus': f'projects/{self.project}/locations/{self.location}/ragCorpora/{self.corpus_id}'
                }
            },
            'query': {
                'text': query,
                'similarity_top_k': top_k
            }
        }

        if vector_distance_threshold:
            payload['vertex_rag_store']['vector_distance_threshold'] = vector_distance_threshold

        try:
            headers = self._get_auth_headers()
            logger.info(f"🔍 Retrieving RAG contexts for: {query[:100]}...")
            response = requests.post(url, json=payload, headers=headers, timeout=60)
            response.raise_for_status()
            result = response.json()
            contexts_count = len(result.get('contexts', []))
            logger.info(f"✅ Retrieved {contexts_count} contexts from Vertex AI RAG Engine")
            return result
        except requests.exceptions.HTTPError as e:
            error_detail = e.response.text if hasattr(e.response, 'text') else str(e)
            logger.error(f"❌ HTTP Error retrieving contexts: {e.response.status_code} - {error_detail}")
            raise ValueError(f"Failed to retrieve RAG contexts: {error_detail}")
        except Exception as e:
            logger.error(f"❌ Error retrieving contexts: {e}")
            raise ValueError(f"Failed to retrieve RAG contexts: {e}")'''
        
        content = content.replace(old_retrieve, new_retrieve)
        
        # Fix 3: Remove hardcoded classification fallback
        old_classification_fallback = '''        except Exception as e:
            logger.error(f"Error in structured classification: {e}")
            # Fallback classification based on revenue growth
            if revenue_growth > 30:
                classification_result = {
                    'primary_classification': 'hyper_growth',
                    'growth_stage': 'high_growth',
                    'industry_category': 'technology',
                    'risk_profile': 'moderate'
                }
            elif revenue_growth > 15:
                classification_result = {
                    'primary_classification': 'growth',
                    'growth_stage': 'moderate_growth',
                    'industry_category': 'technology',
                    'risk_profile': 'moderate'
                }
            else:
                classification_result = {
                    'primary_classification': 'stable',
                    'growth_stage': 'mature',
                    'industry_category': 'technology',
                    'risk_profile': 'low'
                }'''
        
        new_classification_fallback = '''        except Exception as e:
            logger.error(f"❌ Error in structured classification: {e}")
            raise ValueError(f"Classification failed - Gemini API error: {e}")'''
        
        content = content.replace(old_classification_fallback, new_classification_fallback)
        
        # Write updated content
        with open(llm_orchestrator_file, 'w') as f:
            f.write(content)
        
        logger.info("✅ Fixed LLM orchestrator OAuth and removed fallbacks")
    
    def fix_merger_model_division_by_zero(self):
        """Fix division by zero errors in merger model"""
        logger.info("Fixing merger model division by zero...")
        
        merger_model_file = self.services_dir / "mergers-model" / "main.py"
        
        with open(merger_model_file, 'r') as f:
            content = f.read()
        
        # Add validation for shares outstanding
        old_extract_fundamentals = '''        # Get shares outstanding from multiple sources
        shares_outstanding = company_info.get('sharesOutstanding', 0)
        if shares_outstanding == 0:
            shares_outstanding = market.get('sharesOutstanding', 0)
        if shares_outstanding == 0:
            yf_data = company_info.get('yfinance_data', {})
            shares_outstanding = yf_data.get('shares_outstanding', 0)'''
        
        new_extract_fundamentals = '''        # Get shares outstanding from multiple sources - CRITICAL for valuation
        shares_outstanding = company_info.get('sharesOutstanding', 0)
        if shares_outstanding == 0:
            shares_outstanding = market.get('sharesOutstanding', 0)
        if shares_outstanding == 0:
            yf_data = company_info.get('yfinance_data', {})
            shares_outstanding = yf_data.get('shares_outstanding', 0)
        
        # CRITICAL: Shares outstanding must be > 0 to avoid division by zero
        if shares_outstanding <= 0:
            symbol = company_data.get('symbol', company_info.get('symbol', 'UNKNOWN'))
            raise ValueError(f"❌ CRITICAL: Shares outstanding = {shares_outstanding} for {symbol}. Cannot proceed with merger model. Check data ingestion.")'''
        
        content = content.replace(old_extract_fundamentals, new_extract_fundamentals)
        
        # Add zero-division protection in accretion/dilution
        old_accretion = '''        # Accretion/dilution
        eps_change = pro_forma_eps - acquirer_eps
        eps_accretion_dilution = eps_change / abs(acquirer_eps) if acquirer_eps != 0 else 0'''
        
        new_accretion = '''        # Accretion/dilution
        eps_change = pro_forma_eps - acquirer_eps
        if acquirer_eps == 0:
            raise ValueError("❌ Acquirer EPS is zero - cannot calculate accretion/dilution")
        eps_accretion_dilution = eps_change / abs(acquirer_eps)'''
        
        content = content.replace(old_accretion, new_accretion)
        
        with open(merger_model_file, 'w') as f:
            f.write(content)
        
        logger.info("✅ Fixed merger model division by zero errors")
    
    def fix_data_ingestion_rag_upload(self):
        """Fix data ingestion to properly upload to Vertex AI RAG Engine"""
        logger.info("Fixing data ingestion RAG upload...")
        
        data_ingestion_file = self.services_dir / "data-ingestion" / "main.py"
        
        with open(data_ingestion_file, 'r') as f:
            content = f.read()
        
        # Update _store_in_rag_engine to use proper RAG Engine API
        old_store = '''    def _store_in_rag_engine(self, chunks: List[Dict[str, Any]], metadata: Dict[str, Any]) -> List[str]:
        """Store document chunks in Vertex AI RAG Engine"""

        vector_ids = []

        # RAG Engine is now enabled with proper IAM permissions
        try:
            from google.auth import default
            from google.auth.transport.requests import Request
            
            # Get authentication using service account
            credentials, project = default()
            
            # For now, just track chunks without actual RAG storage
            # Full RAG implementation requires corpus creation which is complex
            logger.info(f"Tracking {len(chunks)} chunks for future RAG integration")
            for chunk in chunks:
                vector_ids.append(chunk['id'])
            
            return vector_ids
            
        except Exception as e:
            logger.error(f"Error in RAG preparation: {e}")
            # Fallback - still track chunk IDs
            for chunk in chunks:
                vector_ids.append(chunk['id'])
            
            return vector_ids'''
        
        new_store = '''    def _store_in_rag_engine(self, chunks: List[Dict[str, Any]], metadata: Dict[str, Any]) -> List[str]:
        """Store document chunks in Vertex AI RAG Engine via Import API"""

        vector_ids = []
        
        try:
            from google.auth import default
            from google.auth.transport.requests import Request
            import tempfile
            
            # Get authentication with proper scopes
            scopes = [
                'https://www.googleapis.com/auth/cloud-platform',
                'https://www.googleapis.com/auth/aiplatform'
            ]
            credentials, project = default(scopes=scopes)
            
            if not credentials.valid:
                credentials.refresh(Request())
            
            # Get RAG corpus configuration
            vertex_project = os.getenv('VERTEX_PROJECT')
            vertex_location = os.getenv('VERTEX_LOCATION')
            rag_corpus_id = os.getenv('RAG_CORPUS_ID')
            
            if not all([vertex_project, vertex_location, rag_corpus_id]):
                raise ValueError("❌ VERTEX_PROJECT, VERTEX_LOCATION, and RAG_CORPUS_ID must all be configured")
            
            # Create temporary file with chunks content
            temp_file_path = None
            try:
                # Combine chunks into single document
                combined_content = "\n\n".join([chunk['content'] for chunk in chunks])
                
                # Create temp file
                with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as tf:
                    tf.write(combined_content)
                    temp_file_path = tf.name
                
                # Upload to GCS first (required by RAG Engine Import API)
                gcs_bucket = os.getenv('GCS_BUCKET')
                if not gcs_bucket:
                    raise ValueError("❌ GCS_BUCKET not configured - required for RAG Engine")
                
                from google.cloud import storage
                storage_client = storage.Client()
                bucket = storage_client.bucket(gcs_bucket)
                
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
                
                headers = {
                    'Authorization': f'Bearer {credentials.token}',
                    'Content-Type': 'application/json'
                }
                
                response = requests.post(url, json=payload, headers=headers, timeout=300)
                response.raise_for_status()
                
                operation = response.json()
                logger.info(f"✅ Started RAG import operation: {operation.get('name', 'unknown')}")
                
                # Track chunk IDs
                for chunk in chunks:
                    vector_ids.append(chunk['id'])
                
                return vector_ids
                
            finally:
                # Cleanup temp file
                if temp_file_path and os.path.exists(temp_file_path):
                    os.unlink(temp_file_path)
            
        except Exception as e:
            logger.error(f"❌ Error storing in RAG Engine: {e}")
            raise ValueError(f"Failed to store in RAG Engine: {e}")'''
        
        content = content.replace(old_store, new_store)
        
        with open(data_ingestion_file, 'w') as f:
            f.write(content)
        
        logger.info("✅ Fixed data ingestion RAG upload")
    
    def create_end_to_end_test(self):
        """Create comprehensive end-to-end production test"""
        logger.info("Creating end-to-end production test...")
        
        test_content = '''"""
END-TO-END PRODUCTION TEST
Tests complete M&A workflow with all services
- Data ingestion (SEC filings, analyst reports, news, yfinance)
- Company classification
- DD agent analysis
- Valuation (DCF, CCA, LBO)
- Merger model
- Final reporting

NO HARDCODED FALLBACKS - All failures must raise errors
"""

import os
import json
import requests
import time
from datetime import datetime

class EndToEndProductionTest:
    """Complete production workflow test"""
    
    def __init__(self):
        self.base_url = os.getenv('RUN_MANAGER_URL', 'http://localhost:8013')
        self.api_key = os.getenv('SERVICE_API_KEY')
        self.headers = {'X-API-Key': self.api_key}
    
    def run_complete_test(self, target_symbol: str, acquirer_symbol: str):
        """Run complete end-to-end test"""
        
        print(f"\\n{'='*80}")
        print(f"END-TO-END PRODUCTION TEST: {acquirer_symbol} → {target_symbol}")
        print(f"{'='*80}\\n")
        
        test_result = {
            'test_timestamp': datetime.now().isoformat(),
            'target_symbol': target_symbol,
            'acquirer_symbol': acquirer_symbol,
            'test_steps': []
        }
        
        try:
            # Step 1: Data Ingestion for both companies
            print("\\n📥 STEP 1: DATA INGESTION")
            print("-" * 80)
            ingestion_result = self._test_data_ingestion(target_symbol, acquirer_symbol)
            test_result['test_steps'].append({
                'step': 1,
                'name': 'data_ingestion',
                'status': 'passed' if ingestion_result['success'] else 'failed',
                'result': ingestion_result
            })
            
            # Step 2: Company Classification
            print("\\n🏷️ STEP 2: COMPANY CLASSIFICATION")
            print("-" * 80)
            classification_result = self._test_classification(target_symbol, acquirer_symbol)
            test_result['test_steps'].append({
                'step': 2,
                'name': 'classification',
                'status': 'passed' if classification_result['success'] else 'failed',
                'result': classification_result
            })
            
            # Step 3: DD Agent Analysis
            print("\\n🔍 STEP 3: DUE DILIGENCE ANALYSIS")
            print("-" * 80)
            dd_result = self._test_dd_agent(target_symbol)
            test_result['test_steps'].append({
                'step': 3,
                'name': 'due_diligence',
                'status': 'passed' if dd_result['success'] else 'failed',
                'result': dd_result
            })
            
            # Step 4: Valuation Analysis
            print("\\n💰 STEP 4: VALUATION ANALYSIS")
            print("-" * 80)
            valuation_result = self._test_valuation(target_symbol)
            test_result['test_steps'].append({
                'step': 4,
                'name': 'valuation',
                'status': 'passed' if valuation_result['success'] else 'failed',
                'result': valuation_result
            })
            
            # Step 5: Merger Model
            print("\\n🔄 STEP 5: MERGER MODEL")
            print("-" * 80)
            merger_result = self._test_merger_model(target_symbol, acquirer_symbol)
            test_result['test_steps'].append({
                'step': 5,
                'name': 'merger_model',
                'status': 'passed' if merger_result['success'] else 'failed',
                'result': merger_result
            })
            
            # Step 6: Final Report Generation
            print("\\n📊 STEP 6: REPORT GENERATION")
            print("-" * 80)
            report_result = self._test_report_generation(target_symbol, acquirer_symbol)
            test_result['test_steps'].append({
                'step': 6,
                'name': 'report_generation',
                'status': 'passed' if report_result['success'] else 'failed',
                'result': report_result
            })
            
            # Overall result
            all_passed = all(step['status'] == 'passed' for step in test_result['test_steps'])
            test_result['overall_status'] = 'PASSED' if all_passed else 'FAILED'
            
        except Exception as e:
            test_result['overall_status'] = 'FAILED'
            test_result['error'] = str(e)
            print(f"\\n❌ TEST FAILED: {e}")
        
        # Save results
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        output_file = f'END_TO_END_TEST_{target_symbol}_{acquirer_symbol}_{timestamp}.json'
        with open(output_file, 'w') as f:
            json.dump(test_result, f, indent=2)
        
        print(f"\\n{'='*80}")
        print(f"TEST RESULT: {test_result['overall_status']}")
        print(f"Results saved to: {output_file}")
        print(f"{'='*80}\\n")
        
        return test_result
    
    def _test_data_ingestion(self, target_symbol: str, acquirer_symbol: str) -> dict:
        """Test data ingestion for both companies"""
        result = {
            'success': False,
            'target_ingested': False,
            'acquirer_ingested': False,
            'errors': []
        }
        
        try:
            for symbol in [target_symbol, acquirer_symbol]:
                print(f"  Ingesting data for {symbol}...")
                
                response = requests.post(
                    f"{self.base_url.replace(':8013', ':8001')}/ingest/comprehensive",
                    json={'symbol': symbol},
                    headers=self.headers,
                    timeout=300
                )
                
                if response.status_code == 200:
                    data = response.json()
                    print(f"  ✅ {symbol}: Data ingested successfully")
                    print(f"     - SEC filings: {len(data.get('fetched_data', {}).get('sec_filings', {}).get('filings', []))}")
                    print(f"     - Analyst reports: {data.get('fetched_data', {}).get('analyst_reports', {}).get('total_reports', 0)}")
                    print(f"     - News articles: {data.get('fetched_data', {}).get('news', {}).get('total_items', 0)}")
                    print(f"     - Vectors created: {data.get('vectorization_results', {}).get('vectors_stored', 0)}")
                    
                    if symbol == target_symbol:
                        result['target_ingested'] = True
                    else:
                        result['acquirer_ingested'] = True
                else:
                    error_msg = f"{symbol}: Ingestion failed - {response.status_code}"
                    result['errors'].append(error_msg)
                    print(f"  ❌ {error_msg}")
            
            result['success'] = result['target_ingested'] and result['acquirer_ingested']
            
        except Exception as e:
            result['errors'].append(str(e))
            print(f"  ❌ Error: {e}")
        
        return result
    
    def _test_classification(self, target_symbol: str, acquirer_symbol: str) -> dict:
        """Test company classification"""
        result = {
            'success': False,
            'target_classified': False,
            'acquirer_classified': False,
            'errors': []
        }
        
        try:
            for symbol in [target_symbol, acquirer_symbol]:
                print(f"  Classifying {symbol}...")
                
                response = requests.post(
                    f"{self.base_url.replace(':8013', ':8002')}/classify/company",
                    json={'symbol': symbol},
                    headers=self.headers,
                    timeout=120
                )
                
                if response.status_code == 200:
                    data = response.json()
                    print(f"  ✅ {symbol}: {data.get('primary_classification', 'unknown')}")
                    print(f"     - Industry: {data.get('industry_category', 'unknown')}")
                    print(f"     - Growth stage: {data.get('growth_stage', 'unknown')}")
                    
                    if symbol == target_symbol:
                        result['target_classified'] = True
                    else:
                        result['acquirer_classified'] = True
                else:
                    error_msg = f"{symbol}: Classification failed - {response.status_code}"
                    result['errors'].append(error_msg)
                    print(f"  ❌ {error_msg}")
            
            result['success'] = result['target_classified'] and result['acquirer_classified']
            
        except Exception as e:
            result['errors'].append(str(e))
            print(f"  ❌ Error: {e}")
        
        return result
    
    def _test_dd_agent(self, target_symbol: str) -> dict:
        """Test DD agent analysis"""
        result = {
            'success': False,
            'analysis_complete': False,
            'errors': []
        }
        
        try:
            print(f"  Running DD agent for {target_symbol}...")
            
            response = requests.post(
                f"{self.base_url.replace(':8013', ':8010')}/analyze",
                json={'symbol': target_symbol},
                headers=self.headers,
                timeout=300
            )
            
            if response.status_code == 200:
                data = response.json()
                print(f"  ✅ DD Analysis complete")
                print(f"     - Risk areas identified: {len(data.get('risk_analysis', {}).get('risk_areas', []))}")
                print(f"     - Recommendations: {len(data.get('recommendations', []))}")
                result['success'] = True
                result['analysis_complete'] = True
            else:
                error_msg = f"DD Agent failed - {response.status_code}"
                result['errors'].append(error_msg)
                print(f"  ❌ {error_msg}")
        
        except Exception as e:
            result['errors'].append(str(e))
            print(f"  ❌ Error: {e}")
        
        return result
    
    def _test_valuation(self, target_symbol: str) -> dict:
        """Test valuation analysis"""
        result = {
            'success': False,
            'dcf_complete': False,
            'cca_complete': False,
            'errors': []
        }
        
        try:
            # DCF
            print(f"  Running DCF for {target_symbol}...")
            response = requests.post(
                f"{self.base_url.replace(':8013', ':8005')}/valuate",
                json={'target_symbol': target_symbol},
                headers=self.headers,
                timeout=120
            )
            
            if response.status_code == 200:
                print(f"  ✅ DCF complete")
                result['dcf_complete'] = True
            
            # CCA
            print(f"  Running CCA for {target_symbol}...")
            response = requests.post(
                f"{self.base_url.replace(':8013', ':8006')}/valuate",
                json={'target_symbol': target_symbol},
                headers=self.headers,
                timeout=120
            )
            
            if response.status_code == 200:
                print(f"  ✅ CCA complete")
                result['cca_complete'] = True
            
            result['success'] = result['dcf_complete'] and result['cca_complete']
            
        except Exception as e:
            result['errors'].append(str(e))
            print(f"  ❌ Error: {e}")
        
        return result
    
    def _test_merger_model(self, target_symbol: str, acquirer_symbol: str) -> dict:
        """Test merger model"""
        result = {
            'success': False,
            'model_complete': False,
            'errors': []
        }
        
        try:
            print(f"  Running merger model: {acquirer_symbol} → {target_symbol}...")
            
            response = requests.post(
                f"{self.base_url.replace(':8013', ':8008')}/model/ma",
                json={
                    'target_symbol': target_symbol,
                    'acquirer_symbol': acquirer_symbol
                },
                headers=self.headers,
                timeout=180
            )
            
            if response.status_code == 200:
                data = response.json()
                print(f"  ✅ Merger model complete")
                print(f"
