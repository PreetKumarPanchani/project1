import psycopg2
from psycopg2.extras import RealDictCursor
import logging
from typing import Optional

logger = logging.getLogger(__name__)




class DatabaseManager:
    def __init__(
        self,
        host: str = "localhost",
        port: int = 5432,
        database: str = "nlquery_db",  # Default database name
        user: str = "postgres",        # Default PgAdmin username
        password: str = "password" 
    ):
        self.config = {
            "host": host,
            "port": port,
            "database": database,
            "user": user,
            "password": password
        }

    def create_database(self) -> None:
        """Create the database if it doesn't exist"""
        # Connect to default postgres database first
        conn = psycopg2.connect(
            **{**self.config, "database": "postgres"}
        )
        conn.autocommit = True
        cursor = conn.cursor()

        try:
            # Check if database exists
            cursor.execute(f"SELECT 1 FROM pg_catalog.pg_database WHERE datname = '{self.config['database']}'")
            exists = cursor.fetchone()
            
            if not exists:
                cursor.execute(f'CREATE DATABASE {self.config["database"]}')
                logger.info(f"Created database: {self.config['database']}")
        finally:
            cursor.close()
            conn.close()

    def init_tables(self) -> None:
        """Initialize database tables"""
        conn = psycopg2.connect(**self.config)
        cursor = conn.cursor()

        try:
            # Create tables
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id SERIAL PRIMARY KEY,
                    name VARCHAR(100) NOT NULL,
                    email VARCHAR(100) UNIQUE NOT NULL,
                    status VARCHAR(20) DEFAULT 'active',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS categories (
                    id SERIAL PRIMARY KEY,
                    name VARCHAR(100) NOT NULL
                );

                CREATE TABLE IF NOT EXISTS products (
                    id SERIAL PRIMARY KEY,
                    name VARCHAR(100) NOT NULL,
                    description TEXT,
                    price DECIMAL(10, 2) NOT NULL,
                    category_id INTEGER REFERENCES categories(id),
                    stock_quantity INTEGER DEFAULT 0
                );

                CREATE TABLE IF NOT EXISTS orders (
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER REFERENCES users(id),
                    total_amount DECIMAL(10, 2) NOT NULL,
                    status VARCHAR(20) DEFAULT 'pending',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS order_items (
                    id SERIAL PRIMARY KEY,
                    order_id INTEGER REFERENCES orders(id),
                    product_id INTEGER REFERENCES products(id),
                    quantity INTEGER NOT NULL,
                    price DECIMAL(10, 2) NOT NULL
                );
            """)
            conn.commit()
            logger.info("Created database tables")

        finally:
            cursor.close()
            conn.close()

    def insert_sample_data(self) -> None:
        """Insert sample data into tables"""
        conn = psycopg2.connect(**self.config)
        cursor = conn.cursor()

        try:
            # Insert Users
            cursor.execute("""
                INSERT INTO users (name, email, status) VALUES 
                ('John Doe', 'john@example.com', 'active'),
                ('Jane Smith', 'jane@example.com', 'active'),
                ('Bob Wilson', 'bob@example.com', 'inactive'),
                ('Alice Johnson', 'alice@example.com', 'active'),
                ('Michael Brown', 'michael@example.com', 'active'),
                ('Emily Davis', 'emily@example.com', 'active'),
                ('Daniel Lee', 'daniel@example.com', 'active'),
                ('Olivia Martinez', 'olivia@example.com', 'active'),
                ('William Taylor', 'william@example.com', 'active'),
                ('Sophia Clark', 'sophia@example.com', 'active')
                ON CONFLICT (email) DO NOTHING;
            """)

            # Insert Categories
            cursor.execute("""
                INSERT INTO categories (name) VALUES
                ('Electronics'),
                ('Books'),
                ('Clothing'),
                ('Furniture'),
                ('Toys'),
                ('Sports'),
                ('Automotive'),
                ('Home Decor'),
                ('Jewelry'),
                ('Art');
            """)

            # Insert Products
            cursor.execute("""
                INSERT INTO products (name, description, price, category_id, stock_quantity) VALUES
                ('Laptop', 'High-performance laptop', 999.99, 1, 50),
                ('Python Book', 'Learning Python Programming', 49.99, 2, 75),
                ('T-Shirt', 'Cotton T-Shirt', 19.99, 3, 200),
                ('Sofa', 'Comfortable sofa', 299.99, 4, 30),
                ('Teddy Bear', 'Soft plush bear', 14.99, 5, 100),
                ('Bicycle', '20-speed bicycle', 199.99, 6, 40),
                ('Car Parts', 'Auto parts kit', 249.99, 7, 15),
                ('Desk', 'Wooden desk', 149.99, 8, 25),
                ('Necklace', 'Silver necklace', 99.99, 9, 50);
            """)

            # Insert Orders
            cursor.execute("""
                INSERT INTO orders (user_id, total_amount, status) VALUES
                (1, 1049.98, 'completed'),
                (2, 49.99, 'pending'),
                (3, 149.99, 'completed'),
                (4, 299.99, 'pending'),
                (5, 99.99, 'completed'),
                (6, 199.99, 'pending'),
                (7, 249.99, 'completed'),
                (8, 149.99, 'pending'),
                (9, 99.99, 'completed'),
                (10, 199.99, 'pending');
            """)

            # Insert Order Items
            cursor.execute("""
                INSERT INTO order_items (order_id, product_id, quantity, price) VALUES
                (1, 1, 1, 999.99),
                (1, 2, 1, 49.99),
                (2, 2, 1, 49.99),
                (3, 3, 1, 19.99),
                (4, 4, 1, 299.99),
                (5, 5, 1, 14.99),
                (6, 6, 1, 199.99),
                (7, 7, 1, 249.99),
                (8, 8, 1, 149.99);
            """)
            
            conn.commit()
            logger.info("Inserted sample data")

        except Exception as e:
            conn.rollback()
            logger.error(f"Error inserting sample data: {str(e)}")
            raise
        finally:
            cursor.close()
            conn.close()

def setup_database():
    import os
    from dotenv import load_dotenv
    load_dotenv()

    host = os.getenv("PG_HOST")
    port = os.getenv("PG_PORT")
    database = os.getenv("PG_DATABASE")
    user = os.getenv("PG_USER")
    password = os.getenv("PG_PASSWORD")

    """Setup database with tables and sample data"""
    # Initialize database manager
    db_manager = DatabaseManager(
        host=host,
        port=port,
        database=database,
        user=user,
        password=password
    )

    # Create and setup database
    print("Setting up database...")
    db_manager.create_database()
    db_manager.init_tables()
    db_manager.insert_sample_data()
    print("Database setup complete!")

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    setup_database()

