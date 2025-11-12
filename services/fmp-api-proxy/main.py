"""
FMP API Proxy Service
Centralized service for accessing Financial Modeling Prep APIs
Handles authentication, rate limiting, and data transformation
"""

import os
import requests
import json
import logging
from flask import Flask, request, jsonify
from functools import wraps
import time
from typing import Dict, Any, Optional
import asyncio
from concurrent.futures import ThreadPoolExecutor

app = Flask(__name__)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration
FMP_API_KEY = os.getenv('FMP_API_KEY')
FMP_BASE_URL = "https://financialmodelingprep.com/stable"
FMP_API_V4_BASE = "https://financialmodelingprep.com/api/v4"

# Rate limiting
REQUESTS_PER_MINUTE = 300
request_times = []

class FMPProxy:
    def __init__(self):
        self.session = requests.Session()
        self.executor = ThreadPoolExecutor(max_workers=10)

    def _check_rate_limit(self) -> bool:
        """Check if we're within rate limits"""
        current_time = time.time()
        # Remove requests older than 1 minute
        global request_times
        request_times = [t for t in request_times if current_time - t < 60]

        if len(request_times) >= REQUESTS_PER_MINUTE:
            return False

        request_times.append(current_time)
        return True

    def _make_request(self, endpoint: str, params: Dict[str, Any] = None) -> Dict[str, Any]:
        """Make authenticated request to FMP API"""
        if not self._check_rate_limit():
            raise Exception("Rate limit exceeded")

        if params is None:
            params = {}

        # Add API key
        params['apikey'] = FMP_API_KEY

        url = f"{FMP_BASE_URL}/{endpoint}"
        logger.info(f"Making request to: {url}")

        try:
            response = self.session.get(url, params=params, timeout=30)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"FMP API request failed: {e}")
            raise

    def get_company_profile(self, symbol: str) -> Dict[str, Any]:
        """Get company profile data"""
        return self._make_request(f"profile?symbol={symbol}")

    def get_financial_statements(self, symbol: str, statement_type: str, period: str = "annual", limit: int = 5) -> Dict[str, Any]:
        """Get financial statements (income, balance, cashflow)"""
        endpoint_map = {
            "income": "income-statement",
            "balance": "balance-sheet-statement",
            "cashflow": "cash-flow-statement"
        }

        if statement_type not in endpoint_map:
            raise ValueError(f"Invalid statement type: {statement_type}")

        endpoint = f"{endpoint_map[statement_type]}?symbol={symbol}&period={period}&limit={limit}"
        return self._make_request(endpoint)

    def get_historical_prices(self, symbol: str, from_date: str = None, to_date: str = None) -> Dict[str, Any]:
        """Get historical stock prices"""
        params = {}
        if from_date:
            params['from'] = from_date
        if to_date:
            params['to'] = to_date

        return self._make_request(f"historical-price-eod/full?symbol={symbol}", params)

    def get_real_time_quote(self, symbol: str) -> Dict[str, Any]:
        """Get real-time stock quote"""
        return self._make_request(f"quote?symbol={symbol}")

    def get_analyst_estimates(self, symbol: str, period: str = "annual", limit: int = 10) -> Dict[str, Any]:
        """Get analyst financial estimates"""
        return self._make_request(f"analyst-estimates?symbol={symbol}&period={period}&limit={limit}")

    def get_price_target(self, symbol: str) -> Dict[str, Any]:
        """Get analyst price targets"""
        return self._make_request(f"price-target-consensus?symbol={symbol}")

    def get_stock_screener(self, filters: Dict[str, Any]) -> Dict[str, Any]:
        """Screen stocks based on criteria"""
        params = {}
        for key, value in filters.items():
            if value is not None:
                params[key] = value

        return self._make_request("company-screener", params)

    def get_insider_trading(self, symbol: str = None, limit: int = 100) -> Dict[str, Any]:
        """Get insider trading data"""
        if symbol:
            return self._make_request(f"insider-trading?symbol={symbol}&limit={limit}")
        else:
            return self._make_request(f"insider-trading/latest?page=0&limit={limit}")

    def get_institutional_ownership(self, symbol: str = None, limit: int = 100) -> Dict[str, Any]:
        """Get institutional ownership data"""
        if symbol:
            return self._make_request(f"institutional-ownership/symbol-positions-summary?symbol={symbol}")
        else:
            return self._make_request(f"institutional-ownership/latest?page=0&limit={limit}")

    def get_mergers_acquisitions(self, search_term: str = None, limit: int = 100) -> Dict[str, Any]:
        """Get M&A data"""
        if search_term:
            return self._make_request(f"mergers-acquisitions-search?name={search_term}&limit={limit}")
        else:
            return self._make_request(f"mergers-acquisitions-latest?page=0&limit={limit}")

    def get_sec_filings(self, symbol: str = None, form_type: str = None, limit: int = 100) -> Dict[str, Any]:
        """Get SEC filings"""
        if symbol:
            return self._make_request(f"sec-filings-search/symbol?symbol={symbol}&limit={limit}")
        elif form_type:
            return self._make_request(f"sec-filings-search/form-type?formType={form_type}&limit={limit}")
        else:
            return self._make_request(f"sec-filings-financials?from=2024-01-01&to=2024-12-31&page=0&limit={limit}")

    def get_stock_peers(self, symbol: str) -> Dict[str, Any]:
        """Get peer companies for a stock using API v4"""
        # Use API v4 for stock peers
        url = f"{FMP_API_V4_BASE}/stock_peers"
        params = {
            'symbol': symbol,
            'apikey': FMP_API_KEY
        }
        
        try:
            if not self._check_rate_limit():
                raise Exception("Rate limit exceeded")
            
            response = self.session.get(url, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()
            
            # API v4 returns [{"symbol": "XXX", "peersList": ["PEER1", "PEER2", ...]}]
            if isinstance(data, list) and len(data) > 0:
                peers_list = data[0].get('peersList', [])
                return {'peers': peers_list}
            
            return {'peers': []}
        except Exception as e:
            logger.error(f"FMP API v4 peers request failed: {e}")
            return {'peers': []}

    def get_news(self, symbol: str = None, limit: int = 50) -> Dict[str, Any]:
        """Get news articles"""
        if symbol:
            return self._make_request(f"news/stock?symbols={symbol}&limit={limit}")
        else:
            return self._make_request(f"news/general-latest?page=0&limit={limit}")

# Global proxy instance
fmp_proxy = FMPProxy()

def require_api_key(f):
    """Decorator to require API key for external access"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        api_key = request.headers.get('X-API-Key')
        if not api_key or api_key != os.getenv('SERVICE_API_KEY'):
            return jsonify({'error': 'Invalid API key'}), 401
        return f(*args, **kwargs)
    return decorated_function

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({'status': 'healthy', 'service': 'fmp-api-proxy'})

@app.route('/company/profile/<symbol>', methods=['GET'])
@require_api_key
def get_company_profile(symbol):
    """Get company profile"""
    try:
        data = fmp_proxy.get_company_profile(symbol.upper())
        return jsonify(data)
    except Exception as e:
        logger.error(f"Error getting company profile for {symbol}: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/company/financials/<symbol>/<statement_type>', methods=['GET'])
@require_api_key
def get_financial_statements(symbol, statement_type):
    """Get financial statements"""
    try:
        period = request.args.get('period', 'annual')
        limit = int(request.args.get('limit', 5))

        data = fmp_proxy.get_financial_statements(symbol.upper(), statement_type, period, limit)
        return jsonify(data)
    except Exception as e:
        logger.error(f"Error getting {statement_type} for {symbol}: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/market/quote/<symbol>', methods=['GET'])
@require_api_key
def get_quote(symbol):
    """Get real-time quote"""
    try:
        data = fmp_proxy.get_real_time_quote(symbol.upper())
        return jsonify(data)
    except Exception as e:
        logger.error(f"Error getting quote for {symbol}: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/market/historical/<symbol>', methods=['GET'])
@require_api_key
def get_historical_prices(symbol):
    """Get historical prices"""
    try:
        from_date = request.args.get('from')
        to_date = request.args.get('to')

        data = fmp_proxy.get_historical_prices(symbol.upper(), from_date, to_date)
        return jsonify(data)
    except Exception as e:
        logger.error(f"Error getting historical prices for {symbol}: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/analyst/estimates/<symbol>', methods=['GET'])
@require_api_key
def get_analyst_estimates(symbol):
    """Get analyst estimates"""
    try:
        period = request.args.get('period', 'annual')
        limit = int(request.args.get('limit', 10))

        data = fmp_proxy.get_analyst_estimates(symbol.upper(), period, limit)
        return jsonify(data)
    except Exception as e:
        logger.error(f"Error getting analyst estimates for {symbol}: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/analyst/price-target/<symbol>', methods=['GET'])
@require_api_key
def get_price_target(symbol):
    """Get price target consensus"""
    try:
        data = fmp_proxy.get_price_target(symbol.upper())
        return jsonify(data)
    except Exception as e:
        logger.error(f"Error getting price target for {symbol}: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/screening/stocks', methods=['POST'])
@require_api_key
def screen_stocks():
    """Screen stocks based on criteria"""
    try:
        filters = request.get_json()
        data = fmp_proxy.get_stock_screener(filters)
        return jsonify(data)
    except Exception as e:
        logger.error(f"Error screening stocks: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/insider-trading', methods=['GET'])
@require_api_key
def get_insider_trading():
    """Get insider trading data"""
    try:
        symbol = request.args.get('symbol')
        limit = int(request.args.get('limit', 100))

        data = fmp_proxy.get_insider_trading(symbol.upper() if symbol else None, limit)
        return jsonify(data)
    except Exception as e:
        logger.error(f"Error getting insider trading data: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/institutional-ownership', methods=['GET'])
@require_api_key
def get_institutional_ownership():
    """Get institutional ownership data"""
    try:
        symbol = request.args.get('symbol')
        limit = int(request.args.get('limit', 100))

        data = fmp_proxy.get_institutional_ownership(symbol.upper() if symbol else None, limit)
        return jsonify(data)
    except Exception as e:
        logger.error(f"Error getting institutional ownership: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/mergers-acquisitions', methods=['GET'])
@require_api_key
def get_mergers_acquisitions():
    """Get M&A data"""
    try:
        search_term = request.args.get('search')
        limit = int(request.args.get('limit', 100))

        data = fmp_proxy.get_mergers_acquisitions(search_term, limit)
        return jsonify(data)
    except Exception as e:
        logger.error(f"Error getting M&A data: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/sec-filings', methods=['GET'])
@require_api_key
def get_sec_filings():
    """Get SEC filings"""
    try:
        symbol = request.args.get('symbol')
        form_type = request.args.get('form_type')
        limit = int(request.args.get('limit', 100))

        data = fmp_proxy.get_sec_filings(symbol.upper() if symbol else None, form_type, limit)
        return jsonify(data)
    except Exception as e:
        logger.error(f"Error getting SEC filings: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/peers', methods=['GET'])
@require_api_key
def get_peers():
    """Get peer companies"""
    try:
        symbol = request.args.get('symbol')
        if not symbol:
            return jsonify({'error': 'symbol parameter required'}), 400

        data = fmp_proxy.get_stock_peers(symbol.upper())
        # FMP returns array directly, wrap it in object with 'peers' key
        if isinstance(data, list):
            return jsonify({'peers': data})
        return jsonify(data)
    except Exception as e:
        logger.error(f"Error getting peers for {symbol}: {e}")
        return jsonify({'error': str(e), 'peers': []}), 200  # Return empty peers on error

@app.route('/stock-screener', methods=['GET'])
@require_api_key
def stock_screener():
    """Stock screener endpoint"""
    try:
        filters = {}
        if request.args.get('industry'):
            filters['industry'] = request.args.get('industry')
        if request.args.get('sector'):
            filters['sector'] = request.args.get('sector')
        if request.args.get('limit'):
            filters['limit'] = int(request.args.get('limit'))
        
        data = fmp_proxy.get_stock_screener(filters)
        return jsonify(data)
    except Exception as e:
        logger.error(f"Error in stock screener: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/news', methods=['GET'])
@require_api_key
def get_news():
    """Get news articles"""
    try:
        symbol = request.args.get('symbol')
        limit = int(request.args.get('limit', 50))

        data = fmp_proxy.get_news(symbol.upper() if symbol else None, limit)
        return jsonify(data)
    except Exception as e:
        logger.error(f"Error getting news: {e}")
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    port = int(os.getenv('PORT', 8080))
    app.run(host='0.0.0.0', port=port, debug=False)
