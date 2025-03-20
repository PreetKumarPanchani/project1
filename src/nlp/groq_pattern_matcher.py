from pydantic import BaseModel, Field, field_validator
from typing import Any
from src.query.query_mappings import QueryMappings
import logging

logger = logging.getLogger(__name__)

# Get all patterns from QueryMappings
query_mappings = QueryMappings()
all_patterns = tuple(query_mappings.get_all_patterns())  # Convert to tuple

class QueryPattern(BaseModel):
    """Model to validate and return exact pattern matches"""
    pattern: str = Field(
        description=" Must be one of the predefined patterns."
    )

    @field_validator('pattern')
    def validate_pattern(cls, v):
        if v not in all_patterns:
            raise ValueError(f"Pattern must be one of: {all_patterns}")
        return v
    
async def match_pattern_async(client: Any, prompt: str) -> str:
    """
    Match user query to predefined patterns using Groq.
    
    Args:
        client: Groq client instance
        prompt: Natural language query from user and instructions/prompt
        
    Returns:
        Exact matching pattern from predefined list
    """
    try:
        response = await client.chat.completions.create(
            model="mixtral-8x7b-32768",
            messages=[
                {
                    "role": "system",
                    "content": f"Match the user query to one of these exact patterns only: {all_patterns}"
                },
                {
                    "role": "user", 
                    "content": prompt
                }
            ],
            response_model=QueryPattern,
            temperature=0
        )
        return response.pattern
        
    except Exception as e:
        logger.error(f"Pattern matching error: {str(e)}")
        raise 


def match_pattern(client: Any, prompt: str) -> str:
    """
    Match user query to predefined patterns using Groq.
    
    Args:
        client: Groq client instance
        prompt: Natural language query from user and instructions/prompt
        
    Returns:
        Exact matching pattern from predefined list
    """
    
    try:
        response = client.chat.completions.create(
                model="mixtral-8x7b-32768",
                messages=[
                {
                    "role": "system",
                    "content": f"Match the user query to one of these exact patterns only: {all_patterns}"
                },
                {
                    "role": "user", 
                    "content": prompt
                }
            ],
            response_model=QueryPattern,
            temperature=0
        )
        return response.pattern
        
    except Exception as e:
        logger.error(f"Pattern matching error: {str(e)}")
        raise 
