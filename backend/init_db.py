from sqlalchemy import text

from database import engine
from models import Base
import pymysql
from dotenv import load_dotenv
import os

load_dotenv()

def init_database():
    try:
        print("Connecting to MySQL...")
        
        # Create all tables
        print("Creating tables...")
        Base.metadata.create_all(bind=engine)
        print("All tables created successfully")
        
        # List tables
        with engine.connect() as conn:
            result = conn.execute(text("SHOW TABLES"))
            tables = [row[0] for row in result.fetchall()]
            print("\nTables created:")
            for table in tables:
                print(f"   - {table}")
        
        return True
        
    except Exception as e:
        print(f"Error: {e}")
        print("\nPlease check:")
        print("1. Is MySQL running? (Service: MySQL80)")
        print("2. Is the password correct in .env?")
        print("3. Did you create the database first?")
        return False

if __name__ == "__main__":
    init_database()




    