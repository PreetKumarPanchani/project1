from typing import Optional, Dict, Any, Tuple, List
import difflib
from sentence_transformers import SentenceTransformer
import numpy as np
from groq import AsyncGroq
import logging
import asyncio
from src.query.query_mappings import QueryMappings
import re
from src.utils.logger import JSONLogger
from src.nlp.groq_pattern_matcher import match_pattern as groq_match_pattern

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class AsyncQueryMatcher:
    def __init__(self, mappings: QueryMappings):
        """Initialize AsyncQueryMatcher with mappings"""
        self.mappings = mappings
        self.model = None
        self.pattern_embeddings = None
        self.patterns = None
        self.groq_client = None
        self.model_lock = asyncio.Lock()  # Lock for model initialization
        self.patterns = self.mappings.get_all_patterns()
        
    async def match_query(self, user_input: str, method: str = 'text', threshold: float = 0.8, groq_api_key: str = None) -> Optional[str]:
        """Asynchronously match user input to a query using specified method."""
        try:
            user_input = self._normalize_text(user_input)
            
            if method == 'text':
                return await self._text_based_matching(user_input, threshold)
            elif method == 'transformer':
                return await self._transformer_based_matching(user_input, threshold)
            elif method == 'groq':
                return await self._groq_based_matching(user_input, groq_api_key)
            else:
                raise ValueError(f"Unknown matching method: {method}")
                
        except Exception as e:
            logger.error(f"Error matching query: {str(e)}")
            return None

    def _normalize_text(self, text: str) -> str:
        """Normalize text for comparison"""
        text = text.lower()
        text = ' '.join(text.split())
        text = re.sub(r'[^\w\s.]', '', text)
        return text

    async def _text_based_matching(self, user_input: str, threshold: float) -> Optional[str]:
        """Asynchronously match using text similarity with difflib"""
        try:
            loop = asyncio.get_running_loop()
            
            def compare_patterns():
                best_match = None
                highest_ratio = 0
                patterns = self.patterns
                
                for pattern in patterns:
                    normalized_pattern = self._normalize_text(pattern)
                    ratio = difflib.SequenceMatcher(None, user_input, normalized_pattern).ratio()
                    if ratio > highest_ratio:
                        highest_ratio = ratio
                        best_match = pattern
                
                return best_match, highest_ratio

            # Run in thread pool
            best_match, highest_ratio = await loop.run_in_executor(None, compare_patterns)
            
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
            async with self.model_lock:  # Use lock to prevent multiple initializations
                if self.model is None:  # Double check after acquiring lock
                    loop = asyncio.get_running_loop()
                    
                    def init_model():
                        model = SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')
                        patterns = self.mappings.get_all_patterns()
                        pattern_embeddings = model.encode(patterns)
                        return model, pattern_embeddings, patterns
                    
                    self.model, self.pattern_embeddings, self.patterns = await loop.run_in_executor(None, init_model)
                    logger.info("Transformer model initialized successfully")

    async def _transformer_based_matching(self, user_input: str, threshold: float) -> Optional[str]:
        """Asynchronously match using sentence transformers"""
        try:
            # Initialize model if needed
            await self._initialize_transformer()
            
            loop = asyncio.get_running_loop()
            
            def compute_similarity():
                # Encode user input
                input_embedding = self.model.encode([user_input])[0]
                
                # Compute similarities
                similarities = np.dot(self.pattern_embeddings, input_embedding) / (
                    np.linalg.norm(self.pattern_embeddings, axis=1) * np.linalg.norm(input_embedding)
                )
                
                best_idx = np.argmax(similarities)
                return best_idx, similarities[best_idx]
            
            best_idx, highest_similarity = await loop.run_in_executor(None, compute_similarity)
            
            logger.info(f"Transformer matcher input: '{user_input}' -> best match: '{self.patterns[best_idx]}' (similarity: {highest_similarity:.2f})")
            
            if highest_similarity >= threshold:
                return self.mappings.get_query(self.patterns[best_idx])
            return None
            
        except Exception as e:
            logger.error(f"Transformer matching error: {str(e)}")
            return None

    async def _groq_based_matching(self, user_input: str, groq_api_key: str) -> Optional[str]:
        """Asynchronously match using Groq LLM API"""
        try:
            import instructor
            if self.groq_client is None:
                self.groq_client = AsyncGroq(api_key=groq_api_key)
                
                # Enable instructor patches for Groq client
                self.groq_client = instructor.from_groq(self.groq_client)
            
            prompt = f"""Task: Match the user's input query to the most similar predefined pattern.

            Available patterns:
            {chr(10).join(f"- {pattern}" for pattern in self.patterns)}

            User input: "{user_input}"

            Instructions:
            1. Compare the user input to each available pattern
            2. Return the EXACT matching pattern if there's a good semantic match
            3. Return "none" if no pattern matches well enough

            Important: Only return one of the exact patterns listed above or "none". No explanations needed.

            Your response:"""

            matched_pattern = await groq_match_pattern(self.groq_client, prompt)
            logger.info(f"Groq matcher input: '{user_input}' -> matched: '{matched_pattern}'")
            
            if matched_pattern in self.mappings.get_all_patterns():
                return self.mappings.get_query(matched_pattern)
            
            return None
            
        except Exception as e:
            logger.error(f"Groq matching error: {str(e)}")
            return None

