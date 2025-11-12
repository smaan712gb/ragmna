"""
DCF Valuation Service
Implements Discounted Cash Flow analysis with multiple scenarios and sensitivity analysis
Handles different company classifications and terminal value calculations
"""

import os
import json
import logging
import numpy as np
from flask import Flask, request, jsonify
from functools import wraps
from typing import Dict, Any, List, Optional
from datetime import datetime
import copy

app = Flask(__name__)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Service configurations
SERVICE_API_KEY = os.getenv('SERVICE_API_KEY')

class DCFValuationEngine:
    """Advanced DCF valuation engine with scenario analysis"""

    def __init__(self):
        # TODO: Externalize these financial metrics. Fetch from a reliable source or make them configurable.
        self.risk_free_rate = 0.04  # 4% risk-free rate (10-year Treasury)
        self.market_risk_premium = 0.06  # 6% market risk premium

        # TODO: Expand and maintain this list of industry betas. Consider using a more dynamic approach.
        # Industry beta adjustments
        self.industry_betas = {
            'technology': 1.2,
            'healthcare': 0.9,
            'financials': 1.1,
            'energy': 1.4,
            'consumer_staples': 0.7,
            'industrials': 1.0,
            'materials': 1.1,
            'utilities': 0.6,
            'real_estate': 0.8,
            'communication': 1.0
        }

        # TODO: These terminal growth rates are based on classification. Consider a more nuanced approach.
        # Terminal growth rates by classification
        self.terminal_growth_rates = {
            'hyper_growth': 0.045,  # 4.5% - Strong sustained growth for tech leaders
            'growth': 0.035,       # 3.5%
            'mature_growth': 0.03, # 3%
            'stable': 0.025,       # 2.5% - very conservative
            'declining': 0.015,    # 1.5%
            'distressed': 0.01     # 1% - minimal growth
        }

    def perform_dcf_analysis(self, company_data: Dict[str, Any],
                           financial_model: Dict[str, Any],
                           classification: Dict[str, Any]) -> Dict[str, Any]:
        """Perform comprehensive DCF valuation analysis"""

        logger.info(f"Performing DCF analysis for classification: {classification.get('primary_classification')}")

        # Extract cash flows from financial model
        cash_flows = self._extract_free_cash_flows(financial_model)

        # Calculate WACC
        wacc = self._calculate_wacc(company_data, classification)

        # Terminal value calculations
        terminal_value = self._calculate_terminal_value(
            cash_flows, wacc, classification
        )

        # Present value calculations
        pv_analysis = self._calculate_present_values(cash_flows, terminal_value, wacc)

        # Sensitivity analysis
        sensitivity_analysis = self._perform_sensitivity_analysis(
            cash_flows, terminal_value, wacc, classification
        )

        # Scenario analysis
        scenario_analysis = self._perform_scenario_analysis(
            cash_flows, classification
        )

        # Final valuation
        final_valuation = self._calculate_final_valuation(pv_analysis, company_data)

        return {
            'wacc': wacc,
            'cash_flow_projections': cash_flows,
            'terminal_value': terminal_value,
            'present_value_analysis': pv_analysis,
            'sensitivity_analysis': sensitivity_analysis,
            'scenario_analysis': scenario_analysis,
            'final_valuation': final_valuation,
            'assumptions': self._get_assumptions(classification),
            'generated_at': datetime.now().isoformat()
        }

    def _extract_free_cash_flows(self, financial_model: Dict[str, Any]) -> List[float]:
        """Extract free cash flows from financial model"""

        cash_flow_statement = financial_model.get('cash_flow_statement', [])
        balance_sheet = financial_model.get('balance_sheet', [])

        fcf_list = []

        for year_data in cash_flow_statement:
            # Free Cash Flow = Operating Cash Flow - CapEx
            operating_cf = year_data.get('operating_cash_flow', 0)
            capex = year_data.get('capex', 0)

            # Adjust for working capital changes (simplified)
            wc_change = year_data.get('working_capital_change', 0)

            fcf = operating_cf - capex + wc_change
            fcf_list.append(fcf)

        return fcf_list

    def _calculate_wacc(self, company_data: Dict[str, Any], classification: Dict[str, Any]) -> float:
        """Calculate Weighted Average Cost of Capital"""

        # Get company-specific data
        profile = company_data.get('profile', [{}])[0] if company_data.get('profile') else {}
        market_data = company_data.get('market', {})

        sector = profile.get('sector', 'Industrials').lower()

        # Beta calculation
        industry_beta = self.industry_betas.get(sector, 1.0)

        # Adjust beta based on classification
        classification_multiplier = self._get_beta_adjustment(classification)
        beta = industry_beta * classification_multiplier

        # Cost of equity (CAPM)
        cost_of_equity = self.risk_free_rate + beta * self.market_risk_premium

        # Cost of debt (simplified)
        # TODO: Implement a more robust calculation for the cost of debt.
        # This could be based on the company's credit rating or interest expense.
        cost_of_debt = 0.05  # 5% average corporate bond rate

        # Capital structure
        market_cap = market_data.get('marketCap', 0)
        total_debt = self._estimate_total_debt(company_data)

        total_capital = market_cap + total_debt

        if total_capital == 0:
            return cost_of_equity  # Equity-only financing

        weight_equity = market_cap / total_capital
        weight_debt = total_debt / total_capital

        # Tax rate
        # TODO: Use the effective tax rate from the company's financial statements.
        tax_rate = 0.25  # Simplified

        # WACC calculation
        wacc = (weight_equity * cost_of_equity) + (weight_debt * cost_of_debt * (1 - tax_rate))

        return wacc

    def _get_beta_adjustment(self, classification: Dict[str, Any]) -> float:
        """Get beta adjustment based on company classification"""

        primary_class = classification.get('primary_classification', 'stable')

        adjustments = {
            'hyper_growth': 0.95,  # Lower beta for established tech leaders with strong positions
            'growth': 1.1,         # Moderate increase
            'mature_growth': 1.0,  # Baseline
            'stable': 0.9,         # Lower volatility
            'declining': 1.2,      # Higher risk
            'distressed': 1.5      # Much higher risk
        }

        return adjustments.get(primary_class, 1.0)

    def _estimate_total_debt(self, company_data: Dict[str, Any]) -> float:
        """Estimate total debt from available data"""

        # TODO: This is a simplified estimation of total debt. A more comprehensive approach would be to
        # consider other debt-like items such as capital leases and unfunded pension liabilities.
        financials = company_data.get('financials', {})
        balance_stmts = financials.get('balance_sheets', [])

        if balance_stmts:
            latest_balance = balance_stmts[0]
            short_term_debt = latest_balance.get('shortTermDebt', 0)
            long_term_debt = latest_balance.get('longTermDebt', 0)
            return short_term_debt + long_term_debt

        return 0

    def _calculate_terminal_value(self, cash_flows: List[float], wacc: float,
                                classification: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate terminal value using multiple methods"""

        if not cash_flows:
            return {'value': 0, 'method': 'none', 'assumptions': {}}

        # Get final year FCF
        final_fcf = cash_flows[-1]

        # Terminal growth rate
        primary_class = classification.get('primary_classification', 'stable')
        terminal_growth = self.terminal_growth_rates.get(primary_class, 0.025)

        # Method 1: Gordon Growth Model
        gordon_tv = final_fcf * (1 + terminal_growth) / (wacc - terminal_growth)

        # Method 2: Exit Multiple (simplified - 8x final year FCF)
        # TODO: The exit multiple is simplified. It should be based on comparable company analysis (CCA)
        # or precedent transactions for a more accurate valuation.
        exit_multiple = self._get_exit_multiple(classification)
        multiple_tv = final_fcf * exit_multiple

        # Weighted average (60% Gordon, 40% Multiple)
        terminal_value = (gordon_tv * 0.6) + (multiple_tv * 0.4)

        return {
            'value': terminal_value,
            'gordon_growth_value': gordon_tv,
            'exit_multiple_value': multiple_tv,
            'terminal_growth_rate': terminal_growth,
            'exit_multiple': exit_multiple,
            'method': 'weighted_average'
        }

    def _get_exit_multiple(self, classification: Dict[str, Any]) -> float:
        """Get appropriate exit multiple based on classification"""

        primary_class = classification.get('primary_classification', 'stable')

        multiples = {
            'hyper_growth': 18.0,   # High growth tech leaders command premium multiples
            'growth': 12.0,         # Solid growth multiple
            'mature_growth': 9.0,   # Standard multiple
            'stable': 7.0,          # Conservative multiple
            'declining': 5.0,       # Discounted for decline
            'distressed': 3.0       # Heavily discounted
        }

        return multiples.get(primary_class, 8.0)

    def _calculate_present_values(self, cash_flows: List[float], terminal_value: Dict[str, Any],
                                wacc: float) -> Dict[str, Any]:
        """Calculate present values of cash flows"""

        pv_cash_flows = []
        cumulative_pv = 0

        # PV of explicit forecast period
        for i, fcf in enumerate(cash_flows):
            year = i + 1
            pv_fcf = fcf / ((1 + wacc) ** year)
            pv_cash_flows.append({
                'year': year,
                'fcf': fcf,
                'present_value': pv_fcf
            })
            cumulative_pv += pv_fcf

        # PV of terminal value
        terminal_years = len(cash_flows)
        pv_terminal = terminal_value['value'] / ((1 + wacc) ** terminal_years)

        # Total enterprise value
        enterprise_value = cumulative_pv + pv_terminal

        return {
            'cash_flow_pvs': pv_cash_flows,
            'terminal_pv': pv_terminal,
            'total_pv_cash_flows': cumulative_pv,
            'enterprise_value': enterprise_value,
            'discount_rate': wacc
        }

    def _perform_sensitivity_analysis(self, cash_flows: List[float], terminal_value: Dict[str, Any],
                                   base_wacc: float, classification: Dict[str, Any]) -> Dict[str, Any]:
        """Perform sensitivity analysis on key assumptions"""

        # WACC sensitivity
        wacc_range = np.linspace(base_wacc * 0.8, base_wacc * 1.2, 5)
        wacc_sensitivity = []

        for wacc in wacc_range:
            pv_analysis = self._calculate_present_values(cash_flows, terminal_value, wacc)
            wacc_sensitivity.append({
                'wacc': wacc,
                'enterprise_value': pv_analysis['enterprise_value']
            })

        # Terminal growth sensitivity
        base_growth = terminal_value.get('terminal_growth_rate', 0.025)
        growth_range = np.linspace(max(0.01, base_growth * 0.5), min(0.06, base_growth * 1.5), 5)
        growth_sensitivity = []

        for growth_rate in growth_range:
            # Recalculate terminal value with new growth rate
            final_fcf = cash_flows[-1] if cash_flows else 0
            new_tv = final_fcf * (1 + growth_rate) / (base_wacc - growth_rate)

            pv_analysis = self._calculate_present_values(cash_flows, {'value': new_tv}, base_wacc)
            growth_sensitivity.append({
                'terminal_growth': growth_rate,
                'enterprise_value': pv_analysis['enterprise_value']
            })

        return {
            'wacc_sensitivity': wacc_sensitivity,
            'growth_sensitivity': growth_sensitivity,
            'base_case_wacc': base_wacc,
            'base_case_growth': base_growth
        }

    def _perform_scenario_analysis(self, cash_flows: List[float],
                                 classification: Dict[str, Any]) -> Dict[str, Any]:
        """Perform scenario analysis (Base, Upside, Downside)"""

        # TODO: The scenario analysis is based on simple multipliers. A more robust implementation
        # would involve adjusting the underlying drivers of the financial model (e.g., revenue growth, margins)
        # to create more realistic scenarios.
        primary_class = classification.get('primary_classification', 'stable')

        # Scenario adjustments
        scenarios = {
            'base': {'fcf_adjustment': 1.0, 'wacc_adjustment': 1.0, 'tv_adjustment': 1.0},
            'upside': {'fcf_adjustment': 1.2, 'wacc_adjustment': 0.9, 'tv_adjustment': 1.1},
            'downside': {'fcf_adjustment': 0.8, 'wacc_adjustment': 1.1, 'tv_adjustment': 0.9}
        }

        results = {}

        for scenario_name, adjustments in scenarios.items():
            # Adjust cash flows
            adjusted_fcf = [fcf * adjustments['fcf_adjustment'] for fcf in cash_flows]

            # Adjust WACC
            base_wacc = self._calculate_wacc({}, classification)  # Simplified
            adjusted_wacc = base_wacc * adjustments['wacc_adjustment']

            # Adjust terminal value
            terminal_value = self._calculate_terminal_value(adjusted_fcf, adjusted_wacc, classification)
            terminal_value['value'] *= adjustments['tv_adjustment']

            # Calculate PV
            pv_analysis = self._calculate_present_values(adjusted_fcf, terminal_value, adjusted_wacc)

            results[scenario_name] = {
                'enterprise_value': pv_analysis['enterprise_value'],
                'wacc': adjusted_wacc,
                'terminal_value': terminal_value['value'],
                'fcf_adjustment': adjustments['fcf_adjustment']
            }

        return results

    def _calculate_final_valuation(self, pv_analysis: Dict[str, Any],
                                 company_data: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate final valuation metrics"""

        enterprise_value = pv_analysis['enterprise_value']

        # Get shares outstanding - check multiple sources
        shares_outstanding = 0
        
        # Try company_info first (from yfinance)
        company_info = company_data.get('company_info', {})
        shares_outstanding = company_info.get('sharesOutstanding', 0)
        
        # Try market data if not in company_info
        if shares_outstanding == 0:
            market_data = company_data.get('market', {})
            shares_outstanding = market_data.get('sharesOutstanding', 0)
        
        # Try yfinance data
        if shares_outstanding == 0:
            yf_data = company_info.get('yfinance_data', {})
            shares_outstanding = yf_data.get('shares_outstanding', 0)

        # Estimate net debt
        net_debt = self._estimate_total_debt(company_data)

        # Equity value
        equity_value = enterprise_value - net_debt

        # Per share values
        equity_value_per_share = equity_value / shares_outstanding if shares_outstanding > 0 else 0

        # Current market price for comparison - check multiple sources
        current_price = company_info.get('yfinance_data', {}).get('current_price', 0)
        if current_price == 0:
            profile = company_data.get('profile', [{}])
            if isinstance(profile, list) and len(profile) > 0:
                current_price = profile[0].get('price', 0)

        # Premium/discount
        premium_discount = (equity_value_per_share - current_price) / current_price if current_price > 0 else 0

        return {
            'enterprise_value': enterprise_value,
            'equity_value': equity_value,
            'equity_value_per_share': equity_value_per_share,
            'current_market_price': current_price,
            'premium_discount': premium_discount,
            'shares_outstanding': shares_outstanding,
            'net_debt': net_debt
        }

    def _get_assumptions(self, classification: Dict[str, Any]) -> Dict[str, Any]:
        """Get valuation assumptions"""

        primary_class = classification.get('primary_classification', 'stable')

        return {
            'risk_free_rate': self.risk_free_rate,
            'market_risk_premium': self.market_risk_premium,
            'terminal_growth_rate': self.terminal_growth_rates.get(primary_class, 0.025),
            'exit_multiple': self._get_exit_multiple(classification),
            'beta_adjustment': self._get_beta_adjustment(classification),
            'classification': primary_class
        }

    def calculate_dcf(self, symbol: str, financial_model: Dict[str, Any],
                     wacc: float = None, terminal_growth_rate: float = None,
                     projection_years: int = 5) -> Dict[str, Any]:
        """
        Simplified DCF calculation method for direct integration
        Wrapper around perform_dcf_analysis with simpler interface
        """
        # Build company_data from financial_model
        company_data = {
            'market': {
                'sharesOutstanding': financial_model.get('income_statement', [{}])[0].get('shares_outstanding', 0)
            }
        }
        
        # Extract classification from financial model or use default
        classification = {
            'primary_classification': financial_model.get('classification', 'stable')
        }
        
        # Run full DCF analysis
        full_analysis = self.perform_dcf_analysis(company_data, financial_model, classification)
        
        # Return simplified result matching expected interface
        return {
            'enterprise_value': full_analysis['present_value_analysis']['enterprise_value'],
            'equity_value': full_analysis['final_valuation']['equity_value'],
            'value_per_share': full_analysis['final_valuation']['equity_value_per_share'],
            'wacc': full_analysis['wacc'],
            'terminal_value': full_analysis['terminal_value']['value'],
            'cash_flows': full_analysis['cash_flow_projections'],
            'detailed_analysis': full_analysis
        }

# Global DCF engine instance
dcf_engine = DCFValuationEngine()

def require_api_key(f):
    """Decorator to require API key"""
    # TODO: Integrate with the auth-service for a more robust authentication mechanism (e.g., OAuth2, JWT).
    @wraps(f)
    def decorated_function(*args, **kwargs):
        api_key = request.headers.get('X-API-Key')
        if not api_key or api_key != SERVICE_API_KEY:
            return jsonify({'error': 'Invalid API key'}), 401
        return f(*args, **kwargs)
    return decorated_function

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'service': 'dcf-valuation',
        'version': '1.0.0'
    })

