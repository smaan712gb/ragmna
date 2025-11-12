"""
PRODUCTION AUDIT SCRIPT
Comprehensive system diagnostic to identify root causes and verify production readiness
"""

import os
import sys
import json
import time
import requests
from datetime import datetime
from typing import Dict, Any, List, Tuple
import subprocess

class ProductionAuditor:
    """Comprehensive production audit system"""
    
    def __init__(self):
        self.results = {
            'timestamp': datetime.now().isoformat(),
            'overall_status': 'UNKNOWN',
            'tests_passed': 0,
            'tests_failed': 0,
            'warnings': 0,
            'critical_issues': [],
            'detailed_results': {}
        }
        
        # Service URLs (mapped from docker-compose.yml)
        self.services = {
            'data-ingestion': 'http://localhost:8001',
            'llm-orchestrator': 'http://localhost:8002',
            'mergers-model': 'http://localhost:8008',
            'dd-agent': 'http://localhost:8010'
        }
        
        # Required environment variables
        self.required_env_vars = [
            'FMP_API_KEY',
            'SERVICE_API_KEY',
            'PROJECT_ID',
            'VERTEX_PROJECT',
            'VERTEX_LOCATION',
            'GOOGLE_APPLICATION_CREDENTIALS'
        ]
    
    def log(self, message: str, level: str = 'INFO'):
        """Log messages with timestamp"""
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        symbols = {
            'INFO': 'ℹ️',
            'SUCCESS': '✅',
            'WARNING': '⚠️',
            'ERROR': '❌',
            'TEST': '🔍'
        }
        symbol = symbols.get(level, 'ℹ️')
        print(f"[{timestamp}] {symbol} {message}")
    
    def run_audit(self) -> Dict[str, Any]:
        """Run complete system audit"""
        self.log("=" * 80, 'INFO')
        self.log("PRODUCTION AUDIT STARTING", 'INFO')
        self.log("=" * 80, 'INFO')
        
        # 1. Environment Variables
        self.log("\n1️⃣ CHECKING ENVIRONMENT VARIABLES", 'TEST')
        env_result = self.check_environment_variables()
        self.results['detailed_results']['environment'] = env_result
        
        # 2. Docker Services
        self.log("\n2️⃣ CHECKING DOCKER SERVICES", 'TEST')
        docker_result = self.check_docker_services()
        self.results['detailed_results']['docker'] = docker_result
        
        # 3. Service Health
        self.log("\n3️⃣ CHECKING SERVICE HEALTH", 'TEST')
        health_result = self.check_service_health()
        self.results['detailed_results']['health'] = health_result
        
        # 4. API Keys
        self.log("\n4️⃣ VALIDATING API KEYS", 'TEST')
        api_result = self.validate_api_keys()
        self.results['detailed_results']['api_keys'] = api_result
        
        # 5. GCP Authentication
        self.log("\n5️⃣ CHECKING GCP AUTHENTICATION", 'TEST')
        gcp_result = self.check_gcp_auth()
        self.results['detailed_results']['gcp_auth'] = gcp_result
        
        # 6. Data Ingestion Test
        self.log("\n6️⃣ TESTING DATA INGESTION", 'TEST')
        ingestion_result = self.test_data_ingestion()
        self.results['detailed_results']['data_ingestion'] = ingestion_result
        
        # 7. Classification Test
        self.log("\n7️⃣ TESTING CLASSIFICATION", 'TEST')
        classification_result = self.test_classification()
        self.results['detailed_results']['classification'] = classification_result
        
        # 8. Merger Model Test
        self.log("\n8️⃣ TESTING MERGER MODEL", 'TEST')
        merger_result = self.test_merger_model()
        self.results['detailed_results']['merger_model'] = merger_result
        
        # Calculate overall status
        self.calculate_overall_status()
        
        # Generate report
        self.generate_report()
        
        return self.results
    
    def check_environment_variables(self) -> Dict[str, Any]:
        """Check all required environment variables"""
        result = {
            'status': 'PASS',
            'missing': [],
            'present': [],
            'issues': []
        }
        
        for var in self.required_env_vars:
            value = os.getenv(var)
            if not value or value == '':
                self.log(f"❌ MISSING: {var}", 'ERROR')
                result['missing'].append(var)
                result['status'] = 'FAIL'
                self.results['critical_issues'].append(f"Missing environment variable: {var}")
            else:
                # Mask sensitive values
                if 'KEY' in var or 'SECRET' in var:
                    display_value = value[:8] + '...' if len(value) > 8 else '***'
                else:
                    display_value = value
                self.log(f"✅ FOUND: {var} = {display_value}", 'SUCCESS')
                result['present'].append(var)
        
        # Check optional but recommended
        optional_vars = ['RAG_CORPUS_ID', 'GCS_BUCKET', 'GOOGLE_CLOUD_KEY_PATH']
        for var in optional_vars:
            value = os.getenv(var)
            if not value:
                self.log(f"⚠️  OPTIONAL: {var} not set (may be needed for RAG)", 'WARNING')
                result['issues'].append(f"Optional var not set: {var}")
                self.results['warnings'] += 1
        
        if result['status'] == 'PASS':
            self.results['tests_passed'] += 1
        else:
            self.results['tests_failed'] += 1
        
        return result
    
    def check_docker_services(self) -> Dict[str, Any]:
        """Check Docker services are running"""
        result = {
            'status': 'PASS',
            'running': [],
            'not_running': [],
            'issues': []
        }
        
        try:
            # Get docker ps output
            output = subprocess.check_output(
                ['docker-compose', 'ps', '--format', 'json'],
                stderr=subprocess.STDOUT,
                text=True
            )
            
            # Parse docker services
            services_info = []
            for line in output.strip().split('\n'):
                if line.strip():
                    try:
                        services_info.append(json.loads(line))
                    except:
                        pass
            
            # Check each service
            expected_services = ['data-ingestion', 'llm-orchestrator', 'mergers-model', 'dd-agent']
            
            for service in expected_services:
                found = False
                for info in services_info:
                    if service in info.get('Name', '').lower():
                        found = True
                        state = info.get('State', 'unknown')
                        if state.lower() == 'running':
                            self.log(f"✅ {service}: RUNNING", 'SUCCESS')
                            result['running'].append(service)
                        else:
                            self.log(f"❌ {service}: {state}", 'ERROR')
                            result['not_running'].append(service)
                            result['status'] = 'FAIL'
                            self.results['critical_issues'].append(f"{service} is not running")
                        break
                
                if not found:
                    self.log(f"❌ {service}: NOT FOUND", 'ERROR')
                    result['not_running'].append(service)
                    result['status'] = 'FAIL'
                    self.results['critical_issues'].append(f"{service} container not found")
        
        except Exception as e:
            self.log(f"❌ Error checking Docker: {e}", 'ERROR')
            result['status'] = 'FAIL'
            result['issues'].append(f"Docker check failed: {str(e)}")
            self.results['critical_issues'].append(f"Cannot check Docker services: {str(e)}")
        
        if result['status'] == 'PASS':
            self.results['tests_passed'] += 1
        else:
            self.results['tests_failed'] += 1
        
        return result
    
    def check_service_health(self) -> Dict[str, Any]:
        """Check health endpoints of all services"""
        result = {
            'status': 'PASS',
            'healthy': [],
            'unhealthy': [],
            'unreachable': []
        }
        
        for service_name, base_url in self.services.items():
            health_url = f"{base_url}/health"
            try:
                response = requests.get(health_url, timeout=5)
                if response.status_code == 200:
                    self.log(f"✅ {service_name}: HEALTHY", 'SUCCESS')
                    result['healthy'].append(service_name)
                else:
                    self.log(f"❌ {service_name}: Status {response.status_code}", 'ERROR')
                    result['unhealthy'].append(service_name)
                    result['status'] = 'FAIL'
                    self.results['critical_issues'].append(f"{service_name} returned status {response.status_code}")
            except Exception as e:
                self.log(f"❌ {service_name}: UNREACHABLE - {str(e)}", 'ERROR')
                result['unreachable'].append(service_name)
                result['status'] = 'FAIL'
                self.results['critical_issues'].append(f"{service_name} is unreachable: {str(e)}")
        
        if result['status'] == 'PASS':
            self.results['tests_passed'] += 1
        else:
            self.results['tests_failed'] += 1
        
        return result
    
    def validate_api_keys(self) -> Dict[str, Any]:
        """Validate API keys actually work"""
        result = {
            'status': 'PASS',
            'valid': [],
            'invalid': [],
            'issues': []
        }
        
        # Test FMP API Key
        fmp_key = os.getenv('FMP_API_KEY')
        if fmp_key:
            try:
                test_url = f"https://financialmodelingprep.com/api/v3/profile/AAPL?apikey={fmp_key}"
                response = requests.get(test_url, timeout=10)
                if response.status_code == 200:
                    data = response.json()
                    if data and isinstance(data, list) and len(data) > 0:
                        self.log(f"✅ FMP_API_KEY: VALID", 'SUCCESS')
                        result['valid'].append('FMP_API_KEY')
                    else:
                        self.log(f"❌ FMP_API_KEY: Invalid response", 'ERROR')
                        result['invalid'].append('FMP_API_KEY')
                        result['status'] = 'FAIL'
                        self.results['critical_issues'].append("FMP API key returns invalid data")
                elif response.status_code == 401 or response.status_code == 403:
                    self.log(f"❌ FMP_API_KEY: INVALID (Status {response.status_code})", 'ERROR')
                    result['invalid'].append('FMP_API_KEY')
                    result['status'] = 'FAIL'
                    self.results['critical_issues'].append("FMP API key is invalid or expired")
                else:
                    self.log(f"⚠️  FMP_API_KEY: Unexpected status {response.status_code}", 'WARNING')
                    result['issues'].append(f"FMP API returned status {response.status_code}")
                    self.results['warnings'] += 1
            except Exception as e:
                self.log(f"❌ FMP_API_KEY: Test failed - {str(e)}", 'ERROR')
                result['invalid'].append('FMP_API_KEY')
                result['status'] = 'FAIL'
                self.results['critical_issues'].append(f"Cannot test FMP API: {str(e)}")
        else:
            self.log(f"❌ FMP_API_KEY: NOT SET", 'ERROR')
            result['invalid'].append('FMP_API_KEY')
            result['status'] = 'FAIL'
        
        # Test SERVICE_API_KEY exists
        service_key = os.getenv('SERVICE_API_KEY')
        if service_key:
            self.log(f"✅ SERVICE_API_KEY: SET", 'SUCCESS')
            result['valid'].append('SERVICE_API_KEY')
        else:
            self.log(f"❌ SERVICE_API_KEY: NOT SET", 'ERROR')
            result['invalid'].append('SERVICE_API_KEY')
            result['status'] = 'FAIL'
        
        if result['status'] == 'PASS':
            self.results['tests_passed'] += 1
        else:
            self.results['tests_failed'] += 1
        
        return result
    
    def check_gcp_auth(self) -> Dict[str, Any]:
        """Check GCP authentication"""
        result = {
            'status': 'PASS',
            'issues': []
        }
        
        # Check credentials file
        creds_path = os.getenv('GOOGLE_APPLICATION_CREDENTIALS')
        if creds_path and os.path.exists(creds_path):
            self.log(f"✅ Credentials file exists: {creds_path}", 'SUCCESS')
            
            # Try to read and validate
            try:
                with open(creds_path, 'r') as f:
                    creds_data = json.load(f)
                    if 'project_id' in creds_data:
                        self.log(f"✅ Credentials valid for project: {creds_data['project_id']}", 'SUCCESS')
                    else:
                        self.log(f"⚠️  Credentials file missing project_id", 'WARNING')
                        result['issues'].append("Credentials file missing project_id")
                        self.results['warnings'] += 1
            except Exception as e:
                self.log(f"❌ Error reading credentials: {e}", 'ERROR')
                result['status'] = 'FAIL'
                result['issues'].append(f"Cannot read credentials: {str(e)}")
                self.results['critical_issues'].append(f"GCP credentials file is invalid: {str(e)}")
        else:
            self.log(f"❌ Credentials file not found: {creds_path}", 'ERROR')
            result['status'] = 'FAIL'
            result['issues'].append("GOOGLE_APPLICATION_CREDENTIALS file not found")
            self.results['critical_issues'].append("GCP credentials file not found")
        
        # Check required GCP env vars
        project_id = os.getenv('PROJECT_ID')
        vertex_project = os.getenv('VERTEX_PROJECT')
        vertex_location = os.getenv('VERTEX_LOCATION')
        
        if project_id:
            self.log(f"✅ PROJECT_ID: {project_id}", 'SUCCESS')
        else:
            self.log(f"❌ PROJECT_ID not set", 'ERROR')
            result['status'] = 'FAIL'
        
        if vertex_project:
            self.log(f"✅ VERTEX_PROJECT: {vertex_project}", 'SUCCESS')
        else:
            self.log(f"❌ VERTEX_PROJECT not set", 'ERROR')
            result['status'] = 'FAIL'
        
        if vertex_location:
            self.log(f"✅ VERTEX_LOCATION: {vertex_location}", 'SUCCESS')
        else:
            self.log(f"❌ VERTEX_LOCATION not set", 'ERROR')
            result['status'] = 'FAIL'
        
        if result['status'] == 'PASS':
            self.results['tests_passed'] += 1
        else:
            self.results['tests_failed'] += 1
        
        return result
    
    def test_data_ingestion(self) -> Dict[str, Any]:
        """Test data ingestion service"""
        result = {
            'status': 'PASS',
            'test_symbol': 'AAPL',
            'shares_outstanding': 0,
            'issues': []
        }
        
        try:
            url = f"{self.services['data-ingestion']}/ingest/comprehensive"
            headers = {
                'X-API-Key': os.getenv('SERVICE_API_KEY'),
                'Content-Type': 'application/json'
            }
            payload = {
                'symbol': result['test_symbol'],
                'data_sources': ['sec_filings', 'analyst_reports']
            }
            
            self.log(f"Testing data ingestion for {result['test_symbol']}...", 'INFO')
            response = requests.post(url, json=payload, headers=headers, timeout=30)
            
            if response.status_code == 200:
                data = response.json()
                
                # Check shares outstanding
                shares = data.get('company_info', {}).get('sharesOutstanding', 0)
                result['shares_outstanding'] = shares
                
                if shares > 0:
                    self.log(f"✅ Data ingestion working - Shares: {shares:,.0f}", 'SUCCESS')
                else:
                    self.log(f"❌ Shares outstanding is 0 - CRITICAL BUG", 'ERROR')
                    result['status'] = 'FAIL'
                    result['issues'].append("Shares outstanding is 0")
                    self.results['critical_issues'].append("Data ingestion returns 0 shares outstanding")
                
                # Check other data
                sec_filings = len(data.get('fetched_data', {}).get('sec_filings', {}).get('filings', []))
                analyst_reports = data.get('fetched_data', {}).get('analyst_reports', {}).get('total_reports', 0)
                
                self.log(f"  - SEC filings: {sec_filings}", 'INFO')
                self.log(f"  - Analyst reports: {analyst_reports}", 'INFO')
                
                result['sec_filings'] = sec_filings
                result['analyst_reports'] = analyst_reports
            else:
                self.log(f"❌ Data ingestion failed - Status {response.status_code}", 'ERROR')
                self.log(f"  Response: {response.text[:200]}", 'ERROR')
                result['status'] = 'FAIL'
                result['issues'].append(f"HTTP {response.status_code}")
                self.results['critical_issues'].append(f"Data ingestion failed with status {response.status_code}")
        
        except Exception as e:
            self.log(f"❌ Data ingestion test failed: {e}", 'ERROR')
            result['status'] = 'FAIL'
            result['issues'].append(str(e))
            self.results['critical_issues'].append(f"Data ingestion test error: {str(e)}")
        
        if result['status'] == 'PASS':
            self.results['tests_passed'] += 1
        else:
            self.results['tests_failed'] += 1
        
        return result
    
    def test_classification(self) -> Dict[str, Any]:
        """Test classification service"""
        result = {
            'status': 'PASS',
            'test_symbol': 'AAPL',
            'classification': None,
            'issues': []
        }
        
        try:
            url = f"{self.services['llm-orchestrator']}/classify"
            headers = {
                'X-API-Key': os.getenv('SERVICE_API_KEY'),
                'Content-Type': 'application/json'
            }
            payload = {
                'symbol': result['test_symbol'],
                'company_data': {
                    'symbol': result['test_symbol'],
                    'companyName': 'Apple Inc.',
                    'industry': 'Technology',
                    'revenue': 394000000000,
                    'netIncome': 97000000000
                }
            }
            
            self.log(f"Testing classification for {result['test_symbol']}...", 'INFO')
            response = requests.post(url, json=payload, headers=headers, timeout=30)
            
            if response.status_code == 200:
                data = response.json()
                classification = data.get('classification', {})
                result['classification'] = classification
                
                primary = classification.get('primary_classification', '')
                if primary and primary != 'growth':  # 'growth' was the old default
                    self.log(f"✅ Classification working - Type: {primary}", 'SUCCESS')
                else:
                    self.log(f"⚠️  Classification may be using defaults", 'WARNING')
                    result['issues'].append("Using default classification")
                    self.results['warnings'] += 1
                
                self.log(f"  - Primary: {classification.get('primary_classification', 'N/A')}", 'INFO')
                self.log(f"  - Industry: {classification.get('industry_classification', 'N/A')}", 'INFO')
            else:
                self.log(f"❌ Classification failed - Status {response.status_code}", 'ERROR')
                self.log(f"  Response: {response.text[:200]}", 'ERROR')
                result['status'] = 'FAIL'
                result['issues'].append(f"HTTP {response.status_code}")
                self.results['critical_issues'].append(f"Classification failed with status {response.status_code}")
        
        except Exception as e:
            self.log(f"❌ Classification test failed: {e}", 'ERROR')
            result['status'] = 'FAIL'
            result['issues'].append(str(e))
            self.results['critical_issues'].append(f"Classification test error: {str(e)}")
        
        if result['status'] == 'PASS':
            self.results['tests_passed'] += 1
        else:
            self.results['tests_failed'] += 1
        
        return result
    
    def test_merger_model(self) -> Dict[str, Any]:
        """Test merger model service"""
        result = {
            'status': 'PASS',
            'test_target': 'AAPL',
            'test_acquirer': 'MSFT',
            'issues': []
        }
        
        try:
            url = f"{self.services['mergers-model']}/analyze"
            headers = {
                'X-API-Key': os.getenv('SERVICE_API_KEY'),
                'Content-Type': 'application/json'
            }
            
            # Create minimal test data with shares outstanding
            payload = {
                'target_symbol': result['test_target'],
                'acquirer_symbol': result['test_acquirer'],
                'target_data': {
                    'symbol': result['test_target'],
                    'companyName': 'Apple Inc.',
                    'sharesOutstanding': 15550061000,
                    'price': 180.0,
                    'mktCap': 2799010980000
                },
                'acquirer_data': {
                    'symbol': result['test_acquirer'],
                    'companyName': 'Microsoft Corporation',
                    'sharesOutstanding': 7433039000,
                    'price': 370.0,
                    'mktCap': 2750224430000
                },
                'deal_parameters': {
                    'consideration_type': 'stock',
                    'premium': 25.0
                }
            }
            
            self.log(f"Testing merger model: {result['test_acquirer']} → {result['test_target']}...", 'INFO')
            response = requests.post(url, json=payload, headers=headers, timeout=30)
            
            if response.status_code == 200:
                data = response.json()
                
                # Check for key outputs
                if 'exchange_ratio' in data or 'accretion_dilution' in data:
                    self.log(f"✅ Merger model working", 'SUCCESS')
                    if 'exchange_ratio' in data:
                        self.log(f"  - Exchange ratio: {data['exchange_ratio']}", 'INFO')
                else:
                    self.log(f"⚠️  Merger model returned incomplete data", 'WARNING')
                    result['issues'].append("Incomplete merger model output")
                    self.results['warnings'] += 1
            else:
                self.log(f"❌ Merger model failed - Status {response.status_code}", 'ERROR')
                self.log(f"  Response: {response.text[:200]}", 'ERROR')
                result['status'] = 'FAIL'
                result['issues'].append(f"HTTP {response.status_code}")
                self.results['critical_issues'].append(f"Merger model failed with status {response.status_code}")
        
        except Exception as e:
            self.log(f"❌ Merger model test failed: {e}", 'ERROR')
            result['status'] = 'FAIL'
            result['issues'].append(str(e))
            self.results['critical_issues'].append(f"Merger model test error: {str(e)}")
        
        if result['status'] == 'PASS':
            self.results['tests_passed'] += 1
        else:
            self.results['tests_failed'] += 1
        
        return result
    
    def calculate_overall_status(self):
        """Calculate overall system status"""
        if self.results['tests_failed'] > 0:
            self.results['overall_status'] = 'FAIL'
        elif self.results['warnings'] > 5:
            self.results['overall_status'] = 'WARNING'
        else:
            self.results['overall_status'] = 'PASS'
    
    def generate_report(self):
        """Generate final audit report"""
        self.log("\n" + "=" * 80, 'INFO')
        self.log("AUDIT COMPLETE", 'INFO')
        self.log("=" * 80, 'INFO')
        
        # Overall status
        status_symbol = {
            'PASS': '✅',
            'FAIL': '❌',
            'WARNING': '⚠️',
            'UNKNOWN': '❓'
        }
        symbol = status_symbol.get(self.results['overall_status'], '❓')
        
        self.log(f"\nOVERALL STATUS: {symbol} {self.results['overall_status']}", 'INFO')
        self.log(f"Tests Passed: {self.results['tests_passed']}", 'SUCCESS')
        self.log(f"Tests Failed: {self.results['tests_failed']}", 'ERROR')
        self.log(f"Warnings: {self.results['warnings']}", 'WARNING')
        
        # Critical issues
        if self.results['critical_issues']:
            self.log(f"\n🚨 CRITICAL ISSUES ({len(self.results['critical_issues'])}):", 'ERROR')
            for i, issue in enumerate(self.results['critical_issues'], 1):
                self.log(f"  {i}. {issue}", 'ERROR')
        
        # Save detailed results
        report_file = f"AUDIT_RESULTS_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(report_file, 'w') as f:
            json.dump(self.results, f, indent=2)
        
        self.log(f"\n📄 Detailed results saved to: {report_file}", 'INFO')
        
        # Recommendations
        self.log("\n📋 RECOMMENDATIONS:", 'INFO')
        if self.results['overall_status'] == '❌ FAIL':
            self.log("  1. Fix all critical issues listed above", 'ERROR')
            self.log("  2. Verify environment variables are set correctly", 'ERROR')
            self.log("  3. Check Docker services are running", 'ERROR')
            self.log("  4. Validate API keys and credentials", 'ERROR')
        elif self.results['overall_status'] == 'WARNING':
            self.log("  1. Review warnings and address if possible", 'WARNING')
            self.log("  2. System may be functional but not optimal", 'WARNING')
        else:
            self.log("  ✅ System is ready for production!", 'SUCCESS')


def main():
    """Main entry point"""
    auditor = ProductionAuditor()
    results = auditor.run_audit()
    
    # Exit with appropriate code
    if results['overall_status'] == 'FAIL':
        sys.exit(1)
    else:
        sys.exit(0)


if __name__ == '__main__':
    main()
