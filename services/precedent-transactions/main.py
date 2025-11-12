"""
Precedent Transactions Service
M&A deal comparables analysis with Google Search grounding
Uses Gemini 2.5 Pro for real-time deal discovery
"""

import os
import json
import logging
from flask import Flask, request, jsonify
from functools import wraps
from typing import Dict, Any, List
from datetime import datetime, timedelta
import vertexai
from vertexai.generative_models import GenerativeModel, Tool
from vertexai.preview.generative_models import grounding
from vertexai.preview import caching
import requests

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

SERVICE_API_KEY = os.getenv('SERVICE_API_KEY')
VERTEX_PROJECT = os.getenv('PROJECT_ID') or os.getenv('VERTEX_PROJECT')
VERTEX_LOCATION = os.getenv('VERTEX_AI_LOCATION') or os.getenv('VERTEX_LOCATION', 'us-west1')
FMP_PROXY_URL = os.getenv('FMP_PROXY_URL', 'http://fmp-api-proxy:8080')

class PrecedentTransactionsAnalyzer:
    """Uses Gemini 2.5 Pro with Google Search grounding for deal comps"""

    def __init__(self):
        self.google_search_tool = None
        self.model = None
        self.vertex_initialized = False

    def _ensure_initialized(self):
        """Initialize Vertex AI on first use"""
        if not self.vertex_initialized and VERTEX_PROJECT:
            try:
                vertexai.init(project=VERTEX_PROJECT, location=VERTEX_LOCATION)
                self.google_search_tool = Tool.from_google_search_retrieval(
                    grounding.GoogleSearchRetrieval()
                )

                self.model = GenerativeModel(
                    'gemini-2.5-pro',
                    system_instruction="""
You are an M&A analyst specializing in precedent transaction analysis.
Use Google Search to find recent M&A deals in the target's industry.
Focus on: deal size, multiples, premiums, strategic rationale.
Always cite sources and calculate metrics precisely.
"""
                )
                self.vertex_initialized = True
                logger.info("Vertex AI initialized successfully for precedent transactions")
            except Exception as e:
                logger.error(f"Failed to initialize Vertex AI: {e}")
                self.vertex_initialized = False

    def analyze_precedent_transactions(self, target_symbol: str, target_industry: str,
                                       target_size: float, run_cache_name: str = None) -> dict:
        """Find and analyze comparable M&A transactions"""

        logger.info(f"Analyzing precedent transactions for {target_symbol}")

        # Ensure Vertex AI is initialized
        self._ensure_initialized()

        if not self.vertex_initialized or not self.model:
            error_msg = "Vertex AI not initialized - cannot perform precedent transactions analysis"
            logger.error(error_msg)
            raise RuntimeError(error_msg)

        # Define FMP API function calling
        fmp_tools = Tool(function_declarations=[
            {
                "name": "search_ma_deals",
                "description": "Search M&A deals via FMP API",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "industry": {"type": "string", "description": "Industry sector"},
                        "from_date": {"type": "string", "description": "Start date YYYY-MM-DD"},
                        "to_date": {"type": "string", "description": "End date YYYY-MM-DD"}
                    }
                }
            },
            {
                "name": "get_company_profile",
                "description": "Get company profile from FMP",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "symbol": {"type": "string", "description": "Stock symbol"}
                    },
                    "required": ["symbol"]
                }
            }
        ])

        # Use cached context if available
        if run_cache_name:
            try:
                cache = caching.CachedContent(name=run_cache_name)
                model = GenerativeModel.from_cached_content(cached_content=cache)
            except:
                model = self.model
        else:
            model = self.model

        prompt = f"""
Find and analyze precedent transactions comparable to {target_symbol}.

Target Profile:
- Industry: {target_industry}
- Market Cap: ${target_size:,.0f}

PROCESS:
1. Use Google Search to find recent M&A deals (last 3 years) in {target_industry}
2. Call search_ma_deals function to get structured data
3. Filter deals by size (50%-200% of target)
4. For each deal, analyze:
   - Deal value and structure
   - EV/Revenue and EV/EBITDA multiples
   - Premium to unaffected price (1-day, 30-day)
   - Strategic vs financial buyer
5. Use code execution to calculate summary statistics

Return JSON:
{{
  "comparable_deals": [
    {{
      "target": "Company",
      "acquirer": "Company",
      "announce_date": "YYYY-MM-DD",
      "deal_value": 0,
      "ev_revenue": 0,
      "ev_ebitda": 0,
      "premium_1day": 0,
      "premium_30day": 0,
      "buyer_type": "strategic|financial",
      "source": "citation"
    }}
  ],
  "multiples_summary": {{
    "ev_revenue_median": 0,
    "ev_ebitda_median": 0,
    "premium_median": 0
  }},
  "our_target_implications": {{
    "implied_ev_low": 0,
    "implied_ev_high": 0,
    "implied_price_range": "X-Y"
  }}
}}
"""

        try:
            response = model.generate_content(
                prompt,
                tools=[self.google_search_tool, fmp_tools, {'code_execution': {}}],
                generation_config={'response_mime_type': 'application/json', 'temperature': 0.2}
            )

            # Handle function calls
            if response.candidates and response.candidates[0].content.parts:
                first_part = response.candidates[0].content.parts[0]
                if hasattr(first_part, 'function_call'):
                    function_responses = self._execute_function_calls(response)
                    response = model.generate_content(
                        [prompt, response.candidates[0].content, function_responses],
                        tools=[{'code_execution': {}}],
                        generation_config={'response_mime_type': 'application/json'}
                    )

            result = json.loads(response.text)
            result['analyzed_at'] = datetime.now().isoformat()
            return result

        except Exception as e:
            logger.error(f"Error analyzing precedents: {e}")
            return self._generate_basic_analysis(target_symbol, target_industry, target_size)

    def _execute_function_calls(self, response):
        """Execute FMP API function calls"""
        from vertexai.generative_models import Part

        responses = []
        for part in response.candidates[0].content.parts:
            if hasattr(part, 'function_call') and part.function_call:
                name = part.function_call.name
                args = dict(part.function_call.args)

                if name == 'search_ma_deals':
                    result = self._search_ma_deals_fmp(args)
                elif name == 'get_company_profile':
                    result = self._get_company_profile_fmp(args)
                else:
                    result = {'error': f'Unknown function: {name}'}

                responses.append(Part.from_function_response(name=name, response={"result": result}))

        return responses[0] if responses else None

    def _search_ma_deals_fmp(self, args: dict) -> dict:
        """Search M&A deals via FMP proxy"""
        try:
            headers = {'X-API-Key': SERVICE_API_KEY}
            response = requests.get(f"{FMP_PROXY_URL}/ma-deals", params=args, headers=headers, timeout=30)
            return response.json() if response.status_code == 200 else {'error': 'FMP API error'}
        except Exception as e:
            return {'error': str(e)}

    def _get_company_profile_fmp(self, args: dict) -> dict:
        """Get company profile via FMP proxy"""
        try:
            headers = {'X-API-Key': SERVICE_API_KEY}
            response = requests.get(f"{FMP_PROXY_URL}/profile/{args['symbol']}", headers=headers, timeout=30)
            return response.json() if response.status_code == 200 else {'error': 'FMP API error'}
        except Exception as e:
            return {'error': str(e)}

    def _generate_basic_analysis(self, target_symbol: str, target_industry: str, target_size: float) -> dict:
        """Basic analysis fallback"""
        return {
            'comparable_deals': [],
            'multiples_summary': {},
            'our_target_implications': {},
            'analyzed_at': datetime.now().isoformat(),
            'status': 'basic'
        }

analyzer = PrecedentTransactionsAnalyzer()

def require_api_key(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if request.headers.get('X-API-Key') != SERVICE_API_KEY:
            return jsonify({'error': 'Invalid API key'}), 401
        return f(*args, **kwargs)
    return decorated

@app.route('/health', methods=['GET'])
def health():
    return jsonify({'status': 'healthy', 'service': 'precedent-transactions', 'version': '1.0.0'})

@app.route('/analyze', methods=['POST'])
@require_api_key
def analyze():
    try:
        data = request.get_json()
        result = analyzer.analyze_precedent_transactions(
            target_symbol=data.get('target_symbol'),
            target_industry=data.get('target_industry'),
            target_size=data.get('target_size', 0),
            run_cache_name=data.get('run_cache_name')
        )
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error: {e}")
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.getenv('PORT', 8080)))
