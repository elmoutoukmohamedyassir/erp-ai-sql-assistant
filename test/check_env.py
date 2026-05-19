"""
Run this file from the same folder as your project to debug .env loading.
    python check_env.py
"""
import os
from pathlib import Path
from dotenv import load_dotenv, dotenv_values

ENV_PATH = Path(__file__).parent / ".env"

print(f"Looking for .env at: {ENV_PATH}")
print(f"File exists: {ENV_PATH.exists()}")
print()

if ENV_PATH.exists():
    raw = dotenv_values(ENV_PATH)
    print("Keys found in .env file:")
    for key, value in raw.items():
        masked = value[:2] + "*" * (len(value) - 2) if value and len(value) > 2 else "***"
        print(f"  {key} = {masked}")
    print()
    load_dotenv(ENV_PATH, override=True)
    print("After load_dotenv:")
    for key in ["DB_SERVER", "DB_NAME", "DB_USER", "DB_PASSWORD", "GROQ_API_KEY"]:
        val = os.getenv(key)
        if val:
            masked = val[:2] + "*" * (len(val) - 2)
            print(f"  {key} = {masked}")
        else:
            print(f"  {key} = *** NOT FOUND ***")
else:
    print("ERROR: .env file not found!")
    print()
    print("Create a .env file in the same folder as your scripts with this content:")
    print()
    print("  DB_SERVER=your_server_name")
    print("  DB_NAME=your_database_name")
    print("  DB_USER=your_username")
    print("  DB_PASSWORD=your_password")
    print("  GROQ_API_KEY=your_groq_api_key")