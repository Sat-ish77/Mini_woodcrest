# 🏢 PropertyAI - Property Document Intelligence System

A mini demo version of a Property Intelligence AI System that uses RAG (Retrieval Augmented Generation) to answer questions about property documents using semantic search and AI.

## ✨ Features

- 📤 **Document Upload**: Upload multiple property documents (PDF, TXT) at once
- 🔍 **Semantic Search**: Chunk-based RAG system for accurate information retrieval
- ❓ **AI Q&A**: Ask questions about your property documents and get accurate answers
- 📊 **Document Management**: View, filter, and delete your uploaded documents
- 🔐 **User Authentication**: Secure user accounts with Supabase Auth
- 🎯 **Chunked RAG**: Advanced chunking system for better accuracy than document-level embeddings

## 🚀 Tech Stack

- **Frontend**: Streamlit
- **Backend**: Python
- **Database**: Supabase (PostgreSQL with pgvector)
- **AI/ML**: 
  - OpenAI GPT-4o-mini (for Q&A)
  - OpenAI text-embedding-3-small (for embeddings)
- **Vector Search**: pgvector extension in Supabase

## 📋 Prerequisites

- Python 3.8+
- Supabase account and project
- OpenAI API key
- Git

## 🛠️ Installation

### 1. Clone the Repository

```bash
git clone https://github.com/Sat-ish77/Mini_woodcrest.git
cd Mini_woodcrest
```

### 2. Create Virtual Environment

```bash
python -m venv venv
```

### 3. Activate Virtual Environment

**Windows:**
```bash
venv\Scripts\activate
```

**Mac/Linux:**
```bash
source venv/bin/activate
```

### 4. Install Dependencies

```bash
pip install -r requirements.txt
```

### 5. Set Up Environment Variables

Create a `.env` file in the root directory:

```env
# Supabase Configuration
SUPABASE_URL=your_supabase_project_url
SUPABASE_KEY=your_supabase_anon_public_key

# OpenAI Configuration
OPENAI_API_KEY=your_openai_api_key
```

**Important:** 
- Use the **anon public** key (JWT format starting with `eyJ...`) from Supabase, NOT the publishable key
- Get your keys from: Supabase Dashboard → Settings → API

### 6. Set Up Supabase Database

Run the following SQL in your Supabase SQL Editor:

```sql
-- Extensions
CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE EXTENSION IF NOT EXISTS vector;

-- Documents table
CREATE TABLE IF NOT EXISTS documents (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE,
  filename TEXT NOT NULL,
  property_name TEXT,
  document_type TEXT,
  vendor TEXT,
  amount DECIMAL(10,2),
  document_date DATE,
  uploaded_at TIMESTAMP DEFAULT NOW(),
  file_content TEXT,
  created_at TIMESTAMP DEFAULT NOW(),
  embedding VECTOR(1536)
);

-- Document chunks table (for chunked RAG)
CREATE TABLE IF NOT EXISTS document_chunks (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  document_id UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
  user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  chunk_index INTEGER NOT NULL,
  chunk_text TEXT NOT NULL,
  embedding VECTOR(1536),
  start_char INTEGER,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  UNIQUE(document_id, chunk_index)
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_documents_user_id ON documents(user_id);
CREATE INDEX IF NOT EXISTS idx_documents_property ON documents(property_name);
CREATE INDEX IF NOT EXISTS idx_documents_type ON documents(document_type);
CREATE INDEX IF NOT EXISTS document_chunks_embedding_idx ON document_chunks USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);
CREATE INDEX IF NOT EXISTS document_chunks_document_id_idx ON document_chunks(document_id);
CREATE INDEX IF NOT EXISTS document_chunks_user_id_idx ON document_chunks(user_id);

-- Row Level Security
ALTER TABLE documents ENABLE ROW LEVEL SECURITY;
ALTER TABLE document_chunks ENABLE ROW LEVEL SECURITY;

-- RLS Policies for documents
DROP POLICY IF EXISTS "Users can view their own documents" ON documents;
CREATE POLICY "Users can view their own documents" ON documents FOR SELECT USING (auth.uid() = user_id);
CREATE POLICY "Users can insert their own documents" ON documents FOR INSERT WITH CHECK (auth.uid() = user_id);
CREATE POLICY "Users can update their own documents" ON documents FOR UPDATE USING (auth.uid() = user_id);
CREATE POLICY "Users can delete their own documents" ON documents FOR DELETE USING (auth.uid() = user_id);

-- RLS Policies for document_chunks
DROP POLICY IF EXISTS "Users can view their own chunks" ON document_chunks;
CREATE POLICY "Users can view their own chunks" ON document_chunks FOR SELECT USING (auth.uid() = user_id);
DROP POLICY IF EXISTS "Users can insert their own chunks" ON document_chunks;
CREATE POLICY "Users can insert their own chunks" ON document_chunks FOR INSERT WITH CHECK (auth.uid() = user_id);
DROP POLICY IF EXISTS "Users can delete their own chunks" ON document_chunks;
CREATE POLICY "Users can delete their own chunks" ON document_chunks FOR DELETE USING (auth.uid() = user_id);

-- Semantic search function for chunks
CREATE OR REPLACE FUNCTION match_chunks(
    query_embedding VECTOR(1536),
    match_threshold FLOAT DEFAULT 0.3,
    match_count INT DEFAULT 10
)
RETURNS TABLE (
    id UUID,
    document_id UUID,
    chunk_index INT,
    chunk_text TEXT,
    similarity FLOAT,
    metadata JSONB
)
LANGUAGE plpgsql
SECURITY INVOKER
AS $$
BEGIN
    RETURN QUERY
    SELECT
        dc.id,
        dc.document_id,
        dc.chunk_index,
        dc.chunk_text,
        1 - (dc.embedding <=> query_embedding) AS similarity,
        jsonb_build_object(
            'filename', d.filename,
            'property_name', d.property_name,
            'document_type', d.document_type,
            'vendor', d.vendor,
            'amount', d.amount,
            'document_date', d.document_date
        ) AS metadata
    FROM document_chunks dc
    JOIN documents d ON dc.document_id = d.id
    WHERE 
        dc.user_id = auth.uid()
        AND dc.embedding IS NOT NULL
        AND (1 - (dc.embedding <=> query_embedding)) > match_threshold
    ORDER BY dc.embedding <=> query_embedding
    LIMIT match_count;
END;
$$;
```

