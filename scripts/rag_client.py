#!/usr/bin/env python3
"""
RAG Engine Client
Production-ready client for Vertex AI RAG Engine operations
"""

import os
import json
import logging
import argparse
import sys
from datetime import datetime
from typing import Dict, Any, List, Optional
import requests
from google.auth import default
from google.auth.transport.requests import Request
import google.auth.transport.requests

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class RAGClient:
    """Client for Vertex AI RAG Engine operations"""

    def __init__(self, project_id: str, location: str, corpus_id: str):
        self.project_id = project_id
        self.location = location
        self.corpus_id = corpus_id
        self.base_url = f"https://{location}-aiplatform.googleapis.com/v1beta1"
        self._credentials = None

    def _get_credentials(self):
        """Get authenticated credentials"""
        if not self._credentials:
            self._credentials, _ = default()
            self._credentials.refresh(Request())
        return self._credentials

    def _get_auth_headers(self) -> Dict[str, str]:
        """Get authentication headers"""
        credentials = self._get_credentials()
        return {
            'Authorization': f'Bearer {credentials.token}',
            'Content-Type': 'application/json'
        }

    def create_corpus(self, display_name: str, description: str = "") -> str:
        """Create a new RAG corpus"""
        url = f"{self.base_url}/projects/{self.project_id}/locations/{self.location}/ragCorpora"

        payload = {
            "display_name": display_name,
            "description": description
        }

        response = requests.post(url, json=payload, headers=self._get_auth_headers())
        response.raise_for_status()

        corpus_data = response.json()
        corpus_id = corpus_data['name'].split('/')[-1]

        logger.info(f"Created RAG corpus: {corpus_id}")
        return corpus_id

    def import_documents(self, gcs_uris: List[str], chunk_size: int = 1000,
                        chunk_overlap: int = 200, max_embedding_qpm: int = 1000) -> str:
        """Import documents from GCS into the corpus"""
        url = f"{self.base_url}/projects/{self.project_id}/locations/{self.location}/ragCorpora/{self.corpus_id}/ragFiles:import"

        payload = {
            "import_rag_files_config": {
                "gcs_source": {
                    "uris": gcs_uris
                },
                "rag_file_transformation_config": {
                    "rag_file_chunking_config": {
                        "fixed_length_chunking": {
                            "chunk_size": chunk_size,
                            "chunk_overlap": chunk_overlap
                        }
                    }
                },
                "max_embedding_requests_per_min": max_embedding_qpm
            }
        }

        response = requests.post(url, json=payload, headers=self._get_auth_headers())
        response.raise_for_status()

        operation_data = response.json()
        operation_name = operation_data['name']

        logger.info(f"Started document import operation: {operation_name}")
        return operation_name

    def retrieve_contexts(self, query: str, top_k: int = 10,
                         vector_distance_threshold: float = None) -> Dict[str, Any]:
        """Retrieve relevant contexts for a query"""
        url = f"{self.base_url}/projects/{self.project_id}/locations/{self.location}:retrieveContexts"

        payload = {
            'vertex_rag_store': {
                'rag_resources': {
                    'rag_corpus': f'projects/{self.project_id}/locations/{self.location}/ragCorpora/{self.corpus_id}'
                }
            },
            'query': {
                'text': query,
                'similarity_top_k': top_k
            }
        }

        if vector_distance_threshold:
            payload['vertex_rag_store']['vector_distance_threshold'] = vector_distance_threshold

        response = requests.post(url, json=payload, headers=self._get_auth_headers())
        response.raise_for_status()

        return response.json()

    async def generate_with_rag(self, prompt: str, contexts: Dict[str, Any] = None,
                         model_name: str = "gemini-2.5-pro") -> str:
        """Generate response using Gemini with RAG context"""
        try:
            import vertexai
            from vertexai.generative_models import GenerativeModel

            # Initialize Vertex AI if not already done
            vertexai.init(project=self.project_id, location=self.location)

            model = GenerativeModel(model_name)

            # Prepare context from RAG retrieval
            context_text = ""
            if contexts and 'contexts' in contexts and 'contexts' in contexts['contexts']:
                context_parts = []
                for ctx in contexts['contexts']['contexts'][:5]:  # Limit to top 5 contexts
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
            return f"Error: {str(e)}"

    async def analyze_ma_documents(self, symbol: str, document_content: str,
                           analysis_type: str = "due_diligence") -> Dict[str, Any]:
        """Analyze M&A documents using RAG"""

        # Retrieve relevant contexts based on analysis type
        if analysis_type == "due_diligence":
            query = f"due diligence analysis for {symbol} company"
        elif analysis_type == "valuation":
            query = f"valuation considerations for {symbol}"
        elif analysis_type == "risk_assessment":
            query = f"risk factors for {symbol} industry"
        else:
            query = f"analysis of {symbol} company documents"

        contexts = self.retrieve_contexts(query, top_k=5)

        # Generate analysis prompt
        analysis_prompt = f"""
Analyze the following document content for {symbol} and provide insights relevant to {analysis_type}:

Document Content:
{document_content}

Please provide:
1. Key findings and insights
2. Potential risks or concerns identified
3. Recommendations based on the analysis
4. Any additional context that would be valuable for decision making

Focus on {analysis_type} aspects and be specific to the company's situation.
"""

        analysis = await self.generate_with_rag(analysis_prompt, contexts)

        return {
            'analysis_type': analysis_type,
            'symbol': symbol,
            'rag_contexts_used': len(contexts.get('contexts', [])),
            'analysis': analysis,
            'generated_at': str(datetime.now())
        }

    def list_corpora(self) -> List[Dict[str, Any]]:
        """List all RAG corpora in the project"""
        url = f"{self.base_url}/projects/{self.project_id}/locations/{self.location}/ragCorpora"

        response = requests.get(url, headers=self._get_auth_headers())
        response.raise_for_status()

        return response.json().get('ragCorpora', [])

    def get_corpus(self, corpus_id: str) -> Dict[str, Any]:
        """Get details of a specific corpus"""
        url = f"{self.base_url}/projects/{self.project_id}/locations/{self.location}/ragCorpora/{corpus_id}"

        response = requests.get(url, headers=self._get_auth_headers())
        response.raise_for_status()

        return response.json()

    def delete_corpus(self, corpus_id: str) -> None:
        """Delete a RAG corpus"""
        url = f"{self.base_url}/projects/{self.project_id}/locations/{self.location}/ragCorpora/{corpus_id}"

        response = requests.delete(url, headers=self._get_auth_headers())
        response.raise_for_status()

        logger.info(f"Deleted RAG corpus: {corpus_id}")


