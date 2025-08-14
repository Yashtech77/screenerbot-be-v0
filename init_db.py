import sqlite3

def init_db():
    conn = sqlite3.connect('vapi.db')
    cursor = conn.cursor()
    
    # Create tables
    cursor.executescript('''
        CREATE TABLE IF NOT EXISTS calls (
            id TEXT PRIMARY KEY,
            customer_number TEXT NOT NULL,
            assistant_id TEXT,
            start_time TIMESTAMP,
            end_time TIMESTAMP,
            duration INTEGER,
            status TEXT,
            recording_url TEXT
        );
        
        CREATE TABLE IF NOT EXISTS transcripts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            call_id TEXT NOT NULL,
            timestamp TIMESTAMP,
            transcript TEXT,
            is_final BOOLEAN DEFAULT 0,
            FOREIGN KEY (call_id) REFERENCES calls(id)
        );
        
        CREATE TABLE IF NOT EXISTS function_calls (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            call_id TEXT NOT NULL,
            function_name TEXT NOT NULL,
            parameters TEXT,
            timestamp TIMESTAMP,
            FOREIGN KEY (call_id) REFERENCES calls(id)
        );
        
        CREATE TABLE IF NOT EXISTS errors (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            call_id TEXT,
            message TEXT,
            timestamp TIMESTAMP,
            FOREIGN KEY (call_id) REFERENCES calls(id)
        );
        
        CREATE TABLE IF NOT EXISTS donations (
            donation_id INTEGER PRIMARY KEY AUTOINCREMENT,
            call_id TEXT NOT NULL,
            amount DECIMAL(10, 2) NOT NULL,
            currency TEXT DEFAULT 'INR',
            donation_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (call_id) REFERENCES calls(id)
        );
    ''')
    
    conn.commit()
    conn.close()
    print("Database initialized successfully!")

if __name__ == '__main__':
    init_db()