# SEQUENTIAL WORKFLOW ANALYSIS
## M&A Financial Analysis Platform - Human-Grade Sequential Run Plan

**Analysis Date:** November 10, 2025  
**Deal Context:** NVDA Acquisition by Tesla (hypothetical example)  
**As-of Date:** November 10, 2025  
**Output Set:** Glass-box Excel, PDF deck, logs, coverage & vector stats

---

## EXECUTIVE SUMMARY

This document maps the current platform implementation against a **human-grade sequential workflow** for M&A analysis. The workflow follows industry best practices: Setup → Ingestion → Normalization → Modeling → Valuations → QA → Deliverables.

### Overall Readiness Assessment
| Phase | Human-Grade Requirement | Current Status | Gap Severity |
|-------|------------------------|----------------|--------------|
| Phase 0: Setup & Config | ✅ Required | ❌ Not Implemented | 🔴 CRITICAL |
| Phase 1: Source Ingestion | ✅ Required | ⚠️ Partial (70%) | 🟡 MEDIUM |
| Phase 2: Vectorization & RAG | ✅ Required | ⚠️ Partial (60%) | 🟡 MEDIUM |
| Phase 3: Lifecycle Classification | ✅ Required | ✅ Implemented (85%) | 🟢 LOW |
| Phase 4: Historical Normalization | ✅ Required | ❌ Not Implemented | 🔴 CRITICAL |
| Phase 5: 3-Statement Model | ✅ Required | ⚠️ Disconnected (50%) | 🔴 CRITICAL |
| Phase 6: Valuation Stack | ✅ Required | ⚠️ Partial (45%) | 🔴 CRITICAL |
| Phase 7: QA & Traceability | ✅ Required | ❌ Not Implemented | 🔴 CRITICAL |
| Phase 8: Reporting & Delivery | ✅ Required | ⚠️ Basic (30%) | 🔴 CRITICAL |

**Overall Platform Readiness: 55% - NOT READY FOR PRODUCTION**

---

## PHASE 0 — SETUP & CONFIG
**Gate: ✅ Config saved**

### Human-Grade Requirements

1. **Initialize Run Context**
   - Tickers: TSLA (acquirer), NVDA (target)
   - As-of date: 2025-11-10
   - Freeze market data snapshot and FX set

2. **Record Versions**
   - Commit hashes (code, prompts)
   - Model/embedding versions
   - Feature flags

3. **Parameter File**
   - Load parameter block
   - Persist to `/runs/TSLA_NVDA_2025-11-10/config.json`

### Current Implementation Status: ❌ NOT IMPLEMENTED

**What Exists:**
- Environment variables for API keys
- Service configuration in .env file
- No run management system
- No versioning system
- No parameter persistence

**Critical Gaps:**
1. ❌ No run context management
2. ❌ No versioning/hashing system
3. ❌ No parameter persistence layer
4. ❌ No market data snapshot capability
5. ❌ No run folder structure (`/runs/DEAL_DATE/`)

**Required Implementation:**

