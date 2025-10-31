# Quick Setup Instructions

## 1. Set Up Supabase

### Create a Supabase Project
1. Go to https://supabase.com
2. Sign up or log in
3. Click "New Project"
4. Fill in the project details and wait for it to be created

### Get Your Credentials
1. In your Supabase dashboard, go to **Settings** → **API**
2. Copy your **Project URL** and **anon/public** key

### Create the Database Tables
1. In Supabase dashboard, go to **SQL Editor**
2. Click **New query**
3. Open the file `schema.sql` from this directory
4. Copy the entire contents and paste into the SQL editor
5. Click **Run** to create all tables

## 2. Configure Environment Variables

1. In the `backend` directory, you'll find a `.env` file
2. Open it and fill in your Supabase credentials:

```env
SUPABASE_URL=https://your-project-id.supabase.co
SUPABASE_KEY=your-anon-key-here

JWT_SECRET=your-random-secret-key-here
JWT_ALGORITHM=HS256
```

**Where to find these:**
- `SUPABASE_URL` and `SUPABASE_KEY`: From Supabase dashboard → Settings → API
- `JWT_SECRET`: Any random string (keep it secret!)
- `JWT_ALGORITHM`: Keep as `HS256`

## 3. Install Dependencies

```bash
cd backend
pip install -r requirements.txt
```

## 4. Start the Server

```bash
uvicorn app.main:app --reload
```

The server should start at `http://localhost:8000`

## 5. Test the Connection

Open your browser or use curl:
```bash
curl http://localhost:8000/check-db
```

Should return: `{"message": "Supabase connection successful"}`

## Troubleshooting

### "SUPABASE_URL and SUPABASE_KEY must be set"
- Make sure the `.env` file exists in the `backend` directory
- Make sure you've replaced `your_supabase_project_url_here` with your actual Supabase URL
- Make sure you've replaced `your_supabase_anon_key_here` with your actual Supabase key

### Database connection errors
- Verify your Supabase URL and key are correct
- Check that you've run the `schema.sql` in Supabase SQL Editor
- Make sure your Supabase project is running (not paused)

### Still having issues?
Check the detailed guide in `MIGRATION_GUIDE.md`


