import psycopg2
from psycopg2.extras import RealDictCursor
from typing import List, Dict, Any
import logging
from src.config.config_manager import ConfigManager

logger = logging.getLogger(__name__)

class PostgresExecutor:
    """Executes PostgreSQL queries and manages database connections"""
    
    def __init__(self, config_manager: ConfigManager):
        """Initialize with configuration"""
        self.config = config_manager.get_pg_config()
        self.connection = None
        logger.info("PostgreSQL executor initialized")

    def connect(self) -> None:
        """Establish database connection"""
        try:
            if not self.connection or self.connection.closed:
                self.connection = psycopg2.connect(
                    host=self.config.host,
                    port=self.config.port,
                    database=self.config.database,
                    user=self.config.username,
                    password=self.config.password
                )
                logger.info("Database connection established")
        except Exception as e:
            logger.error(f"Connection error: {str(e)}")
            raise

    def execute_query(self, query: str, params: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        """
        Execute a SQL query and return results as list of dictionaries
        
        Args:
            query: SQL query to execute
            params: Query parameters (optional)
            
        Returns:
            List of dictionaries containing query results
        """
        try:
            self.connect()
            
            with self.connection.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute(query, params)
                
                if cursor.description:  # If query returns data
                    results = cursor.fetchall()
                    return [dict(row) for row in results]
                    
                self.connection.commit()
                return []
                
        except Exception as e:
            self.connection.rollback()
            logger.error(f"Query execution error: {str(e)}")
            raise
            
    def close(self) -> None:
        """Close database connection"""
        if self.connection:
            self.connection.close()
            logger.info("Database connection closed")

def test_executor():
    """Test the PostgreSQL executor"""
    print("\n=== Testing PostgreSQL Executor ===\n")
    
    try:
        # Initialize components
        config_manager = ConfigManager()
        executor = PostgresExecutor(config_manager)
        
        # Test queries from QueryMappings
        test_queries = [
            "SELECT * FROM users ORDER BY created_at DESC LIMIT 5;",
            """
            SELECT u.name, COUNT(o.id) as order_count 
            FROM users u 
            LEFT JOIN orders o ON u.id = o.user_id 
            WHERE u.status = 'active'
            GROUP BY u.id, u.name
            HAVING COUNT(o.id) > 0
            ORDER BY order_count DESC
            LIMIT 5;
            """
        ]
        
        for query in test_queries:
            print(f"\nExecuting query:\n{query}")
            results = executor.execute_query(query)
            print(f"\nResults:")
            for row in results:
                print(row)
                
    except Exception as e:
        print(f"Test failed: {str(e)}")
        
    finally:
        executor.close()
        
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    test_executor()