```python
# services/run-manager/main.py (NEW SERVICE NEEDED)

class RunManager:
    """Manages analysis runs with versioning and config persistence"""
    
    def initialize_run(self, acquirer_symbol: str, target_symbol: str, 
                      as_of_date: str) -> str:
        """
        Initialize a new analysis run
        Returns: run_id (e.g., "TSLA_NVDA_2025-11-10")
        """
        run_id = f"{acquirer_symbol}_{target_symbol}_{as_of_date}"
        run_dir = f"/runs/{run_id}"
        
        # Create run directory structure
        os.makedirs(f"{run_dir}/data", exist_ok=True)
        os.makedirs(f"{run_dir}/models", exist_ok=True)
        os.makedirs(f"{run_dir}/reports", exist_ok=True)
        os.makedirs(f"{run_dir}/logs", exist_ok=True)
        
        # Capture versions
        version_manifest = {
            'run_id': run_id,
            'created_at': datetime.now().isoformat(),
            'git_commit': self._get_git_commit(),
            'python_version': sys.version,
            'service_versions': self._get_service_versions(),
            'model_versions': {
                'gemini': GEMINI_MODEL,
                'embedding': 'text-embedding-004'
            }
        }
        
        # Save config
        config = {
            'acquirer': acquirer_symbol,
            'target': target_symbol,
            'as_of_date': as_of_date,
            'market_snapshot': self._capture_market_snapshot(),
            'fx_rates': self._capture_fx_rates(),
            'parameters': self._load_parameters()
        }
        
        with open(f"{run_dir}/config.json", 'w') as f:
            json.dump(config, f, indent=2)
            
        with open(f"{run_dir}/version_manifest.json", 'w') as f:
            json.dump(version_manifest, f, indent=2)
        
        return run_id
```

**Deliverables Required:**
- ✅ config.json (run parameters)
- ✅ version_manifest.json (code/model versions)
- ✅ Run folder structure created

**Implementation Priority:** 🔴 CRITICAL - Must be first

---

## PHASE 1 — SOURCE INGESTION
**Gate: ✅ Coverage ≥95%**

### Human-Grade Requirements

1. **Collect Documents (both companies)**
   - 10-K (last 3 years)
   - Latest 10-Q
   - 8-K filings
   - DEF 14A (proxy statements)
   - Historical S-4s if relevant
   - Footnotes, MD&A, risk factors
   - Management projections
   - Earnings call transcripts
   - IR decks

2. **Validate Completeness**
   - Emit coverage report (doc list, dates, hashes)
   - Flag gaps and closest substitutes

### Current Implementation Status: ⚠️ PARTIAL (70%)

**What Exists:**
✅ Data ingestion service implemented (services/data-ingestion/main.py)
✅ SEC filing fetching (10-K, 10-Q, 8-K)
✅ FMP API integration
✅ Document chunking
✅ Multiple data sources (SEC, analysts, news)

**Critical Gaps:**
1. ❌ No coverage validation (≥95% requirement)
2. ❌ No proxy statement (DEF 14A) fetching
3. ❌ No earnings call transcript integration
4. ❌ No IR deck collection
5. ❌ No gap flagging/substitution logic
6. ❌ No document hashing for verification
7. ❌ No "last 3 years" enforcement (currently arbitrary)

**Required Enhancements:**

```python
# Enhancement to services/data-ingestion/main.py

class ComprehensiveDocumentCollector:
    """Collects all required documents with coverage validation"""
    
    REQUIRED_DOCUMENTS = {
        'annual_10k': {'count': 3, 'priority': 'critical'},
        'quarterly_10q': {'count': 1, 'priority': 'critical'},
        'proxy_def14a': {'count': 1, 'priority': 'high'},
        '8k_filings': {'count': 'all_recent', 'priority': 'medium'},
        'earnings_transcripts': {'count': 4, 'priority': 'high'},
        'investor_presentations': {'count': 2, 'priority': 'medium'}
    }
    
    def collect_with_validation(self, symbol: str, as_of_date: str) -> Dict:
        """
        Collect documents and validate coverage
        Returns: {
            'documents': [...],
            'coverage_report': {...},
            'gaps': [...],
            'coverage_percentage': 0.0-1.0
        }
        """
        collected = {}
        gaps = []
        
        # Collect each document type
        for doc_type, requirements in self.REQUIRED_DOCUMENTS.items():
            docs = self._fetch_document_type(symbol, doc_type, as_of_date, requirements)
            collected[doc_type] = docs
            
            # Validate count
            expected = requirements['count']
            actual = len(docs)
            
            if isinstance(expected, int) and actual < expected:
                gaps.append({
                    'type': doc_type,
                    'expected': expected,
                    'actual': actual,
                    'priority': requirements['priority'],
                    'substitution': self._find_substitution(doc_type, symbol)
                })
        
        # Calculate coverage
        coverage = self._calculate_coverage(collected, gaps)
        
        # Generate coverage report
        coverage_report = {
            'symbol': symbol,
            'as_of_date': as_of_date,
            'coverage_percentage': coverage,
            'documents_collected': sum(len(docs) for docs in collected.values()),
            'document_manifest': self._create_manifest(collected),
            'gaps': gaps,
            'status': 'PASS' if coverage >= 0.95 else 'FAIL'
        }
        
        return {
            'documents': collected,
            'coverage_report': coverage_report,
            'gaps': gaps,
            'coverage_percentage': coverage
        }
```

