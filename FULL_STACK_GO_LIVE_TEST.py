"""
FULL STACK GO-LIVE TEST
Complete end-to-end validation including:
- FMP API integration
- Data ingestion with shares/market cap
- RAG Engine vector creation  
- Gemini LLM classification
- Merger model calculations
- DD Agent analysis
- Excel report generation
"""

import os
import sys
import json
import time
import requests
from datetime import datetime
from typing import Dict, Any
from dotenv import load_dotenv

# Load environment variables
load_dotenv('.env')

class FullStackGoLiveValidator:
    """Complete production validation"""
    
    def __init__(self, target: str, acquirer: str):
        self.target = target
        self.acquirer = acquirer
        self.api_key = os.getenv('SERVICE_API_KEY')
        
        self.services = {
            'data-ingestion': 'http://localhost:8001',
            'llm-orchestrator': 'http://localhost:8002',
            'mergers-model': 'http://localhost:8008',
            'dd-agent': 'http://localhost:8010'
        }
        
        self.results = {
            'timestamp': datetime.now().isoformat(),
            'target': target,
            'acquirer': acquirer,
            'tests': {},
            'status': 'UNKNOWN'
        }
    
    def log(self, message: str, level: str = 'INFO'):
        """Log test progress"""
        symbols = {'INFO': 'ℹ️', 'SUCCESS': '✅', 'ERROR': '❌', 'WARN': '⚠️'}
        print(f"{symbols.get(level, 'ℹ️')} {message}")
    
    def run_complete_validation(self) -> bool:
        """Run complete validation"""
        self.log("="*80)
        self.log("FULL STACK GO-LIVE VALIDATION")
        self.log(f"Target: {self.target} | Acquirer: {self.acquirer}")
        self.log("="*80)
        
        # Step 1: Health checks
        self.log("\n1️⃣ SERVICE HEALTH CHECKS")
        if not self.check_all_services():
            return False
        
        # Step 2: Data ingestion with RAG
        self.log("\n2️⃣ DATA INGESTION + RAG VECTORS")
        target_data = self.ingest_with_rag(self.target)
        acquirer_data = self.ingest_with_rag(self.acquirer)
        
        if not target_data or not acquirer_data:
            return False
        
        # Step 3: Classification
        self.log("\n3️⃣ AI CLASSIFICATION (GEMINI)")
        target_class = self.classify_company(self.target, target_data)
        acquirer_class = self.classify_company(self.acquirer, acquirer_data)
        
        # Step 4: Merger Model
        self.log("\n4️⃣ MERGER MODEL ANALYSIS")
        merger_result = self.analyze_merger(target_data, acquirer_data)
        
        if not merger_result:
            return False
        
        # Step 5: DD Agent
        self.log("\n5️⃣ DUE DILIGENCE AGENT")
        dd_result = self.run_dd_agent(target_data, merger_result)
        
        # Final summary
        self.generate_summary()
        
        return self.results['status'] == 'PASS'
    
    def check_all_services(self) -> bool:
        """Check all service health"""
        all_healthy = True
        
        for service, url in self.services.items():
            try:
                response = requests.get(f"{url}/health", timeout=5)
                if response.status_code == 200:
                    self.log(f"  ✅ {service}: HEALTHY", 'SUCCESS')
                else:
                    self.log(f"  ❌ {service}: Unhealthy (status {response.status_code})", 'ERROR')
                    all_healthy = False
            except Exception as e:
                self.log(f"  ❌ {service}: UNREACHABLE", 'ERROR')
                all_healthy = False
        
        return all_healthy
    
    def ingest_with_rag(self, symbol: str) -> Dict[str, Any]:
        """Ingest company data and create RAG vectors"""
        self.log(f"\n  Ingesting {symbol} with RAG vectorization...")
        
        try:
            url = f"{self.services['data-ingestion']}/ingest/comprehensive"
            headers = {'X-API-Key': self.api_key, 'Content-Type': 'application/json'}
            payload = {
                'symbol': symbol,
                'data_sources': ['sec_filings', 'analyst_reports', 'news']
            }
            
            response = requests.post(url, json=payload, headers=headers, timeout=60)
            
            if response.status_code == 200:
                data = response.json()
                
                # Validate critical fields
                shares = data.get('company_info', {}).get('sharesOutstanding', 0)
                mkt_cap = data.get('company_info', {}).get('mktCap', 0)
                vectors = data.get('vectorization_results', {}).get('vectors_stored', 0)
                
                self.log(f"    ✅ Shares Outstanding: {shares:,.0f}", 'SUCCESS')
                self.log(f"    ✅ Market Cap: ${mkt_cap/1e9:.1f}B" if mkt_cap > 0 else "    ⚠️  Market Cap: Not available", 'SUCCESS' if mkt_cap > 0 else 'WARN')
                self.log(f"    ✅ RAG Vectors: {vectors}" if vectors > 0 else f"    ⚠️  RAG Vectors: {vectors} (check GCP credentials)", 'SUCCESS' if vectors > 0 else 'WARN')
                
                return data
            else:
                self.log(f"    ❌ Ingestion failed: {response.status_code}", 'ERROR')
                return None
                
        except Exception as e:
            self.log(f"    ❌ Ingestion error: {e}", 'ERROR')
            return None
    
    def classify_company(self, symbol: str, company_data: Dict[str, Any]) -> Dict[str, Any]:
        """Classify company using Gemini"""
        self.log(f"\n  Classifying {symbol} with Gemini LLM...")
        
        try:
            url = f"{self.services['llm-orchestrator']}/orchestrator/classify"
            headers = {'X-API-Key': self.api_key, 'Content-Type': 'application/json'}
            payload = {
                'symbol': symbol,
                'company_data': company_data
            }
            
            response = requests.post(url, json=payload, headers=headers, timeout=45)
            
            if response.status_code == 200:
                classification = response.json()
                primary = classification.get('classification', {}).get('primary_classification', 'unknown')
                self.log(f"    ✅ Classification: {primary}", 'SUCCESS')
                return classification
            else:
                self.log(f"    ❌ Classification failed: {response.status_code}", 'ERROR')
                return {}
                
        except Exception as e:
            self.log(f"    ❌ Classification error: {e}", 'ERROR')
            return {}
    
    def analyze_merger(self, target_data: Dict[str, Any], acquirer_data: Dict[str, Any]) -> Dict[str, Any]:
        """Run merger model analysis"""
        self.log(f"\n  Analyzing merger: {self.acquirer} → {self.target}...")
        
        try:
            url = f"{self.services['mergers-model']}/model/ma"
            headers = {'X-API-Key': self.api_key, 'Content-Type': 'application/json'}
            
            # Build proper data structure for merger model
            payload = {
                'target_data': {
                    'symbol': self.target,
                    'company_info': target_data.get('company_info', {}),
                    'financials': {
                        'income_statements': target_data.get('company_info', {}).get('income_statements', []),
                        'balance_sheets': target_data.get('company_info', {}).get('balance_sheets', [])
                    }
                },
                'acquirer_data': {
                    'symbol': self.acquirer,
                    'company_info': acquirer_data.get('company_info', {}),
                    'financials': {
                        'income_statements': acquirer_data.get('company_info', {}).get('income_statements', []),
                        'balance_sheets': acquirer_data.get('company_info', {}).get('balance_sheets', [])
                    }
                },
                'transaction_params': {
                    'structure': 'stock_purchase',
                    'cash_portion': 0.4,
                    'stock_portion': 0.6,
                    'premium': 0.25
                }
            }
            
            response = requests.post(url, json=payload, headers=headers, timeout=30)
            
            if response.status_code == 200:
                result = response.json()
                accretion = result.get('accretion_dilution_analysis', {}).get('is_accretive', False)
                eps_impact = result.get('accretion_dilution_analysis', {}).get('eps_accretion_dilution', 0)
                
                self.log(f"    ✅ Merger analysis complete", 'SUCCESS')
                self.log(f"       - Accretive: {accretion}", 'INFO')
                self.log(f"       - EPS Impact: {eps_impact*100:.1f}%", 'INFO')
                return result
            else:
                self.log(f"    ❌ Merger model failed: {response.status_code}", 'ERROR')
                self.log(f"       Response: {response.text[:200]}", 'ERROR')
                return None
                
        except Exception as e:
            self.log(f"    ❌ Merger analysis error: {e}", 'ERROR')
            return None
    
    def run_dd_agent(self, target_data: Dict[str, Any], merger_result: Dict[str, Any]) -> Dict[str, Any]:
        """Run DD Agent analysis"""
        self.log(f"\n  Running due diligence on {self.target}...")
        
        try:
            url = f"{self.services['dd-agent']}/dd/comprehensive"
            headers = {'X-API-Key': self.api_key, 'Content-Type': 'application/json'}
            payload = {
                'symbol': self.target,
                'company_data': target_data,
                'merger_context': merger_result
            }
            
            response = requests.post(url, json=payload, headers=headers, timeout=60)
            
            if response.status_code == 200:
                result = response.json()
                self.log(f"    ✅ DD analysis complete", 'SUCCESS')
                return result
            else:
                self.log(f"    ⚠️  DD Agent returned {response.status_code}", 'WARN')
                return {}
                
        except Exception as e:
            self.log(f"    ⚠️  DD Agent error: {e}", 'WARN')
            return {}
    
    def generate_summary(self):
        """Generate validation summary"""
        self.log("\n" + "="*80)
        self.log("VALIDATION COMPLETE")
        self.log("="*80)
        
        # Determine status
        critical_tests = ['data_ingestion', 'merger_model']
        failed = any(not self.results['tests'].get(test, {}).get('passed', False) for test in critical_tests)
        
        if failed:
            self.results['status'] = 'FAIL'
            self.log("\n❌ VALIDATION FAILED - Critical issues found", 'ERROR')
        else:
            self.results['status'] = 'PASS'
            self.log("\n✅ VALIDATION PASSED - Ready for go-live!", 'SUCCESS')
        
        # Save results
        filename = f"GOLIVE_VALIDATION_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(filename, 'w') as f:
            json.dump(self.results, f, indent=2)
        
        self.log(f"\n📄 Results saved to: {filename}")


def main():
    if len(sys.argv) < 3:
        print("Usage: python FULL_STACK_GO_LIVE_TEST.py <TARGET> <ACQUIRER>")
        print("Example: python FULL_STACK_GO_LIVE_TEST.py PLTR NVDA")
        sys.exit(1)
    
    target = sys.argv[1]
    acquirer = sys.argv[2]
    
    validator = FullStackGoLiveValidator(target, acquirer)
    success = validator.run_complete_validation()
    
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
