"""
Comprehensive DD Agent Test
Tests full vector integration and comprehensive due diligence analysis
"""

import os
import json
import requests
from datetime import datetime
from typing import Dict, Any

# Configuration
SERVICE_API_KEY = os.getenv('SERVICE_API_KEY', 'test-api-key-12345')
DD_AGENT_URL = "http://localhost:8016"  # DD Agent port

# Test symbols
TEST_SYMBOL = "NVDA"

def test_dd_agent_health():
    """Test DD Agent health endpoint"""
    print("\n" + "="*80)
    print("TEST 1: DD Agent Health Check")
    print("="*80)
    
    try:
        response = requests.get(f"{DD_AGENT_URL}/health", timeout=10)
        print(f"✓ DD Agent is healthy: {response.json()}")
        return True
    except Exception as e:
        print(f"✗ DD Agent health check failed: {e}")
        return False

def create_mock_company_data(symbol: str) -> Dict[str, Any]:
    """Create mock company data for testing"""
    return {
        'profile': [{
            'symbol': symbol,
            'companyName': 'NVIDIA Corporation',
            'industry': 'Semiconductors',
            'sector': 'Technology',
            'country': 'US',
            'website': 'https://www.nvidia.com'
        }],
        'financials': {
            'income_statements': [
                {
                    'date': '2024-01-31',
                    'revenue': 60922000000,
                    'netIncome': 29760000000,
                    'operatingIncome': 32972000000
                },
                {
                    'date': '2023-01-31',
                    'revenue': 26974000000,
                    'netIncome': 4368000000,
                    'operatingIncome': 4224000000
                },
                {
                    'date': '2022-01-31',
                    'revenue': 26914000000,
                    'netIncome': 9752000000,
                    'operatingIncome': 10041000000
                }
            ],
            'balance_sheets': [
                {
                    'date': '2024-01-31',
                    'totalAssets': 65728000000,
                    'totalLiabilities': 28141000000,
                    'totalStockholdersEquity': 37587000000
                }
            ]
        },
        'sec_filings': [
            {
                'form_type': '10-K',
                'filing_date': '2024-02-21',
                'content': 'Annual report discussing GPU business, AI datacenter growth, litigation matters, and regulatory compliance. Significant IP portfolio mentioned.'
            },
            {
                'form_type': '10-Q',
                'filing_date': '2023-11-22',
                'content': 'Quarterly report with revenue recognition policies, off-balance sheet arrangements, and related party transactions.'
            },
            {
                'form_type': '8-K',
                'filing_date': '2023-08-23',
                'content': 'Current report on earnings announcement and forward-looking statements.'
            }
        ],
        'market': {
            'marketCap': 3000000000000,
            'peRatio': 75.5,
            'beta': 1.7
        },
        'news': {
            'sentiment': {
                'score': 0.15
            }
        },
        'executives': [
            {'name': 'Jensen Huang', 'title': 'CEO'},
            {'name': 'Colette Kress', 'title': 'CFO'},
            {'name': 'Ajay Puri', 'title': 'EVP Worldwide Field Operations'},
            {'name': 'Debora Shoquist', 'title': 'EVP Operations'}
        ]
    }