**Deliverables Required:**
- ✅ Coverage report (JSON/CSV) with document list, dates, hashes
- ✅ Raw docs store with organized structure
- ✅ Gap analysis with substitutions
- ❌ Currently missing: Comprehensive coverage validation

**Gate Check:** Coverage ≥95% must be enforced before proceeding

**Implementation Priority:** 🟡 MEDIUM - Functional but needs validation layer

---

## PHASE 2 — VECTORIZATION & RAG
**Gate: ✅ Citations resolving**

### Human-Grade Requirements

1. **Chunk & Embed**
   - Chunk size ~1200 tokens
   - Overlap ~150 tokens
   - Embed to vector DB

2. **RAG Smoke Test**
   - Probe sample queries:
     - SBC policy
     - Lease commitments
     - Segment revenue footnotes
   - Verify section-level citations resolve to doc+page/section

### Current Implementation Status: ⚠️ PARTIAL (60%)

**What Exists:**
✅ Document chunking implemented
✅ Vector embedding to Vertex AI RAG
✅ Chunk metadata tracking
✅ RAG retrieval methods in orchestrator

**Critical Gaps:**
1. ❌ Chunk size not standardized (currently 1000, not 1200)
2. ❌ Overlap not consistent (currently 200, should be 150)
3. ❌ No RAG smoke test suite
4. ❌ Citations don't resolve to page/section level
5. ❌ No validation that citations are working
6. ❌ No vector index stats reporting

**Required Enhancements:**

```python
# Enhancement to services/data-ingestion/main.py

class RAGValidator:
    """Validates RAG functionality with smoke tests"""
    
    SMOKE_TEST_QUERIES = [
        {
            'query': 'What is the stock-based compensation policy?',
            'expected_sections': ['Significant Accounting Policies', 'Note 2'],
            'doc_types': ['10-K']
        },
        {
            'query': 'What are the lease commitments?',
            'expected_sections': ['Note 8', 'Leases', 'Commitments'],
            'doc_types': ['10-K', '10-Q']
        },
        {
            'query': 'What is the segment revenue breakdown?',
            'expected_sections': ['Segment Information', 'Note 15'],
            'doc_types': ['10-K', '10-Q']
        }
    ]
    
    def validate_rag_citations(self, symbol: str, corpus_id: str) -> Dict:
        """
        Run smoke tests and validate citation resolution
        Returns: {
            'tests_passed': int,
            'tests_failed': int,
            'citation_resolution_rate': float,
            'failed_queries': [],
            'vector_stats': {...}
        }
        """
        results = {
            'passed': 0,
            'failed': 0,
            'failed_queries': [],
            'citation_details': []
        }
        
        for test in self.SMOKE_TEST_QUERIES:
            # Retrieve contexts
            contexts = self._retrieve_contexts(corpus_id, test['query'], top_k=3)
            
            # Validate citations
            citations_valid = self._validate_citations(contexts, test['expected_sections'])
            
            if citations_valid:
                results['passed'] += 1
            else:
                results['failed'] += 1
                results['failed_queries'].append(test['query'])
            
            results['citation_details'].append({
                'query': test['query'],
                'valid': citations_valid,
                'contexts': contexts
            })
        
        # Get vector index stats
        vector_stats = self._get_vector_stats(corpus_id)
        
        return {
            'tests_passed': results['passed'],
            'tests_failed': results['failed'],
            'citation_resolution_rate': results['passed'] / len(self.SMOKE_TEST_QUERIES),
            'failed_queries': results['failed_queries'],
            'vector_stats': vector_stats,
            'citation_details': results['citation_details']
        }
    
    def _validate_citations(self, contexts: List, expected_sections: List) -> bool:
        """Check if retrieved contexts contain expected sections"""
        retrieved_sections = [ctx.get('section', '') for ctx in contexts]
        
        # Check if any expected section is found
        for expected in expected_sections:
            if any(expected.lower() in section.lower() for section in retrieved_sections):
                return True
        
        return False
    
    def _get_vector_stats(self, corpus_id: str) -> Dict:
        """Get vector index statistics"""
        return {
            'total_chunks': 0,  # Query from Vertex AI
            'total_documents': 0,
            'avg_chunk_size': 1200,
            'overlap': 150,
            'embedding_model': 'text-embedding-004'
        }
```

