"""
Run Manager Service
Manages M&A analysis runs with version control, audit trails, and Gemini context caching
Uses Gemini 2.5 Pro for intelligent run orchestration
"""

import os
import json
import logging
import subprocess
from datetime import datetime, timedelta
from flask import Flask, request, jsonify
from functools import wraps
from typing import Dict, Any, Optional
import requests
from google.cloud import storage
import vertexai
from vertexai.generative_models import GenerativeModel, Part, Tool
from vertexai.preview import caching

app = Flask(__name__)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Service configurations
SERVICE_API_KEY = os.getenv('SERVICE_API_KEY')
PROJECT_ID = os.getenv('PROJECT_ID')
VERTEX_PROJECT = os.getenv('VERTEX_PROJECT')
VERTEX_LOCATION = os.getenv('VERTEX_LOCATION', 'us-central1')
GCS_BUCKET = os.getenv('RUNS_BUCKET', 'ma-analysis-runs')
DATA_INGESTION_URL = os.getenv('DATA_INGESTION_URL', 'http://data-ingestion:8080')

# Initialize Vertex AI
vertexai.init(project=VERTEX_PROJECT, location=VERTEX_LOCATION)

class RunManager:
    """Manages analysis runs with Gemini-powered context caching"""
    
    def __init__(self):
        self.model_name = 'gemini-2.5-pro'
        self.storage_client = storage.Client()
        self.cached_contexts = {}  # In-memory cache of active contexts
        
    def initialize_run(self, acquirer: str, target: str, as_of_date: str) -> Dict[str, Any]:
        """
        Initialize a new M&A analysis run with cached context
        
        Uses Gemini 2.5 Pro:
        - Context Caching for run configuration
        - Function Calling to create GCS objects
        
        Args:
            acquirer: Acquirer company symbol
            target: Target company symbol
            as_of_date: Analysis date (YYYY-MM-DD)
            
        Returns:
            Dict with run_id, cache info, and manifest
        """
        logger.info(f"Initializing run: {acquirer} → {target} as of {as_of_date}")
        
        run_id = f"{acquirer}_{target}_{as_of_date}"
        run_dir = f"{GCS_BUCKET}/{run_id}"
        
        # Fetch comprehensive data for both companies
        logger.info("Fetching company data...")
        acquirer_data = self._fetch_company_comprehensive(acquirer)
        target_data = self._fetch_company_comprehensive(target)
        
        # Get market snapshot
        market_snapshot = self._get_market_snapshot(as_of_date)
        
        # Create cached context (1-hour TTL)
        logger.info("Creating cached context...")
        cache = self._create_cached_context(
            run_id=run_id,
            acquirer=acquirer,
            target=target,
            acquirer_data=acquirer_data,
            target_data=target_data,
            as_of_date=as_of_date,
            market_snapshot=market_snapshot
        )
        
        # Store cache reference
        self.cached_contexts[run_id] = {
            'cache': cache,
            'created_at': datetime.now().isoformat(),
            'expires_at': (datetime.now() + timedelta(hours=1)).isoformat()
        }
        
        # Generate run manifest using Gemini
        logger.info("Generating run manifest...")
        manifest = self._generate_run_manifest(
            cache=cache,
            run_id=run_id,
            acquirer=acquirer,
            target=target,
            as_of_date=as_of_date
        )
        
        # Save to GCS
        logger.info("Saving to GCS...")
        self._save_to_gcs(f"{run_dir}/manifest.json", json.dumps(manifest, indent=2))
        self._save_to_gcs(f"{run_dir}/acquirer_data.json", json.dumps(acquirer_data, indent=2))
        self._save_to_gcs(f"{run_dir}/target_data.json", json.dumps(target_data, indent=2))
        
        logger.info(f"Run initialized successfully: {run_id}")
        
        return {
            'run_id': run_id,
            'run_dir': run_dir,
            'cache_name': cache.name,
            'cache_expires_at': self.cached_contexts[run_id]['expires_at'],
            'manifest': manifest,
            'status': 'initialized'
        }
    
    def _create_cached_context(self, run_id: str, acquirer: str, target: str,
                              acquirer_data: Dict, target_data: Dict,
                              as_of_date: str, market_snapshot: Dict) -> caching.CachedContent:
        """Create Gemini cached context for the run"""
        
        system_instruction = f"""
You are a financial analysis assistant managing an M&A analysis run.

RUN CONTEXT:
- Acquirer: {acquirer}
- Target: {target}
- Analysis Date: {as_of_date}
- Run ID: {run_id}

This cached context contains comprehensive company data for both companies.
You have access to:
- Financial statements (historical and projections)
- SEC filings and documents
- Market data and peer information
- Analyst reports and estimates

Your role is to provide context-aware analysis, valuation, and reporting
for this specific M&A transaction throughout the analysis workflow.

Always cite sources from the provided data when making statements.
"""
        
        # Prepare content for caching
        content_parts = [
            "# ACQUIRER COMPANY DATA",
            f"Company: {acquirer}",
            f"Full Data:\n{json.dumps(acquirer_data, indent=2)}",
            "",
            "# TARGET COMPANY DATA",
            f"Company: {target}",
            f"Full Data:\n{json.dumps(target_data, indent=2)}",
            "",
            "# MARKET SNAPSHOT",
            f"Date: {as_of_date}",
            f"Market Data:\n{json.dumps(market_snapshot, indent=2)}",
        ]
        
        content_text = "\n".join(content_parts)
        
        # Create cached content
        cache = caching.CachedContent.create(
            model_name=self.model_name,
            display_name=f'run_{run_id}',
            system_instruction=system_instruction,
            contents=[content_text],
            ttl=timedelta(hours=1)  # Cache for 1 hour
        )
        
        logger.info(f"Created cache: {cache.name}")
        return cache
    
    def _generate_run_manifest(self, cache: caching.CachedContent, run_id: str,
                              acquirer: str, target: str, as_of_date: str) -> Dict[str, Any]:
        """Generate run manifest using Gemini with cached context"""
        
        # Define function declarations for version info
        version_tools = Tool(
            function_declarations=[
                {
                    "name": "get_git_commit",
                    "description": "Get current git commit hash",
                    "parameters": {
                        "type": "object",
                        "properties": {}
                    }
                },
                {
                    "name": "get_service_versions",
                    "description": "Get versions of all microservices",
                    "parameters": {
                        "type": "object",
                        "properties": {}
                    }
                }
            ]
        )
        
        # Use cached model (pays only for new prompt, not context)
        model = GenerativeModel.from_cached_content(cached_content=cache)
        
        prompt = f"""
Generate a comprehensive run manifest for this M&A analysis.

Required information:
1. Run metadata (ID, date, companies)
2. System versions (call get_git_commit and get_service_versions functions)
3. Data completeness assessment
4. Initial company classifications
5. Recommended analysis workflow

Return as structured JSON with these fields:
{{
  "run_id": "{run_id}",
  "acquirer": "{acquirer}",
  "target": "{target}",
  "analysis_date": "{as_of_date}",
  "created_at": "ISO timestamp",
  "versions": {{}},
  "data_completeness": {{}},
  "initial_assessment": {{}},
  "recommended_workflow": []
}}
"""
        
        try:
            # Generate with function calling
            response = model.generate_content(
                prompt,
                tools=[version_tools],
                generation_config={
                    'response_mime_type': 'application/json',
                    'temperature': 0.1
                }
            )
            
            # Handle function calls if present
            if response.candidates and response.candidates[0].content.parts:
                first_part = response.candidates[0].content.parts[0]
                
                if hasattr(first_part, 'function_call') and first_part.function_call:
                    # Execute function calls
                    function_responses = self._execute_function_calls(response)
                    
                    # Send results back to model
                    response = model.generate_content(
                        [prompt, response.candidates[0].content, function_responses],
                        generation_config={'response_mime_type': 'application/json'}
                    )
            
            manifest = json.loads(response.text)
            
            # Add actual timestamps
            manifest['created_at'] = datetime.now().isoformat()
            manifest['cache_name'] = cache.name
            
            return manifest
            
        except Exception as e:
            logger.error(f"Error generating manifest with Gemini: {e}")
            # Fallback to basic manifest
            return self._generate_basic_manifest(run_id, acquirer, target, as_of_date, cache)
    
    def _execute_function_calls(self, response) -> Part:
        """Execute function calls and return results"""
        
        function_responses = []
        
        for part in response.candidates[0].content.parts:
            if hasattr(part, 'function_call') and part.function_call:
                function_name = part.function_call.name
                
                if function_name == 'get_git_commit':
                    result = self._get_git_commit()
                elif function_name == 'get_service_versions':
                    result = self._get_service_versions()
                else:
                    result = {'error': f'Unknown function: {function_name}'}
                
                function_responses.append(
                    Part.from_function_response(
                        name=function_name,
                        response={"result": result}
                    )
                )
        
        return function_responses[0] if function_responses else None
    
    def _get_git_commit(self) -> str:
        """Get current git commit hash"""
        try:
            result = subprocess.run(
                ['git', 'rev-parse', 'HEAD'],
                capture_output=True,
                text=True,
                timeout=5
            )
            return result.stdout.strip() if result.returncode == 0 else 'unknown'
        except Exception as e:
            logger.error(f"Error getting git commit: {e}")
            return 'unknown'
    
    def _get_service_versions(self) -> Dict[str, str]:
        """Get versions of all microservices"""
        services = [
            'data-ingestion',
            'llm-orchestrator',
            'three-statement-modeler',
            'dcf-valuation',
            'cca-valuation',
            'lbo-analysis',
            'mergers-model',
            'dd-agent',
            'excel-exporter',
            'reporting-dashboard'
        ]
        
        versions = {}
        for service in services:
            try:
                # Try to get version from health endpoint
                response = requests.get(
                    f"http://{service}:8080/health",
                    timeout=2
                )
                if response.status_code == 200:
                    data = response.json()
                    versions[service] = data.get('version', '1.0.0')
                else:
                    versions[service] = 'unknown'
            except:
                versions[service] = 'not-running'
        
        return versions
    
    def _fetch_company_comprehensive(self, symbol: str) -> Dict[str, Any]:
        """Fetch comprehensive company data from data-ingestion service"""
        try:
            headers = {'X-API-Key': SERVICE_API_KEY}
            payload = {'symbol': symbol}
            
            response = requests.post(
                f"{DATA_INGESTION_URL}/ingest/comprehensive",
                json=payload,
                headers=headers,
                timeout=300
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"Error fetching data for {symbol}: {response.status_code}")
                return {
                    'symbol': symbol,
                    'error': f'HTTP {response.status_code}',
                    'status': 'failed'
                }
        except Exception as e:
            logger.error(f"Exception fetching data for {symbol}: {e}")
            return {
                'symbol': symbol,
                'error': str(e),
                'status': 'failed'
            }
    
    def _get_market_snapshot(self, as_of_date: str) -> Dict[str, Any]:
        """Get market snapshot for the analysis date"""
        # This would integrate with market data provider
        # For now, return basic structure
        return {
            'date': as_of_date,
            'indices': {
                'sp500': 0.0,
                'nasdaq': 0.0,
                'dow': 0.0
            },
            'rates': {
                'fed_funds_rate': 0.0,
                'ten_year_treasury': 0.0
            },
            'fx_rates': {
                'usd_eur': 1.0,
                'usd_gbp': 1.0,
                'usd_jpy': 1.0
            }
        }
    
    def _save_to_gcs(self, path: str, content: str):
        """Save content to Google Cloud Storage"""
        try:
            bucket = self.storage_client.bucket(GCS_BUCKET)
            blob = bucket.blob(path)
            blob.upload_from_string(content, content_type='application/json')
            logger.info(f"Saved to GCS: gs://{GCS_BUCKET}/{path}")
        except Exception as e:
            logger.error(f"Error saving to GCS: {e}")
            # Continue execution even if GCS save fails
    
    def _generate_basic_manifest(self, run_id: str, acquirer: str, target: str,
                                 as_of_date: str, cache) -> Dict[str, Any]:
        """Generate basic manifest without Gemini (fallback)"""
        return {
            'run_id': run_id,
            'acquirer': acquirer,
            'target': target,
            'analysis_date': as_of_date,
            'created_at': datetime.now().isoformat(),
            'cache_name': cache.name,
            'versions': {
                'git_commit': self._get_git_commit(),
                'services': self._get_service_versions()
            },
            'status': 'initialized_basic'
        }
    
    def get_run(self, run_id: str) -> Optional[Dict[str, Any]]:
        """Get run information including cache status"""
        if run_id in self.cached_contexts:
            cached_info = self.cached_contexts[run_id]
            return {
                'run_id': run_id,
                'cache_name': cached_info['cache'].name,
                'created_at': cached_info['created_at'],
                'expires_at': cached_info['expires_at'],
                'status': 'active'
            }
        return None
    
    def get_cached_context(self, run_id: str) -> Optional[caching.CachedContent]:
        """Get cached context for a run"""
        if run_id in self.cached_contexts:
            return self.cached_contexts[run_id]['cache']
        return None

