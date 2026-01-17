import sqlite3
import sys

def check_fks(db_path):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Get all table names
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = cursor.fetchall()
    
    print("Checking foreign keys pointing to 'auth_user':")
    for table in tables:
        table_name = table[0]
        cursor.execute(f"PRAGMA foreign_key_list({table_name});")
        fks = cursor.fetchall()
        for fk in fks:
            # fk tuple: (id, seq, table, from, to, on_update, on_delete, match)
            to_table = fk[2]
            if to_table == 'auth_user':
                print(f"Table '{table_name}' references 'auth_user' via column '{fk[3]}' (on_delete: {fk[6]})")

if __name__ == "__main__":
    check_fks('db.sqlite3')