**Chunk Standardization Required:**

```python
def _chunk_document(self, content: str, metadata: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Chunk document with standardized parameters"""
    
    # STANDARDIZED PARAMETERS
    CHUNK_SIZE = 1200  # tokens (not characters)
    OVERLAP = 150  # tokens
    
    # Convert to tokens for precise chunking
    tokenizer = self._get_tokenizer()
    tokens = tokenizer.encode(content)
    
    chunks = []
    start = 0
    chunk_id = 0
    
    while start < len(tokens):
        end = min(start + CHUNK_SIZE, len(tokens))
        chunk_tokens = tokens[start:end]
        chunk_text = tokenizer.decode(chunk_tokens)
        
        # Extract section information for citation
        section_info = self._extract_section_info(chunk_text)
        
        chunks.append({
            'id': f"{metadata['file_name']}_chunk_{chunk_id}",
            'content': chunk_text,
            'metadata': {
                **metadata,
                'chunk_number': chunk_id,
                'start_token': start,
                'end_token': end,
                'section': section_info.get('section'),
                'page': section_info.get('page'),
                'document_part': section_info.get('part')
            }
        })
        
        chunk_id += 1
        start = end - OVERLAP  # Overlap for context
    
    return chunks
```

**Deliverables Required:**
- ✅ Vector index stats report
- ✅ RAG probe log with smoke test results
- ❌ Currently missing: Citation resolution validation

**Gate Check:** Citations must resolve to doc+page/section before proceeding

**Implementation Priority:** 🟡 MEDIUM - Infrastructure exists, needs validation

---

## PHASE 3 — LIFECYCLE CLASSIFICATION
**Gate: ✅ Memo approved**

### Human-Grade Requirements

1. **Classify TSLA & NVDA**
   - Labels: Emerging / Growth / Mature / Transition
   - Basis: revenue CAGR, margin trajectory, reinvestment, R&D/CapEx intensity, ROIC vs WACC, TAM/competition

2. **Write 1-pager per company**
   - Metrics table → conclusion → implications for model (WACC/LTG, reinvestment/multiples)

### Current Implementation Status: ✅ IMPLEMENTED (85%)

**What Exists:**
✅ Company classifier in LLM Orchestrator
✅ 10+ classification categories
✅ Growth profile classification (hyper-growth to distressed)
✅ Business model classification
✅ Industry-specific analysis
✅ Gemini 2.5 Pro integration

**Minor Gaps:**
1. ⚠️ Classification labels don't exactly match (uses "hyper_growth" vs "Emerging")
2. ⚠️ No formal 1-pager memo generation
3. ⚠️ ROIC vs WACC calculation not explicit
4. ⚠️ TAM/competition analysis superficial

**Required Enhancements:**

