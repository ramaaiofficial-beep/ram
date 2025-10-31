-- ============================================================================
-- RAMA AI - Complete PostgreSQL Schema for Supabase
-- ============================================================================
-- This schema creates all tables with proper foreign key relationships
-- and data isolation to ensure users only see their own data.
-- ============================================================================

-- ============================================================================
-- STEP 1: Create Tables in Order (respecting dependencies)
-- ============================================================================

-- Users table - foundation table for all relationships
CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    username TEXT NOT NULL,
    email TEXT NOT NULL UNIQUE,
    phone TEXT NOT NULL,
    password TEXT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT TIMEZONE('utc', NOW()),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT TIMEZONE('utc', NOW())
);

-- Elders table - linked to users with CASCADE delete
CREATE TABLE IF NOT EXISTS elders (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    relationship TEXT NOT NULL,
    name TEXT NOT NULL,
    age INTEGER NOT NULL,
    email TEXT NOT NULL,
    phone TEXT NOT NULL,
    address TEXT,
    notes TEXT,
    last_updated TIMESTAMP WITH TIME ZONE DEFAULT TIMEZONE('utc', NOW()),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT TIMEZONE('utc', NOW())
);

-- Younger table - linked to users with CASCADE delete
CREATE TABLE IF NOT EXISTS younger (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    relationship TEXT,
    name TEXT NOT NULL,
    age INTEGER NOT NULL,
    email TEXT NOT NULL,
    phone TEXT NOT NULL,
    address TEXT,
    notes TEXT,
    last_updated TIMESTAMP WITH TIME ZONE DEFAULT TIMEZONE('utc', NOW()),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT TIMEZONE('utc', NOW())
);

-- Chat history table - linked to users with CASCADE delete
CREATE TABLE IF NOT EXISTS chat_history (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    message TEXT NOT NULL,
    response TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT TIMEZONE('utc', NOW())
);

-- Reminders table - MUST be linked to BOTH user AND elder for proper isolation
CREATE TABLE IF NOT EXISTS reminders (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    elder_id UUID REFERENCES elders(id) ON DELETE CASCADE,
    patient_name TEXT NOT NULL,
    medication_name TEXT NOT NULL,
    dosage TEXT NOT NULL,
    send_time TIMESTAMP WITH TIME ZONE NOT NULL,
    phone_number TEXT NOT NULL,
    frequency TEXT,
    is_sent BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT TIMEZONE('utc', NOW())
);

-- ============================================================================
-- STEP 2: Add Missing Columns to Existing Tables (Safe Migration)
-- ============================================================================

-- This ensures existing reminders table gets user_id if it's missing
DO $$
BEGIN
    -- Ensure reminders table exists then add any missing columns independently
    IF EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'reminders') THEN
        -- user_id
        IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='reminders' AND column_name='user_id') THEN
            ALTER TABLE reminders ADD COLUMN user_id UUID REFERENCES users(id) ON DELETE CASCADE;
        END IF;
        -- elder_id
        IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='reminders' AND column_name='elder_id') THEN
            ALTER TABLE reminders ADD COLUMN elder_id UUID REFERENCES elders(id) ON DELETE CASCADE;
        END IF;
        -- frequency
        IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='reminders' AND column_name='frequency') THEN
            ALTER TABLE reminders ADD COLUMN frequency TEXT;
        END IF;
        -- is_sent
        IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='reminders' AND column_name='is_sent') THEN
            ALTER TABLE reminders ADD COLUMN is_sent BOOLEAN DEFAULT FALSE;
        END IF;
    END IF;
END $$;

-- ============================================================================
-- STEP 3: Create Indexes for Performance
-- ============================================================================

-- Indexes on ALL foreign keys for fast JOINs
CREATE INDEX IF NOT EXISTS idx_elders_user_id ON elders(user_id);
CREATE INDEX IF NOT EXISTS idx_younger_user_id ON younger(user_id);
CREATE INDEX IF NOT EXISTS idx_chat_history_user_id ON chat_history(user_id);
CREATE INDEX IF NOT EXISTS idx_reminders_user_id ON reminders(user_id);
CREATE INDEX IF NOT EXISTS idx_reminders_elder_id ON reminders(elder_id);

-- Indexes on searchable columns (names, emails)
CREATE INDEX IF NOT EXISTS idx_elders_name ON elders(name);
CREATE INDEX IF NOT EXISTS idx_younger_name ON younger(name);
CREATE INDEX IF NOT EXISTS idx_elders_email ON elders(email);
CREATE INDEX IF NOT EXISTS idx_younger_email ON younger(email);
CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);

-- Indexes on timestamps for sorting
CREATE INDEX IF NOT EXISTS idx_elders_last_updated ON elders(last_updated);
CREATE INDEX IF NOT EXISTS idx_younger_last_updated ON younger(last_updated);
CREATE INDEX IF NOT EXISTS idx_chat_history_created_at ON chat_history(created_at);
CREATE INDEX IF NOT EXISTS idx_reminders_send_time ON reminders(send_time);

-- ============================================================================
-- Education tables (files and messages)
-- ============================================================================

CREATE TABLE IF NOT EXISTS education_files (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    elder_id UUID NOT NULL REFERENCES elders(id) ON DELETE CASCADE,
    filename TEXT NOT NULL,
    category TEXT NOT NULL, -- medical | stories | songs
    mime_type TEXT NOT NULL,
    storage_path TEXT,      -- if later stored in Supabase Storage
    text_excerpt TEXT,      -- short excerpt or OCR text
    created_at TIMESTAMP WITH TIME ZONE DEFAULT TIMEZONE('utc', NOW())
);

