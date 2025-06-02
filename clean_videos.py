import sqlite3

# Path to your SQLite database
DB_PATH = 'myavatar.db'

def clean_videos():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    # Delete all video records
    c.execute('DELETE FROM videos')
    conn.commit()
    conn.close()
    print('All video records deleted.')

if __name__ == '__main__':
    clean_videos()