```python
# Enhancement to services/llm-orchestrator/main.py

class LifecycleClassifier:
    """Human-grade lifecycle classification with memo generation"""
    
    LIFECYCLE_LABELS = ['Emerging', 'Growth', 'Mature', 'Transition']
    
    def classify_with_memo(self, symbol: str, company_data: Dict) -> Dict:
        """
        Classify company and generate 1-pager memo
        
        Returns: {
            'classification': {
                'label': 'Growth',
                'confidence': 0.85,
                'metrics': {...}
            },
            'memo': {
                'metrics_table': {...},
                'conclusion': '...',
                'model_implications': {...}
            }
        }
        """
        # Calculate key metrics
        metrics = self._calculate_lifecycle_metrics(company_data)
        
        # Classify based on metrics
        classification = self._classify_lifecycle(metrics)
        
        # Generate memo
        memo = self._generate_classification_memo(
            symbol, classification, metrics, company_data
        )
        
        return {
            'symbol': symbol,
            'classification': classification,
            'memo': memo,
            'generated_at': datetime.now().isoformat()
        }
    
    def _calculate_lifecycle_metrics(self, company_data: Dict) -> Dict:
        """Calculate metrics for lifecycle classification"""
        financials = company_data.get('financials', {})
        
        # Revenue CAGR (3-year)
        revenue_cagr = self._calculate_cagr(financials, 'revenue', 3)
        
        # Margin trajectory
        margins = self._calculate_margin_trajectory(financials)
        
        # Reinvestment rate (CapEx + R&D) / Revenue
        reinvestment_rate = self._calculate_reinvestment_rate(financials)
        
        # ROIC vs WACC
        roic = self._calculate_roic(financials)
        wacc = self._estimate_wacc(company_data)
        roic_spread = roic - wacc
        
        # R&D and CapEx intensity
        rd_intensity = self._calculate_rd_intensity(financials)
        capex_intensity = self._calculate_capex_intensity(financials)
        
        return {
            'revenue_cagr_3y': revenue_cagr,
            'gross_margin': margins['gross_margin'],
            'operating_margin': margins['operating_margin'],
            'margin_trajectory': margins['trajectory'],
            'reinvestment_rate': reinvestment_rate,
            'roic': roic,
            'wacc': wacc,
            'roic_spread': roic_spread,
            'rd_intensity': rd_intensity,
            'capex_intensity': capex_intensity
        }
    
    def _classify_lifecycle(self, metrics: Dict) -> Dict:
        """Classify company into lifecycle stage"""
        revenue_cagr = metrics['revenue_cagr_3y']
        roic_spread = metrics['roic_spread']
        reinvestment_rate = metrics['reinvestment_rate']
        
        # Classification logic
        if revenue_cagr > 0.30 and reinvestment_rate > 0.20:
            label = 'Emerging'
            ltg = 0.15  # Long-term growth
        elif revenue_cagr > 0.15 and roic_spread > 0.05:
            label = 'Growth'
            ltg = 0.10
        elif revenue_cagr > 0.05 and roic_spread > 0:
            label = 'Mature'
            ltg = 0.04
        else:
            label = 'Transition'
            ltg = 0.02
        
        return {
            'label': label,
            'long_term_growth': ltg,
            'wacc_adjustment': 0.0,  # Can add risk premium adjustments
            'metrics_basis': metrics
        }
    
    def _generate_classification_memo(self, symbol: str, classification: Dict,
                                     metrics: Dict, company_data: Dict) -> Dict:
        """Generate 1-pager memo"""
        
        # Metrics table
        metrics_table = {
            'Revenue CAGR (3Y)': f"{metrics['revenue_cagr_3y']:.1%}",
            'Gross Margin': f"{metrics['gross_margin']:.1%}",
            'Operating Margin': f"{metrics['operating_margin']:.1%}",
            'Margin Trajectory': metrics['margin_trajectory'],
            'Reinvestment Rate': f"{metrics['reinvestment_rate']:.1%}",
            'ROIC': f"{metrics['roic']:.1%}",
            'WACC': f"{metrics['wacc']:.1%}",
            'ROIC Spread': f"{metrics['roic_spread']:.1%}",
            'R&D Intensity': f"{metrics['rd_intensity']:.1%}",
            'CapEx Intensity': f"{metrics['capex_intensity']:.1%}"
        }
        
        # Conclusion
        conclusion = self._generate_conclusion(symbol, classification, metrics)
        
        # Model implications
        model_implications = {
            'wacc': metrics['wacc'],
            'long_term_growth': classification['long_term_growth'],
            'terminal_multiple': self._suggest_terminal_multiple(classification),
            'reinvestment_assumption': metrics['reinvestment_rate'],
            'margin_assumption': 'expanding' if metrics['margin_trajectory'] == 'up' else 'stable'
        }
        
        return {
            'metrics_table': metrics_table,
            'conclusion': conclusion,
            'model_implications': model_implications,
            'classification': classification['label']
        }
```

