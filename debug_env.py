import os
from pathlib import Path

print("Current directory:", os.getcwd())
print("\nFiles in directory:")
for file in Path('.').iterdir():
    if '.env' in file.name:
        print(f"  {file.name} - Size: {file.stat().st_size} bytes")

print("\nEnvironment variables:")
print(f"  MONGODB_URI: {os.getenv('MONGODB_URI', 'NOT SET')}")

print("\nTrying to read .env file directly:")
try:
    with open('.env', 'r') as f:
        content = f.read()
        print(f"  File content:\n{content}")
except FileNotFoundError:
    print("  .env file not found!")
except Exception as e:
    print(f"  Error: {e}")