def test_comprehensive_dd_analysis(symbol: str):
    """Test comprehensive due diligence analysis"""
    print("\n" + "="*80)
    print(f"TEST 2: Comprehensive DD Analysis for {symbol}")
    print("="*80)
    
    company_data = create_mock_company_data(symbol)
    
    headers = {'X-API-Key': SERVICE_API_KEY}
    payload = {
        'symbol': symbol,
        'company_data': company_data
    }
    
    print(f"\nSending DD analysis request for {symbol}...")
    
    try:
        response = requests.post(
            f"{DD_AGENT_URL}/due-diligence/analyze",
            json=payload,
            headers=headers,
            timeout=300  # 5 minutes for comprehensive analysis
        )
        
        if response.status_code == 200:
            result = response.json()
            
            # Validate response structure
            print("\n✓ DD Analysis completed successfully")
            
            # Check vector sources
            if 'vector_sources' in result:
                print("\n📊 Vector Sources Summary:")
                vector_sources = result['vector_sources']
                print(f"  - Ingestion vectors available: {vector_sources.get('ingestion_vectors_available', False)}")
                print(f"  - Financial models available: {vector_sources.get('financial_models_available', False)}")
                print(f"  - Total RAG contexts retrieved: {vector_sources.get('total_rag_contexts', 0)}")
                print(f"  - Sources integrated: {vector_sources.get('sources_integrated', [])}")
                
                if 'rag_vectors_by_category' in vector_sources:
                    print("\n  RAG Vectors by Category:")
                    for category, available in vector_sources['rag_vectors_by_category'].items():
                        print(f"    • {category}: {'✓' if available else '✗'}")
            
            # Check risk analyses
            print("\n🔍 Risk Analysis Summary:")
            risk_categories = ['legal_analysis', 'financial_analysis', 'operational_analysis', 
                             'strategic_analysis', 'reputational_analysis']
            
            for category in risk_categories:
                if category in result:
                    analysis = result[category]
                    risk_level = analysis.get(f"{category.split('_')[0]}_risk_level", 'unknown')
                    score = analysis.get(f"overall_{category.split('_')[0]}_score", 0)
                    
                    # Check for RAG insights
                    rag_insights_count = len(analysis.get('rag_insights', []))
                    
                    # Check vector sources used
                    vectors_used = analysis.get('vector_sources_used', [])
                    
                    print(f"\n  {category.replace('_', ' ').title()}:")
                    print(f"    - Risk Level: {risk_level}")
                    print(f"    - Score: {score:.2f}")
                    print(f"    - RAG Insights: {rag_insights_count}")
                    print(f"    - Vector Sources: {', '.join(vectors_used)}")
                    
                    # Display RAG insights if available
                    if rag_insights_count > 0:
                        print(f"    - Sample Insight: {analysis['rag_insights'][0][:100]}...")
            
            # Check financial model analysis
            if 'financial_model_analysis' in result:
                print("\n💰 Financial Model Analysis:")
                model_analysis = result['financial_model_analysis']
                print(f"  - Red Flags: {len(model_analysis.get('red_flags', []))}")
                print(f"  - Insights: {len(model_analysis.get('insights', []))}")
                print(f"  - Valuation Concerns: {len(model_analysis.get('valuation_concerns', []))}")
                
                if model_analysis.get('red_flags'):
                    print(f"  - Sample Red Flag: {model_analysis['red_flags'][0]}")
            
            # Check document insights
            if 'document_insights' in result:
                print("\n📄 Document Insights:")
                doc_insights = result['document_insights']
                print(f"  - Documents Analyzed: {doc_insights.get('documents_analyzed', 0)}")
                print(f"  - Key Insights: {len(doc_insights.get('key_insights', []))}")
                print(f"  - Risk Indicators: {len(doc_insights.get('risk_indicators', []))}")
                print(f"  - Recommendations: {len(doc_insights.get('recommendations', []))}")
                print(f"  - RAG Analysis Complete: {doc_insights.get('rag_analysis_complete', False)}")
            
            # Check overall assessment
            if 'overall_assessment' in result:
                print("\n📈 Overall Risk Assessment:")
                assessment = result['overall_assessment']
                print(f"  - Overall Risk Level: {assessment.get('overall_risk_level', 'unknown')}")
                print(f"  - Overall Score: {assessment.get('overall_score', 0):.2f}")
                
                if 'risk_distribution' in assessment:
                    dist = assessment['risk_distribution']
                    print(f"  - High Risk Categories: {len(dist.get('high_risk_categories', []))}")
                    print(f"  - Moderate Risk Categories: {len(dist.get('moderate_risk_categories', []))}")
                    print(f"  - Low Risk Categories: {len(dist.get('low_risk_categories', []))}")
                    print(f"  - Risk Concentration: {dist.get('risk_concentration', 'unknown')}")
            
            # Check recommendations
            if 'recommendations' in result:
                print(f"\n💡 Recommendations Generated: {len(result['recommendations'])}")
                if result['recommendations']:
                    print(f"  - Sample: {result['recommendations'][0]}")
            
            # Check comprehensive flag
            comprehensive_complete = result.get('comprehensive_dd_completed', False)
            print(f"\n✓ Comprehensive DD Completed: {comprehensive_complete}")
            
            return result
            
        else:
            print(f"✗ DD analysis failed with status {response.status_code}")
            print(f"Response: {response.text}")
            return None
            
    except Exception as e:
        print(f"✗ Error during DD analysis: {e}")
        return None

def test_specific_risk_category(symbol: str, category: str):
    """Test specific risk category analysis"""
    print("\n" + "="*80)
    print(f"TEST 3: Specific Risk Analysis - {category.upper()}")
    print("="*80)
    
    company_data = create_mock_company_data(symbol)
    
    headers = {'X-API-Key': SERVICE_API_KEY}
    payload = {
        'symbol': symbol,
        'company_data': company_data
    }
    
    try:
        response = requests.post(
            f"{DD_AGENT_URL}/due-diligence/risk-assessment/{category}",
            json=payload,
            headers=headers,
            timeout=120
        )
        
        if response.status_code == 200:
            result = response.json()
            print(f"✓ {category.title()} risk analysis completed")
            
            # Check for RAG insights
            if 'rag_insights' in result:
                print(f"  - RAG Insights: {len(result['rag_insights'])}")
            
            # Check for vector sources
            if 'vector_sources_used' in result:
                print(f"  - Vector Sources: {', '.join(result['vector_sources_used'])}")
            
            # Check risk score
            risk_level = result.get(f"{category}_risk_level", 'unknown')
            print(f"  - Risk Level: {risk_level}")
            
            return result
        else:
            print(f"✗ {category} risk analysis failed: {response.status_code}")
            return None
            
    except Exception as e:
        print(f"✗ Error in {category} risk analysis: {e}")
        return None

