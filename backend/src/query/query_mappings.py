import re
from typing import Optional
from pydantic import BaseModel
from groq import AsyncGroq
import os
import asyncio
import json
import logging
logger = logging.getLogger(__name__)

# First define a model for the response

class OrderNumber(BaseModel):
    """Model for number extraction"""
    order_id: Optional[int] = None

class QueryMappings:
    """Efficient text to query mapping with pattern grouping for Shopify database"""
    
    def __init__(self):

        # Add a structure to store parameters for queries
        self.query_params = {
            # Strip and normalize the SQL queries to match exactly
            """SELECT order_status 
            FROM orders 
            WHERE order_id = %s;""".strip(): ["order_id"],
            
            """SELECT currency, SUM(line_price) as total_value
            FROM order_lines 
            WHERE order_id = %s 
            GROUP BY currency;""".strip(): ["order_id"]
        }


        # Structure: Each key is the SQL query, value is list of matching patterns
        self.mappings = {
            # Customers listing query
            """
            SELECT 
                customer_id,
                source_customer_id,
                customer_source,
                name,
                email,
                phone,
                address_1,
                address_2,
                address_3,
                country,
                postcode
            FROM customers 
            ORDER BY customer_id;
            """: [
                "show all customers",
                "list all customers",
                "display customers",
                "get customers",
                "view customers",
                "show customers",
                "show users",
                "display users"
            ],
            
            # Live customer count query
            """
            SELECT COUNT(DISTINCT customer_id) as customer_count 
            FROM customers;
            """: [
                'How many live customers do we have',
                'How many customers are there',
                "show customer count",
                "how many customers",
                "count customers",
                "number of customers",
                "total number of customers"
            ],

            # Orders by status query
            """
            SELECT order_status, COUNT(*) as status_count
            FROM orders 
            WHERE order_status IS NOT NULL
            GROUP BY order_status;
            """: [
                'How many Sales orders do we have by status',
                "show orders by status",
                "count orders by status",
                "order status breakdown",
                "orders per status",
                "status distribution"
            ],

            # Order details query
            """
                SELECT order_status 
                FROM orders 
                WHERE order_id = %s;
            """: [
                "What is the status of Order {order_id}",
                "Status of Order {order_id}",
                "Order status {order_id}",
                "Order {order_id} status",
                "check status of order {order_id}",
            ],

            # Order value query
            """
            SELECT currency, SUM(line_price) as total_value
            FROM order_lines 
            WHERE order_id = %s 
            GROUP BY currency;
            """: [
                "What is the value of Order {order_id}",
                "Value of Order {order_id}",
                "Total value of Order {order_id}",
                "What is the total value of Order {order_id}",
                "Order {order_id} value",
                "check value of order {order_id}",
            ],



            # Most popular product query
            """
            SELECT source_product_id, 
                SUM(quantity) AS total_quantity 
            FROM order_lines 
            WHERE source_product_id IS NOT NULL
            GROUP BY source_product_id 
            ORDER BY SUM(quantity) DESC 
            LIMIT 1;
            """: [
                "show popular product",
                "list best selling product",
                "top product",
                "most ordered product",
                "product popularity",
                "best seller",
                "What is the most popular product that has been ordered",
            ],

            # Recent orders query
            """
            SELECT 
                o.order_id,
                o.customer_id,
                o.order_date,
                o.order_status,
                c.name as customer_name,
                COUNT(ol.order_line_id) as total_items,
                SUM(ol.line_price) as total_amount,
                ol.currency
            FROM orders o
            LEFT JOIN customers c ON o.customer_id = c.customer_id
            JOIN order_lines ol ON o.order_id = ol.order_id
            GROUP BY 
                o.order_id, 
                o.customer_id, 
                o.order_date,
                o.order_status,
                c.name,
                ol.currency
            ORDER BY o.order_date DESC
            LIMIT 10;
            """: [
                "show recent orders",
                "list latest orders",
                "display recent orders",
                "get recent orders",
                "view latest orders",
                "show new orders"
            ]
        }
        
        # Create reverse mapping for quick lookup
        self.pattern_to_query = {}
        for query, patterns in self.mappings.items():
            for pattern in patterns:
                self.pattern_to_query[pattern] = query





    async def extract_order_number_with_groq(self, text: str, groq_client: AsyncGroq) -> Optional[int]:
        """Extract order number from text using Groq with JSON response format"""
        try:
            chat_completion = await groq_client.chat.completions.create(
                messages=[
                    {
                        "role": "system",
                        "content": "You are a number extractor that outputs in JSON.\n"
                        f"The JSON object must use the schema: {json.dumps(OrderNumber.model_json_schema(), indent=2)}"
                    },
                    {
                        "role": "user",
                        "content": f"Extract the order number from this text: {text}"
                    }
                ],
                model="llama-3.1-8b-instant",
                temperature=0,
                stream=False,
                response_format={"type": "json_object"}
            )

            # Parse response using Pydantic model
            result = OrderNumber.model_validate_json(chat_completion.choices[0].message.content)
            return result.order_id

        except Exception as e:
            logger.error(f"Groq number extraction error: {str(e)}")
            return None
        
        

    async def extract_parameters_from_text(self, text: str, groq_client: AsyncGroq = None) -> dict:
        """Extract parameters from text input using both regex and Groq"""
        params = {}
        
        # First try regex-based extraction
        text = text.lower()
        order_patterns = [
            r'order\s*(?:id)?\s*[#]?\s*(\d+)',
            r'order\s*status\s*(\d+)',
            r'status\s*(?:of)?\s*order\s*(\d+)',
            r'value\s*(?:of)?\s*order\s*(\d+)',
            r'order\s*(\d+)\s*(?:status|value)',
            r'#\s*(\d+)',
            r'(\d+)\s*status',
            r'order\s*(\d+)',
        ]
        
        # Try regex first
        for pattern in order_patterns:
            match = re.search(pattern, text)
            if match:
                params['order_id'] = int(match.group(1))
                return params
        
        # If regex fails and Groq client is available, try Groq
        if not params and groq_client:
            order_id = await self.extract_order_number_with_groq(text, groq_client)
            if order_id:
                params['order_id'] = order_id
        
        return params



    def get_all_patterns(self):
        """Get all available text patterns"""
        return list(self.pattern_to_query.keys())
    

    def get_query(self, pattern: str) -> str:
        """Get query for a specific pattern"""
        return self.pattern_to_query.get(pattern)

    def get_patterns_for_query(self, query: str) -> list:
        """Get all patterns that map to a specific query"""
        return self.mappings.get(query, [])




async def test_parameter_extraction():
    from dotenv import load_dotenv
    load_dotenv()
    
    groq_api_key = os.getenv("GROQ_API_KEY")
    groq_client = AsyncGroq(api_key=groq_api_key)
    mappings = QueryMappings()
    
    test_cases = [
        "What is the value of Order 40",
        "Can you tell me about order number 123",
        "I need info for #456",
        "Looking up order ID: 789",
        "Status for the forty-second order",
        "Get order details for no. 42",
        "Show me everything about order 555",
        "This is order 333's status",
        "Show all customers",
        "What is the value of Order 40",
        "Check status of order 41",
        "Show me Order 42 status",
        "Value of Order 40",
        "Order status 123",
        "status of order 456",
        "Order #789 status",
    ]
    
    print("\nTesting Groq parameter extraction:")
    for test_input in test_cases:
        print(f"\nInput: '{test_input}'")
        params = await mappings.extract_parameters_from_text(test_input, groq_client)
        if params:
            print(f"Extracted parameters: {params}")
        else:
            print("No parameters found")

if __name__ == "__main__":
    asyncio.run(test_parameter_extraction())