@app.route('/valuation/dcf', methods=['POST'])
@require_api_key
def perform_dcf_valuation():
    """Perform DCF valuation analysis"""
    # TODO: Implement more specific error handling.
    try:
        data = request.get_json()
        company_data = data.get('company_data', {})
        financial_model = data.get('financial_model', {})
        classification = data.get('classification', {})
        run_cache_name = data.get('run_cache_name')  # Optional

        # TODO: Implement a caching layer using the run_cache_name.
        # This could be a simple in-memory cache or a more robust solution like Redis.
        if run_cache_name:
            logger.info(f"Received run_cache_name: {run_cache_name}")

        if not company_data or not financial_model:
            return jsonify({'error': 'Company data and financial model are required'}), 400

        valuation = dcf_engine.perform_dcf_analysis(
            company_data, financial_model, classification
        )

        return jsonify(valuation)

    except Exception as e:
        logger.error(f"Error performing DCF valuation: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/valuation/sensitivity', methods=['POST'])
@require_api_key
def perform_sensitivity_analysis():
    """Perform sensitivity analysis on DCF inputs"""
    try:
        data = request.get_json()
        company_data = data.get('company_data', {})
        financial_model = data.get('financial_model', {})
        classification = data.get('classification', {})

        # Perform full DCF analysis
        full_analysis = dcf_engine.perform_dcf_analysis(
            company_data, financial_model, classification
        )

        # Return only sensitivity results
        return jsonify({
            'sensitivity_analysis': full_analysis['sensitivity_analysis'],
            'base_case': {
                'wacc': full_analysis['wacc'],
                'enterprise_value': full_analysis['final_valuation']['enterprise_value']
            }
        })

    except Exception as e:
        logger.error(f"Error performing sensitivity analysis: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/valuation/scenarios', methods=['POST'])
@require_api_key
def perform_scenario_analysis():
    """Perform scenario analysis"""
    try:
        data = request.get_json()
        company_data = data.get('company_data', {})
        financial_model = data.get('financial_model', {})
        classification = data.get('classification', {})

        # Perform full DCF analysis
        full_analysis = dcf_engine.perform_dcf_analysis(
            company_data, financial_model, classification
        )

        # Return only scenario results
        return jsonify({
            'scenario_analysis': full_analysis['scenario_analysis'],
            'base_case': full_analysis['final_valuation']
        })

    except Exception as e:
        logger.error(f"Error performing scenario analysis: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/valuation/compare', methods=['POST'])
@require_api_key
def compare_valuation_methods():
    """Compare DCF with other valuation methods"""
    try:
        data = request.get_json()
        dcf_valuation = data.get('dcf_valuation', {})
        comparable_valuation = data.get('comparable_valuation', {})

        # Simple comparison logic
        dcf_equity_value = dcf_valuation.get('equity_value_per_share', 0)
        comp_equity_value = comparable_valuation.get('implied_share_price', 0)

        if dcf_equity_value > 0 and comp_equity_value > 0:
            difference = dcf_equity_value - comp_equity_value
            percent_diff = difference / comp_equity_value

            comparison = {
                'dcf_value_per_share': dcf_equity_value,
                'comparable_value_per_share': comp_equity_value,
                'absolute_difference': difference,
                'percent_difference': percent_diff,
                'dcf_premium_to_comparable': percent_diff > 0
            }
        else:
            comparison = {'error': 'Insufficient data for comparison'}

        return jsonify(comparison)

    except Exception as e:
        logger.error(f"Error comparing valuation methods: {e}")
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    port = int(os.getenv('PORT', 8080))
    app.run(host='0.0.0.0', port=port, debug=False)