def save_test_results(results: Dict[str, Any], filename: str):
    """Save test results to file"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = f"{filename}_{timestamp}.json"
    
    with open(output_file, 'w') as f:
        json.dump(results, f, indent=2)
    
    print(f"\n💾 Test results saved to: {output_file}")
    return output_file

def main():
    """Run comprehensive DD agent tests"""
    print("\n" + "="*80)
    print("DD AGENT COMPREHENSIVE TEST SUITE")
    print("Testing Full Vector Integration & Comprehensive Due Diligence")
    print("="*80)
    
    test_results = {
        'test_suite': 'DD Agent Comprehensive Test',
        'timestamp': datetime.now().isoformat(),
        'symbol': TEST_SYMBOL,
        'tests': {}
    }
    
    # Test 1: Health check
    health_ok = test_dd_agent_health()
    test_results['tests']['health_check'] = {
        'status': 'passed' if health_ok else 'failed'
    }
    
    if not health_ok:
        print("\n⚠️ DD Agent is not available. Please start the service.")
        return
    
    # Test 2: Comprehensive DD analysis
    dd_result = test_comprehensive_dd_analysis(TEST_SYMBOL)
    test_results['tests']['comprehensive_dd'] = {
        'status': 'passed' if dd_result else 'failed',
        'result': dd_result
    }
    
    # Test 3: Specific risk category analyses
    risk_categories = ['legal', 'financial', 'operational', 'strategic', 'reputational']
    
    for category in risk_categories:
        category_result = test_specific_risk_category(TEST_SYMBOL, category)
        test_results['tests'][f'{category}_risk'] = {
            'status': 'passed' if category_result else 'failed',
            'result': category_result
        }
    
    # Summary
    print("\n" + "="*80)
    print("TEST SUMMARY")
    print("="*80)
    
    total_tests = len(test_results['tests'])
    passed_tests = sum(1 for test in test_results['tests'].values() if test['status'] == 'passed')
    
    print(f"\nTotal Tests: {total_tests}")
    print(f"Passed: {passed_tests}")
    print(f"Failed: {total_tests - passed_tests}")
    print(f"Success Rate: {(passed_tests/total_tests)*100:.1f}%")
    
    # Validate comprehensive integration
    if dd_result:
        print("\n" + "="*80)
        print("COMPREHENSIVE INTEGRATION VALIDATION")
        print("="*80)
        
        validation_checks = []
        
        # Check 1: Vector sources integrated
        vector_sources = dd_result.get('vector_sources', {})
        sources_integrated = vector_sources.get('sources_integrated', [])
        validation_checks.append(('Ingestion Vectors', 'ingestion_data' in sources_integrated))
        validation_checks.append(('Financial Models', 'financial_models' in sources_integrated))
        validation_checks.append(('RAG Vectors', 'rag_vectors' in sources_integrated))
        
        # Check 2: RAG contexts retrieved
        total_rag = vector_sources.get('total_rag_contexts', 0)
        validation_checks.append(('RAG Contexts Retrieved', total_rag > 0))
        
        # Check 3: All risk categories analyzed
        risk_categories_present = all(
            cat in dd_result for cat in 
            ['legal_analysis', 'financial_analysis', 'operational_analysis', 
             'strategic_analysis', 'reputational_analysis']
        )
        validation_checks.append(('All Risk Categories', risk_categories_present))
        
        # Check 4: RAG insights in analyses
        rag_insights_present = any(
            len(dd_result.get(cat, {}).get('rag_insights', [])) > 0
            for cat in ['legal_analysis', 'financial_analysis', 'operational_analysis', 
                       'strategic_analysis', 'reputational_analysis']
        )
        validation_checks.append(('RAG Insights Present', rag_insights_present))
        
        # Check 5: Financial model analysis
        model_analysis_present = 'financial_model_analysis' in dd_result
        validation_checks.append(('Financial Model Analysis', model_analysis_present))
        
        # Check 6: Document insights
        doc_insights = dd_result.get('document_insights', {})
        doc_analysis_complete = doc_insights.get('rag_analysis_complete', False)
        validation_checks.append(('Document Analysis Complete', doc_analysis_complete))
        
        # Check 7: Comprehensive flag
        comprehensive_flag = dd_result.get('comprehensive_dd_completed', False)
        validation_checks.append(('Comprehensive DD Flag', comprehensive_flag))
        
        # Display validation results
        print("\nValidation Checks:")
        for check_name, passed in validation_checks:
            status = '✓' if passed else '✗'
            print(f"  {status} {check_name}")
        
        all_passed = all(passed for _, passed in validation_checks)
        
        if all_passed:
            print("\n🎉 ALL VALIDATION CHECKS PASSED!")
            print("DD Agent is fully integrated with all vector sources.")
        else:
            print("\n⚠️ Some validation checks failed.")
            print("Review the failed checks above.")
    
    # Save results
    output_file = save_test_results(test_results, 'DD_AGENT_TEST')
    
    print("\n" + "="*80)
    print("TEST COMPLETE")
    print("="*80)
    print(f"\nResults saved to: {output_file}")
    
    return test_results

if __name__ == "__main__":
    main()