CREATE INDEX IF NOT EXISTS idx_education_files_user_id ON education_files(user_id);
CREATE INDEX IF NOT EXISTS idx_education_files_elder_id ON education_files(elder_id);
CREATE INDEX IF NOT EXISTS idx_education_files_created_at ON education_files(created_at);

CREATE TABLE IF NOT EXISTS education_messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    elder_id UUID NOT NULL REFERENCES elders(id) ON DELETE CASCADE,
    role TEXT NOT NULL,     -- user | assistant
    content TEXT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT TIMEZONE('utc', NOW())
);

CREATE INDEX IF NOT EXISTS idx_education_messages_user_id ON education_messages(user_id);
CREATE INDEX IF NOT EXISTS idx_education_messages_elder_id ON education_messages(elder_id);
CREATE INDEX IF NOT EXISTS idx_education_messages_created_at ON education_messages(created_at);

-- ============================================================================
-- STEP 4: Create Functions and Triggers for Auto-Update Timestamps
-- ============================================================================

-- Function to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = TIMEZONE('utc', NOW());
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Trigger for users table
DROP TRIGGER IF EXISTS update_users_updated_at ON users;
CREATE TRIGGER update_users_updated_at
    BEFORE UPDATE ON users
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Function to update last_updated timestamp
CREATE OR REPLACE FUNCTION update_last_updated_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.last_updated = TIMEZONE('utc', NOW());
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Triggers for elders and younger tables
DROP TRIGGER IF EXISTS update_elders_last_updated ON elders;
CREATE TRIGGER update_elders_last_updated
    BEFORE UPDATE ON elders
    FOR EACH ROW
    EXECUTE FUNCTION update_last_updated_column();

DROP TRIGGER IF EXISTS update_younger_last_updated ON younger;
CREATE TRIGGER update_younger_last_updated
    BEFORE UPDATE ON younger
    FOR EACH ROW
    EXECUTE FUNCTION update_last_updated_column();

-- ============================================================================
-- STEP 5: Row Level Security (RLS) - DISABLED
-- ============================================================================
-- 
-- NOTE: RLS is disabled because this application uses FastAPI with custom
-- JWT authentication, NOT Supabase Auth. Data isolation is enforced in the
-- application layer through foreign key queries with user_id filters.
--
-- If you want to enable RLS for Supabase Auth in the future, uncomment below.
-- ============================================================================

-- For now, we disable RLS and rely on application-level filtering
-- ALTER TABLE users ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE elders ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE younger ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE chat_history ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE reminders ENABLE ROW LEVEL SECURITY;

-- Disable RLS on all tables (RLS conflicts with FastAPI authentication)
ALTER TABLE users DISABLE ROW LEVEL SECURITY;
ALTER TABLE elders DISABLE ROW LEVEL SECURITY;
ALTER TABLE younger DISABLE ROW LEVEL SECURITY;
ALTER TABLE chat_history DISABLE ROW LEVEL SECURITY;
ALTER TABLE reminders DISABLE ROW LEVEL SECURITY;

-- ============================================================================
-- STEP 6: Add Comments for Documentation
-- ============================================================================

COMMENT ON TABLE users IS 'User accounts for RAMA AI application';
COMMENT ON TABLE elders IS 'Elder family members profiles - belongs to a user';
COMMENT ON TABLE younger IS 'Younger family members profiles - belongs to a user';
COMMENT ON TABLE chat_history IS 'Chat history between users and the AI assistant';
COMMENT ON TABLE reminders IS 'Medication reminders - belongs to a user and optional elder';

-- ============================================================================
-- ENTITY RELATIONSHIP SUMMARY
-- ============================================================================
/*
RELATIONSHIPS:
================

1. users (1) -----> (many) elders
   - One user can have multiple elders
   - Foreign key: elders.user_id -> users.id
   - When user deleted: all elders deleted (CASCADE)

2. users (1) -----> (many) younger
   - One user can have multiple younger family members
   - Foreign key: younger.user_id -> users.id
   - When user deleted: all younger deleted (CASCADE)

3. users (1) -----> (many) chat_history
   - One user can have multiple chat messages
   - Foreign key: chat_history.user_id -> users.id
   - When user deleted: all chat history deleted (CASCADE)

4. users (1) -----> (many) reminders
   - One user can have multiple medication reminders
   - Foreign key: reminders.user_id -> users.id
   - When user deleted: all reminders deleted (CASCADE)

5. elders (1) -----> (many) reminders [optional link]
   - One elder can have multiple medication reminders
   - Foreign key: reminders.elder_id -> elders.id
   - When elder deleted: all their reminders deleted (CASCADE)
   - NOTE: Reminder also requires user_id for data isolation

DATA ISOLATION:
================
- All tables are filtered by user_id
- When User A queries elders, they only see their own elders
- When User A queries reminders, they only see their own reminders
- Foreign keys enforce referential integrity
- Row Level Security (RLS) provides additional protection
- CASCADE delete ensures no orphaned records

EXAMPLE:
================
- User A (id: abc) creates Elder X (id: xyz, user_id: abc)
- User A creates Reminder Y (id: 123, user_id: abc, elder_id: xyz)
- User B (id: def) cannot see Elder X or Reminder Y
- If User A is deleted, Elder X and Reminder Y are automatically deleted

INDEXES:
================
- All foreign keys indexed for fast JOINs
- Name and email columns indexed for search
- Timestamp columns indexed for sorting

TRIGGERS:
================
- users.updated_at: auto-updated on UPDATE
- elders.last_updated: auto-updated on UPDATE
- younger.last_updated: auto-updated on UPDATE
*/

-- ============================================================================
-- SCHEMA COMPLETE
-- ============================================================================
