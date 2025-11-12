"""
QA Engine Service
Automated validation of financial models and M&A analysis outputs
Uses Gemini 2.5 Pro Code Execution for comprehensive checks
"""

import os
import json
import logging
from flask import Flask, request, jsonify
from functools import wraps
from typing import Dict, Any
from datetime import datetime
import vertexai
from vertexai.generative_models import GenerativeModel
from vertexai.preview import caching

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

SERVICE_API_KEY = os.getenv('SERVICE_API_KEY')
VERTEX_PROJECT = os.getenv('VERTEX_PROJECT')
VERTEX_LOCATION = os.getenv('VERTEX_LOCATION', 'us-central1')

vertexai.init(project=VERTEX_PROJECT, location=VERTEX_LOCATION)

class QAEngine:
    """Uses Gemini 2.5 Pro Code Execution for automated QA"""
    
    def __init__(self):
        self.model = GenerativeModel(
            'gemini-2.5-pro',
            system_instruction="""
You are a quality assurance specialist for financial models.
Use code execution to validate all calculations and check for errors.
Be thorough and precise - financial accuracy is critical.

Your responsibilities:
1. Validate model integrity (balance sheets, cash flows)
2. Check valuation consistency
3. Verify calculation accuracy
4. Map citations to sources
5. Identify and report all errors
"""
        )
    
    def validate_analysis(self, analysis_data: dict, run_cache_name: str = None) -> dict:
        """Comprehensive QA validation using code execution"""
        
        logger.info("Performing QA validation on analysis")
        
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
Perform comprehensive QA validation on this M&A analysis.

VALIDATION CHECKS (use code execution for all):

1. MODEL INTEGRITY:
   - Balance sheet: Assets = Liabilities + Equity (all periods)
   - Cash flow: NI + D&A - ΔWC - CapEx = FCF
   - Income statement: Revenue → EBIT → Net Income flows
   - No circular references

2. VALUATION CONSISTENCY:
   - Enterprise Value = Equity Value + Net Debt
   - DCF components: PV(FCF) + PV(Terminal) = EV
   - Sensitivity tables: Calculate all cells correctly
   - Cross-method sanity: DCF ~= CCA range

3. DATA QUALITY:
   - No #DIV/0!, #REF!, #VALUE! errors
   - All percentages between -100% and +500%
   - Growth rates realistic (<100% annually)
   - Margins within industry norms

4. CITATION TRACEABILITY:
   - Every key assumption → source reference
   - All multiples → comparable company
   - Terminal growth → industry analysis

5. CALCULATION ERRORS:
   - WACC calculation correct
   - Terminal value math validates
   - Accretion/dilution % matches

Analysis Data:
{json.dumps(analysis_data, indent=2)[:50000]}

Return structured JSON:
{{
  "critical_errors": [],
  "warnings": [],
  "model_integrity_checks": {{}},
  "valuation_consistency": {{}},
  "data_quality": {{}},
  "citation_coverage": 0.0,
  "overall_qa_score": 0,
  "pass_fail": "PASS|FAIL",
  "recommendations": []
}}
"""
        
        try:
            response = model.generate_content(
                prompt,
                tools=[{'code_execution': {}}],
                generation_config={
                    'response_mime_type': 'application/json',
                    'temperature': 0.0  # Deterministic for QA
                }
            )
            
            qa_result = json.loads(response.text)
            qa_result['validated_at'] = datetime.now().isoformat()
            
            # If critical errors, generate fixes
            if qa_result.get('critical_errors'):
                fix_prompt = f"""
Generate Python code to fix these critical errors:
{json.dumps(qa_result['critical_errors'], indent=2)}

Provide executable Python that corrects the issues.
Include clear comments explaining each fix.
"""
                
                fix_response = model.generate_content(
                    fix_prompt,
                    tools=[{'code_execution': {}}]
                )
                
                qa_result['suggested_fixes'] = fix_response.text
            
            return qa_result
            
        except Exception as e:
            logger.error(f"Error in QA validation: {e}")
            return {
                'critical_errors': [{'error': str(e)}],
                'pass_fail': 'ERROR',
                'error': str(e)
            }

qa_engine = QAEngine()

def require_api_key(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if request.headers.get('X-API-Key') != SERVICE_API_KEY:
            return jsonify({'error': 'Invalid API key'}), 401
        return f(*args, **kwargs)
    return decorated

@app.route('/health', methods=['GET'])
def health():
    return jsonify({'status': 'healthy', 'service': 'qa-engine', 'version': '1.0.0'})

@app.route('/validate', methods=['POST'])
@require_api_key
def validate():
    try:
        data = request.get_json()
        result = qa_engine.validate_analysis(
            analysis_data=data.get('analysis_data', {}),
            run_cache_name=data.get('run_cache_name')
        )
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error: {e}")
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.getenv('PORT', 8080)))
