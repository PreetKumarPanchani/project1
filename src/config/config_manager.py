import os
from typing import Dict, Any, Optional
from dataclasses import dataclass
import logging
from pathlib import Path
from dotenv import load_dotenv
from src.utils.logger import JSONLogger 
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class PostgresConfig:
    """PostgreSQL configuration"""
    host: str
    port: int
    database: str
    username: str
    password: str
    schema: Optional[str] = 'public'
    sslmode: Optional[str] = 'require'

@dataclass 
class GroqConfig:
    """Groq API configuration"""
    api_key: str
    model: str = 'mixtral-8x7b-32768'
    temperature: float = 0.0

class ConfigManager:
    def __init__(self, env_path: Optional[str] = None):
        """
        Initialize configuration manager.
        
        Args:
            env_path: Path to .env file (optional)
        """
        # Load environment variables
        if env_path:
            load_dotenv(env_path)
        else:
            load_dotenv()
            
        # Initialize configurations

        self.pg_config = self._load_pg_config()
        self.aws_pg_config = self._load_aws_pg_config()

        self.groq_config = self._load_groq_config()
        logger.info("Configuration manager initialized")

    def _load_pg_config(self) -> PostgresConfig:
        """Load PostgreSQL configuration"""
        return PostgresConfig(
            host=os.getenv('PG_HOST', 'localhost'),
            port=int(os.getenv('PG_PORT', '5432')),
            database=os.getenv('PG_DATABASE', 'nl2query_test_db'),
            username=os.getenv('PG_USER', 'postgres'),
            password=os.getenv('PG_PASSWORD', ''),
            schema=os.getenv('PG_SCHEMA', 'public')

            
        )


    def _load_aws_pg_config(self) -> PostgresConfig:
        """Load PostgreSQL configuration"""
        return PostgresConfig(
           
            host=os.getenv('PG_HOST_AWS', ''),
            port=int(os.getenv('PG_PORT_AWS', '5432')),
            database=os.getenv('PG_DATABASE_AWS', ''),
            username=os.getenv('PG_USER_AWS', ''),
            password=os.getenv('PG_PASSWORD_AWS', ''),
            sslmode=os.getenv('PG_SSLMODE_AWS', 'require')
            
        )
    
    
    def _load_groq_config(self) -> GroqConfig:
        """Load Groq configuration"""
        return GroqConfig(
            api_key=os.getenv('GROQ_API_KEY', ''),
            model=os.getenv('GROQ_MODEL', 'mixtral-8x7b-32768'),
            temperature=float(os.getenv('GROQ_TEMP', '0.0'))
        )

    def get_pg_config(self) -> PostgresConfig:
        """Get PostgreSQL configuration"""
        return self.pg_config

    def get_groq_config(self) -> GroqConfig:
        """Get Groq configuration"""
        return self.groq_config

# Simple test to verify configuration manager
if __name__ == "__main__":
    print("\n=== Testing Configuration Manager ===\n")
    
    path = "test_config"
    env_file = Path(path) / ".env.test"
    test_dir = Path(path)

    
    try:
        # Test configuration loading
        print("1. Testing configuration loading...")

        try:
            print("Trying to load config from .env file")
            # Try to load config from .env file
            config_manager = ConfigManager()
        except:
            print("No .env file found, creating a test environment file")
            # If .env file is not found, create a test environment file

            # Create test environment file just for testing the config manager
            test_env_content = """
            PG_HOST=localhost
            PG_PORT=5432
            PG_DATABASE=test_db
            PG_USER=test_user
            PG_PASSWORD=test_pass
            PG_SCHEMA=public
            
            GROQ_API_KEY=test_key_123
            GROQ_MODEL=mixtral-8x7b-32768
            GROQ_TEMP=0.0
            """
            
            # Create test config directory and file
            test_dir.mkdir(exist_ok=True)
            
            env_file.write_text(test_env_content.strip())

            config_manager = ConfigManager(str(env_file))
        
        
        # Test PostgreSQL config
        print("\n2. PostgreSQL Configuration:")
        pg_config = config_manager.get_pg_config()
        print(f"Host: {pg_config.host}")
        print(f"Port: {pg_config.port}")
        print(f"Database: {pg_config.database}")
        print(f"Username: {pg_config.username}")
        print(f"Schema: {pg_config.schema}")
        
        # Test Groq config
        print("\n3. Groq Configuration:")
        groq_config = config_manager.get_groq_config()
        print(f"Model: {groq_config.model}")
        print(f"Temperature: {groq_config.temperature}")
        
        print("\nConfiguration test completed successfully!")
    
    
    except Exception as e:
        print(f"Test failed: {str(e)}")
        
    finally:
        # Clean up test files 

        # Check if the environment file exists
        if env_file.exists():
            env_file.unlink()   

        # Check if the test directory exists
        if test_dir.exists():
            test_dir.rmdir()