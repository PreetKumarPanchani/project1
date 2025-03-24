# query_matcher.py

from typing import Optional, Dict, Any, Tuple
import difflib
from sentence_transformers import SentenceTransformer
import numpy as np
from groq import AsyncGroq
import asyncio
import logging
from src.query.query_mappings import QueryMappings
import re
from src.utils.logger import JSONLogger 
from src.nlp.groq_pattern_matcher import match_pattern


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class QueryMatcherAWS:
    def __init__(self, mappings: QueryMappings):
        """Initialize QueryMatcherAWS with mappings"""
        self.mappings = mappings
        self.model = None  # Lazy load the sentence transformer
        self.pattern_embeddings = None
        self.groq_client = None
        self.model_lock = asyncio.Lock()  # Lock for model initialization



    async def match_query(self, user_input: str, method: str = 'text', threshold: float = 0.8, groq_api_key: str = None):
        try:
            # First extract any parameters
            params = await self.mappings.extract_parameters_from_text(user_input, self.groq_client)
        

            # Normalize input but preserve parameter placeholders
            #user_input = self._normalize_text(user_input)
            

            template_input = user_input.lower()
            if params and 'order_id' in params:
                template_input = re.sub(
                    r'\b' + str(params['order_id']) + r'\b', 
                    "{order_id}", 
                    template_input
                )
            
            # Match template pattern
            query = None
            if method == 'text':
                query = await self._text_based_matching(template_input, threshold)
            elif method == 'transformer':
                query = await self._transformer_based_matching(template_input, threshold)
            elif method == 'groq':
                query = await self._groq_based_matching(template_input, groq_api_key)
                
            # Replace %s with actual parameter values
            if query and params:
                for param_name, param_value in params.items():
                    query = query.replace("%s", str(param_value), 1)  # Replace only first occurrence
            
            return query, params

        except Exception as e:
            logger.error(f"Error matching query: {str(e)}")
            return None, None
        
    def _normalize_text(self, text: str) -> str:
        """Normalize text for comparison but preserve parameter placeholders"""
        text = text.lower()
        text = ' '.join(text.split())
        # Don't remove curly braces for parameters
        text = re.sub(r'[^\w\s.{}]', '', text)
        return text

    async def _text_based_matching(self, user_input: str, threshold: float) -> Optional[str]:
        """Match using text similarity with difflib"""
        try:
            best_match = None
            highest_ratio = 0
            
            for pattern in self.mappings.get_all_patterns():
                normalized_pattern = self._normalize_text(pattern)
                ratio = difflib.SequenceMatcher(None, user_input, normalized_pattern).ratio()
                if ratio > highest_ratio:
                    highest_ratio = ratio
                    best_match = pattern
            
            logger.info(f"Text matcher input: '{user_input}' -> best match: '{best_match}' (ratio: {highest_ratio:.2f})")
            
            if highest_ratio >= threshold:
                return self.mappings.get_query(best_match)
            return None
            
        except Exception as e:
            logger.error(f"Text matching error: {str(e)}")
            return None

    async def _initialize_transformer(self):
        """Initialize the transformer model and compute pattern embeddings"""
        if self.model is None:
            async with self.model_lock:
                if self.model is None:
                    loop = asyncio.get_running_loop()
                    
                    def init_model():
                        model = SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')
                        patterns = self.mappings.get_all_patterns()
                        pattern_embeddings = model.encode(patterns)
                        return model, pattern_embeddings, patterns
                    
                    self.model, self.pattern_embeddings, self.patterns = await loop.run_in_executor(None, init_model)
                    logger.info("Transformer model initialized successfully")

    async def _transformer_based_matching(self, user_input: str, threshold: float) -> Optional[str]:
        """Match using sentence transformers"""
        try:
            await self._initialize_transformer()
            
            loop = asyncio.get_running_loop()
            
            def compute_similarity():
                input_embedding = self.model.encode([user_input])[0]
                similarities = np.dot(self.pattern_embeddings, input_embedding) / (
                    np.linalg.norm(self.pattern_embeddings, axis=1) * np.linalg.norm(input_embedding)
                )
                best_idx = np.argmax(similarities)
                return best_idx, similarities[best_idx]
            
            best_idx, highest_similarity = await loop.run_in_executor(None, compute_similarity)
            
            if highest_similarity >= threshold:
                best_pattern = self.patterns[best_idx]
                return self.mappings.get_query(best_pattern)
            return None
            
        except Exception as e:
            logger.error(f"Transformer matching error: {str(e)}")
            return None



async def test_query_matching():
    print("\n=== Testing Query Matching ===\n")
    
    import os
    from dotenv import load_dotenv
    load_dotenv()

    groq_api_key = os.getenv("GROQ_API_KEY")

    # Initialize components
    mappings = QueryMappings()
    matcher = QueryMatcherAWS(mappings)
    
    # Test queries
    test_queries = [
        'How many live customers do we have',
        'How many customers are there',
        "show customer count",
        "What is the status of Order 40",
        "Status of Order 40",
        "Order status 40",
        "Value of Order 40",
        "Total value of Order 40",
        "What is the total value of Order 40",
        "top product",
        "most ordered product",
        "product popularity",
        "show all users",
        "display users",
        "view users",
        "show users",
        "get active users",
        "view active users",
        "get recent orders",
        "view latest orders",
        "show latest orders"

    ]

    # Test different methods
    #methods = ['text', 'transformer', 'groq']
    methods = ['text', 'transformer']

    thresholds = {
        'text': 0.8,
        'transformer': 0.8,
        #'groq': 0.0
    }
    
    for method in methods:
        print(f"\nTesting {method.upper()} matching:")
        print("-" * 50)
        
        for test_input in test_queries:
            print(f"\nInput: {test_input}")
            
            # Await the result
            query, params = await matcher.match_query(
                test_input,
                method=method,
                threshold=thresholds[method],
                #groq_api_key=groq_api_key
            )
            
            if query:
                # Format query for display
                formatted_query = query.strip().replace('\n', ' ').replace('    ', ' ')
                print(f"Found matching query: {formatted_query[:200]}...")
                if params:
                    print(f"Parameters: {params}")
            else:
                print("No matching query found")
            
        print("-" * 50)


if __name__ == "__main__":
    # Run the async function
    asyncio.run(test_query_matching())
