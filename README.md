# 🏢 PropertyAI - Document Intelligence System

A smart document management system that uses RAG (Retrieval Augmented Generation) to help property managers organize, search, and query their property documents using natural language.

## ✨ Features

- 📤 **Document Upload**: Upload and process PDF and TXT files
- 🤖 **AI-Powered Metadata Extraction**: Automatically extracts property name, document type, vendor, amount, and dates
- 🔍 **Semantic Search**: Ask questions in natural language about your documents
- 💬 **RAG-Powered Q&A**: Get accurate answers based on your document content
- 📊 **Document Management**: View, filter, and manage all your documents
- 🔐 **User Authentication**: Secure login/signup with Supabase Auth
- 🗂️ **Chunking-Based RAG**: Advanced chunking system for precise information retrieval

## 🛠️ Tech Stack

- **Frontend**: Streamlit
- **Backend**: Python (FastAPI-style functions)
- **Database**: Supabase (PostgreSQL + pgvector)
- **Vector Search**: PostgreSQL pgvector extension
- **AI/ML**: 
  - OpenAI GPT-4o-mini (for metadata extraction and Q&A)
  - OpenAI text-embedding-3-small (for embeddings)
- **Authentication**: Supabase Auth
- **File Processing**: PyPDF2 (for PDF text extraction)

## 📋 Prerequisites

- Python 3.10 or higher
- Supabase account ([Sign up here](https://supabase.com))
- OpenAI API key ([Get one here](https://platform.openai.com))

## 🚀 Getting Started

### 1. Clone the Repository

```bash
git clone <repository-url>
cd mini_property_ai
```

### 2. Create Virtual Environment

```bash
python -m venv venv

# On Windows
venv\Scripts\activate

# On macOS/Linux
source venv/bin/activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Set Up Environment Variables

Create a `.env` file in the root directory:

```env
SUPABASE_URL=your_supabase_project_url
SUPABASE_KEY=your_supabase_anon_key
OPENAI_API_KEY=your_openai_api_key
```

**Where to find these values:**
- **SUPABASE_URL & SUPABASE_KEY**: Go to Supabase Dashboard → Settings → API
- **OPENAI_API_KEY**: Go to OpenAI Platform → API Keys

### 5. Set Up Database

1. Go to your Supabase Dashboard → SQL Editor
2. Ensure you have a `documents` table with the following structure:
   ```sql
   CREATE TABLE documents (
       id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
       user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
       filename TEXT NOT NULL,
       file_content TEXT,
       property_name TEXT,
       document_type TEXT,
       vendor TEXT,
       amount NUMERIC,
       document_date DATE,
       uploaded_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
       embedding VECTOR(1536)
   );
   ```

3. Run the SQL script to create the chunking system:
   ```bash
   # Copy contents of ADD_CHUNKS_TABLE.sql and run in Supabase SQL Editor
   ```

4. Enable Row Level Security (RLS) on the `documents` table if not already enabled.

### 6. Run the Application

```bash
streamlit run app.py
```

The app will open in your browser at `http://localhost:8501`

## 📖 Usage

### Uploading Documents

1. Sign up or log in to your account
2. Navigate to the "📤 Upload Documents" tab
3. Select one or more PDF or TXT files
4. Click "Process All Files"
5. The system will automatically:
   - Extract text from documents
   - Extract metadata (property, type, vendor, amount, date)
   - Split documents into chunks
   - Create embeddings for semantic search

### Asking Questions

1. Navigate to the "❓ Ask Questions" tab
2. Type your question in natural language, for example:
   - "What was the total spent on HVAC services?"
   - "Which property had utility bills over $400?"
   - "Show me all invoices from Superior HVAC"
3. Click "Get Answer"
4. View the answer with source documents and relevance scores

### Viewing Documents

1. Navigate to the "📄 View Documents" tab
2. Use filters to find specific documents by property or type
3. View document details, metadata, and content preview
4. Delete documents if needed

## 🏗️ Architecture

### System Components

- **app.py**: Main Streamlit application and UI
- **auth.py**: Authentication handlers (login, signup, session management)
- **database.py**: Database operations (CRUD, semantic search)
- **ingest.py**: Document processing pipeline (extraction, chunking, embeddings)
- **qa.py**: RAG-based question answering system

### RAG Implementation

The system uses a chunking-based RAG approach:

1. **Document Ingestion**:
   - Documents are split into chunks (~500 characters with 50 character overlap)
   - Each chunk gets its own embedding vector (1536 dimensions)
   - Chunks are stored in `document_chunks` table

2. **Question Answering**:
   - User question is converted to an embedding
   - Vector similarity search finds relevant chunks
   - Top chunks are passed to GPT with context
   - GPT generates answer based on retrieved chunks

### Database Schema

**documents** table: Stores document metadata and full content
**document_chunks** table: Stores chunks with embeddings for semantic search

## 🔒 Security

- Row Level Security (RLS) ensures users only access their own documents
- Supabase Auth handles authentication and session management
- API keys are stored in environment variables (never commit `.env` file)

## 📁 Project Structure

```
mini_property_ai/
├── app.py                 # Main Streamlit application
├── auth.py                # Authentication handlers
├── database.py            # Database operations
├── ingest.py              # Document processing
├── qa.py                  # Question answering (RAG)
├── ADD_CHUNKS_TABLE.sql   # Database schema for chunking
├── requirements.txt       # Python dependencies
├── .env                   # Environment variables (create this)
└── README.md              # This file
```

## 🔧 Configuration

### Chunking Parameters

You can modify chunking parameters in `ingest.py`:

```python
chunks = chunk_text(text, chunk_size=500, overlap=50)
```

- `chunk_size`: Target chunk size in characters (default: 500)
- `overlap`: Characters to overlap between chunks (default: 50)

### Search Parameters

You can modify search parameters in `qa.py`:

```python
relevant_docs = search_documents_semantic(
    query_embedding=query_embedding,
    match_threshold=0.3,  # Minimum similarity (0.0 to 1.0)
    match_count=10        # Number of chunks to retrieve
)
```

## 🐛 Troubleshooting

### Common Issues

**"SUPABASE_URL not found"**
- Make sure you've created a `.env` file
- Check that environment variables are set correctly

**"OPENAI_API_KEY not found"**
- Verify your API key is correct in `.env`
- Check that you have credits in your OpenAI account

**"Could not save chunks"**
- Run the SQL from `ADD_CHUNKS_TABLE.sql` in Supabase
- Ensure `document_chunks` table exists

**PDF extraction fails**
- Some PDFs are scanned images (require OCR)
- Try converting to text file first

## 📝 License

See LICENSE file for details.

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## 📧 Support

For issues and questions, please open an issue in the repository.

---

**Built with ❤️ using Streamlit, Supabase, and OpenAI**
