"""
LLM Orchestrator Service
Central orchestration service for M&A analysis
Handles company classification, peer identification, and workflow management
"""

import os
import json
import logging
import asyncio
import requests
from flask import Flask, request, jsonify
from flask_cors import CORS
from functools import wraps
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timedelta
import numpy as np
from concurrent.futures import ThreadPoolExecutor
import google.auth
from google.auth.transport.requests import Request
from google.oauth2 import service_account
from google.cloud import aiplatform
from vertexai.generative_models import GenerativeModel
import vertexai

app = Flask(__name__)

# Configure logging first
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configure CORS for production-ready frontend access
# Get allowed origins from environment variable (comma-separated)
ALLOWED_ORIGINS = os.getenv('ALLOWED_ORIGINS', 'http://localhost:3000,http://127.0.0.1:3000').split(',')
logger.info(f"CORS configured for origins: {ALLOWED_ORIGINS}")

CORS(app, resources={
    r"/*": {
        "origins": ALLOWED_ORIGINS,
        "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        "allow_headers": ["Content-Type", "X-API-Key"],
        "expose_headers": ["Content-Type"],
        "supports_credentials": True
    }
})

# Service URLs (to be configured via environment variables)
FMP_PROXY_URL = os.getenv('FMP_PROXY_URL', 'http://fmp-api-proxy:8080')
RAG_ENGINE_URL = os.getenv('RAG_ENGINE_URL', 'https://LOCATION-aiplatform.googleapis.com/v1beta1')
THREE_STATEMENT_MODELER_URL = os.getenv('THREE_STATEMENT_MODELER_URL', 'http://three-statement-modeler:8080')
CCA_VALUATION_URL = os.getenv('CCA_VALUATION_URL', 'http://cca-valuation:8080')
DCF_VALUATION_URL = os.getenv('DCF_VALUATION_URL', 'http://dcf-valuation:8080')
LBO_ANALYSIS_URL = os.getenv('LBO_ANALYSIS_URL', 'http://lbo-analysis:8080')
MERGERS_MODEL_URL = os.getenv('MERGERS_MODEL_URL', 'http://mergers-model:8080')
DD_AGENT_URL = os.getenv('DD_AGENT_URL', 'http://dd-agent:8080')
EXCEL_EXPORTER_URL = os.getenv('EXCEL_EXPORTER_URL', 'http://excel-exporter:8080')
REPORTING_DASHBOARD_URL = os.getenv('REPORTING_DASHBOARD_URL', 'http://reporting-dashboard:8080')
DATA_INGESTION_URL = os.getenv('DATA_INGESTION_URL', 'http://data-ingestion:8080')

# API Keys and Configuration
SERVICE_API_KEY = os.getenv('SERVICE_API_KEY')
VERTEX_PROJECT = os.getenv('VERTEX_PROJECT')
VERTEX_LOCATION = os.getenv('VERTEX_LOCATION')
RAG_CORPUS_ID = os.getenv('RAG_CORPUS_ID')
GOOGLE_CLOUD_KEY_PATH = os.getenv('GOOGLE_CLOUD_KEY_PATH')

# Initialize Vertex AI
if VERTEX_PROJECT and VERTEX_LOCATION:
    if GOOGLE_CLOUD_KEY_PATH:
        credentials = service_account.Credentials.from_service_account_file(GOOGLE_CLOUD_KEY_PATH)
        vertexai.init(project=VERTEX_PROJECT, location=VERTEX_LOCATION, credentials=credentials)
    else:
        vertexai.init(project=VERTEX_PROJECT, location=VERTEX_LOCATION)

# Gemini 2.5 Pro Configuration
GEMINI_MODEL = "gemini-2.5-pro"  # Gemini 2.5 Pro

