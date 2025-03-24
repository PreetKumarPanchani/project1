# query_matcher.py

from typing import Optional, Dict, Any, Tuple
import difflib
from sentence_transformers import SentenceTransformer
import numpy as np
from groq import Groq
import logging
from src.query.query_mappings import QueryMappings
import re
from src.utils.logger import JSONLogger 
from src.nlp.groq_pattern_matcher import match_pattern


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class QueryMatcher:
    def __init__(self, mappings: QueryMappings):
        """Initialize QueryMatcher with mappings"""
        self.mappings = mappings
        self.model = None  # Lazy load the sentence transformer
        self.pattern_embeddings = None
        self.groq_client = None
        
    def match_query(self, user_input: str, method: str = 'text', threshold: float = 0.8, groq_api_key: str = None) -> Optional[str]:
        """
        Match user input to a query using specified method.
        
        Args:
            user_input: User's natural language input
            method: Matching method ('text', 'transformer', or 'groq')
            threshold: Similarity threshold for matching
            
        Returns:
            Matching SQL query or None if no match found
        """
        try:
            # Normalize input
            user_input = self._normalize_text(user_input)
            
            if method == 'text':
                return self._text_based_matching(user_input, threshold)
            elif method == 'transformer':
                return self._transformer_based_matching(user_input, threshold)
            elif method == 'groq':

                return self._groq_based_matching(user_input, groq_api_key)
            else:
                raise ValueError(f"Unknown matching method: {method}")
                
        except Exception as e:
            logger.error(f"Error matching query: {str(e)}")
            return None

    def _normalize_text(self, text: str) -> str:
        """Normalize text for comparison"""
        # Convert to lowercase
        text = text.lower()
        
        # Remove extra whitespace
        text = ' '.join(text.split())
        
        # Remove punctuation except in numbers
        text = re.sub(r'[^\w\s.]', '', text)
        
        return text

    def _text_based_matching(self, user_input: str, threshold: float) -> Optional[str]:
        """Match using text similarity with difflib"""
        try:
            best_match = None
            highest_ratio = 0
            
            # Compare with each pattern
            for pattern in self.mappings.get_all_patterns():
                ratio = difflib.SequenceMatcher(None, user_input, pattern).ratio()
                if ratio > highest_ratio:
                    highest_ratio = ratio
                    best_match = pattern
            
            # Return query if similarity exceeds threshold
            if highest_ratio >= threshold:
                return self.mappings.get_query(best_match)
            return None
            
        except Exception as e:
            logger.error(f"Text matching error: {str(e)}")
            return None

    def _transformer_based_matching(self, user_input: str, threshold: float) -> Optional[str]:
        """Match using sentence transformers"""
        try:
            # Lazy load model and compute pattern embeddings
            if self.model is None:
                self.model = SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')
                
                # Compute embeddings for all patterns
                patterns = self.mappings.get_all_patterns()
                self.pattern_embeddings = self.model.encode(patterns)
                self.patterns = patterns
            
            # Compute embedding for user input
            input_embedding = self.model.encode([user_input])[0]
            
            # Compute similarities
            similarities = np.dot(self.pattern_embeddings, input_embedding) / (
                np.linalg.norm(self.pattern_embeddings, axis=1) * np.linalg.norm(input_embedding)
            )
            
            # Find best match
            best_idx = np.argmax(similarities)
            highest_similarity = similarities[best_idx]
            
            # Return query if similarity exceeds threshold
            if highest_similarity >= threshold:
                best_pattern = self.patterns[best_idx]
                return self.mappings.get_query(best_pattern)
            return None
            
        except Exception as e:
            logger.error(f"Transformer matching error: {str(e)}")
            return None

    def _groq_based_matching(self, user_input: str, groq_api_key: str) -> Optional[str]:
        """Match using Groq LLM API"""
        try:
            import instructor
            # Lazy load Groq client
            if self.groq_client is None:
                self.groq_client = Groq(api_key=groq_api_key)
                self.groq_client = instructor.from_groq(self.groq_client)

            
            
            # Create prompt with all patterns
            patterns = self.mappings.get_all_patterns()
            prompt = f"""Given the following list of valid query patterns:
            {', '.join(patterns)}
            
            Find the most similar pattern to this user input: "{user_input}"
            Return only the exact matching pattern from the list or "none" if no good match is found.
            """
            
            # Get response from Groq
            response = self.groq_client.chat.completions.create(
                messages=[{
                    "role": "user",
                    "content": prompt
                }],
                model="llama-3.1-8b-instant",
                temperature=0
            )
            
            matched_pattern = response.choices[0].message.content.strip().lower()
            
            # Return query if valid pattern found
            if matched_pattern in patterns:
                return self.mappings.get_query(matched_pattern)
            return None
            
        except Exception as e:
            logger.error(f"Groq matching error: {str(e)}")
            return None




    def _groq_based_matching(self, user_input: str, groq_api_key: str) -> Optional[str]:
        """Asynchronously match using Groq LLM API"""
        try:
            import instructor
            if self.groq_client is None:
                self.groq_client = Groq(api_key=groq_api_key)
                
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

            matched_pattern = match_pattern(self.groq_client, prompt)
            logger.info(f"Groq matcher input: '{user_input}' -> matched: '{matched_pattern}'")
            
            if matched_pattern in self.mappings.get_all_patterns():
                return self.mappings.get_query(matched_pattern)
            
            return None
        
        except Exception as e:
            logger.error(f"Groq matching error: {str(e)}")
            return None

    def _groq_based_matching(self, user_input: str, groq_api_key: str) -> Optional[str]:
        """Match using Groq LLM API with improved prompt and error handling"""
        try:
            # Lazy load Groq client
            if self.groq_client is None:
                self.groq_client = Groq(api_key=groq_api_key)
            
            # Get patterns and create a more structured prompt
            patterns = self.mappings.get_all_patterns()
            
            # Improved prompt with clear instructions and examples
            prompt = f"""Task: Match the user's input query to the most similar predefined pattern.

            Available patterns:
            {chr(10).join(f"- {pattern}" for pattern in patterns)}

            User input: "{user_input}"

            Instructions:
            1. Compare the user input to each available pattern
            2. Return the EXACT matching pattern if there's a good semantic match
            3. Return "none" if no pattern matches well enough

            Important: Only return one of the exact patterns listed above or "none". No explanations needed.

            Your response:"""
            
            # Get response from Groq
            response = self.groq_client.chat.completions.create(
                messages=[{
                    "role": "system",
                    "content": "You are a pattern matching assistant. Only return exact matches from the provided pattern list or 'none'. No explanations."
                },
                {
                    "role": "user",
                    "content": prompt
                }],
                model="llama-3.1-8b-instant",
                temperature=0.1  # Slightly higher than 0 to allow for some flexibility
            )
            
            # Extract and clean the response
            matched_pattern = response.choices[0].message.content.strip().lower()
            
            # Log the match attempt
            logger.info(f"Groq matcher input: '{user_input}' -> matched: '{matched_pattern}'")
            
            # Handle the response
            if matched_pattern in patterns:
                return self.mappings.get_query(matched_pattern)
            elif matched_pattern != "none":
                # If we got something back but it's not in our patterns, log it
                logger.warning(f"Groq returned invalid pattern: '{matched_pattern}'")
            
            return None
                
        except Exception as e:
            logger.error(f"Groq matching error: {str(e)}")
            return None


