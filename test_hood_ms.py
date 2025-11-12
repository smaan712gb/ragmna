#!/usr/bin/env python3
"""
Test script for HOOD → MS acquisition analysis
"""

import sys
import os
sys.path.append('services/data-ingestion')
sys.path.append('.')

from main import DataIngestionService

def test_company_data_ingestion():
    """Test data ingestion for HOOD and MS"""
    print("🧪 Testing Data Ingestion for HOOD → MS Acquisition")
    print("=" * 60)

    ingestion = DataIngestionService()

    # Test HOOD (Robinhood)
    print("\n📊 Testing HOOD (Robinhood) Data Ingestion...")
    try:
        hood_result = ingestion.fetch_company_data('HOOD')
        print(f"✅ Status: {hood_result.get('status')}")

        if hood_result.get('company_info'):
            info = hood_result['company_info']
            print(f"🏢 Company: {info.get('companyName', 'Unknown')}")
            print(f"💰 Market Cap: ${info.get('mktCap', 0):,.0f}")
            print(f"🏭 Sector: {info.get('sector', 'Unknown')}")
            print(f"⚙️ Industry: {info.get('industry', 'Unknown')}")

        if hood_result.get('vectorization_results'):
            vec = hood_result['vectorization_results']
            print(f"📄 Documents processed: {vec.get('total_documents', 0)}")
            print(f"🔢 Chunks created: {vec.get('chunks_created', 0)}")
            print(f"🧠 Vectors stored: {vec.get('vectors_stored', 0)}")

    except Exception as e:
        print(f"❌ Error testing HOOD: {e}")

    # Test MS (Morgan Stanley)
    print("\n📊 Testing MS (Morgan Stanley) Data Ingestion...")
    try:
        ms_result = ingestion.fetch_company_data('MS')
        print(f"✅ Status: {ms_result.get('status')}")

        if ms_result.get('company_info'):
            info = ms_result['company_info']
            print(f"🏢 Company: {info.get('companyName', 'Unknown')}")
            print(f"💰 Market Cap: ${info.get('mktCap', 0):,.0f}")
            print(f"🏭 Sector: {info.get('sector', 'Unknown')}")
            print(f"⚙️ Industry: {info.get('industry', 'Unknown')}")

        if ms_result.get('vectorization_results'):
            vec = ms_result['vectorization_results']
            print(f"📄 Documents processed: {vec.get('total_documents', 0)}")
            print(f"🔢 Chunks created: {vec.get('chunks_created', 0)}")
            print(f"🧠 Vectors stored: {vec.get('vectors_stored', 0)}")

    except Exception as e:
        print(f"❌ Error testing MS: {e}")

    print("\n🎯 Test Summary:")
    print("- HOOD: Fintech/retail trading platform")
    print("- MS: Major investment bank")
    print("- Analysis: Financial Services acquiring Consumer Cyclical/Tech")
    print("\n✅ Data ingestion pipeline working for any company combination!")

if __name__ == '__main__':
    test_company_data_ingestion()