class RAGManager:
    """Manager for Vertex AI RAG Engine operations"""

    def __init__(self):
        self.project = VERTEX_PROJECT
        self.location = VERTEX_LOCATION
        self.corpus_id = RAG_CORPUS_ID
        self.base_url = f"https://{self.location}-aiplatform.googleapis.com/v1beta1"

    def _get_auth_headers(self) -> Dict[str, str]:
        """Get authentication headers for Vertex AI RAG Engine API calls"""
        try:
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
                    raise ValueError(f"Invalid access token from gcloud")
                logger.info(f"✅ RAG: Access token from gcloud")
            except Exception as gcloud_error:
                logger.warning(f"⚠️ gcloud command failed, trying service account directly")
                
                # Fallback: Use service account with explicit access token request
                if not GOOGLE_CLOUD_KEY_PATH or not os.path.exists(GOOGLE_CLOUD_KEY_PATH):
                    raise ValueError(f"❌ Service account key not found")
                
                # Load service account and manually get OAuth2 access token
                with open(GOOGLE_CLOUD_KEY_PATH, 'r') as f:
                    sa_info = json.load(f)
                
                from google.oauth2 import service_account
                from google.auth.transport.requests import Request as AuthRequest
                
                credentials = service_account.Credentials.from_service_account_info(
                    sa_info,
                    scopes=['https://www.googleapis.com/auth/cloud-platform']
                )
                credentials.refresh(AuthRequest())
                access_token = credentials.token
                
                if not access_token:
                    raise ValueError("❌ Failed to get access token from service account")
                
                logger.info(f"✅ RAG: Access token from service account")
            
            return {
                'Authorization': f'Bearer {access_token}',
                'Content-Type': 'application/json'
            }
        except Exception as e:
            logger.error(f"❌ Failed to get authentication headers: {e}")
            raise ValueError(f"Authentication failed: {e}")

    async def retrieve_contexts(self, query: str, top_k: int = 10,
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
            raise ValueError(f"Failed to retrieve RAG contexts: {e}")

    async def generate_with_rag(self, prompt: str, contexts: List[Dict[str, Any]] = None,
                               model_name: str = None) -> str:
        """Generate response using Gemini with RAG context"""
        if not model_name:
            model_name = GEMINI_MODEL

        try:
            model = GenerativeModel(model_name)

            # Prepare context from RAG retrieval
            context_text = ""
            if contexts:
                context_parts = []
                for ctx in contexts.get('contexts', [])[:5]:  # Limit to top 5 contexts
                    if 'text' in ctx:
                        context_parts.append(ctx['text'])
                context_text = "\n\n".join(context_parts)

            # Create enhanced prompt
            enhanced_prompt = f"""
Based on the following context information:

{context_text}

Please answer the following question:
{prompt}

If the context doesn't contain relevant information, use your general knowledge but prioritize the provided context.
"""

            response = model.generate_content(enhanced_prompt)
            return response.text

        except Exception as e:
            logger.error(f"Error generating with RAG: {e}")
            # Fallback to direct generation
            try:
                model = GenerativeModel(model_name)
                response = model.generate_content(prompt)
                return response.text
            except Exception as e2:
                logger.error(f"Error in fallback generation: {e2}")
                return f"Error generating response: {str(e2)}"

    async def analyze_documents_with_rag(self, symbol: str, document_content: str,
                                       analysis_type: str = "due_diligence") -> Dict[str, Any]:
        """Analyze documents using RAG for enhanced insights"""

        # Retrieve relevant contexts based on analysis type
        if analysis_type == "due_diligence":
            query = f"due diligence analysis for {symbol} company"
        elif analysis_type == "valuation":
            query = f"valuation considerations for {symbol}"
        elif analysis_type == "risk_assessment":
            query = f"risk factors for {symbol} industry"
        else:
            query = f"analysis of {symbol} company documents"

        contexts = await self.retrieve_contexts(query, top_k=5)

        # Generate analysis prompt
        analysis_prompt = f"""
Analyze the following document content for {symbol} and provide insights relevant to {analysis_type}:

Document Content:
{document_content}

Please provide:
1. Key findings and insights
2. Potential risks or concerns identified
3. Recommendations based on the analysis
4. Any additional context that would be valuable for decision making

Focus on {analysis_type} aspects and be specific to the company's situation.
"""

        analysis = await self.generate_with_rag(analysis_prompt, contexts)

        return {
            'analysis_type': analysis_type,
            'symbol': symbol,
            'rag_contexts_used': len(contexts.get('contexts', [])),
            'analysis': analysis,
            'generated_at': datetime.now().isoformat()
        }

class CompanyClassifier:
    """Classifies companies by growth profile and business characteristics"""

    def __init__(self, rag_manager: RAGManager):
        self.rag_manager = rag_manager

    async def classify_company_profile(self, symbol: str, company_data: Dict[str, Any]) -> Dict[str, Any]:
        """Classify company by growth profile, industry, and business model"""

        # Extract key financial metrics
        market_cap = company_data.get('mktCap', 0)
        revenue_growth = self._extract_growth_rate(company_data, 'revenue')
        earnings_growth = self._extract_growth_rate(company_data, 'earnings')
        industry = company_data.get('industry', '')
        sector = company_data.get('sector', '')

        # Retrieve RAG context for company classification
        logger.info(f"🔄 Classifying {symbol} with RAG context")

        # Get RAG insights for company classification
        try:
            classification_query = f"company classification and business model for {symbol} in {industry} industry"
            rag_contexts = await self.rag_manager.retrieve_contexts(classification_query, top_k=5)
            logger.info(f"✅ Retrieved {len(rag_contexts.get('contexts', []))} RAG contexts for classification")
        except Exception as rag_error:
            logger.warning(f"⚠️ RAG retrieval failed, proceeding without RAG: {rag_error}")
            rag_contexts = {'contexts': []}

        # Use structured output from Gemini with RAG context
        try:
            # Prepare RAG context text
            context_text = ""
            contexts_list = rag_contexts.get('contexts', {}).get('contexts', [])
            if contexts_list:
                context_parts = []
                for ctx in contexts_list[:3]:
                    if isinstance(ctx, dict) and 'text' in ctx:
                        context_parts.append(ctx['text'])
                context_text = "\n\n".join(context_parts)
            model = GenerativeModel(GEMINI_MODEL)

            structured_prompt = f"""
Analyze this company and return a JSON response with these exact fields:

Company: {symbol} - {company_data.get('companyName', '')}
Market Cap: ${market_cap:,.0f}
Industry: {industry}
Sector: {sector}
Revenue Growth: {revenue_growth}%

Additional Context from Documents:
{context_text if context_text else "No additional context available"}

Return JSON with:
{{
  "primary_classification": "<hyper_growth|growth|mature_growth|stable|declining|distressed>",
  "growth_stage": "<high_growth|moderate_growth|mature|declining>",
  "industry_category": "<technology|financial|healthcare|consumer|industrial|energy|real_estate|other>",
  "risk_profile": "<low|moderate|high>",
  "reasoning": "<brief explanation>"
}}

Based on the metrics, classify appropriately.
"""

            response = model.generate_content(
                structured_prompt,
                generation_config={
                    'response_mime_type': 'application/json',
                    'temperature': 0.1
                }
            )

            classification_result = json.loads(response.text)

        except Exception as e:
            logger.error(f"❌ Error in structured classification: {e}")
            # For commercial deployment, raise error instead of fallback
            raise ValueError(f"Classification failed for {symbol}: {str(e)}. Commercial deployment requires reliable AI classification.")

        return {
            'symbol': symbol,
            **classification_result,  # Unpack structured fields
            'profile_data': {
                'market_cap': market_cap,
                'revenue_growth': revenue_growth,
                'earnings_growth': earnings_growth,
                'industry': industry,
                'sector': sector
            },
            'classified_at': datetime.now().isoformat()
        }

    def _extract_growth_rate(self, company_data: Dict[str, Any], metric: str) -> float:
        """Extract growth rate from company data"""
        try:
            if metric == 'revenue':
                income_statements = company_data.get('income_statements', [])
                if len(income_statements) >= 2:
                    # Get most recent two years
                    current_year = income_statements[0]
                    prior_year = income_statements[1]
                    
                    current_revenue = current_year.get('revenue', 0)
                    prior_revenue = prior_year.get('revenue', 0)
                    
                    if prior_revenue > 0:
                        growth_rate = ((current_revenue - prior_revenue) / prior_revenue) * 100
                        return round(growth_rate, 1)
            
            elif metric == 'earnings':
                income_statements = company_data.get('income_statements', [])
                if len(income_statements) >= 2:
                    current_year = income_statements[0]
                    prior_year = income_statements[1]
                    
                    current_earnings = current_year.get('netIncome', 0)
                    prior_earnings = prior_year.get('netIncome', 0)
                    
                    if prior_earnings > 0:
                        growth_rate = ((current_earnings - prior_earnings) / prior_earnings) * 100
                        return round(growth_rate, 1)
            
        except Exception as e:
            logger.error(f"Error calculating {metric} growth rate: {e}")
        
        # Fallback if calculation fails
        return 0.0

class MAOrchestrator:
    """Main orchestrator for M&A analysis workflow"""

    def __init__(self):
        self.rag_manager = RAGManager()
        self.classifier = CompanyClassifier(self.rag_manager)

    async def orchestrate_ma_analysis(self, target_symbol: str, acquirer_symbol: str) -> Dict[str, Any]:
        """Orchestrate complete M&A analysis workflow"""

        logger.info(f"Starting M&A analysis orchestration: {acquirer_symbol} → {target_symbol}")

        analysis_result = {
            'target_symbol': target_symbol,
            'acquirer_symbol': acquirer_symbol,
            'workflow_steps': [],
            'analysis_timestamp': datetime.now().isoformat()
        }

        try:
            # Step 1: Data Ingestion for both companies (PARALLEL)
            logger.info("Step 1: Ingesting comprehensive data for both companies in parallel")
            target_data_task = asyncio.create_task(self._ingest_company_data(target_symbol))
            acquirer_data_task = asyncio.create_task(self._ingest_company_data(acquirer_symbol))
            
            target_data, acquirer_data = await asyncio.gather(
                target_data_task,
                acquirer_data_task,
                return_exceptions=True
            )
            
            # Handle potential errors from parallel execution
            if isinstance(target_data, Exception):
                logger.error(f"Target data ingestion failed: {target_data}")
                target_data = {'status': 'error', 'symbol': target_symbol, 'error': str(target_data)}
            if isinstance(acquirer_data, Exception):
                logger.error(f"Acquirer data ingestion failed: {acquirer_data}")
                acquirer_data = {'status': 'error', 'symbol': acquirer_symbol, 'error': str(acquirer_data)}

            logger.info("Parallel data ingestion completed")
            analysis_result['workflow_steps'].append({
                'step': 'data_ingestion',
                'target_data_ingested': target_data.get('status') == 'success',
                'acquirer_data_ingested': acquirer_data.get('status') == 'success',
                'parallel_execution': True,
                'timestamp': datetime.now().isoformat()
            })

            # Step 2: Company Classification (PARALLEL with RAG)
            logger.info("Step 2: Classifying company profiles in parallel")
            target_profile_task = asyncio.create_task(
                self.classifier.classify_company_profile(
                    target_symbol, target_data.get('company_info', {})
                )
            )
            acquirer_profile_task = asyncio.create_task(
                self.classifier.classify_company_profile(
                    acquirer_symbol, acquirer_data.get('company_info', {})
                )
            )
            
            target_profile, acquirer_profile = await asyncio.gather(
                target_profile_task,
                acquirer_profile_task,
                return_exceptions=True
            )
            
            # Handle potential errors
            if isinstance(target_profile, Exception):
                logger.error(f"Target classification failed: {target_profile}")
                raise ValueError(f"Target classification failed: {target_profile}")
            if isinstance(acquirer_profile, Exception):
                logger.error(f"Acquirer classification failed: {acquirer_profile}")
                raise ValueError(f"Acquirer classification failed: {acquirer_profile}")
            
            logger.info("Parallel classification completed")

            analysis_result['company_profiles'] = {
                'target': target_profile,
                'acquirer': acquirer_profile
            }
            analysis_result['workflow_steps'].append({
                'step': 'company_classification',
                'completed': True,
                'timestamp': datetime.now().isoformat()
            })

            # Step 3: Peer Identification
            logger.info("Step 3: Identifying peer companies")
            peers = await self._identify_peers(target_symbol, target_profile)
            analysis_result['peer_companies'] = peers
            analysis_result['workflow_steps'].append({
                'step': 'peer_identification',
                'peers_found': len(peers),
                'timestamp': datetime.now().isoformat()
            })

            # Step 4: 3-Statement Modeling
            logger.info("Step 4: Building 3-statement financial models")
            financial_models = await self._build_financial_models(target_symbol, target_profile)
            analysis_result['financial_models'] = financial_models
            analysis_result['workflow_steps'].append({
                'step': 'financial_modeling',
                'models_built': len(financial_models),
                'timestamp': datetime.now().isoformat()
            })

            # Step 5: Valuation Analysis
            logger.info("Step 5: Performing valuation analysis")
            valuation_results = await self._perform_valuation_analysis(
                target_symbol, acquirer_symbol, financial_models, peers
            )
            analysis_result['valuation_analysis'] = valuation_results
            analysis_result['workflow_steps'].append({
                'step': 'valuation_analysis',
                'valuations_completed': len(valuation_results),
                'timestamp': datetime.now().isoformat()
            })

            # Step 6: Due Diligence
            logger.info("Step 6: Conducting due diligence")
            dd_results = await self._conduct_due_diligence(target_symbol, target_data)
            analysis_result['due_diligence'] = dd_results
            analysis_result['workflow_steps'].append({
                'step': 'due_diligence',
                'completed': True,
                'timestamp': datetime.now().isoformat()
            })

            # Step 7: Generate Final Report
            logger.info("Step 7: Generating final report")
            final_report = await self._generate_final_report(analysis_result)
            analysis_result['final_report'] = final_report
            analysis_result['workflow_steps'].append({
                'step': 'final_report',
                'completed': True,
                'timestamp': datetime.now().isoformat()
            })

            analysis_result['status'] = 'completed'

        except Exception as e:
            logger.error(f"Error in M&A orchestration: {e}")
            analysis_result['status'] = 'error'
            analysis_result['error'] = str(e)

        return analysis_result

    async def _ingest_company_data(self, symbol: str) -> Dict[str, Any]:
        """Ingest comprehensive data for a company"""
        try:
            headers = {'X-API-Key': SERVICE_API_KEY}
            payload = {'symbol': symbol}

            response = requests.post(
                f"{DATA_INGESTION_URL}/ingest/comprehensive",
                json=payload,
                headers=headers,
                timeout=300  # 5 minutes timeout
            )

            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"Data ingestion failed for {symbol}: {response.status_code}")
                return {'status': 'error', 'symbol': symbol}

        except Exception as e:
            logger.error(f"Error ingesting data for {symbol}: {e}")
            return {'status': 'error', 'symbol': symbol, 'error': str(e)}

    async def _identify_peers(self, symbol: str, company_profile: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Identify peer companies for comparison"""
        try:
            # Use FMP API to get peer companies
            headers = {'X-API-Key': SERVICE_API_KEY}
            payload = {'symbol': symbol}

            response = requests.get(
                f"{FMP_PROXY_URL}/peers",
                params={'symbol': symbol},
                headers=headers,
                timeout=30
            )

            if response.status_code == 200:
                peers_data = response.json()
                return peers_data.get('peers', [])
            else:
                logger.warning(f"Could not fetch peers for {symbol}")
                return []

        except Exception as e:
            logger.error(f"Error identifying peers for {symbol}: {e}")
            return []

    async def _build_financial_models(self, symbol: str, company_profile: Dict[str, Any]) -> Dict[str, Any]:
        """Build 3-statement financial models based on company profile"""
        try:
            headers = {'X-API-Key': SERVICE_API_KEY}
            payload = {
                'symbol': symbol,
                'company_profile': company_profile,
                'model_type': 'three_statement'
            }

            response = requests.post(
                f"{THREE_STATEMENT_MODELER_URL}/model",
                json=payload,
                headers=headers,
                timeout=120
            )

            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"Financial modeling failed for {symbol}")
                return {}

        except Exception as e:
            logger.error(f"Error building financial models for {symbol}: {e}")
            return {}

    async def _perform_valuation_analysis(self, target_symbol: str, acquirer_symbol: str,
                                        financial_models: Dict[str, Any], peers: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Perform comprehensive valuation analysis with parallel execution"""
        
        logger.info("Executing valuations in parallel for maximum performance")
        
        # Create async tasks for parallel execution
        async def call_dcf():
            try:
                headers = {'X-API-Key': SERVICE_API_KEY}
                dcf_payload = {
                    'target_symbol': target_symbol,
                    'financial_models': financial_models
                }
                loop = asyncio.get_event_loop()
                response = await loop.run_in_executor(
                    None,
                    lambda: requests.post(
                        f"{DCF_VALUATION_URL}/valuate",
                        json=dcf_payload,
                        headers=headers,
                        timeout=60
                    )
                )
                return response.json() if response.status_code == 200 else {}
            except Exception as e:
                logger.error(f"Error in DCF valuation: {e}")
                return {}

        async def call_cca():
            try:
                headers = {'X-API-Key': SERVICE_API_KEY}
                cca_payload = {
                    'target_symbol': target_symbol,
                    'peers': peers,
                    'financial_models': financial_models
                }
                loop = asyncio.get_event_loop()
                response = await loop.run_in_executor(
                    None,
                    lambda: requests.post(
                        f"{CCA_VALUATION_URL}/valuate",
                        json=cca_payload,
                        headers=headers,
                        timeout=60
                    )
                )
                return response.json() if response.status_code == 200 else {}
            except Exception as e:
                logger.error(f"Error in CCA valuation: {e}")
                return {}

        async def call_lbo():
            try:
                headers = {'X-API-Key': SERVICE_API_KEY}
                lbo_payload = {
                    'target_symbol': target_symbol,
                    'acquirer_symbol': acquirer_symbol,
                    'financial_models': financial_models
                }
                loop = asyncio.get_event_loop()
                response = await loop.run_in_executor(
                    None,
                    lambda: requests.post(
                        f"{LBO_ANALYSIS_URL}/analyze",
                        json=lbo_payload,
                        headers=headers,
                        timeout=60
                    )
                )
                return response.json() if response.status_code == 200 else {}
            except Exception as e:
                logger.error(f"Error in LBO analysis: {e}")
                return {}

        # Execute all valuations in parallel
        dcf_result, cca_result, lbo_result = await asyncio.gather(
            call_dcf(),
            call_cca(),
            call_lbo(),
            return_exceptions=True
        )

        valuations = {}
        if isinstance(dcf_result, dict) and dcf_result:
            valuations['dcf'] = dcf_result
        if isinstance(cca_result, dict) and cca_result:
            valuations['cca'] = cca_result
        if isinstance(lbo_result, dict) and lbo_result:
            valuations['lbo'] = lbo_result

        logger.info(f"Parallel valuations completed: {len(valuations)} valuations successful")
        return valuations

    async def _conduct_due_diligence(self, symbol: str, company_data: Dict[str, Any]) -> Dict[str, Any]:
        """Conduct comprehensive due diligence"""
        try:
            headers = {'X-API-Key': SERVICE_API_KEY}
            payload = {
                'symbol': symbol,
                'company_data': company_data
            }

            response = requests.post(
                f"{DD_AGENT_URL}/analyze",
                json=payload,
                headers=headers,
                timeout=120
            )

            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"Due diligence failed for {symbol}")
                return {}

        except Exception as e:
            logger.error(f"Error in due diligence for {symbol}: {e}")
            return {}

    async def _generate_final_report(self, analysis_result: Dict[str, Any]) -> Dict[str, Any]:
        """Generate final comprehensive report"""
        try:
            headers = {'X-API-Key': SERVICE_API_KEY}

            response = requests.post(
                f"{REPORTING_DASHBOARD_URL}/generate",
                json=analysis_result,
                headers=headers,
                timeout=120
            )

            if response.status_code == 200:
                return response.json()
            else:
                logger.error("Final report generation failed")
                return {'error': 'Report generation failed'}

        except Exception as e:
            logger.error(f"Error generating final report: {e}")
            return {'error': str(e)}

