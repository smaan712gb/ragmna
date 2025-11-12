"""
Due Diligence Agent Service
Comprehensive due diligence analysis covering legal, operational, financial, and strategic risks
Uses RAG for document analysis and LLM for risk assessment
Integrates with all vector sources and data repositories
"""

import os
import json
import logging
import re
from flask import Flask, request, jsonify
from functools import wraps
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
import requests
import numpy as np
import google.auth
from google.auth.transport.requests import Request
from google.oauth2 import service_account
from google.cloud import aiplatform
from vertexai.generative_models import GenerativeModel
import vertexai

app = Flask(__name__)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Service configurations
SERVICE_API_KEY = os.getenv('SERVICE_API_KEY')
RAG_ENGINE_URL = os.getenv('RAG_ENGINE_URL', 'https://LOCATION-aiplatform.googleapis.com/v1beta1')
VERTEX_PROJECT = os.getenv('VERTEX_PROJECT')
VERTEX_LOCATION = os.getenv('VERTEX_LOCATION')
RAG_CORPUS_ID = os.getenv('RAG_CORPUS_ID')
GOOGLE_CLOUD_KEY_PATH = os.getenv('GOOGLE_CLOUD_KEY_PATH')

# Service URLs for integration
DATA_INGESTION_URL = os.getenv('DATA_INGESTION_URL', 'http://data-ingestion:8080')
THREE_STATEMENT_MODELER_URL = os.getenv('THREE_STATEMENT_MODELER_URL', 'http://three-statement-modeler:8080')
DCF_VALUATION_URL = os.getenv('DCF_VALUATION_URL', 'http://dcf-valuation:8080')
CCA_VALUATION_URL = os.getenv('CCA_VALUATION_URL', 'http://cca-valuation:8080')
LBO_ANALYSIS_URL = os.getenv('LBO_ANALYSIS_URL', 'http://lbo-analysis:8080')
MERGERS_MODEL_URL = os.getenv('MERGERS_MODEL_URL', 'http://mergers-model:8080')

# Vertex AI will be initialized lazily in the DueDiligenceAgent class

# Gemini Model Configuration
GEMINI_MODEL = "gemini-2.5-pro"

class RAGManager:
    """Manager for Vertex AI RAG Engine operations"""

    def __init__(self):
        self.project = VERTEX_PROJECT
        self.location = VERTEX_LOCATION
        self.corpus_id = RAG_CORPUS_ID
        self.base_url = f"https://{self.location}-aiplatform.googleapis.com/v1beta1"
        self.vertex_initialized = False

    def _ensure_initialized(self):
        """Initialize Vertex AI on first use"""
        if not self.vertex_initialized and VERTEX_PROJECT and VERTEX_LOCATION:
            try:
                if GOOGLE_CLOUD_KEY_PATH:
                    credentials = service_account.Credentials.from_service_account_file(GOOGLE_CLOUD_KEY_PATH)
                    vertexai.init(project=VERTEX_PROJECT, location=VERTEX_LOCATION, credentials=credentials)
                else:
                    vertexai.init(project=VERTEX_PROJECT, location=VERTEX_LOCATION)
                self.vertex_initialized = True
                logger.info("Vertex AI initialized successfully for RAG operations")
            except Exception as e:
                logger.error(f"Failed to initialize Vertex AI: {e}")
                self.vertex_initialized = False

    def _get_auth_headers(self) -> Dict[str, str]:
        """Get authentication headers for Vertex AI API calls"""
        if GOOGLE_CLOUD_KEY_PATH:
            credentials = service_account.Credentials.from_service_account_file(GOOGLE_CLOUD_KEY_PATH)
        else:
            credentials, _ = google.auth.default()

        credentials.refresh(Request())
        return {
            'Authorization': f'Bearer {credentials.token}',
            'Content-Type': 'application/json'
        }

    def retrieve_contexts(self, query: str, top_k: int = 10,
                         vector_distance_threshold: float = None) -> Dict[str, Any]:
        """Retrieve relevant contexts from RAG corpus"""
        if not self.corpus_id:
            logger.warning("RAG_CORPUS_ID not configured, skipping retrieval")
            return {'contexts': []}

        url = f"{self.base_url}/projects/{self.project}/locations/{self.location}:retrieveContexts"

        payload = {
            'vertex_rag_store': {
                'rag_resources': {
                    'rag_corpus': f'projects/{self.project}/locations/{self.location}/ragCorpora/{self.corpus_id}'
                }
            },
            'query': {
                'text': query,
                'similarity_top_k': top_k
            }
        }

        if vector_distance_threshold:
            payload['vertex_rag_store']['vector_distance_threshold'] = vector_distance_threshold

        try:
            headers = self._get_auth_headers()
            response = requests.post(url, json=payload, headers=headers, timeout=60)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Error retrieving contexts: {e}")
            return {'contexts': []}

    def generate_with_rag(self, prompt: str, contexts: List[Dict[str, Any]] = None,
                         model_name: str = None) -> str:
        """Generate response using Gemini with RAG context"""
        if not model_name:
            model_name = GEMINI_MODEL

        # Ensure Vertex AI is initialized
        self._ensure_initialized()

        try:
            model = GenerativeModel(model_name)

            # Prepare context from RAG retrieval
            context_text = ""
            if contexts:
                context_parts = []
                for ctx in contexts.get('contexts', [])[:5]:
                    if 'text' in ctx:
                        context_parts.append(ctx['text'])
                context_text = "\n\n".join(context_parts)

            # Create enhanced prompt
            enhanced_prompt = f"""
Based on the following context information:

{context_text}

Please answer the following question:
{prompt}

If the context doesn't contain relevant information, use your general knowledge but prioritize the provided context.
"""

            response = model.generate_content(enhanced_prompt)
            return response.text

        except Exception as e:
            logger.error(f"Error generating with RAG: {e}")
            try:
                model = GenerativeModel(model_name)
                response = model.generate_content(prompt)
                return response.text
            except Exception as e2:
                logger.error(f"Error in fallback generation: {e2}")
                return f"Error generating response: {str(e2)}"

