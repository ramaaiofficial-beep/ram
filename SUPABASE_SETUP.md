# Quick Start: Supabase Setup

## Step 1: Create Supabase Project

1. Go to https://supabase.com and sign up/login
2. Click "New Project"
3. Fill in:
   - Project name: `rama-ai`
   - Database password: (choose a strong password)
   - Region: (select closest to you)
4. Click "Create new project" (takes 2-3 minutes)

## Step 2: Create Tables

1. In Supabase dashboard, go to "SQL Editor"
2. Click "New query"
3. Copy and paste the entire contents of `schema.sql`
4. Click "Run" to execute
5. You should see success messages for each table creation

## Step 3: Get Credentials

1. In Supabase dashboard, go to "Settings" (gear icon)
2. Click "API" from the sidebar
3. Copy the following:
   - **Project URL** (starts with `https://`)
   - **anon/public key** (under "Project API keys")

## Step 4: Configure Environment

1. In your backend directory, create a `.env` file (if it doesn't exist)
2. Add these variables:

```env
SUPABASE_URL=https://your-project-id.supabase.co
SUPABASE_KEY=your-anon-key-here

JWT_SECRET=your-very-secret-jwt-key-change-this
JWT_ALGORITHM=HS256

# Optional: For medication reminders
TWILIO_ACCOUNT_SID=your_twilio_account_sid
TWILIO_AUTH_TOKEN=your_twilio_auth_token
TWILIO_PHONE_NUMBER=your_twilio_phone_number
```

## Step 5: Test the Connection

1. Start your backend server:
   ```bash
   cd backend
   python -m uvicorn app.main:app --reload
   ```

2. Test the database connection:
   ```bash
   curl http://localhost:8000/check-db
   ```
   Should return: `{"message": "Supabase connection successful"}`

## Step 6: Verify Tables

In Supabase dashboard, go to "Table Editor" and you should see:
- `users`
- `elders`
- `younger`
- `chat_history`
- `reminders`

## Done! ✅

Your application is now connected to Supabase!


