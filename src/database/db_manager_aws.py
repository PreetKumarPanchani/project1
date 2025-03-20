import psycopg2
from psycopg2.extras import RealDictCursor
import os
from dotenv import load_dotenv
import pandas as pd

# Load environment variables
load_dotenv()

# AWS RDS Configuration
DB_CONFIG = {
    "host": os.getenv("PG_HOST_AWS", "your-rds-endpoint.region.rds.amazonaws.com"),
    "port": int(os.getenv("PG_PORT_AWS", 5432)),
    "database": os.getenv("PG_DATABASE_AWS"),
    "user": os.getenv("PG_USER_AWS", "postgres"),
    "password": os.getenv("PG_PASSWORD_AWS"),
    "sslmode": "require"  # Important for AWS RDS
}



def get_db_connection():
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        return conn
    except Exception as e:
        print(f"Error connecting to database: {e}")
        raise

def get_all_tables():
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        # List all tables in the database
        cur.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public'
        """)
        
        tables = cur.fetchall()
        print("Available tables:")
        for table in tables:
            table_name = table['table_name']
            print(f"\n- {table_name}")
            
            # Get column names for the table
            cur.execute(f"""
                SELECT column_name, data_type 
                FROM information_schema.columns 
                WHERE table_name = '{table_name}'
                ORDER BY ordinal_position;
            """)
            columns = cur.fetchall()
            print("\nColumns:")
            for col in columns:
                print(f"  - {col['column_name']} ({col['data_type']})")
            
            # Show sample data with all columns
            cur.execute(f"SELECT * FROM {table_name} LIMIT 5")
            data = cur.fetchall()
            df = pd.DataFrame(data)
            
            # Set display options to show all columns
            pd.set_option('display.max_columns', None)
            pd.set_option('display.width', None)
            pd.set_option('display.max_colwidth', None)
            
            print("\nSample data:")
            print(df)
            print("\n" + "="*50)
            
        cur.close()
        conn.close()
        
    except Exception as e:
        print(f"Error: {str(e)}")

if __name__ == "__main__":
    try:
        conn = get_db_connection()
        if conn:
            print("Successfully connected to AWS RDS!")
            get_all_tables()
            conn.close()
    except Exception as e:
        print(f"Connection failed: {e}")

        