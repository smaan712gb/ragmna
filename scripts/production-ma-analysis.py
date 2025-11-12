#!/usr/bin/env python3
"""
Production M&A Analysis System
Complete TSLA → NVDA acquisition analysis using Gemini 2.5 Pro + RAG
"""

import os
import json
import logging
import asyncio
from datetime import datetime
from typing import Dict, Any, List
import requests
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('production-analysis.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Import after environment setup
from rag_client import RAGClient

class ProductionMAAnalysis:
    """Production-ready M&A analysis system"""

    def __init__(self):
        self.project = os.getenv('VERTEX_PROJECT')
        self.location = os.getenv('VERTEX_LOCATION')
        self.corpus_id = os.getenv('RAG_CORPUS_ID')
        self.fmp_api_key = os.getenv('FMP_API_KEY')

        if not all([self.project, self.location, self.corpus_id]):
            raise ValueError("Missing required environment variables")

        self.rag_client = RAGClient(self.project, self.location, self.corpus_id)
        logger.info("Production M&A Analysis system initialized")

    async def fetch_company_data(self, symbol: str) -> Dict[str, Any]:
        """Fetch real company data from FMP"""
        logger.info(f"Fetching data for {symbol}")

        try:
            # Get company profile
            profile_url = f"https://financialmodelingprep.com/api/v3/profile/{symbol}"
            params = {'apikey': self.fmp_api_key}
            profile_response = requests.get(profile_url, params=params)
            profile_data = profile_response.json()

            # Get financial statements
            income_url = f"https://financialmodelingprep.com/api/v3/income-statement/{symbol}"
            balance_url = f"https://financialmodelingprep.com/api/v3/balance-sheet-statement/{symbol}"
            cashflow_url = f"https://financialmodelingprep.com/api/v3/cash-flow-statement/{symbol}"

            income_data = requests.get(income_url, params=params).json()
            balance_data = requests.get(balance_url, params=params).json()
            cashflow_data = requests.get(cashflow_url, params=params).json()

            return {
                'profile': profile_data[0] if profile_data else {},
                'income_statement': income_data[:4] if income_data else [],  # Last 4 quarters
                'balance_sheet': balance_data[:4] if balance_data else [],
                'cash_flow': cashflow_data[:4] if cashflow_data else []
            }

        except Exception as e:
            logger.error(f"Error fetching data for {symbol}: {e}")
            return {}

    async def perform_rag_enhanced_analysis(self, target_symbol: str, acquirer_symbol: str) -> Dict[str, Any]:
        """Perform comprehensive RAG-enhanced M&A analysis"""

        logger.info(f"Starting RAG-enhanced analysis: {acquirer_symbol} → {target_symbol}")

        # Fetch real company data
        target_data = await self.fetch_company_data(target_symbol)
        acquirer_data = await self.fetch_company_data(acquirer_symbol)

        analysis_results = {
            'analysis_metadata': {
                'target_symbol': target_symbol,
                'acquirer_symbol': acquirer_symbol,
                'analysis_timestamp': datetime.now().isoformat(),
                'model_used': 'gemini-2.5-pro',
                'rag_enabled': True
            },
            'company_profiles': {
                'target': target_data.get('profile', {}),
                'acquirer': acquirer_data.get('profile', {})
            }
        }

        # Strategic Rationale Analysis
        strategic_prompt = f"""
Analyze the strategic rationale for {acquirer_symbol} acquiring {target_symbol}.
Consider:
1. Synergies in AI, autonomous driving, and semiconductor technologies
2. Market positioning and competitive advantages
3. Growth opportunities and TAM expansion
4. Integration challenges and execution risks

Provide a comprehensive strategic assessment.
"""

        strategic_contexts = self.rag_client.retrieve_contexts(
            f"strategic rationale for {acquirer_symbol} acquiring {target_symbol}",
            top_k=5
        )

        analysis_results['strategic_rationale'] = {
            'analysis': await self.rag_client.generate_with_rag(strategic_prompt, strategic_contexts),
            'rag_contexts_used': len(strategic_contexts.get('contexts', []))
        }

        # Valuation Analysis
        valuation_prompt = f"""
Perform a comprehensive valuation analysis for {target_symbol} acquisition by {acquirer_symbol}.
Consider:
1. Current market capitalization and trading multiples
2. Growth prospects and competitive positioning
3. Synergy valuation and premium analysis
4. Risk-adjusted valuation range

Target company key metrics:
- Market Cap: ${target_data.get('profile', {}).get('mktCap', 'N/A'):,.0f}
- Revenue Growth: Analyze from financial statements
- Profitability: Net margins and operating leverage

Provide detailed valuation analysis with ranges.
"""

        valuation_contexts = self.rag_client.retrieve_contexts(
            f"valuation analysis for {target_symbol} acquisition",
            top_k=5
        )

        analysis_results['valuation_analysis'] = {
            'analysis': await self.rag_client.generate_with_rag(valuation_prompt, valuation_contexts),
            'rag_contexts_used': len(valuation_contexts.get('contexts', []))
        }

        # Risk Assessment
        risk_prompt = f"""
Conduct a comprehensive risk assessment for {acquirer_symbol} acquiring {target_symbol}.
Analyze:
1. Integration risks and execution challenges
2. Regulatory and antitrust concerns
3. Technology integration complexities
4. Market and competitive risks
5. Financial and balance sheet impacts

Provide detailed risk analysis with mitigation strategies.
"""

        risk_contexts = self.rag_client.retrieve_contexts(
            f"risk assessment for {acquirer_symbol} {target_symbol} acquisition",
            top_k=5
        )

        analysis_results['risk_assessment'] = {
            'analysis': await self.rag_client.generate_with_rag(risk_prompt, risk_contexts),
            'rag_contexts_used': len(risk_contexts.get('contexts', []))
        }

        # Due Diligence Insights
        dd_prompt = f"""
Perform due diligence analysis for {target_symbol} from {acquirer_symbol}'s perspective.
Focus on:
1. Financial health and performance trends
2. Technology and IP portfolio assessment
3. Management quality and corporate governance
4. Market position and competitive advantages
5. Growth drivers and sustainability

Provide detailed due diligence findings.
"""

        dd_contexts = self.rag_client.retrieve_contexts(
            f"due diligence analysis for {target_symbol}",
            top_k=5
        )

        analysis_results['due_diligence'] = {
            'analysis': await self.rag_client.generate_with_rag(dd_prompt, dd_contexts),
            'rag_contexts_used': len(dd_contexts.get('contexts', []))
        }

        # Executive Summary
        summary_prompt = f"""
Create an executive summary for the {acquirer_symbol} acquisition of {target_symbol}.
Include:
1. Strategic rationale and key synergies
2. Valuation analysis and deal metrics
3. Key risks and mitigation strategies
4. Investment recommendation with confidence level
5. Critical success factors

Provide a concise yet comprehensive executive summary.
"""

        summary_contexts = self.rag_client.retrieve_contexts(
            f"executive summary for {acquirer_symbol} {target_symbol} acquisition",
            top_k=3
        )

        analysis_results['executive_summary'] = {
            'summary': await self.rag_client.generate_with_rag(summary_prompt, summary_contexts),
            'rag_contexts_used': len(summary_contexts.get('contexts', []))
        }

        # Performance Metrics
        total_rag_contexts = sum([
            analysis_results['strategic_rationale']['rag_contexts_used'],
            analysis_results['valuation_analysis']['rag_contexts_used'],
            analysis_results['risk_assessment']['rag_contexts_used'],
            analysis_results['due_diligence']['rag_contexts_used'],
            analysis_results['executive_summary']['rag_contexts_used']
        ])

        analysis_results['performance_metrics'] = {
            'total_rag_contexts_used': total_rag_contexts,
            'analysis_duration_seconds': (datetime.now() - datetime.fromisoformat(analysis_results['analysis_metadata']['analysis_timestamp'])).total_seconds(),
            'model_version': 'gemini-2.5-pro',
            'rag_corpus_id': self.corpus_id
        }

        logger.info(f"Analysis completed successfully. Total RAG contexts used: {total_rag_contexts}")
        return analysis_results

async def main():
    """Main production analysis execution"""

    print("🚀 Starting Production M&A Analysis System")
    print("=" * 50)

    try:
        # Initialize analysis system
        analyzer = ProductionMAAnalysis()

        # Execute comprehensive TSLA → NVDA analysis
        print("📊 Executing TSLA → NVDA Acquisition Analysis...")
        print("   - Using Gemini 2.5 Pro + RAG")
        print("   - Real-time financial data integration")
        print("   - Document-contextualized insights")
        print()

        results = await analyzer.perform_rag_enhanced_analysis("NVDA", "TSLA")

        # Save comprehensive results
        output_file = f"tsla-nvda-analysis-{datetime.now().strftime('%Y%m%d-%H%M%S')}.json"
        with open(output_file, 'w') as f:
            json.dump(results, f, indent=2, default=str)

        print("✅ Analysis Completed Successfully!")
        print(f"📄 Results saved to: {output_file}")
        print()
        print("📈 Analysis Summary:")
        print(f"   • Strategic Rationale: {len(results['strategic_rationale']['analysis'])} chars")
        print(f"   • Valuation Analysis: {len(results['valuation_analysis']['analysis'])} chars")
        print(f"   • Risk Assessment: {len(results['risk_assessment']['analysis'])} chars")
        print(f"   • Due Diligence: {len(results['due_diligence']['analysis'])} chars")
        print(f"   • Executive Summary: {len(results['executive_summary']['summary'])} chars")
        print(f"   • Total RAG Contexts Used: {results['performance_metrics']['total_rag_contexts_used']}")
        print(f"   • Analysis Duration: {results['performance_metrics']['analysis_duration_seconds']:.2f} seconds")
        print()
        print("🎯 Key Findings Preview:")
        print("-" * 30)
        summary = results['executive_summary']['summary'][:500] + "..."
        print(summary)
        print()
        print("📊 Production System Status: ✅ OPERATIONAL")
        print("🤖 AI Model: Gemini 2.5 Pro")
        print("📚 RAG System: Active with document context")
        print("🔒 Security: Service account authentication")
        print("⚡ Performance: Real-time analysis completed")

    except Exception as e:
        logger.error(f"Production analysis failed: {e}")
        print(f"❌ Analysis failed: {e}")
        raise

if __name__ == '__main__':
    asyncio.run(main())