def main():
    """Main CLI interface"""
    parser = argparse.ArgumentParser(description='RAG Engine Client')
    parser.add_argument('--project', required=True, help='GCP Project ID')
    parser.add_argument('--location', default='us-central1', help='GCP Location')
    parser.add_argument('--corpus', help='RAG Corpus ID')

    subparsers = parser.add_subparsers(dest='command', help='Available commands')

    # Create corpus
    create_parser = subparsers.add_parser('create-corpus', help='Create a new RAG corpus')
    create_parser.add_argument('--name', required=True, help='Display name for the corpus')
    create_parser.add_argument('--description', default='', help='Description of the corpus')

    # Import documents
    import_parser = subparsers.add_parser('import-docs', help='Import documents from GCS')
    import_parser.add_argument('--gcs-uris', required=True, nargs='+', help='GCS URIs to import')
    import_parser.add_argument('--chunk-size', type=int, default=1000, help='Chunk size in tokens')
    import_parser.add_argument('--chunk-overlap', type=int, default=200, help='Chunk overlap in tokens')
    import_parser.add_argument('--max-qpm', type=int, default=1000, help='Max embedding requests per minute')

    # Query
    query_parser = subparsers.add_parser('query', help='Query the RAG corpus')
    query_parser.add_argument('--text', required=True, help='Query text')
    query_parser.add_argument('--top-k', type=int, default=10, help='Number of results to return')

    # Generate
    generate_parser = subparsers.add_parser('generate', help='Generate response with RAG')
    generate_parser.add_argument('--prompt', required=True, help='Prompt for generation')
    generate_parser.add_argument('--model', default='gemini-2.5-pro', help='Gemini model to use')

    # Analyze M&A
    analyze_parser = subparsers.add_parser('analyze-ma', help='Analyze M&A documents')
    analyze_parser.add_argument('--symbol', required=True, help='Company symbol')
    analyze_parser.add_argument('--content', required=True, help='Document content to analyze')
    analyze_parser.add_argument('--type', default='due_diligence',
                               choices=['due_diligence', 'valuation', 'risk_assessment'],
                               help='Type of analysis')

    # List corpora
    subparsers.add_parser('list-corpora', help='List all RAG corpora')

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    # Initialize client
    if args.command in ['create-corpus', 'list-corpora']:
        client = RAGClient(args.project, args.location, "")
    else:
        if not args.corpus:
            print("Error: --corpus is required for this command")
            sys.exit(1)
        client = RAGClient(args.project, args.location, args.corpus)

    try:
        if args.command == 'create-corpus':
            corpus_id = client.create_corpus(args.name, args.description)
            print(f"Created corpus: {corpus_id}")

        elif args.command == 'import-docs':
            operation = client.import_documents(
                args.gcs_uris, args.chunk_size, args.chunk_overlap, args.max_qpm
            )
            print(f"Import operation started: {operation}")

        elif args.command == 'query':
            results = client.retrieve_contexts(args.text, args.top_k)
            print(json.dumps(results, indent=2))

        elif args.command == 'generate':
            # First retrieve contexts
            contexts = client.retrieve_contexts(args.prompt, 5)
            response = client.generate_with_rag(args.prompt, contexts, args.model)
            print(response)

        elif args.command == 'analyze-ma':
            results = client.analyze_ma_documents(args.symbol, args.content, args.type)
            print(json.dumps(results, indent=2))

        elif args.command == 'list-corpora':
            corpora = client.list_corpora()
            for corpus in corpora:
                print(f"ID: {corpus['name'].split('/')[-1]}, Name: {corpus.get('displayName', 'N/A')}")

    except Exception as e:
        logger.error(f"Command failed: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
