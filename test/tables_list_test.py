from core.db import get_connection
from sqlalchemy import text

conn = get_connection()

result = conn.execute(text("""
SELECT TABLE_NAME 
FROM INFORMATION_SCHEMA.TABLES
"""))

for row in result:
    print(row)