# Test function
def test_query_matching():
    print("\n=== Testing Query Matching ===\n")
    
    import os
    from dotenv import load_dotenv
    load_dotenv()

    groq_api_key = os.getenv("GROQ_API_KEY")

    # Initialize components
    mappings = QueryMappings()
    matcher = QueryMatcher(mappings)
    
    # Test queries
    test_queries = [
        "show me all the users please",
        "i want to see active users",
        "display product list",
        "get the most recent orders",
        "what are the latest orders",
        "show me users that are active"
    ]

    
    # Test different methods
    #methods = ['text', 'transformer', 'groq']
    methods = ['text', 'transformer']
    thresholds = {
        'text': 0.8,
        'transformer': 0.7,
        #'groq': 0.0  # Not used for groq
    }
    
    for method in methods:
        print(f"\nTesting {method.upper()} matching:")
        print("-" * 50)
        
        for test_input in test_queries:
            print(f"\nInput: {test_input}")
            
            result = matcher.match_query(
                test_input,
                method=method,
                threshold=thresholds[method],
                #groq_api_key=groq_api_key,
            )
            
            if result:
                # Format query for display
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
        result = matcher.match_query(test_input, method='text', threshold=0.8)
        if result:
            print(f"Found matching query: {result[:200]}...")
        else:
            print("No matching query found")
    print("-" * 50)





    print("\n=== Testing Transformer-Based Matching ===\n")
    print("-" * 50)
    for test_input in text_test_queries:
        print(f"\nInput: {test_input}")
        result = matcher.match_query(test_input, method='transformer', threshold=0.8)
        if result:
            print(f"Found matching query: {result[:200]}...")
        else:
            print("No matching query found")
    print("-" * 50)

if __name__ == "__main__":
    test_query_matching()