class VectorDataIntegrator:
    """Integrates data from all vector sources"""

    def __init__(self, rag_manager: RAGManager):
        self.rag_manager = rag_manager

    def get_ingestion_vectors(self, symbol: str) -> Dict[str, Any]:
        """Retrieve ingestion data vectors for comprehensive analysis"""
        try:
            headers = {'X-API-Key': SERVICE_API_KEY}
            response = requests.get(
                f"{DATA_INGESTION_URL}/data/vectors/{symbol}",
                headers=headers,
                timeout=60
            )

            if response.status_code == 200:
                return response.json()
            else:
                logger.warning(f"Could not retrieve ingestion vectors for {symbol}")
                return {}

        except Exception as e:
            logger.error(f"Error retrieving ingestion vectors: {e}")
            return {}

    def get_financial_model_outputs(self, symbol: str) -> Dict[str, Any]:
        """Retrieve financial model outputs (3SM, DCF, CCA, LBO)"""
        try:
            headers = {'X-API-Key': SERVICE_API_KEY}
            
            # Get 3-Statement Model outputs
            three_sm_response = requests.get(
                f"{THREE_STATEMENT_MODELER_URL}/model/{symbol}",
                headers=headers,
                timeout=60
            )
            
            three_sm_data = three_sm_response.json() if three_sm_response.status_code == 200 else {}

            # Get DCF Valuation outputs
            dcf_response = requests.get(
                f"{DCF_VALUATION_URL}/valuation/{symbol}",
                headers=headers,
                timeout=60
            )
            
            dcf_data = dcf_response.json() if dcf_response.status_code == 200 else {}

            # Get CCA outputs
            cca_response = requests.get(
                f"{CCA_VALUATION_URL}/valuation/{symbol}",
                headers=headers,
                timeout=60
            )
            
            cca_data = cca_response.json() if cca_response.status_code == 200 else {}

            # Get LBO outputs
            lbo_response = requests.get(
                f"{LBO_ANALYSIS_URL}/analysis/{symbol}",
                headers=headers,
                timeout=60
            )
            
            lbo_data = lbo_response.json() if lbo_response.status_code == 200 else {}

            return {
                'three_statement_model': three_sm_data,
                'dcf_valuation': dcf_data,
                'cca_valuation': cca_data,
                'lbo_analysis': lbo_data,
                'retrieved_at': datetime.now().isoformat()
            }

        except Exception as e:
            logger.error(f"Error retrieving financial model outputs: {e}")
            return {}

    def query_rag_vectors(self, symbol: str, risk_category: str) -> Dict[str, Any]:
        """Query RAG vectors for specific risk categories"""
        
        risk_queries = {
            'legal': f"legal risks, litigation, regulatory compliance for {symbol}",
            'financial': f"financial reporting quality, accounting practices for {symbol}",
            'operational': f"operational risks, supply chain, key personnel for {symbol}",
            'strategic': f"market position, competitive threats, industry trends for {symbol}",
            'reputational': f"brand reputation, ESG compliance, social sentiment for {symbol}"
        }

        query = risk_queries.get(risk_category, f"due diligence analysis for {symbol}")
        
        contexts = self.rag_manager.retrieve_contexts(query, top_k=10)
        
        return {
            'risk_category': risk_category,
            'symbol': symbol,
            'contexts_retrieved': len(contexts.get('contexts', [])),
            'contexts': contexts,
            'retrieved_at': datetime.now().isoformat()
        }

    def get_comprehensive_vectors(self, symbol: str) -> Dict[str, Any]:
        """Get vectors from all sources for comprehensive DD"""
        
        logger.info(f"Retrieving comprehensive vectors for {symbol}")
        
        return {
            'ingestion_vectors': self.get_ingestion_vectors(symbol),
            'financial_models': self.get_financial_model_outputs(symbol),
            'rag_vectors': {
                'legal': self.query_rag_vectors(symbol, 'legal'),
                'financial': self.query_rag_vectors(symbol, 'financial'),
                'operational': self.query_rag_vectors(symbol, 'operational'),
                'strategic': self.query_rag_vectors(symbol, 'strategic'),
                'reputational': self.query_rag_vectors(symbol, 'reputational')
            },
            'retrieved_at': datetime.now().isoformat()
        }

