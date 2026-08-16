import sqlite3
import psycopg2

print("Migrating data from SQLite (db.sqlite3) to PostgreSQL (ai_teaching_db)...")

sqlite_conn = sqlite3.connect('db.sqlite3')
sqlite_conn.row_factory = sqlite3.Row
sqlite_cur = sqlite_conn.cursor()

pg_conn = psycopg2.connect("postgres://postgres:postgres@127.0.0.1:5432/ai_teaching_db")
pg_conn.autocommit = True
pg_cur = pg_conn.cursor()

# 1. Migrate accounts_user
sqlite_cur.execute("SELECT * FROM accounts_user")
users = sqlite_cur.fetchall()
for u in users:
    row = dict(u)
    date_joined = row.get('date_joined')
    created_at = row.get('created_at') or date_joined
    updated_at = row.get('updated_at') or date_joined
    pg_cur.execute("""
        INSERT INTO accounts_user (id, password, last_login, is_superuser, username, first_name, last_name, email, is_staff, is_active, date_joined, role, created_at, updated_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (id) DO NOTHING;
    """, (
        row['id'], row['password'], row['last_login'], bool(row['is_superuser']),
        row['username'], row['first_name'], row['last_name'], row['email'],
        bool(row['is_staff']), bool(row['is_active']), date_joined, row['role'],
        created_at, updated_at
    ))
print(f"Migrated {len(users)} users to PostgreSQL!")

# 2. Migrate accounts_teacherprofile
sqlite_cur.execute("SELECT * FROM accounts_teacherprofile")
profiles = sqlite_cur.fetchall()
for p in profiles:
    row = dict(p)
    pg_cur.execute("""
        INSERT INTO accounts_teacherprofile (id, employee_id, department, created_at, updated_at, user_id)
        VALUES (%s, %s, %s, %s, %s, %s)
        ON CONFLICT (id) DO NOTHING;
    """, (
        row['id'], row['employee_id'], row['department'], row['created_at'], row['updated_at'], row['user_id']
    ))
print(f"Migrated {len(profiles)} teacher profiles to PostgreSQL!")

sqlite_conn.close()
pg_conn.close()
print("Data migration from SQLite to PostgreSQL completed successfully!")
