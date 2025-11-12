#!/usr/bin/env python3
"""
M&A Analysis Platform - Deployment and Integration Tests
Tests all services and end-to-end functionality
"""

import os
import json
import requests
import time
from typing import Dict, Any, List
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class MADeploymentTester:
    """Comprehensive testing suite for M&A Analysis Platform"""

    def __init__(self):
        self.base_urls = {
            'fmp_proxy': os.getenv('FMP_PROXY_URL', 'http://localhost:8081'),
            'llm_orchestrator': os.getenv('LLM_ORCHESTRATOR_URL', 'http://localhost:8082'),
            'three_statement': os.getenv('THREE_STATEMENT_URL', 'http://localhost:8083'),
            'dcf_valuation': os.getenv('DCF_VALUATION_URL', 'http://localhost:8084'),
            'cca_valuation': os.getenv('CCA_VALUATION_URL', 'http://localhost:8085'),
            'lbo_analysis': os.getenv('LBO_ANALYSIS_URL', 'http://localhost:8086'),
            'dd_agent': os.getenv('DD_AGENT_URL', 'http://localhost:8087'),
            'excel_exporter': os.getenv('EXCEL_EXPORTER_URL', 'http://localhost:8088'),
            'reporting': os.getenv('REPORTING_URL', 'http://localhost:8089'),
            'data_ingestion': os.getenv('DATA_INGESTION_URL', 'http://localhost:8090')
        }

        self.api_key = os.getenv('SERVICE_API_KEY', 'test-api-key')
        self.headers = {'X-API-Key': self.api_key, 'Content-Type': 'application/json'}

    def run_all_tests(self) -> Dict[str, Any]:
        """Run complete test suite"""

        logger.info("🚀 Starting M&A Analysis Platform Test Suite")

        results = {
            'health_checks': self.test_health_checks(),
            'service_integration': self.test_service_integration(),
            'end_to_end': self.test_end_to_end_workflow(),
            'performance': self.test_performance(),
            'security': self.test_security(),
            'timestamp': time.time()
        }

        # Generate test report
        self.generate_test_report(results)

        return results

    def test_health_checks(self) -> Dict[str, Any]:
        """Test health endpoints for all services"""

        logger.info("🔍 Testing service health checks")

        health_results = {}

        for service_name, url in self.base_urls.items():
            try:
                response = requests.get(f"{url}/health", timeout=10)
                if response.status_code == 200:
                    health_results[service_name] = {'status': 'healthy', 'response_time': response.elapsed.total_seconds()}
                else:
                    health_results[service_name] = {'status': 'unhealthy', 'status_code': response.status_code}
            except Exception as e:
                health_results[service_name] = {'status': 'error', 'error': str(e)}

        healthy_count = sum(1 for r in health_results.values() if r.get('status') == 'healthy')
        total_count = len(health_results)

        logger.info(f"Health check results: {healthy_count}/{total_count} services healthy")

        return {
            'results': health_results,
            'healthy_count': healthy_count,
            'total_count': total_count,
            'success_rate': healthy_count / total_count if total_count > 0 else 0
        }

    def test_service_integration(self) -> Dict[str, Any]:
        """Test integration between services"""

        logger.info("🔗 Testing service integration")

        integration_tests = {
            'fmp_proxy_data': self.test_fmp_proxy_data(),
            'company_classification': self.test_company_classification(),
            'financial_modeling': self.test_financial_modeling(),
            'valuation_methods': self.test_valuation_methods(),
            'due_diligence': self.test_due_diligence_integration()
        }

        return integration_tests

    def test_fmp_proxy_data(self) -> Dict[str, Any]:
        """Test FMP API proxy data retrieval"""

        try:
            # Test company profile
            response = requests.get(
                f"{self.base_urls['fmp_proxy']}/company/profile/AAPL",
                headers=self.headers,
                timeout=30
            )

            if response.status_code == 200:
                data = response.json()
                return {
                    'status': 'success',
                    'data_points': len(data) if isinstance(data, list) else 1,
                    'has_required_fields': 'companyName' in str(data)
                }
            else:
                return {'status': 'failed', 'status_code': response.status_code}

        except Exception as e:
            return {'status': 'error', 'error': str(e)}

    def test_company_classification(self) -> Dict[str, Any]:
        """Test company classification functionality"""

        try:
            response = requests.get(
                f"{self.base_urls['llm_orchestrator']}/classification/company/AAPL",
                headers=self.headers,
                timeout=60
            )

            if response.status_code == 200:
                data = response.json()
                return {
                    'status': 'success',
                    'classification': data.get('primary_classification'),
                    'confidence': data.get('confidence_score', 0)
                }
            else:
                return {'status': 'failed', 'status_code': response.status_code}

        except Exception as e:
            return {'status': 'error', 'error': str(e)}

    def test_financial_modeling(self) -> Dict[str, Any]:
        """Test financial modeling capabilities"""

        try:
            # Test 3-statement model generation
            test_data = {
                'company_data': {
                    'financials': {
                        'income_statements': [{'revenue': 100000000, 'netIncome': 10000000}],
                        'balance_sheets': [{'totalAssets': 200000000, 'totalLiabilities': 100000000}],
                        'cash_flow_statements': [{'operatingCashFlow': 15000000}]
                    }
                },
                'classification': {'primary_classification': 'growth'}
            }

            response = requests.post(
                f"{self.base_urls['three_statement']}/model/generate",
                json=test_data,
                headers=self.headers,
                timeout=120
            )

            if response.status_code == 200:
                data = response.json()
                return {
                    'status': 'success',
                    'projection_years': data.get('projection_years', 0),
                    'has_income_statement': 'income_statement' in data,
                    'has_balance_sheet': 'balance_sheet' in data
                }
            else:
                return {'status': 'failed', 'status_code': response.status_code}

        except Exception as e:
            return {'status': 'error', 'error': str(e)}

    def test_valuation_methods(self) -> Dict[str, Any]:
        """Test valuation method integrations"""

        valuation_tests = {}

        # Test DCF valuation
        try:
            test_data = {
                'company_data': {'market': {'marketCap': 1000000000}},
                'financial_model': {
                    'cash_flow_statement': [{'free_cash_flow': 50000000}]
                },
                'classification': {'primary_classification': 'growth'}
            }

            response = requests.post(
                f"{self.base_urls['dcf_valuation']}/valuation/dcf",
                json=test_data,
                headers=self.headers,
                timeout=60
            )

            valuation_tests['dcf'] = {
                'status': 'success' if response.status_code == 200 else 'failed',
                'status_code': response.status_code
            }

        except Exception as e:
            valuation_tests['dcf'] = {'status': 'error', 'error': str(e)}

        # Test CCA valuation
        try:
            test_data = {
                'company_data': {'market': {'marketCap': 1000000000}},
                'peers': [{'marketCap': 800000000, 'ev_revenue': 5.0}],
                'classification': {'primary_classification': 'growth'}
            }

            response = requests.post(
                f"{self.base_urls['cca_valuation']}/valuation/cca",
                json=test_data,
                headers=self.headers,
                timeout=60
            )

            valuation_tests['cca'] = {
                'status': 'success' if response.status_code == 200 else 'failed',
                'status_code': response.status_code
            }

        except Exception as e:
            valuation_tests['cca'] = {'status': 'error', 'error': str(e)}

        return valuation_tests

    def test_due_diligence_integration(self) -> Dict[str, Any]:
        """Test due diligence agent integration"""

        try:
            test_data = {
                'symbol': 'AAPL',
                'company_data': {
                    'profile': [{'companyName': 'Apple Inc.', 'sector': 'Technology'}],
                    'financials': {'income_statements': []},
                    'sec_filings': []
                }
            }

            response = requests.post(
                f"{self.base_urls['dd_agent']}/due-diligence/analyze",
                json=test_data,
                headers=self.headers,
                timeout=120
            )

            return {
                'status': 'success' if response.status_code == 200 else 'failed',
                'status_code': response.status_code,
                'has_risk_assessment': 'overall_assessment' in response.json() if response.status_code == 200 else False
            }

        except Exception as e:
            return {'status': 'error', 'error': str(e)}

    def test_end_to_end_workflow(self) -> Dict[str, Any]:
        """Test complete end-to-end M&A analysis workflow"""

        logger.info("🔄 Testing end-to-end M&A analysis workflow")

        try:
            # Test full M&A analysis
            test_data = {
                'target_symbol': 'AAPL',
                'acquirer_symbol': 'MSFT'
            }

            response = requests.post(
                f"{self.base_urls['llm_orchestrator']}/analysis/ma",
                json=test_data,
                headers=self.headers,
                timeout=300  # 5 minutes timeout
            )

            if response.status_code == 200:
                result = response.json()

                # Check for required components
                has_classification = 'classification' in result
                has_valuation = 'valuation' in result
                has_due_diligence = 'due_diligence' in result
                has_final_report = 'final_report' in result

                return {
                    'status': 'success',
                    'has_classification': has_classification,
                    'has_valuation': has_valuation,
                    'has_due_diligence': has_due_diligence,
                    'has_final_report': has_final_report,
                    'completeness_score': sum([has_classification, has_valuation, has_due_diligence, has_final_report]) / 4
                }
            else:
                return {
                    'status': 'failed',
                    'status_code': response.status_code,
                    'error': response.text[:200]
                }

        except Exception as e:
            return {'status': 'error', 'error': str(e)}

    def test_performance(self) -> Dict[str, Any]:
        """Test performance metrics"""

        logger.info("⚡ Testing performance metrics")

        performance_results = {}

        # Test response times for key endpoints
        endpoints_to_test = [
            ('fmp_proxy', '/company/profile/AAPL'),
            ('llm_orchestrator', '/classification/company/AAPL'),
            ('three_statement', '/health'),
            ('dcf_valuation', '/health'),
            ('cca_valuation', '/health')
        ]

        for service, endpoint in endpoints_to_test:
            try:
                url = f"{self.base_urls[service]}{endpoint}"
                start_time = time.time()
                response = requests.get(url, headers=self.headers, timeout=30)
                end_time = time.time()

                performance_results[f"{service}_{endpoint.replace('/', '_')}"] = {
                    'response_time': end_time - start_time,
                    'status_code': response.status_code,
                    'success': response.status_code == 200
                }

            except Exception as e:
                performance_results[f"{service}_{endpoint.replace('/', '_')}"] = {
                    'error': str(e),
                    'success': False
                }

        # Calculate average response time
        response_times = [r['response_time'] for r in performance_results.values()
                         if isinstance(r, dict) and 'response_time' in r]

        avg_response_time = sum(response_times) / len(response_times) if response_times else 0

        return {
            'endpoint_performance': performance_results,
            'average_response_time': avg_response_time,
            'performance_rating': 'good' if avg_response_time < 5 else 'fair' if avg_response_time < 15 else 'poor'
        }

    def test_security(self) -> Dict[str, Any]:
        """Test security configurations"""

        logger.info("🔒 Testing security configurations")

        security_tests = {}

        # Test API key requirement
        for service_name, url in self.base_urls.items():
            try:
                # Test without API key
                response = requests.get(f"{url}/health", timeout=10)
                if response.status_code == 401:
                    security_tests[f"{service_name}_auth"] = {'status': 'secure', 'blocks_unauthorized': True}
                else:
                    security_tests[f"{service_name}_auth"] = {'status': 'warning', 'blocks_unauthorized': False}

            except Exception as e:
                security_tests[f"{service_name}_auth"] = {'status': 'error', 'error': str(e)}

        # Test rate limiting (simplified)
        try:
            # Make multiple rapid requests
            responses = []
            for i in range(5):
                response = requests.get(
                    f"{self.base_urls['fmp_proxy']}/health",
                    headers=self.headers,
                    timeout=5
                )
                responses.append(response.status_code)
                time.sleep(0.1)  # Small delay

            rate_limited = 429 in responses
            security_tests['rate_limiting'] = {
                'status': 'effective' if rate_limited else 'not_tested',
                'rate_limited_requests': rate_limited
            }

        except Exception as e:
            security_tests['rate_limiting'] = {'status': 'error', 'error': str(e)}

        return security_tests

    def generate_test_report(self, results: Dict[str, Any]):
        """Generate comprehensive test report"""

        report = {
            'test_summary': {
                'total_tests': len(results),
                'passed_tests': sum(1 for r in results.values() if isinstance(r, dict) and r.get('status') == 'success'),
                'failed_tests': sum(1 for r in results.values() if isinstance(r, dict) and r.get('status') == 'failed'),
                'error_tests': sum(1 for r in results.values() if isinstance(r, dict) and r.get('status') == 'error')
            },
            'detailed_results': results,
            'recommendations': self.generate_recommendations(results),
            'generated_at': time.time()
        }

        # Save report
        with open('test_report.json', 'w') as f:
            json.dump(report, f, indent=2, default=str)

        logger.info("📊 Test report generated: test_report.json")

        # Print summary
        print("\n" + "="*60)
        print("M&A ANALYSIS PLATFORM - TEST RESULTS")
        print("="*60)
        print(f"Total Tests: {report['test_summary']['total_tests']}")
        print(f"Passed: {report['test_summary']['passed_tests']}")
        print(f"Failed: {report['test_summary']['failed_tests']}")
        print(f"Errors: {report['test_summary']['error_tests']}")
        print("\nKey Recommendations:")
        for rec in report['recommendations'][:5]:
            print(f"• {rec}")
        print("="*60)

    def generate_recommendations(self, results: Dict[str, Any]) -> List[str]:
        """Generate test-based recommendations"""

        recommendations = []

        # Health check recommendations
        health_results = results.get('health_checks', {})
        if health_results.get('success_rate', 0) < 0.8:
            recommendations.append("Improve service availability - some services are unhealthy")

        # Performance recommendations
        performance = results.get('performance', {})
        if performance.get('performance_rating') == 'poor':
            recommendations.append("Optimize service response times - current performance is poor")

        # Security recommendations
        security = results.get('security', {})
        insecure_services = [k for k, v in security.items() if isinstance(v, dict) and not v.get('blocks_unauthorized', True)]
        if insecure_services:
            recommendations.append(f"Strengthen authentication for services: {', '.join(insecure_services)}")

        # Integration recommendations
        integration = results.get('service_integration', {})
        failed_integrations = []
        for test_name, test_result in integration.items():
            if isinstance(test_result, dict) and test_result.get('status') != 'success':
                failed_integrations.append(test_name)

        if failed_integrations:
            recommendations.append(f"Fix service integrations: {', '.join(failed_integrations)}")

        # End-to-end recommendations
        e2e = results.get('end_to_end', {})
        if e2e.get('status') != 'success':
            recommendations.append("Complete end-to-end workflow implementation")

        if not recommendations:
            recommendations.append("All systems operational - continue monitoring")

        return recommendations

def main():
    """Main test execution"""

    # Check environment
    if not os.getenv('SERVICE_API_KEY'):
        logger.error("SERVICE_API_KEY environment variable required")
        return 1

    # Run tests
    tester = MADeploymentTester()
    results = tester.run_all_tests()

    # Return exit code based on results
    success_rate = sum(1 for r in results.values()
                      if isinstance(r, dict) and r.get('status') == 'success') / len(results)

    return 0 if success_rate >= 0.8 else 1

if __name__ == '__main__':
    exit(main())
