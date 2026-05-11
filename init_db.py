#!/usr/bin/env python3
"""
init_db.py – Initialize the SQLite database with tables
Run this script to create the database file and tables if they don't exist.
Usage:
    python init_db.py
"""

import os
import sys
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from app.database import engine, Base
from app.models import User, ApiToken, UsageLog  # Import all models


def init_database():
    """Create database file and all tables"""
    try:
        print("Creating database tables...")
        
        # Create all tables defined in the models
        Base.metadata.create_all(bind=engine)
        
        print("✅ Database initialized successfully!")
        print(f"📁 Database file location: {engine.url.database}")
        
        # Check if database file actually exists
        db_path = Path(engine.url.database.replace('sqlite:///', ''))
        if db_path.exists():
            print(f"📊 Database file size: {db_path.stat().st_size} bytes")
        else:
            print("⚠️  Warning: Database file not found at expected location")
            
    except Exception as e:
        print(f"❌ Error initializing database: {e}")
        sys.exit(1)


if __name__ == "__main__":
    init_database()
