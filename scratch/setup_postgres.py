import psycopg2

conn = psycopg2.connect('postgres://postgres@127.0.0.1:5432/postgres')
conn.autocommit = True
cur = conn.cursor()

cur.execute("ALTER USER postgres WITH PASSWORD 'postgres';")
print("Password set for postgres user!")

cur.execute("SELECT 1 FROM pg_database WHERE datname='ai_teaching_db';")
exists = cur.fetchone()
if not exists:
    cur.execute("CREATE DATABASE ai_teaching_db;")
    print("Created database: ai_teaching_db")
else:
    print("Database ai_teaching_db already exists.")

cur.close()
conn.close()
