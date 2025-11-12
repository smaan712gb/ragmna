"""
3-Statement Modeler Service
Creates comprehensive financial models with income statement, balance sheet, and cash flow projections
Handles different company classifications and growth scenarios
"""

import os
import json
import logging
import numpy as np
import pandas as pd
from flask import Flask, request, jsonify
from functools import wraps
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
import copy

app = Flask(__name__)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Service URLs and configurations
SERVICE_API_KEY = os.getenv('SERVICE_API_KEY')

class FinancialModeler:
    """Advanced 3-statement financial modeling engine"""

    def __init__(self):
        self.growth_scenarios = {
            'hyper_growth': {
                'revenue_growth': [0.80, 0.65, 0.50, 0.35, 0.25],  # 5-year growth - AGGRESSIVE for companies like NVDA
                'margin_expansion': [0.03, 0.04, 0.05, 0.06, 0.07],  # Annual improvements - Strong margin expansion
                'capex_ratio': 0.18,  # % of revenue - Higher for growth investment
                'working_capital': 0.15,  # % of revenue - Efficient for tech
                'tax_rate': 0.15  # Lower effective rate for tech companies with global operations
            },
            'growth': {
                'revenue_growth': [0.25, 0.20, 0.15, 0.12, 0.10],
                'margin_expansion': [0.01, 0.02, 0.02, 0.02, 0.02],
                'capex_ratio': 0.12,
                'working_capital': 0.18,
                'tax_rate': 0.26
            },
            'mature_growth': {
                'revenue_growth': [0.12, 0.10, 0.08, 0.06, 0.04],
                'margin_expansion': [0.005, 0.005, 0.005, 0.005, 0.005],
                'capex_ratio': 0.10,
                'working_capital': 0.15,
                'tax_rate': 0.27
            },
            'stable': {
                'revenue_growth': [0.05, 0.04, 0.03, 0.02, 0.01],
                'margin_expansion': [0.002, 0.002, 0.002, 0.002, 0.002],
                'capex_ratio': 0.08,
                'working_capital': 0.12,
                'tax_rate': 0.28
            },
            'declining': {
                'revenue_growth': [-0.02, -0.05, -0.08, -0.10, -0.12],
                'margin_expansion': [-0.01, -0.02, -0.03, -0.04, -0.05],
                'capex_ratio': 0.06,
                'working_capital': 0.10,
                'tax_rate': 0.25
            },
            'distressed': {
                'revenue_growth': [-0.15, -0.20, -0.25, -0.30, -0.35],
                'margin_expansion': [-0.05, -0.08, -0.10, -0.12, -0.15],
                'capex_ratio': 0.04,
                'working_capital': 0.08,
                'tax_rate': 0.21  # NOL utilization
            }
        }

    def generate_three_statement_model(self, company_data: Dict[str, Any],
                                     classification: Dict[str, Any],
                                     projection_years: int = 5) -> Dict[str, Any]:
        """Generate complete 3-statement financial model"""

        logger.info(f"Generating 3-statement model for classification: {classification.get('primary_classification')}")

        # Extract historical data
        historical_data = self._extract_historical_data(company_data)

        # Get scenario parameters
        scenario = classification.get('primary_classification', 'stable')
        scenario_params = self.growth_scenarios.get(scenario, self.growth_scenarios['stable'])

        # Generate projections
        income_statement = self._project_income_statement(
            historical_data, scenario_params, projection_years
        )

        balance_sheet = self._project_balance_sheet(
            historical_data, income_statement, scenario_params, projection_years
        )

        cash_flow = self._project_cash_flow_statement(
            income_statement, balance_sheet, scenario_params, projection_years
        )

        # Calculate financial ratios and metrics
        ratios = self._calculate_financial_ratios(income_statement, balance_sheet, cash_flow)

        return {
            'income_statement': income_statement,
            'balance_sheet': balance_sheet,
            'cash_flow_statement': cash_flow,
            'financial_ratios': ratios,
            'assumptions': scenario_params,
            'classification': scenario,
            'projection_years': projection_years,
            'generated_at': datetime.now().isoformat()
        }

    def _extract_historical_data(self, company_data: Dict[str, Any]) -> Dict[str, Any]:
        """Extract and normalize historical financial data"""
        
        # Handle different data structure formats
        # Format 1: Direct company_info (from data ingestion)
        if 'company_info' in company_data:
            company_info = company_data['company_info']
            income_stmts = company_info.get('income_statements', [])
            balance_stmts = company_info.get('balance_sheets', [])
            cashflow_stmts = company_info.get('cash_flow_statements', [])
            shares_outstanding = company_info.get('sharesOutstanding', 0)
        # Format 2: Separated financials and market (legacy format)
        else:
            financials = company_data.get('financials', {})
            market = company_data.get('market', {})
            income_stmts = financials.get('income_statements', [])
            balance_stmts = financials.get('balance_sheets', [])
            cashflow_stmts = financials.get('cash_flow_statements', [])
            shares_outstanding = market.get('sharesOutstanding', 0)

        if not income_stmts:
            raise ValueError("No income statement data available")

        # Use most recent data
        latest_income = income_stmts[0] if income_stmts else {}
        latest_balance = balance_stmts[0] if balance_stmts else {}
        latest_cashflow = cashflow_stmts[0] if cashflow_stmts else {}

        return {
            'income_statement': {
                'revenue': latest_income.get('revenue', 0),
                'cost_of_revenue': latest_income.get('costOfRevenue', 0),
                'gross_profit': latest_income.get('grossProfit', 0),
                'operating_expenses': latest_income.get('operatingExpenses', 0),
                'operating_income': latest_income.get('operatingIncome', 0),
                'interest_expense': latest_income.get('interestExpense', 0),
                'pretax_income': latest_income.get('incomeBeforeTax', 0),
                'tax_expense': latest_income.get('incomeTaxExpense', 0),
                'net_income': latest_income.get('netIncome', 0),
                'eps': latest_income.get('eps', 0),
                'shares_outstanding': shares_outstanding
            },
            'balance_sheet': {
                'cash_and_equivalents': latest_balance.get('cashAndCashEquivalents', 0),
                'short_term_investments': latest_balance.get('shortTermInvestments', 0),
                'accounts_receivable': latest_balance.get('netReceivables', 0),
                'inventory': latest_balance.get('inventory', 0),
                'other_current_assets': latest_balance.get('otherCurrentAssets', 0),
                'total_current_assets': latest_balance.get('totalCurrentAssets', 0),
                'property_plant_equipment': latest_balance.get('propertyPlantEquipmentNet', 0),
                'goodwill': latest_balance.get('goodwill', 0),
                'intangible_assets': latest_balance.get('intangibleAssets', 0),
                'other_assets': latest_balance.get('otherAssets', 0),
                'total_assets': latest_balance.get('totalAssets', 0),
                'accounts_payable': latest_balance.get('accountPayables', 0),
                'short_term_debt': latest_balance.get('shortTermDebt', 0),
                'other_current_liabilities': latest_balance.get('otherCurrentLiabilities', 0),
                'total_current_liabilities': latest_balance.get('totalCurrentLiabilities', 0),
                'long_term_debt': latest_balance.get('longTermDebt', 0),
                'other_liabilities': latest_balance.get('otherLiabilities', 0),
                'total_liabilities': latest_balance.get('totalLiabilities', 0),
                'retained_earnings': latest_balance.get('retainedEarnings', 0),
                'shareholders_equity': latest_balance.get('totalStockholdersEquity', 0),
                'total_equity': latest_balance.get('totalEquity', latest_balance.get('totalStockholdersEquity', 0))
            },
            'cash_flow': {
                'operating_cash_flow': latest_cashflow.get('netCashProvidedByOperatingActivities', 0),
                'investing_cash_flow': latest_cashflow.get('netCashUsedForInvestingActivities', 0),
                'financing_cash_flow': latest_cashflow.get('netCashUsedProvidedByFinancingActivities', 0),
                'net_change_in_cash': latest_cashflow.get('netChangeInCash', 0),
                'capex': abs(latest_cashflow.get('capitalExpenditure', 0)),
                'free_cash_flow': latest_cashflow.get('freeCashFlow', 0)
            },
            'market_data': {
                'sharesOutstanding': shares_outstanding
            }
        }

    def _project_income_statement(self, historical: Dict[str, Any],
                                scenario_params: Dict[str, Any],
                                years: int) -> List[Dict[str, Any]]:
        """Project income statement for multiple years"""

        base_income = historical['income_statement']
        projections = []

        current_revenue = base_income['revenue']
        current_gross_margin = (base_income['gross_profit'] / current_revenue) if current_revenue > 0 else 0.6
        current_operating_margin = (base_income['operating_income'] / current_revenue) if current_revenue > 0 else 0.15

        for year in range(years):
            # Revenue growth
            revenue_growth = scenario_params['revenue_growth'][min(year, len(scenario_params['revenue_growth'])-1)]
            current_revenue *= (1 + revenue_growth)

            # Margin expansion
            margin_expansion = scenario_params['margin_expansion'][min(year, len(scenario_params['margin_expansion'])-1)]
            current_gross_margin = min(current_gross_margin + margin_expansion, 0.95)  # Cap at 95%
            current_operating_margin = min(current_operating_margin + margin_expansion, 0.50)  # Cap at 50%

            # Calculate line items
            cost_of_revenue = current_revenue * (1 - current_gross_margin)
            gross_profit = current_revenue - cost_of_revenue
            operating_expenses = current_revenue * (current_gross_margin - current_operating_margin)
            operating_income = gross_profit - operating_expenses

            # Interest expense (simplified)
            interest_expense = abs(base_income.get('interest_expense', operating_income * 0.02))

            pretax_income = operating_income - interest_expense
            tax_expense = pretax_income * scenario_params['tax_rate'] if pretax_income > 0 else 0
            net_income = pretax_income - tax_expense

            # EPS calculation
            shares_outstanding = base_income.get('shares_outstanding', 100000000)
            eps = net_income / shares_outstanding if shares_outstanding > 0 else 0

            projection = {
                'year': year + 1,
                'revenue': current_revenue,
                'cost_of_revenue': cost_of_revenue,
                'gross_profit': gross_profit,
                'gross_margin': current_gross_margin,
                'operating_expenses': operating_expenses,
                'operating_income': operating_income,
                'operating_margin': current_operating_margin,
                'interest_expense': interest_expense,
                'pretax_income': pretax_income,
                'tax_expense': tax_expense,
                'net_income': net_income,
                'eps': eps,
                'shares_outstanding': shares_outstanding
            }

            projections.append(projection)

        return projections

    def _project_balance_sheet(self, historical: Dict[str, Any],
                             income_projections: List[Dict[str, Any]],
                             scenario_params: Dict[str, Any],
                             years: int) -> List[Dict[str, Any]]:
        """Project balance sheet for multiple years"""

        base_balance = historical['balance_sheet']
        projections = []

        # Initialize with base year
        current_assets = copy.deepcopy(base_balance)
        current_year = 0

        for year_projection in income_projections:
            year = year_projection['year']

            # Working capital as % of revenue
            revenue = year_projection['revenue']
            wc_ratio = scenario_params['working_capital']

            # Current assets
            accounts_receivable = revenue * wc_ratio * 0.3  # 30% of WC
            inventory = revenue * wc_ratio * 0.4  # 40% of WC
            other_current_assets = revenue * wc_ratio * 0.3  # 30% of WC
            total_current_assets = accounts_receivable + inventory + other_current_assets

            # Fixed assets and capex
            capex = revenue * scenario_params['capex_ratio']
            accumulated_capex = sum([income_projections[y-1]['revenue'] * scenario_params['capex_ratio']
                                   for y in range(1, year+1)])

            # Depreciation (simplified - 3-year life)
            depreciation = accumulated_capex * 0.333

            # Current liabilities
            accounts_payable = revenue * wc_ratio * 0.5
            other_current_liabilities = revenue * wc_ratio * 0.5
            total_current_liabilities = accounts_payable + other_current_liabilities

            # Long-term debt (maintain leverage ratio)
            target_debt_to_equity = 0.5  # Simplified
            shareholders_equity = base_balance.get('shareholders_equity', 1000000000)

            # Net income accumulation
            accumulated_net_income = sum([p['net_income'] for p in income_projections[:year]])
            shareholders_equity += accumulated_net_income

            long_term_debt = shareholders_equity * target_debt_to_equity

            # Total liabilities and equity
            total_liabilities = total_current_liabilities + long_term_debt
            total_liabilities_equity = total_liabilities + shareholders_equity

            # Total assets (balance the balance sheet)
            total_assets = total_current_assets + base_balance.get('property_plant_equipment', 0) + accumulated_capex - depreciation

            projection = {
                'year': year,
                'cash_and_equivalents': max(total_assets - total_liabilities_equity, 0),  # Plug for balancing
                'accounts_receivable': accounts_receivable,
                'inventory': inventory,
                'other_current_assets': other_current_assets,
                'total_current_assets': total_current_assets,
                'property_plant_equipment': base_balance.get('property_plant_equipment', 0) + accumulated_capex - depreciation,
                'goodwill': base_balance.get('goodwill', 0),
                'intangible_assets': base_balance.get('intangible_assets', 0),
                'total_assets': total_assets,
                'accounts_payable': accounts_payable,
                'short_term_debt': total_current_liabilities * 0.3,
                'other_current_liabilities': other_current_liabilities,
                'total_current_liabilities': total_current_liabilities,
                'long_term_debt': long_term_debt,
                'total_liabilities': total_liabilities,
                'retained_earnings': base_balance.get('retained_earnings', 0) + accumulated_net_income,
                'shareholders_equity': shareholders_equity,
                'total_liabilities_equity': total_liabilities_equity
            }

            projections.append(projection)

        return projections

    def _project_cash_flow_statement(self, income_projections: List[Dict[str, Any]],
                                   balance_projections: List[Dict[str, Any]],
                                   scenario_params: Dict[str, Any],
                                   years: int) -> List[Dict[str, Any]]:
        """Project cash flow statement for multiple years"""

        projections = []

        for year in range(years):
            income = income_projections[year]
            balance = balance_projections[year]

            # Operating cash flow
            net_income = income['net_income']
            depreciation = balance['property_plant_equipment'] * 0.1  # Simplified depreciation
            working_capital_change = 0  # Simplified

            operating_cash_flow = net_income + depreciation - working_capital_change

            # Investing cash flow
            capex = income['revenue'] * scenario_params['capex_ratio']
            investing_cash_flow = -capex

            # Financing cash flow
            interest_expense = income['interest_expense']
            debt_change = balance['long_term_debt'] - (balance_projections[year-1]['long_term_debt'] if year > 0 else 0)
            equity_change = balance['shareholders_equity'] - (balance_projections[year-1]['shareholders_equity'] if year > 0 else 0)

            financing_cash_flow = -interest_expense + debt_change + equity_change

            # Net change in cash
            net_change_in_cash = operating_cash_flow + investing_cash_flow + financing_cash_flow

            projection = {
                'year': year + 1,
                'net_income': net_income,
                'depreciation_amortization': depreciation,
                'working_capital_change': working_capital_change,
                'operating_cash_flow': operating_cash_flow,
                'capex': capex,
                'investing_cash_flow': investing_cash_flow,
                'debt_change': debt_change,
                'equity_change': equity_change,
                'interest_expense': interest_expense,
                'financing_cash_flow': financing_cash_flow,
                'net_change_in_cash': net_change_in_cash
            }

            projections.append(projection)

        return projections

    def _calculate_financial_ratios(self, income_statement: List[Dict[str, Any]],
                                  balance_sheet: List[Dict[str, Any]],
                                  cash_flow: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Calculate key financial ratios"""

        ratios = {}

        for year in range(len(income_statement)):
            income = income_statement[year]
            balance = balance_sheet[year]
            cf = cash_flow[year]

            revenue = income['revenue']
            net_income = income['net_income']
            total_assets = balance['total_assets']
            total_liabilities = balance['total_liabilities']
            shareholders_equity = balance['shareholders_equity']
            operating_cash_flow = cf['operating_cash_flow']

            year_ratios = {
                'profitability_ratios': {
                    'gross_margin': income['gross_margin'],
                    'operating_margin': income['operating_margin'],
                    'net_margin': net_income / revenue if revenue > 0 else 0,
                    'return_on_assets': net_income / total_assets if total_assets > 0 else 0,
                    'return_on_equity': net_income / shareholders_equity if shareholders_equity > 0 else 0
                },
                'liquidity_ratios': {
                    'current_ratio': balance['total_current_assets'] / balance['total_current_liabilities'] if balance['total_current_liabilities'] > 0 else 0,
                    'quick_ratio': (balance['cash_and_equivalents'] + balance['accounts_receivable']) / balance['total_current_liabilities'] if balance['total_current_liabilities'] > 0 else 0
                },
                'leverage_ratios': {
                    'debt_to_equity': total_liabilities / shareholders_equity if shareholders_equity > 0 else 0,
                    'debt_to_assets': total_liabilities / total_assets if total_assets > 0 else 0
                },
                'valuation_ratios': {
                    'price_to_earnings': balance.get('market_cap', 0) / net_income if net_income > 0 else 0,
                    'enterprise_value_to_ebitda': 0,  # Would need market cap + debt data
                    'price_to_book': balance.get('market_cap', 0) / shareholders_equity if shareholders_equity > 0 else 0
                },
                'cash_flow_ratios': {
                    'operating_cash_flow_to_revenue': operating_cash_flow / revenue if revenue > 0 else 0,
                    'free_cash_flow': operating_cash_flow - cf['capex']
                }
            }

            ratios[f'year_{year + 1}'] = year_ratios

        return ratios

# Global modeler instance
modeler = FinancialModeler()

def require_api_key(f):
    """Decorator to require API key"""
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
        'service': 'three-statement-modeler',
        'version': '1.0.0'
    })

@app.route('/model/generate', methods=['POST'])
@require_api_key
def generate_model():
    """Generate 3-statement financial model"""
    try:
        data = request.get_json()
        company_data = data.get('company_data', {})
        classification = data.get('classification', {})
        projection_years = data.get('projection_years', 5)

        if not company_data:
            return jsonify({'error': 'Company data is required'}), 400

        model = modeler.generate_three_statement_model(
            company_data, classification, projection_years
        )

        return jsonify(model)

    except Exception as e:
        logger.error(f"Error generating financial model: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/model/validate', methods=['POST'])
@require_api_key
def validate_model():
    """Validate financial model assumptions"""
    try:
        data = request.get_json()
        model_data = data.get('model', {})

        # Basic validation checks
        validation_results = {
            'balance_sheet_balances': True,
            'cash_flow_consistency': True,
            'ratio_reasonableness': True,
            'warnings': [],
            'errors': []
        }

        # Check balance sheet balancing
        balance_sheet = model_data.get('balance_sheet', [])
        for year_data in balance_sheet:
            assets = year_data.get('total_assets', 0)
            liabilities_equity = year_data.get('total_liabilities_equity', 0)
            if abs(assets - liabilities_equity) > 1000000:  # $1M tolerance
                validation_results['balance_sheet_balances'] = False
                validation_results['errors'].append(f"Balance sheet doesn't balance for year {year_data.get('year')}")

        # Check for negative revenues
        income_statement = model_data.get('income_statement', [])
        for year_data in income_statement:
            if year_data.get('revenue', 0) < 0:
                validation_results['warnings'].append(f"Negative revenue projected for year {year_data.get('year')}")

        return jsonify(validation_results)

    except Exception as e:
        logger.error(f"Error validating model: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/model/scenarios', methods=['POST'])
@require_api_key
def run_scenarios():
    """Run multiple scenario analyses"""
    try:
        data = request.get_json()
        base_model = data.get('base_model', {})
        scenarios = data.get('scenarios', [])

        results = []

        for scenario in scenarios:
            # Modify base assumptions
            scenario_model = copy.deepcopy(base_model)
            scenario_classification = scenario.get('classification', {})

            # Generate scenario model
            scenario_result = modeler.generate_three_statement_model(
                scenario_model.get('company_data', {}),
                scenario_classification,
                scenario_model.get('projection_years', 5)
            )

            results.append({
                'scenario_name': scenario.get('name', 'Unnamed'),
                'model': scenario_result
            })

        return jsonify({'scenarios': results})

    except Exception as e:
        logger.error(f"Error running scenarios: {e}")
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    port = int(os.getenv('PORT', 8080))
    app.run(host='0.0.0.0', port=port, debug=False)
