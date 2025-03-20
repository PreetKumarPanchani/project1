import psycopg2
from psycopg2.extras import RealDictCursor
from typing import List, Dict, Any, Optional
import logging
from dataclasses import dataclass
import os
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

@dataclass
class DatabaseConfig:
    host: str
    port: int
    database: str
    username: str
    password: str

class AWSPostgresExecutor:
    """Executes PostgreSQL queries for Shopify database"""
    
    def __init__(self, config: DatabaseConfig):
        self.config = config
        self.connection = None
        logger.info("Shopify PostgreSQL executor initialized")
    
    def connect(self) -> None:
        try:
            if not self.connection or self.connection.closed:
                self.connection = psycopg2.connect(
                    host=self.config.host,
                    port=self.config.port,
                    database=self.config.database,
                    user=self.config.username,
                    password=self.config.password,
                    sslmode='require'
                )
                logger.info("Database connection established")
        except Exception as e:
            logger.error(f"Connection error: {str(e)}")
            raise

    def execute_query(self, query: str, params: tuple = None) -> List[Dict[str, Any]]:
        try:
            self.connect()
            
            with self.connection.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute(query, params)
                
                if cursor.description:
                    results = cursor.fetchall()
                    return [dict(row) for row in results]
                
                self.connection.commit()
                return []
                
        except Exception as e:
            self.connection.rollback()
            logger.error(f"Query execution error: {str(e)}")
            raise

    def get_live_customer_count(self) -> int:
        """Get count of distinct customers"""
        query = """
        SELECT COUNT(DISTINCT customer_id) as customer_count 
        FROM customers
        """
        result = self.execute_query(query)
        return result[0]['customer_count'] if result else 0

    def get_orders_by_status(self) -> List[Dict[str, Any]]:
        """Get count of orders grouped by status"""
        query = """
        SELECT order_status, COUNT(*) as status_count
        FROM orders 
        WHERE order_status IS NOT NULL
        GROUP BY order_status
        """
        return self.execute_query(query)

    def get_order_status(self, order_id: int) -> Optional[str]:
        """Get status of specific order"""
        query = """
        SELECT order_status 
        FROM orders 
        WHERE order_id = %s
        """
        result = self.execute_query(query, (order_id,))
        return result[0]['order_status'] if result else None

    def get_order_value(self, order_id: int) -> List[Dict[str, Any]]:
        """Get total value of order by currency"""
        query = """
        SELECT currency, SUM(line_price) as total_value
        FROM order_lines 
        WHERE order_id = %s 
        GROUP BY currency
        """
        return self.execute_query(query, (order_id,))

    def get_most_popular_product(self) -> Dict[str, Any]:
        """Get the product with highest total quantity ordered"""
        query = """
        SELECT source_product_id, 
               SUM(quantity) AS total_quantity 
        FROM order_lines 
        WHERE source_product_id IS NOT NULL
        GROUP BY source_product_id 
        ORDER BY SUM(quantity) DESC 
        LIMIT 1
        """
        result = self.execute_query(query)
        return result[0] if result else None

    def close(self) -> None:
        if self.connection:
            self.connection.close()
            logger.info("Database connection closed")

def test_executor():
    print("\n=== Testing Updated Shopify PostgreSQL Executor ===\n")
    
    try:
        config = DatabaseConfig(
            host=os.getenv("PG_HOST_AWS"),
            port=int(os.getenv("PG_PORT_AWS", 5432)),
            database=os.getenv("PG_DATABASE_AWS"),
            username=os.getenv("PG_USER_AWS"),
            password=os.getenv("PG_PASSWORD_AWS"),
        )
        
        executor = AWSPostgresExecutor(config)
        
        # Test live customer count
        print("\nTesting live customer count:")
        customer_count = executor.get_live_customer_count()
        print(f"Total distinct customers: {customer_count}")
        
        # Test orders by status
        print("\nTesting orders by status:")
        status_counts = executor.get_orders_by_status()
        for status in status_counts:
            print(f"Status {status['order_status']}: {status['status_count']} orders")
        
        # Test specific order status
        order_id = 40  # Using a valid order_id from sample data
        print(f"\nTesting order status (OrderID: {order_id}):")
        status = executor.get_order_status(order_id)
        print(f"Order {order_id} status: {status}")
        
        # Test order value
        print(f"\nTesting order value (OrderID: {order_id}):")
        values = executor.get_order_value(order_id)
        for value in values:
            print(f"Total value: {value['total_value']} {value['currency']}")
        
        # Test most popular product
        print("\nTesting most popular product:")
        popular_product = executor.get_most_popular_product()
        if popular_product:
            print(f"Most ordered product ID: {popular_product['source_product_id']}")
            print(f"Total quantity ordered: {popular_product['total_quantity']}")

        else:
            print("No product data found")

    except Exception as e:
        print(f"Test failed: {str(e)}")
        
    finally:
        executor.close()

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    test_executor()