async def run_batch_queries(matcher: AsyncQueryMatcher, queries: List[str], method: str, threshold: float, groq_api_key: str = None) -> List[Tuple[str, Optional[str]]]:
    """Run a batch of queries concurrently"""
    tasks = []
    for query in queries:
        task = matcher.match_query(query, method=method, threshold=threshold, groq_api_key=groq_api_key)
        tasks.append((query, task))
    
    results = []
    for query, task in tasks:
        try:
            result = await task
            results.append((query, result))
        except Exception as e:
            logger.error(f"Error processing query '{query}': {str(e)}")
            results.append((query, None))
    
    return results

async def test_query_matching():
    print("\n=== Testing Async Query Matching ===\n")
    
    import os
    from dotenv import load_dotenv
    load_dotenv()

    groq_api_key = os.getenv("GROQ_API_KEY")
    mappings = QueryMappings()
    matcher = AsyncQueryMatcher(mappings)
    
    # Test queries
    test_queries = [
        "show me all the users please",
        "i want to see active users",
        "display product list",
        "get the most recent orders",
        "what are the latest orders",
        "show me users that are active"
    ]

    # Test each method
    methods = ['text', 'transformer', 'groq']
    thresholds = {
        'text': 0.8,
        'transformer': 0.7,
        'groq': 0.0
    }
    
    for method in methods:
        print(f"\nTesting {method.upper()} matching:")
        print("-" * 50)
        
        results = await run_batch_queries(
            matcher,
            test_queries,
            method=method,
            threshold=thresholds[method],
            groq_api_key=groq_api_key
        )
        
        for query, result in results:
            print(f"\nInput: {query}")
            if result:
                formatted_query = result.strip().replace('\n', ' ').replace('    ', ' ')
                print(f"Found matching query: {formatted_query[:200]}...")
            else:
                print("No matching query found")
        
        print("-" * 50)




    text_test_queries = [ 
        "show all users",
        "list all users",
        "display users",
        "get users",
        "view users",
        "show users",
        "show active users",
        "list active users",
        "display active users",
        "get active users",
        "view active users",
        "find active users",
        "show all products",
        "list products",
        "display products",
        "get products",
        "view products",
        "show products",
        "show recent orders",
        "list latest orders",
        "display recent orders",
        "get recent orders",
        "view latest orders",
        "show latest orders"
    ]


    print("\n=== Testing Text-Based Matching ===\n")
    print("-" * 50)
    for test_input in text_test_queries:
        print(f"\nInput: {test_input}")
        result = await matcher.match_query(test_input, method='text', threshold=0.8, groq_api_key=groq_api_key)
        if result:
            print(f"Found matching query: {result[:200]}...")
        else:
            print("No matching query found")
    print("-" * 50)

if __name__ == "__main__":
    asyncio.run(test_query_matching())