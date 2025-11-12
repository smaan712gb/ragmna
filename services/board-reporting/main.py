"""
Board Reporting Service
Generates board-ready Excel, PowerPoint, and PDF reports
Uses Gemini 2.5 Pro Code Execution for document generation
"""

import os
import json
import logging
from flask import Flask, request, jsonify, send_file
from functools import wraps
from typing import Dict, Any
from datetime import datetime
import io
import vertexai
from vertexai.generative_models import GenerativeModel
from vertexai.preview import caching

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

SERVICE_API_KEY = os.getenv('SERVICE_API_KEY')
VERTEX_PROJECT = os.getenv('VERTEX_PROJECT')
VERTEX_LOCATION = os.getenv('VERTEX_AI_LOCATION') or os.getenv('VERTEX_LOCATION', 'us-west1')

class BoardReportGenerator:
    """Uses Gemini 2.5 Pro Code Execution to generate board-ready reports"""

    def __init__(self):
        self.model = None
        self.vertex_initialized = False

    def _ensure_initialized(self):
        """Initialize Vertex AI on first use"""
        if not self.vertex_initialized and VERTEX_PROJECT:
            try:
                vertexai.init(project=VERTEX_PROJECT, location=VERTEX_LOCATION)
                self.model = GenerativeModel(
                    'gemini-2.5-pro',
                    system_instruction="""
You are an executive report writer for M&A transactions.
Focus on clarity, precision, and board-level presentation.
Use code execution to generate Excel, PowerPoint, and charts.

Your outputs must be:
- Professional and polished
- Accurate and well-cited
- Clear and actionable
- Board-ready quality
"""
                )
                self.vertex_initialized = True
                logger.info("Vertex AI initialized successfully for board reporting")
            except Exception as e:
                logger.error(f"Failed to initialize Vertex AI: {e}")
                self.vertex_initialized = False
    
    def generate_board_package(self, analysis_data: dict, run_cache_name: str = None) -> dict:
        """Generate complete board reporting package"""

        logger.info("Generating board reporting package")

        # Ensure Vertex AI is initialized
        self._ensure_initialized()

        # Use cached context if available
        if run_cache_name:
            try:
                cache = caching.CachedContent(name=run_cache_name)
                model = GenerativeModel.from_cached_content(cached_content=cache)
            except:
                model = self.model
        else:
            model = self.model
        
        # 1. Generate Executive Summary
        exec_summary = self._generate_executive_summary(model, analysis_data)
        
        # 2. Generate Excel Model
        excel_code = self._generate_excel_model_code(model, analysis_data)
        
        # 3. Generate PowerPoint
        ppt_code = self._generate_powerpoint_code(model, analysis_data)
        
        return {
            'executive_summary': exec_summary,
            'excel_generation_code': excel_code,
            'powerpoint_generation_code': ppt_code,
            'generated_at': datetime.now().isoformat(),
            'status': 'complete'
        }
    
    def _generate_executive_summary(self, model: GenerativeModel, data: dict) -> str:
        """Generate executive summary"""
        
        prompt = f"""
Write an executive summary for this M&A analysis.

Target: {data.get('target_symbol')}
Acquirer: {data.get('acquirer_symbol')}

Structure (2 pages max):
1. Transaction Overview (1 paragraph)
2. Strategic Rationale (1 paragraph)  
3. Valuation Summary (table format)
4. Key Risks (bullet points)
5. Recommendation (clear verdict)

Style: Board-level, clear, decisive.
Return as Markdown with proper formatting.
"""
        
        try:
            response = model.generate_content(prompt, generation_config={'temperature': 0.3})
            return response.text
        except Exception as e:
            logger.error(f"Error generating executive summary: {e}")
            return f"# Executive Summary\n\nError generating summary: {str(e)}"
    
    def _generate_excel_model_code(self, model: GenerativeModel, data: dict) -> str:
        """Generate Python code to create Excel model"""
        
        prompt = f"""
Generate Python code using openpyxl to create a comprehensive Excel workbook.

WORKSHEETS TO CREATE:
1. Summary - Key metrics & valuation
2. Assumptions - All inputs
3. Income Statement - Historical + Projections  
4. Balance Sheet - Historical + Projections
5. Cash Flow - Historical + Projections
6. DCF Analysis - WACC, FCF, Terminal Value
7. Comparable Companies - Multiples table
8. Precedent Transactions - Deal comps
9. Sensitivities - WACC/Growth grids

FORMATTING REQUIREMENTS:
- Headers: Bold, blue background (#4472C4)
- Currency: $#,##0
- Percentages: 0.0%
- Input cells: Yellow background (#FFF2CC)
- Formula cells: White
- Borders on all tables

Analysis Data:
{json.dumps(data, indent=2)[:30000]}

Generate complete Python code that:
1. Imports openpyxl
2. Creates workbook with all sheets
3. Populates data and formulas
4. Applies formatting
5. Saves to BytesIO object
6. Returns bytes

Make code production-ready and well-commented.
"""
        
        try:
            response = model.generate_content(
                prompt,
                tools=[{'code_execution': {}}],
                generation_config={'temperature': 0.1}
            )
            return response.text
        except Exception as e:
            logger.error(f"Error generating Excel code: {e}")
            return f"# Error: {str(e)}"
    
    def _generate_powerpoint_code(self, model: GenerativeModel, data: dict) -> str:
        """Generate Python code to create PowerPoint presentation"""
        
        prompt = f"""
Generate Python code using python-pptx to create a board presentation.

SLIDES TO CREATE (15-20):
1. Title - Transaction overview
2. Executive Summary
3-4. Company Profiles (Target & Acquirer)
5-6. Strategic Rationale
7-8. Financial Projections
9-10. Valuation Analysis (all methods)
11-12. Merger Impact (accretion/dilution)
13-14. Key Risks
15. Recommendation

DESIGN:
- Professional template
- Charts inline (use matplotlib, convert to images)
- Bullet points concise
- Citations in footnotes

Analysis Data:
{json.dumps(data, indent=2)[:30000]}

Generate complete Python code that:
1. Imports python-pptx and matplotlib
2. Creates presentation
3. Adds all slides with content
4. Embeds charts
5. Saves to BytesIO
6. Returns bytes

Make code production-ready.
"""
        
        try:
            response = model.generate_content(
                prompt,
                tools=[{'code_execution': {}}],
                generation_config={'temperature': 0.1}
            )
            return response.text
        except Exception as e:
            logger.error(f"Error generating PowerPoint code: {e}")
            return f"# Error: {str(e)}"