## 🎯 Usage

### Run the Application

```bash
venv\Scripts\streamlit run app.py
```

**Important:** Always use `venv\Scripts\streamlit run app.py` (not just `streamlit run app.py`) to ensure you're using the correct virtual environment.

The app will open in your browser at `http://localhost:8501`

### First Time Setup

1. **Sign Up**: Create a new account with your email
2. **Verify Email**: Check your email and click the confirmation link
3. **Login**: Sign in with your credentials
4. **Upload Documents**: Upload property documents (invoices, bills, leases, etc.)
5. **Ask Questions**: Use the Q&A tab to ask questions about your documents

### Example Questions

- "What was the total spend on repairs on Oak Street?"
- "How much was the electric bill for Oak Street?"
- "Which property had utility bills over $400?"
- "Show me all invoices from Superior HVAC"

## 🏗️ Architecture

### Chunked RAG System

This system uses **chunked RAG** (Retrieval Augmented Generation) for better accuracy:

1. **Document Upload**: Documents are split into chunks (300-500 characters each)
2. **Embedding Creation**: Each chunk gets its own vector embedding
3. **Storage**: Chunks stored in `document_chunks` table with embeddings
4. **Semantic Search**: Questions are converted to embeddings and matched against chunks
5. **Answer Generation**: Relevant chunks are passed to GPT for answer generation

### Why Chunking?

- ✅ **Better Accuracy**: Finds all relevant information, not just best-matching document
- ✅ **Precise Retrieval**: Gets exact relevant sections, not random parts
- ✅ **Comprehensive**: Finds all related chunks from different documents
- ✅ **Scalable**: Works well with large documents

## 📁 Project Structure

```
mini_property_ai/
├── app.py                 # Main Streamlit application
├── auth.py                # Authentication functions
├── database.py            # Database operations (Supabase)
├── ingest.py              # Document processing and chunking
├── qa.py                  # Question-answering system
├── requirements.txt       # Python dependencies
├── .env                   # Environment variables (not in git)
├── .gitignore            # Git ignore rules
└── README.md             # This file
```

## 🔒 Security

- **Row Level Security (RLS)**: Users can only access their own documents
- **Environment Variables**: Sensitive keys stored in `.env` (not committed to git)
- **Supabase Auth**: Secure user authentication and session management
- **API Key Protection**: Never expose API keys in code

## 🐛 Troubleshooting

### "Invalid API key" Error
- Make sure you're using the **anon public** key (JWT format), not the publishable key
- Get it from: Supabase Dashboard → Settings → API → anon public key

### "ModuleNotFoundError" Errors
- Make sure virtual environment is activated
- Run: `venv\Scripts\streamlit run app.py` (not just `streamlit run app.py`)

### "Email not confirmed" Error
- Check your email and click the confirmation link
- Or disable email confirmation in Supabase Dashboard → Authentication → Email Auth

### Documents Not Found in Search
- Make sure documents are re-uploaded after setting up chunking
- Old documents won't use chunking until re-uploaded

## 📝 License

MIT License

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## 📧 Contact

For questions or issues, please open an issue on GitHub.

---

**Note**: This is a mini demo version. For production use, consider additional features like:
- Document versioning
- Advanced analytics
- Multi-tenant support
- API endpoints
- Enhanced security features



