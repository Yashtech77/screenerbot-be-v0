-- Updated schema.sql
CREATE TABLE IF NOT EXISTS calls (
    id TEXT PRIMARY KEY,  -- Vapi call ID
    type TEXT CHECK(type IN ('inbound', 'outbound')),
    status TEXT CHECK(status IN ('queued', 'ringing', 'in-progress', 'completed', 'failed')),
    assistant_id TEXT,
    customer_number TEXT,
    agent_number TEXT,
    start_time TIMESTAMP,
    end_time TIMESTAMP,
    duration INTEGER,
    recording_url TEXT,
    cost REAL,
    ended_reason TEXT,
    org_id TEXT
);

CREATE TABLE IF NOT EXISTS call_messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    call_id TEXT NOT NULL,
    role TEXT CHECK(role IN ('user', 'assistant')),
    content TEXT,
    timestamp TIMESTAMP,
    FOREIGN KEY (call_id) REFERENCES calls(id)
);

CREATE TABLE IF NOT EXISTS call_recordings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    call_id TEXT NOT NULL,
    url TEXT NOT NULL,
    started_at TIMESTAMP,
    ended_at TIMESTAMP,
    FOREIGN KEY (call_id) REFERENCES calls(id)
);

CREATE TABLE IF NOT EXISTS assistants (
    id TEXT PRIMARY KEY,
    name TEXT,
    model_provider TEXT,
    model_name TEXT,
    voice_provider TEXT,
    voice_id TEXT,
    first_message TEXT,
    server_url TEXT,
    created_at TIMESTAMP,
    updated_at TIMESTAMP
);

-- Existing tables for chats, donations, etc. remain as before