report_gen = BoardReportGenerator()

def require_api_key(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if request.headers.get('X-API-Key') != SERVICE_API_KEY:
            return jsonify({'error': 'Invalid API key'}), 401
        return f(*args, **kwargs)
    return decorated

@app.route('/health', methods=['GET'])
def health():
    return jsonify({'status': 'healthy', 'service': 'board-reporting', 'version': '1.0.0'})

@app.route('/generate', methods=['POST'])
@require_api_key
def generate():
    try:
        # For now, return a mock response to test deployment
        return jsonify({
            'executive_summary': '# Executive Summary\n\nMock summary for deployment testing.',
            'excel_generation_code': '# Mock Excel code',
            'powerpoint_generation_code': '# Mock PowerPoint code',
            'generated_at': datetime.now().isoformat(),
            'status': 'mock_complete'
        })
    except Exception as e:
        logger.error(f"Error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/executive-summary', methods=['POST'])
@require_api_key
def exec_summary():
    try:
        data = request.get_json()

        # Ensure Vertex AI is initialized
        report_gen._ensure_initialized()

        if data.get('run_cache_name'):
            cache = caching.CachedContent(name=data['run_cache_name'])
            model = GenerativeModel.from_cached_content(cached_content=cache)
        else:
            model = report_gen.model

        summary = report_gen._generate_executive_summary(model, data.get('analysis_data', {}))
        return jsonify({'summary': summary})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.getenv('PORT', 8080)))
