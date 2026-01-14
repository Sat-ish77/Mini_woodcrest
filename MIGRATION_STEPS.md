# Migration Steps - Adding Chunking to Existing Supabase Setup

## ✅ What You Already Have

You already have:
- ✅ `documents` table with embeddings
- ✅ `match_documents()` function
- ✅ RLS policies
- ✅ Vector indexes

## 🎯 What You Need to Add

Just add the chunking system **alongside** your existing setup:

1. **New table:** `document_chunks` (stores chunks)
2. **New function:** `match_chunks()` (searches chunks)
3. **New indexes:** For fast chunk search

## 📋 Step-by-Step Migration

### Step 1: Run the SQL Migration

1. Go to **Supabase Dashboard** → **SQL Editor**
2. Copy and paste the **entire contents** of `database_schema.sql`
3. Click **Run**

This will:
- ✅ Create `document_chunks` table
- ✅ Add RLS policies
- ✅ Create indexes
- ✅ Create `match_chunks()` function
- ✅ **NOT break** your existing `documents` table or `match_documents()` function

### Step 2: Verify It Worked

Run this query to check:

```sql
-- Check if table exists
SELECT * FROM document_chunks LIMIT 1;

-- Check if function exists
SELECT proname FROM pg_proc WHERE proname = 'match_chunks';
```

Both should return results (or empty table is fine).

### Step 3: Re-upload Your Documents

**Important:** Your existing documents still have old document-level embeddings.

**Options:**

**Option A: Keep old documents, add new ones with chunking**
- Old documents: Will still work with `match_documents()` (old system)
- New documents: Will use `match_chunks()` (new chunking system)
- **Result:** Mixed system (works but not ideal)

**Option B: Delete and re-upload all (RECOMMENDED)**
- Delete all old documents from the app
- Re-upload them
- **Result:** All documents use chunking system

### Step 4: Test the New System

Try your question:
- "What was the total spend on repairs on Oak Street?"

**Expected:** Should now find ALL repair expenses including pest control!

## 🔄 How It Works Now

### Old Documents (if you keep them)
- Still in `documents` table
- Still have document-level embeddings
- Still searchable via `match_documents()`
- **But:** Won't benefit from chunking

### New Documents (after migration)
- Saved to `documents` table (metadata)
- Chunks saved to `document_chunks` table
- Searchable via `match_chunks()` (new function)
- **Benefit:** Much better accuracy!

## 🛡️ Security

- ✅ RLS policies ensure users only see their own chunks
- ✅ `match_chunks()` uses `auth.uid()` automatically
- ✅ Same security model as your existing `match_documents()`

## 📊 Database Structure After Migration

```
documents (existing)
├── id
├── user_id
├── filename
├── property_name
├── document_type
├── vendor
├── amount
├── document_date
├── file_content
└── embedding (not used for new uploads, but kept for old docs)

document_chunks (NEW)
├── id
├── document_id → references documents(id)
├── user_id
├── chunk_index
├── chunk_text
├── embedding (vector for this chunk)
└── start_char
```

## ⚠️ Important Notes

1. **Backward Compatible:** Your existing code won't break
2. **Old Documents:** Will still work but won't use chunking
3. **New Documents:** Automatically use chunking
4. **No Data Loss:** All existing documents remain intact
5. **CASCADE Delete:** Deleting a document automatically deletes its chunks

## 🚀 After Migration

Your app will:
- ✅ Use chunking for all new uploads
- ✅ Find all relevant information (not just best match)
- ✅ Answer questions more accurately
- ✅ Scale to large documents

## ❓ Troubleshooting

**Q: What if I get an error running the SQL?**
A: Check that:
- `vector` extension is enabled (you already have this)
- `documents` table exists (you already have this)
- You're running as a database admin

**Q: Can I keep both systems?**
A: Yes! But it's better to migrate all documents to chunking for consistency.

**Q: Will old documents break?**
A: No, they'll still work with the old `match_documents()` function, but new uploads will use chunking.

