import psycopg2
import os

users = ['postgres', 'LENOVO', 'lenovo', os.getenv('USERNAME')]
for u in users:
    try:
        conn = psycopg2.connect(f'postgres://{u}@127.0.0.1:5432/postgres')
        print(f"SUCCESS connecting with user '{u}' without password!")
        conn.close()
    except Exception as e:
        print(f"User '{u}': {e}")