# Global run manager instance
run_manager = RunManager()

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
        'service': 'run-manager',
        'version': '1.0.0',
        'gemini_model': 'gemini-2.5-pro',
        'active_runs': len(run_manager.cached_contexts)
    })

@app.route('/runs/initialize', methods=['POST'])
@require_api_key
def initialize_run():
    """Initialize a new analysis run"""
    try:
        data = request.get_json()
        acquirer = data.get('acquirer')
        target = data.get('target')
        as_of_date = data.get('as_of_date', datetime.now().strftime('%Y-%m-%d'))
        
        if not acquirer or not target:
            return jsonify({'error': 'acquirer and target are required'}), 400
        
        result = run_manager.initialize_run(acquirer, target, as_of_date)
        
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"Error initializing run: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/runs/<run_id>', methods=['GET'])
@require_api_key
def get_run(run_id: str):
    """Get run information"""
    try:
        result = run_manager.get_run(run_id)
        
        if result:
            return jsonify(result)
        else:
            return jsonify({'error': 'Run not found'}), 404
            
    except Exception as e:
        logger.error(f"Error getting run: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/runs/<run_id>/cache', methods=['GET'])
@require_api_key
def get_cache_info(run_id: str):
    """Get cache information for a run"""
    try:
        cache = run_manager.get_cached_context(run_id)
        
        if cache:
            return jsonify({
                'run_id': run_id,
                'cache_name': cache.name,
                'model': cache.model,
                'status': 'active'
            })
        else:
            return jsonify({'error': 'Cache not found or expired'}), 404
            
    except Exception as e:
        logger.error(f"Error getting cache info: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/runs/list', methods=['GET'])
@require_api_key
def list_runs():
    """List all active runs"""
    try:
        runs = []
        for run_id, info in run_manager.cached_contexts.items():
            runs.append({
                'run_id': run_id,
                'created_at': info['created_at'],
                'expires_at': info['expires_at'],
                'cache_name': info['cache'].name
            })
        
        return jsonify({'runs': runs, 'total': len(runs)})
        
    except Exception as e:
        logger.error(f"Error listing runs: {e}")
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    port = int(os.getenv('PORT', 8080))
    app.run(host='0.0.0.0', port=port, debug=False)
