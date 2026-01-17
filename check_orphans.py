import sqlite3

def check_orphans(db_path):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    orphans = ['account_app_room', 'account_app_chatmessage']
    for table in orphans:
        cursor.execute(f"SELECT name FROM sqlite_master WHERE type='table' AND name='{table}';")
        if cursor.fetchone():
            print(f"Table '{table}' EXISTS")
            
            # Check if it has content for our user?
            # We don't know the exact schema but 'user_id' or 'host_id' is likely.
            cursor.execute(f"PRAGMA table_info({table});")
            cols = [info[1] for info in cursor.fetchall()]
            print(f"Columns for {table}: {cols}")
        else:
            print(f"Table '{table}' DOES NOT EXIST")

if __name__ == "__main__":
    check_orphans('db.sqlite3')