class DueDiligenceAgent:
    """Advanced due diligence analysis agent with comprehensive vector integration"""

    def __init__(self):
        self.rag_manager = RAGManager()
        self.vector_integrator = VectorDataIntegrator(self.rag_manager)
        self.risk_categories = {
            'legal_risks': [
                'litigation_exposure',
                'regulatory_compliance',
                'contractual_obligations',
                'intellectual_property',
                'employment_lawsuits'
            ],
            'financial_risks': [
                'accounting_irregularities',
                'off_balance_sheet_items',
                'related_party_transactions',
                'revenue_recognition_issues',
                'tax_liabilities'
            ],
            'operational_risks': [
                'supply_chain_disruptions',
                'key_personnel_dependence',
                'technology_obsolescence',
                'operational_efficiencies',
                'capacity_constraints'
            ],
            'strategic_risks': [
                'market_position',
                'competitive_threats',
                'customer_concentration',
                'supplier_concentration',
                'industry_trends'
            ],
            'reputational_risks': [
                'brand_perception',
                'social_media_sentiment',
                'executive_compensation',
                'corporate_governance',
                'esg_compliance'
            ]
        }

        # Risk severity scoring
        self.risk_severity = {
            'low': 1,
            'moderate': 2,
            'high': 3,
            'critical': 4
        }

    def perform_comprehensive_due_diligence(self, symbol: str,
                                          company_data: Dict[str, Any]) -> Dict[str, Any]:
        """Perform comprehensive due diligence analysis with full vector integration"""

        logger.info(f"Performing comprehensive due diligence for {symbol}")

        # STEP 1: Retrieve all vectors from all sources
        logger.info("Step 1: Retrieving vectors from all sources")
        all_vectors = self.vector_integrator.get_comprehensive_vectors(symbol)

        # STEP 2: Analyze each risk category with vector data
        logger.info("Step 2: Analyzing risk categories with vector data")
        legal_analysis = self._analyze_legal_risks(symbol, company_data, all_vectors)
        financial_analysis = self._analyze_financial_risks(symbol, company_data, all_vectors)
        operational_analysis = self._analyze_operational_risks(symbol, company_data, all_vectors)
        strategic_analysis = self._analyze_strategic_risks(symbol, company_data, all_vectors)
        reputational_analysis = self._analyze_reputational_risks(symbol, company_data, all_vectors)

        # STEP 3: Comprehensive document analysis using RAG
        logger.info("Step 3: Performing comprehensive document analysis with RAG")
        document_insights = self._analyze_documents_with_rag(symbol, company_data, all_vectors)

        # STEP 4: Analyze financial models for red flags
        logger.info("Step 4: Analyzing financial models for red flags")
        model_analysis = self._analyze_financial_models(all_vectors.get('financial_models', {}))

        # STEP 5: Overall risk assessment
        logger.info("Step 5: Calculating overall risk assessment")
        overall_assessment = self._calculate_overall_risk_assessment({
            'legal': legal_analysis,
            'financial': financial_analysis,
            'operational': operational_analysis,
            'strategic': strategic_analysis,
            'reputational': reputational_analysis
        })

        # STEP 6: Generate recommendations
        logger.info("Step 6: Generating due diligence recommendations")
        recommendations = self._generate_due_diligence_recommendations(
            overall_assessment, company_data, all_vectors
        )

        # STEP 7: Vector source summary
        vector_summary = self._summarize_vector_sources(all_vectors)

        return {
            'company_symbol': symbol,
            'vector_sources': vector_summary,
            'legal_analysis': legal_analysis,
            'financial_analysis': financial_analysis,
            'operational_analysis': operational_analysis,
            'strategic_analysis': strategic_analysis,
            'reputational_analysis': reputational_analysis,
            'document_insights': document_insights,
            'financial_model_analysis': model_analysis,
            'overall_assessment': overall_assessment,
            'recommendations': recommendations,
            'due_diligence_summary': self._generate_dd_summary(overall_assessment),
            'comprehensive_dd_completed': True,
            'generated_at': datetime.now().isoformat()
        }

    def _summarize_vector_sources(self, all_vectors: Dict[str, Any]) -> Dict[str, Any]:
        """Summarize which vector sources were accessed"""
        
        ingestion_available = bool(all_vectors.get('ingestion_vectors'))
        financial_models_available = bool(all_vectors.get('financial_models'))
        
        rag_vectors = all_vectors.get('rag_vectors', {})
        rag_categories_available = {
            category: data.get('contexts_retrieved', 0) > 0
            for category, data in rag_vectors.items()
        }

        return {
            'ingestion_vectors_available': ingestion_available,
            'financial_models_available': financial_models_available,
            'rag_vectors_by_category': rag_categories_available,
            'total_rag_contexts': sum(
                data.get('contexts_retrieved', 0) 
                for data in rag_vectors.values()
            ),
            'sources_integrated': [
                'ingestion_data' if ingestion_available else None,
                'financial_models' if financial_models_available else None,
                'rag_vectors' if any(rag_categories_available.values()) else None
            ]
        }

    def _analyze_financial_models(self, financial_models: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze financial models for red flags and insights"""
        
        analysis = {
            'red_flags': [],
            'insights': [],
            'valuation_concerns': []
        }

        # Analyze 3-Statement Model
        three_sm = financial_models.get('three_statement_model', {})
        if three_sm:
            # Check for unrealistic growth assumptions
            projections = three_sm.get('projections', {})
            if projections:
                revenue_growth = projections.get('revenue_growth_assumptions', [])
                if any(g > 50 for g in revenue_growth):
                    analysis['red_flags'].append("Unrealistic revenue growth projections (>50%)")

        # Analyze DCF Valuation
        dcf = financial_models.get('dcf_valuation', {})
        if dcf:
            wacc = dcf.get('wacc', 0)
            if wacc < 0.05 or wacc > 0.25:
                analysis['valuation_concerns'].append(f"Unusual WACC assumption: {wacc:.2%}")

        # Analyze LBO
        lbo = financial_models.get('lbo_analysis', {})
        if lbo:
            irr = lbo.get('irr', 0)
            if irr > 0.5:
                analysis['insights'].append(f"High LBO IRR suggests attractive leveraged returns: {irr:.1%}")

        return analysis

    def _analyze_legal_risks(self, symbol: str, company_data: Dict[str, Any], 
                            all_vectors: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze legal and regulatory risks with vector data"""

        # Get SEC filings data
        sec_filings = company_data.get('sec_filings', [])
        
        # Get RAG insights for legal risks
        legal_rag = all_vectors.get('rag_vectors', {}).get('legal', {})
        rag_insights = self._extract_rag_insights(legal_rag, 'legal risks')

        # Analyze litigation mentions
        litigation_risks = self._analyze_litigation_risks(sec_filings)

        # Regulatory compliance
        regulatory_risks = self._analyze_regulatory_risks(sec_filings)

        # IP and contracts
        ip_risks = self._analyze_ip_risks(company_data)

        # Employment issues
        employment_risks = self._analyze_employment_risks(sec_filings)

        # Calculate legal risk score
        legal_score = self._calculate_category_score([
            litigation_risks['severity_score'],
            regulatory_risks['severity_score'],
            ip_risks['severity_score'],
            employment_risks['severity_score']
        ])

        return {
            'litigation_risks': litigation_risks,
            'regulatory_risks': regulatory_risks,
            'ip_risks': ip_risks,
            'employment_risks': employment_risks,
            'rag_insights': rag_insights,
            'overall_legal_score': legal_score,
            'legal_risk_level': self._score_to_risk_level(legal_score),
            'key_concerns': self._extract_key_concerns([
                litigation_risks, regulatory_risks, ip_risks, employment_risks
            ]),
            'vector_sources_used': ['sec_filings', 'rag_vectors']
        }

    def _extract_rag_insights(self, rag_data: Dict[str, Any], category: str) -> List[str]:
        """Extract insights from RAG contexts"""
        
        insights = []
        contexts = rag_data.get('contexts', {}).get('contexts', [])
        
        if not contexts:
            return insights

        # Use Gemini to summarize key insights from contexts
        context_texts = [ctx.get('text', '') for ctx in contexts[:5]]
        combined_context = "\n\n".join(context_texts)

        if combined_context:
            prompt = f"""
Analyze the following context about {category} and extract 3-5 key insights:

{combined_context}

Provide specific, actionable insights.
"""
            
            try:
                response = self.rag_manager.generate_with_rag(prompt, rag_data.get('contexts'))
                # Parse response into list
                insights = [line.strip() for line in response.split('\n') if line.strip() and not line.strip().startswith('#')]
            except Exception as e:
                logger.error(f"Error extracting RAG insights: {e}")

        return insights[:5]

    def _analyze_litigation_risks(self, sec_filings: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze litigation exposure from SEC filings"""

        litigation_keywords = [
            'lawsuit', 'litigation', 'complaint', 'settlement', 'arbitration',
            'dispute', 'claim', 'allegation', 'investigation', 'enforcement'
        ]

        total_filings = len(sec_filings)
        litigation_mentions = 0
        significant_cases = []

        for filing in sec_filings:
            content = filing.get('content', '').lower()

            for keyword in litigation_keywords:
                if keyword in content:
                    litigation_mentions += 1
                    if 'significant' in content or 'material' in content:
                        significant_cases.append(filing.get('form_type', 'Unknown'))
                    break

        # Calculate severity
        litigation_ratio = litigation_mentions / max(total_filings, 1)

        if litigation_ratio > 0.3:
            severity = 'high'
            score = 3
        elif litigation_ratio > 0.1:
            severity = 'moderate'
            score = 2
        else:
            severity = 'low'
            score = 1

        return {
            'litigation_mentions': litigation_mentions,
            'total_filings_analyzed': total_filings,
            'litigation_ratio': litigation_ratio,
            'significant_cases': significant_cases,
            'severity_level': severity,
            'severity_score': score
        }

    def _analyze_regulatory_risks(self, sec_filings: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze regulatory compliance risks"""

        regulatory_keywords = [
            'sec', 'regulatory', 'compliance', 'violation', 'penalty',
            'investigation', 'enforcement', 'fine', 'sanction'
        ]

        regulatory_mentions = 0
        sec_investigations = 0

        for filing in sec_filings:
            content = filing.get('content', '').lower()

            for keyword in regulatory_keywords:
                if keyword in content:
                    regulatory_mentions += 1
                    if 'sec investigation' in content or 'formal investigation' in content:
                        sec_investigations += 1
                    break

        # Assess severity
        if sec_investigations > 0:
            severity = 'critical'
            score = 4
        elif regulatory_mentions > 5:
            severity = 'high'
            score = 3
        elif regulatory_mentions > 1:
            severity = 'moderate'
            score = 2
        else:
            severity = 'low'
            score = 1

        return {
            'regulatory_mentions': regulatory_mentions,
            'sec_investigations': sec_investigations,
            'severity_level': severity,
            'severity_score': score
        }

    def _analyze_ip_risks(self, company_data: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze intellectual property risks"""

        # This would analyze patent filings, trademark issues, etc.
        # Simplified analysis based on available data

        profile = company_data.get('profile', [{}])[0]
        industry = profile.get('industry', '').lower()

        # High IP risk industries
        high_ip_risk_industries = [
            'pharmaceuticals', 'biotechnology', 'software', 'semiconductors',
            'entertainment', 'media', 'consumer electronics'
        ]

        if any(ind in industry for ind in high_ip_risk_industries):
            severity = 'high'
            score = 3
            concerns = ["High IP concentration risk", "Potential patent litigation exposure"]
        else:
            severity = 'moderate'
            score = 2
            concerns = ["Standard IP protection requirements"]

        return {
            'ip_risk_level': severity,
            'severity_score': score,
            'key_concerns': concerns
        }

    def _analyze_employment_risks(self, sec_filings: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze employment-related legal risks"""

        employment_keywords = [
            'employment', 'labor', 'union', 'discrimination', 'harassment',
            'wrongful termination', 'wage', 'overtime', 'flsa'
        ]

        employment_mentions = 0

        for filing in sec_filings:
            content = filing.get('content', '').lower()

            for keyword in employment_keywords:
                if keyword in content:
                    employment_mentions += 1
                    break

        if employment_mentions > 3:
            severity = 'high'
            score = 3
        elif employment_mentions > 0:
            severity = 'moderate'
            score = 2
        else:
            severity = 'low'
            score = 1

        return {
            'employment_mentions': employment_mentions,
            'severity_level': severity,
            'severity_score': score
        }

    def _analyze_financial_risks(self, symbol: str, company_data: Dict[str, Any],
                                all_vectors: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze financial reporting and accounting risks with vector data"""

        # Analyze financial statement quality
        quality_issues = self._assess_financial_quality(company_data)
        
        # Get RAG insights for financial risks
        financial_rag = all_vectors.get('rag_vectors', {}).get('financial', {})
        rag_insights = self._extract_rag_insights(financial_rag, 'financial risks')
        
        # Analyze financial models
        model_insights = self._analyze_financial_models(all_vectors.get('financial_models', {}))

        # Related party transactions
        related_party_risks = self._analyze_related_party_transactions(company_data)

        # Off-balance sheet items
        obs_risks = self._analyze_off_balance_sheet_items(company_data)

        # Revenue recognition
        revenue_risks = self._analyze_revenue_recognition(company_data)

        # Calculate financial risk score
        financial_score = self._calculate_category_score([
            quality_issues['severity_score'],
            related_party_risks['severity_score'],
            obs_risks['severity_score'],
            revenue_risks['severity_score']
        ])

        return {
            'financial_quality': quality_issues,
            'related_party_risks': related_party_risks,
            'off_balance_sheet_risks': obs_risks,
            'revenue_recognition_risks': revenue_risks,
            'rag_insights': rag_insights,
            'model_insights': model_insights,
            'overall_financial_score': financial_score,
            'financial_risk_level': self._score_to_risk_level(financial_score),
            'vector_sources_used': ['financial_statements', 'rag_vectors', 'financial_models']
        }

    def _assess_financial_quality(self, company_data: Dict[str, Any]) -> Dict[str, Any]:
        """Assess quality of financial reporting"""

        financials = company_data.get('financials', {})
        income_stmts = financials.get('income_statements', [])

        if len(income_stmts) < 2:
            return {'severity_level': 'unknown', 'severity_score': 2}

        # Check for earnings volatility
        net_incomes = [stmt.get('netIncome', 0) for stmt in income_stmts[:3]]
        revenues = [stmt.get('revenue', 0) for stmt in income_stmts[:3]]

        if revenues[0] > 0:
            earnings_volatility = np.std(net_incomes) / abs(np.mean(net_incomes)) if np.mean(net_incomes) != 0 else 0
            revenue_volatility = np.std(revenues) / np.mean(revenues)

            if earnings_volatility > 0.5 or revenue_volatility > 0.3:
                severity = 'high'
                score = 3
            elif earnings_volatility > 0.3 or revenue_volatility > 0.2:
                severity = 'moderate'
                score = 2
            else:
                severity = 'low'
                score = 1
        else:
            severity = 'moderate'
            score = 2

        return {
            'earnings_volatility': earnings_volatility if 'earnings_volatility' in locals() else 0,
            'revenue_volatility': revenue_volatility if 'revenue_volatility' in locals() else 0,
            'severity_level': severity,
            'severity_score': score
        }

    def _analyze_related_party_transactions(self, company_data: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze related party transaction risks"""

        # This would require detailed footnote analysis
        # Simplified based on available data

        profile = company_data.get('profile', [{}])[0]
        industry = profile.get('industry', '').lower()

        # Industries with higher related party risk
        high_risk_industries = ['real estate', 'construction', 'private equity']

        if any(ind in industry for ind in high_risk_industries):
            severity = 'high'
            score = 3
        else:
            severity = 'moderate'
            score = 2

        return {
            'severity_level': severity,
            'severity_score': score,
            'risk_factors': ['Related party transactions common in industry'] if score > 2 else []
        }

    def _analyze_off_balance_sheet_items(self, company_data: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze off-balance sheet exposures"""

        # Simplified analysis - would need detailed footnote review
        financials = company_data.get('financials', {})
        balance_stmts = financials.get('balance_sheets', [])

        if not balance_stmts:
            return {'severity_level': 'unknown', 'severity_score': 2}

        latest_balance = balance_stmts[0]
        total_assets = latest_balance.get('totalAssets', 0)
        total_liabilities = latest_balance.get('totalLiabilities', 0)

        # Look for signs of off-balance sheet items
        debt_to_assets = total_liabilities / total_assets if total_assets > 0 else 0

        if debt_to_assets > 0.8:
            severity = 'high'
            score = 3
        elif debt_to_assets > 0.6:
            severity = 'moderate'
            score = 2
        else:
            severity = 'low'
            score = 1

        return {
            'debt_to_assets_ratio': debt_to_assets,
            'severity_level': severity,
            'severity_score': score
        }

    def _analyze_revenue_recognition(self, company_data: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze revenue recognition policies and risks"""

        # Simplified analysis based on industry and growth patterns
        profile = company_data.get('profile', [{}])[0]
        industry = profile.get('industry', '').lower()

        # Industries with complex revenue recognition
        complex_revenue_industries = [
            'software', 'saas', 'telecommunications', 'construction',
            'aerospace', 'defense'
        ]

        if any(ind in industry for ind in complex_revenue_industries):
            severity = 'high'
            score = 3
        else:
            severity = 'moderate'
            score = 2

        return {
            'severity_level': severity,
            'severity_score': score,
            'complexity_factors': ['Complex revenue recognition policies'] if score > 2 else []
        }

    def _analyze_operational_risks(self, symbol: str, company_data: Dict[str, Any],
                                  all_vectors: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze operational and business risks with vector data"""

        # Supply chain analysis
        supply_chain_risks = self._analyze_supply_chain_risks(company_data)
        
        # Get RAG insights for operational risks
        operational_rag = all_vectors.get('rag_vectors', {}).get('operational', {})
        rag_insights = self._extract_rag_insights(operational_rag, 'operational risks')

        # Key personnel risk
        personnel_risks = self._analyze_key_personnel_risks(company_data)

        # Technology obsolescence
        tech_risks = self._analyze_technology_risks(company_data)

        # Operational efficiency
        efficiency_risks = self._analyze_operational_efficiency(company_data)

        # Calculate operational risk score
        operational_score = self._calculate_category_score([
            supply_chain_risks['severity_score'],
            personnel_risks['severity_score'],
            tech_risks['severity_score'],
            efficiency_risks['severity_score']
        ])

        return {
            'supply_chain_risks': supply_chain_risks,
            'personnel_risks': personnel_risks,
            'technology_risks': tech_risks,
            'efficiency_risks': efficiency_risks,
            'rag_insights': rag_insights,
            'overall_operational_score': operational_score,
            'operational_risk_level': self._score_to_risk_level(operational_score),
            'vector_sources_used': ['company_data', 'rag_vectors']
        }

    def _analyze_supply_chain_risks(self, company_data: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze supply chain vulnerabilities"""

        profile = company_data.get('profile', [{}])[0]
        industry = profile.get('industry', '').lower()

        # Industries with high supply chain risk
        high_risk_industries = [
            'semiconductors', 'automotive', 'electronics', 'pharmaceuticals',
            'aerospace', 'consumer electronics'
        ]

        if any(ind in industry for ind in high_risk_industries):
            severity = 'high'
            score = 3
        else:
            severity = 'moderate'
            score = 2

        return {
            'severity_level': severity,
            'severity_score': score,
            'risk_factors': ['Global supply chain dependencies', 'Geopolitical risks']
        }

    def _analyze_key_personnel_risks(self, company_data: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze dependence on key personnel"""

        # Analyze executive compensation and tenure
        executives = company_data.get('executives', [])

        if len(executives) < 3:
            severity = 'high'
            score = 3
        else:
            severity = 'moderate'
            score = 2

        return {
            'executive_count': len(executives),
            'severity_level': severity,
            'severity_score': score
        }

    def _analyze_technology_risks(self, company_data: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze technology obsolescence risks"""

        profile = company_data.get('profile', [{}])[0]
        industry = profile.get('industry', '').lower()

        # Technology-dependent industries
        tech_industries = [
            'software', 'internet', 'e-commerce', 'social media',
            'semiconductors', 'biotechnology'
        ]

        if any(ind in industry for ind in tech_industries):
            severity = 'high'
            score = 3
        else:
            severity = 'low'
            score = 1

        return {
            'severity_level': severity,
            'severity_score': score
        }

    def _analyze_operational_efficiency(self, company_data: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze operational efficiency and capacity"""

        financials = company_data.get('financials', {})
        income_stmts = financials.get('income_statements', [])

        if len(income_stmts) < 2:
            return {'severity_level': 'unknown', 'severity_score': 2}

        # Analyze margin trends
        latest = income_stmts[0]
        previous = income_stmts[1]

        latest_margin = latest.get('netIncome', 0) / latest.get('revenue', 1)
        previous_margin = previous.get('netIncome', 0) / previous.get('revenue', 1)

        margin_trend = latest_margin - previous_margin

        if margin_trend < -0.05:
            severity = 'high'
            score = 3
        elif margin_trend < -0.02:
            severity = 'moderate'
            score = 2
        else:
            severity = 'low'
            score = 1

        return {
            'margin_trend': margin_trend,
            'severity_level': severity,
            'severity_score': score
        }

    def _analyze_strategic_risks(self, symbol: str, company_data: Dict[str, Any],
                                all_vectors: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze strategic and market risks with vector data"""

        # Market position analysis
        market_position = self._analyze_market_position(company_data)
        
        # Get RAG insights for strategic risks
        strategic_rag = all_vectors.get('rag_vectors', {}).get('strategic', {})
        rag_insights = self._extract_rag_insights(strategic_rag, 'strategic risks')

        # Competitive threats
        competitive_risks = self._analyze_competitive_threats(company_data)

        # Customer concentration
        customer_risks = self._analyze_customer_concentration(company_data)

        # Industry trends
        industry_risks = self._analyze_industry_trends(company_data)

        # Calculate strategic risk score
        strategic_score = self._calculate_category_score([
            market_position['severity_score'],
            competitive_risks['severity_score'],
            customer_risks['severity_score'],
            industry_risks['severity_score']
        ])

        return {
            'market_position': market_position,
            'competitive_risks': competitive_risks,
            'customer_concentration': customer_risks,
            'industry_trends': industry_risks,
            'rag_insights': rag_insights,
            'overall_strategic_score': strategic_score,
            'strategic_risk_level': self._score_to_risk_level(strategic_score),
            'vector_sources_used': ['market_data', 'rag_vectors']
        }

    def _analyze_market_position(self, company_data: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze company's market position"""

        market_data = company_data.get('market', {})
        market_cap = market_data.get('marketCap', 0)

        # Simplified market share analysis
        if market_cap > 50000000000:  # $50B+
            severity = 'low'
            score = 1
        elif market_cap > 10000000000:  # $10B+
            severity = 'moderate'
            score = 2
        else:
            severity = 'high'
            score = 3

        return {
            'market_cap': market_cap,
            'severity_level': severity,
            'severity_score': score
        }

    def _analyze_competitive_threats(self, company_data: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze competitive landscape"""

        profile = company_data.get('profile', [{}])[0]
        industry = profile.get('industry', '').lower()

        # Highly competitive industries
        competitive_industries = [
            'technology', 'e-commerce', 'social media', 'ride sharing',
            'food delivery', 'streaming'
        ]

        if any(ind in industry for ind in competitive_industries):
            severity = 'high'
            score = 3
        else:
            severity = 'moderate'
            score = 2

        return {
            'severity_level': severity,
            'severity_score': score
        }

    def _analyze_customer_concentration(self, company_data: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze customer concentration risks"""

        # This would require detailed customer data analysis
        # Simplified based on industry

        profile = company_data.get('profile', [{}])[0]
        industry = profile.get('industry', '').lower()

        # Industries with potential customer concentration
        concentration_industries = [
            'aerospace', 'defense', 'automotive suppliers',
            'pharmaceuticals', 'medical devices'
        ]

        if any(ind in industry for ind in concentration_industries):
            severity = 'high'
            score = 3
        else:
            severity = 'moderate'
            score = 2

        return {
            'severity_level': severity,
            'severity_score': score
        }

    def _analyze_industry_trends(self, company_data: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze industry trend risks"""

        profile = company_data.get('profile', [{}])[0]
        industry = profile.get('industry', '').lower()

        # Industries facing disruption
        disruption_industries = [
            'retail', 'traditional media', 'taxi services',
            'film rental', 'travel agencies'
        ]

        if any(ind in industry for ind in disruption_industries):
            severity = 'high'
            score = 3
        else:
            severity = 'moderate'
            score = 2

        return {
            'severity_level': severity,
            'severity_score': score
        }

    def _analyze_reputational_risks(self, symbol: str, company_data: Dict[str, Any],
                                   all_vectors: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze reputational and ESG risks with vector data"""

        # Brand perception
        brand_risks = self._analyze_brand_perception(company_data)
        
        # Get RAG insights for reputational risks
        reputational_rag = all_vectors.get('rag_vectors', {}).get('reputational', {})
        rag_insights = self._extract_rag_insights(reputational_rag, 'reputational risks')

        # Social media sentiment
        social_sentiment = self._analyze_social_sentiment(symbol, company_data)

        # Executive compensation
        compensation_risks = self._analyze_executive_compensation(company_data)

        # ESG compliance
        esg_risks = self._analyze_esg_compliance(company_data)

        # Calculate reputational risk score
        reputational_score = self._calculate_category_score([
            brand_risks['severity_score'],
            social_sentiment['severity_score'],
            compensation_risks['severity_score'],
            esg_risks['severity_score']
        ])

        return {
            'brand_perception': brand_risks,
            'social_sentiment': social_sentiment,
            'executive_compensation': compensation_risks,
            'esg_compliance': esg_risks,
            'rag_insights': rag_insights,
            'overall_reputational_score': reputational_score,
            'reputational_risk_level': self._score_to_risk_level(reputational_score),
            'vector_sources_used': ['news_data', 'rag_vectors']
        }

    def _analyze_brand_perception(self, company_data: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze brand perception risks"""

        # Simplified analysis based on news sentiment
        news_data = company_data.get('news', {})
        sentiment = news_data.get('sentiment', {})

        sentiment_score = sentiment.get('score', 0)

        if sentiment_score < -0.2:
            severity = 'high'
            score = 3
        elif sentiment_score < -0.1:
            severity = 'moderate'
            score = 2
        else:
            severity = 'low'
            score = 1

        return {
            'sentiment_score': sentiment_score,
            'severity_level': severity,
            'severity_score': score
        }

    def _analyze_social_sentiment(self, symbol: str, company_data: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze social media sentiment"""

        # This would integrate with social media APIs
        # Simplified placeholder

        profile = company_data.get('profile', [{}])[0]
        industry = profile.get('industry', '').lower()

        # Industries with high social media scrutiny
        social_industries = [
            'consumer goods', 'food', 'beverages', 'entertainment',
            'social media', 'e-commerce'
        ]

        if any(ind in industry for ind in social_industries):
            severity = 'high'
            score = 3
        else:
            severity = 'moderate'
            score = 2

        return {
            'severity_level': severity,
            'severity_score': score
        }

    def _analyze_executive_compensation(self, company_data: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze executive compensation risks"""

        executives = company_data.get('executives', [])

        if not executives:
            return {'severity_level': 'unknown', 'severity_score': 2}

        # Check for excessive compensation relative to performance
        # Simplified analysis

        severity = 'moderate'
        score = 2

        return {
            'executive_count': len(executives),
            'severity_level': severity,
            'severity_score': score
        }

    def _analyze_esg_compliance(self, company_data: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze ESG compliance risks"""

        # This would integrate with ESG data providers
        # Simplified analysis

        profile = company_data.get('profile', [{}])[0]
        industry = profile.get('industry', '').lower()

        # Industries with high ESG scrutiny
        esg_industries = [
            'oil & gas', 'mining', 'chemicals', 'tobacco',
            'weapons', 'palm oil'
        ]

        if any(ind in industry for ind in esg_industries):
            severity = 'high'
            score = 3
        else:
            severity = 'moderate'
            score = 2

        return {
            'severity_level': severity,
            'severity_score': score
        }

    def _analyze_documents_with_rag(self, symbol: str, company_data: Dict[str, Any], 
                                   all_vectors: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze documents using RAG for comprehensive insights"""

        # Get all RAG vectors
        rag_vectors = all_vectors.get('rag_vectors', {})
        
        # Compile all RAG insights
        all_insights = []
        all_risk_indicators = []
        
        for category, rag_data in rag_vectors.items():
            insights = self._extract_rag_insights(rag_data, f"{category} documents")
            all_insights.extend(insights)
            
            # Extract risk indicators from contexts
            contexts = rag_data.get('contexts', {}).get('contexts', [])
            if contexts:
                # Look for key risk keywords in contexts
                risk_keywords = ['risk', 'concern', 'issue', 'problem', 'challenge', 'threat']
                for ctx in contexts[:3]:
                    text = ctx.get('text', '').lower()
                    if any(keyword in text for keyword in risk_keywords):
                        all_risk_indicators.append({
                            'category': category,
                            'indicator': text[:200]  # First 200 chars
                        })

        # Generate comprehensive RAG-based recommendations
        if all_insights:
            prompt = f"""
Based on the following due diligence insights for {symbol}:

{chr(10).join(all_insights[:10])}

Provide 3-5 actionable recommendations for deal structuring and risk mitigation.
"""
            
            try:
                recommendations_text = self.rag_manager.generate_with_rag(prompt)
                recommendations = [line.strip() for line in recommendations_text.split('\n') 
                                 if line.strip() and not line.strip().startswith('#')]
            except Exception as e:
                logger.error(f"Error generating RAG recommendations: {e}")
                recommendations = []
        else:
            recommendations = []

        return {
            'documents_analyzed': sum(data.get('contexts_retrieved', 0) 
                                     for data in rag_vectors.values()),
            'key_insights': all_insights[:10],
            'risk_indicators': all_risk_indicators[:5],
            'recommendations': recommendations[:5],
            'rag_analysis_complete': True
        }

    def _calculate_category_score(self, scores: List[int]) -> float:
        """Calculate average category score"""

        if not scores:
            return 2.0

        return sum(scores) / len(scores)

    def _score_to_risk_level(self, score: float) -> str:
        """Convert numerical score to risk level"""

        if score >= 3.5:
            return 'critical'
        elif score >= 2.5:
            return 'high'
        elif score >= 1.5:
            return 'moderate'
        else:
            return 'low'

    def _extract_key_concerns(self, risk_analyses: List[Dict[str, Any]]) -> List[str]:
        """Extract key concerns from risk analyses"""

        concerns = []

        for analysis in risk_analyses:
            if analysis.get('severity_level') in ['high', 'critical']:
                concern = f"{analysis.get('severity_level', '').title()} risk: {analysis.get('key_concerns', [''])[0]}"
                concerns.append(concern)

        return concerns[:5]  # Top 5 concerns

    def _calculate_overall_risk_assessment(self, risk_categories: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate overall risk assessment"""

        category_scores = {}

        for category, analysis in risk_categories.items():
            if 'overall_' in analysis and 'score' in analysis['overall_' + category.split('_')[0] + '_score']:
                score_key = f"overall_{category.split('_')[0]}_score"
                category_scores[category] = analysis[score_key]
            elif 'overall_score' in analysis:
                category_scores[category] = analysis['overall_score']

        if not category_scores:
            return {'overall_risk_level': 'unknown', 'overall_score': 2.0}

        overall_score = sum(category_scores.values()) / len(category_scores)

        if overall_score >= 3.5:
            overall_risk = 'critical'
        elif overall_score >= 2.5:
            overall_risk = 'high'
        elif overall_score >= 1.5:
            overall_risk = 'moderate'
        else:
            overall_risk = 'low'

        return {
            'overall_risk_level': overall_risk,
            'overall_score': overall_score,
            'category_scores': category_scores,
            'risk_distribution': self._analyze_risk_distribution(category_scores)
        }

    def _analyze_risk_distribution(self, category_scores: Dict[str, float]) -> Dict[str, Any]:
        """Analyze risk distribution across categories"""

        high_risk_categories = [cat for cat, score in category_scores.items() if score >= 2.5]
        moderate_risk_categories = [cat for cat, score in category_scores.items() if 1.5 <= score < 2.5]
        low_risk_categories = [cat for cat, score in category_scores.items() if score < 1.5]

        return {
            'high_risk_categories': high_risk_categories,
            'moderate_risk_categories': moderate_risk_categories,
            'low_risk_categories': low_risk_categories,
            'risk_concentration': 'high' if len(high_risk_categories) >= 3 else 'moderate' if len(high_risk_categories) >= 2 else 'low'
        }

    def _generate_due_diligence_recommendations(self, overall_assessment: Dict[str, Any],
                                              company_data: Dict[str, Any],
                                              all_vectors: Dict[str, Any]) -> List[str]:
        """Generate due diligence recommendations"""

        recommendations = []
        overall_risk = overall_assessment.get('overall_risk_level', 'moderate')

        if overall_risk in ['critical', 'high']:
            recommendations.extend([
                "Conduct extensive legal and regulatory due diligence",
                "Perform detailed financial audit and quality assessment",
                "Engage specialized consultants for high-risk areas",
                "Consider increased purchase price adjustments"
            ])

        risk_distribution = overall_assessment.get('risk_distribution', {})
        high_risk_categories = risk_distribution.get('high_risk_categories', [])

        for category in high_risk_categories:
            if 'legal' in category:
                recommendations.append("Engage legal counsel for litigation review")
            elif 'financial' in category:
                recommendations.append("Conduct forensic accounting review")
            elif 'operational' in category:
                recommendations.append("Perform operational due diligence")
            elif 'strategic' in category:
                recommendations.append("Analyze competitive positioning thoroughly")

        recommendations.append("Establish clear risk mitigation strategies")
        recommendations.append("Define post-acquisition integration plan")

        return recommendations[:8]  # Limit to top 8 recommendations

    def _generate_dd_summary(self, overall_assessment: Dict[str, Any]) -> Dict[str, Any]:
        """Generate due diligence summary"""

        overall_risk = overall_assessment.get('overall_risk_level', 'moderate')

        if overall_risk == 'critical':
            summary_text = "Critical risk factors identified requiring immediate attention and potential deal restructuring."
            deal_impact = "high_impact"
        elif overall_risk == 'high':
            summary_text = "High risk factors identified requiring thorough mitigation strategies."
            deal_impact = "moderate_high_impact"
        elif overall_risk == 'moderate':
            summary_text = "Moderate risk factors identified, manageable with proper due diligence."
            deal_impact = "moderate_impact"
        else:
            summary_text = "Low risk profile identified, favorable for transaction completion."
            deal_impact = "low_impact"

        return {
            'summary_text': summary_text,
            'deal_impact': deal_impact,
            'overall_risk_level': overall_risk,
            'recommendation': 'proceed_with_caution' if overall_risk in ['critical', 'high'] else 'proceed'
        }

# Global due diligence agent instance
dd_agent = DueDiligenceAgent()

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
        'service': 'dd-agent',
        'version': '1.0.0'
    })

@app.route('/due-diligence/analyze', methods=['POST'])
@require_api_key
def perform_due_diligence():
    """Perform comprehensive due diligence analysis"""
    try:
        data = request.get_json()
        symbol = data.get('symbol', '')
        company_data = data.get('company_data', {})

        if not symbol or not company_data:
            return jsonify({'error': 'Symbol and company data are required'}), 400

        analysis = dd_agent.perform_comprehensive_due_diligence(symbol, company_data)

        return jsonify(analysis)

    except Exception as e:
        logger.error(f"Error performing due diligence: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/due-diligence/risk-assessment/<category>', methods=['POST'])
@require_api_key
def assess_specific_risk(category):
    """Assess specific risk category"""
    try:
        data = request.get_json()
        symbol = data.get('symbol', '')
        company_data = data.get('company_data', {})

        # Get all vectors for comprehensive analysis
        all_vectors = dd_agent.vector_integrator.get_comprehensive_vectors(symbol)

        if category == 'legal':
            result = dd_agent._analyze_legal_risks(symbol, company_data, all_vectors)
        elif category == 'financial':
            result = dd_agent._analyze_financial_risks(symbol, company_data, all_vectors)
        elif category == 'operational':
            result = dd_agent._analyze_operational_risks(symbol, company_data, all_vectors)
        elif category == 'strategic':
            result = dd_agent._analyze_strategic_risks(symbol, company_data, all_vectors)
        elif category == 'reputational':
            result = dd_agent._analyze_reputational_risks(symbol, company_data, all_vectors)
        else:
            return jsonify({'error': 'Invalid risk category'}), 400

        return jsonify(result)

    except Exception as e:
        logger.error(f"Error assessing {category} risk: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/due-diligence/risk-summary', methods=['POST'])
@require_api_key
def get_risk_summary():
    """Get risk assessment summary"""
    try:
        data = request.get_json()
        risk_assessments = data.get('risk_assessments', {})

        summary = dd_agent._calculate_overall_risk_assessment(risk_assessments)

        return jsonify(summary)

    except Exception as e:
        logger.error(f"Error generating risk summary: {e}")
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    port = int(os.getenv('PORT', 8080))
    app.run(host='0.0.0.0', port=port, debug=False)
