import os
from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv()

MONGODB_URI = os.getenv('MONGODB_URI')

if not MONGODB_URI:
    print("ERROR: MONGODB_URI not set in .env")
    exit(1)

try:
    client = MongoClient(MONGODB_URI, serverSelectionTimeoutMS=5000)
    client.server_info()
    print("✓ Connection successful!")
    
    db = client['carvalueai']
    print(f"✓ Database: {db.name}")
    print(f"✓ Collections: {db.list_collection_names()}")
    
    client.close()
except Exception as e:
    print(f"✗ Connection failed: {e}")
    print("\nTroubleshooting tips:")
    print("1. Check MongoDB URI is correct")
    print("2. Ensure cluster is running")
    print("3. Check IP whitelist in Atlas (allows 0.0.0.0/0)")
    print("4. Verify username/password")