# Global orchestrator instance
orchestrator = MAOrchestrator()

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
        'service': 'llm-orchestrator',
        'version': '1.0.0'
    })

@app.route('/analyze/ma', methods=['POST'])
@require_api_key
def analyze_ma():
    """Main M&A analysis endpoint"""
    try:
        data = request.get_json()
        target_symbol = data.get('target_symbol')
        acquirer_symbol = data.get('acquirer_symbol')

        if not target_symbol or not acquirer_symbol:
            return jsonify({'error': 'target_symbol and acquirer_symbol are required'}), 400

        # Run async function synchronously
        import asyncio
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        result = loop.run_until_complete(orchestrator.orchestrate_ma_analysis(target_symbol, acquirer_symbol))

        return jsonify(result)

    except Exception as e:
        logger.error(f"Error in M&A analysis: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/classify/company', methods=['POST'])
@require_api_key
def classify_company():
    """Classify company profile"""
    try:
        data = request.get_json()
        symbol = data.get('symbol')

        if not symbol:
            return jsonify({'error': 'symbol is required'}), 400

        # Run async function synchronously
        import asyncio
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        # Get company data first
        company_data = loop.run_until_complete(orchestrator._ingest_company_data(symbol))

        if company_data.get('status') != 'success':
            return jsonify({'error': 'Could not fetch company data'}), 400

        classification = loop.run_until_complete(orchestrator.classifier.classify_company_profile(
            symbol, company_data.get('company_info', {})
        ))

        return jsonify(classification)

    except Exception as e:
        logger.error(f"Error classifying company: {e}")
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    port = int(os.getenv('PORT', 8080))
    app.run(host='0.0.0.0', port=port, debug=False)