**Deliverables Required:**
- ✅ Two lifecycle memos (one per company) - PDF/Markdown format
- ⚠️ Currently: Classification exists but not in memo format

**Gate Check:** Memo must be approved before proceeding to modeling

**Implementation Priority:** 🟢 LOW - Core functionality exists, needs formatting

---

## PHASE 4 — HISTORICAL NORMALIZATION
**Gate: ✅ Bridges tie out**

### Human-Grade Requirements

1. **Accounting Passes (human-style)**
   - GAAP ↔ Non-GAAP bridges
   - SBC (stock-based compensation)
   - Legal/tax one-offs
   - Acquisition amortization
   - Leases (ASC 842)
   - Capitalized R&D
   - Deferred revenue
   - FX adjustments
   - Working capital seasonality

2. **Normalization Ledger**
   - Before/after tables with footnote citations
   - Reconcile to reported totals

### Current Implementation Status: ❌ NOT IMPLEMENTED

**What Exists:**
- Nothing - this phase is completely missing

**Critical Gaps:**
1. ❌ No normalization service
2. ❌ No GAAP/Non-GAAP bridge logic
3. ❌ No one-time item identification
4. ❌ No accounting adjustment logic
5. ❌ No before/after reconciliation
6. ❌ No footnote citation system

**Required NEW Service:**

```python
# services/financial-normalizer/main.py (NEW SERVICE NEEDED)

class FinancialNormalizer:
    """Normalizes historical financials for modeling"""
    
    NORMALIZATION_CATEGORIES = [
        'stock_based_compensation',
        'legal_settlements',
        'tax_adjustments',
        'acquisition_amortization',
        'lease_adjustments_asc842',
        'capitalized_rd',
        'deferred_revenue',
        'fx_adjustments',
        'restructuring_charges',
        'discontinued_operations'
    ]
    
    def normalize_financials(self, symbol: str, raw_financials: Dict,
                            sec_filings: List[Dict]) -> Dict:
        """
        Normalize historical financials
        
        Returns: {
            'normalized_financials': {...},
            'normalization_ledger': {...},
            'bridges': {...},
            'footnote_citations': [...]
        }
        """
        
        ledger = []
        normalized = copy.deepcopy(raw_financials)
        
        # Process each normalization category
        for category in self.NORMALIZATION_CATEGORIES:
            adjustments = self._identify_adjustments(
                category, raw_financials, sec_filings
            )
            
            for adj in adjustments:
                # Apply adjustment
                normalized = self._apply_adjustment(normalized, adj)
                
                # Record in ledger
                ledger.append({
                    'category': category,
                    'period': adj['period'],
                    'line_item': adj['line_item'],
                    'reported_value': adj['reported_value'],
                    'adjustment': adj['adjustment_amount'],
                    'normalized_value': adj['normalized_value'],
                    'rationale': adj['rationale'],
                    'footnote_citation': adj['citation']
                })
        
        # Generate bridges
        bridges = self._generate_bridges(raw_financials, normalized, ledger)
        
        # Validate reconciliation
        validation = self._validate_reconciliation(raw_financials, normalized, ledger)
        
        return {
            'normalized_financials': normalized,
            'normalization_ledger': ledger,
            'bridges': bridges,
            'footnote_citations': [entry['footnote_citation'] for entry in ledger],
            'validation': validation,
            'normalized_at': datetime.now().isoformat()
        }
    
    def _identify_adjustments(self, category: str, financials: Dict,
                             sec_filings: List[Dict]) -> List[Dict]:
        """Identify normalization adjustments using RAG + rules"""
        
        adjustments = []
        
        if category == 'stock_based_compensation':
            # Extract SBC from cash flow statement and add back to operating income
            for period in financials.get('income_statements', []):
                sbc = period.get('stock_based_compensation', 0)
                if sbc > 0:
                    adjustments.append({
                        'period': period['date'],
                        'line_item': 'operating_income',
                        'reported_value': period['operating_income'],
                        'adjustment_amount': sbc,
                        'normalized_value': period['operating_income'] + sbc,
                        'rationale': 'Add back stock-based compensation to normalize operating income',
                        'citation': self._find_sbc_footnote(sec_filings, period['date'])
                    })
        
        elif category == 'legal_settlements':
            # Use RAG to find legal settlements in 8-K and 10-K
            settlements = self._rag_search_legal_settlements(sec_filings)
            for settlement in settlements:
                adjustments.append({
                    'period': settlement['period'],
                    'line_item': 'operating_expenses',
                    'reported_value': settlement['reported_opex'],
                    'adjustment_amount': -settlement['amount'],
                    'normalized_value': settlement['reported_opex'] - settlement['amount'],
                    'rationale': f"Remove one-time legal settlement: {settlement['description']}",
                    'citation': settlement['citation']
                })
        
        # Add logic for other categories...
        
        return adjustments
    
    def _generate_bridges(self, raw: Dict, normalized: Dict, ledger: List) -> Dict:
        """Generate reconciliation bridges"""
        
        bridges = {}
        
        # Income statement bridge
        bridges['income_statement'] = []
        for period in raw.get('income_statements', []):
            period_date = period['date']
            period_adjustments = [adj for adj in ledger if adj['period'] == period_date]
            
            bridge = {
                'period': period_date,
                'reported_revenue': period['revenue'],
                'revenue_adjustments': sum(adj['adjustment'] for adj in period_adjustments if adj['line_item'] == 'revenue'),
                'normalized_revenue': self._get_normalized_value(normalized, period_date, 'revenue'),
                'reported_operating_income': period['operating_income'],
                'sbc_addback': sum(adj['adjustment'] for adj in period_adjustments if adj['category'] == 'stock_based_compensation'),
                'other_adjustments': sum(adj['adjustment'] for adj in period_adjustments if adj['category'] != 'stock_based_compensation'),
                'normalized_operating_income': self._get_normalized_value(normalized, period_date, 'operating_income')
            }
            
            bridges['income_statement'].append(bridge)
        
        return bridges
    
    def _validate_reconciliation(self, raw: Dict, normalized: Dict, ledger: List) -> Dict:
        """Validate that adjustments reconcile correctly"""
        
        validation_results = {
            'passes': [],
            'failures': [],
            'warnings': []
        }
        
        # Check each period
        for period in raw.get('income_statements', []):
            period_date = period['date']
            
            # Get adjustments for this period
            period_adjustments = [adj for adj in ledger if adj['period'] == period_date]
            total_adjustments = sum(adj['adjustment'] for adj in period_adjustments)
            
            # Validate reconciliation
            reported = period['net_
