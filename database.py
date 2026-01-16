"""
database.py
Handles all database operations with Supabase - using authenticated sessions
"""

import os
from dotenv import load_dotenv
from typing import List, Dict, Optional, TYPE_CHECKING
from datetime import datetime

# Lazy import Supabase - only load when actually needed
if TYPE_CHECKING:
    from supabase import Client

# Load environment variables from .env file
load_dotenv()

# Disable proxy settings that might interfere with httpx
import os
os.environ.pop('HTTP_PROXY', None)
os.environ.pop('HTTPS_PROXY', None)
os.environ.pop('ALL_PROXY', None)
os.environ.pop('http_proxy', None)
os.environ.pop('https_proxy', None)
os.environ.pop('all_proxy', None)

# Lazy load credentials - only validate when client is actually needed
SUPABASE_URL = None
SUPABASE_KEY = None

def _get_supabase_credentials():
    """Lazy load and validate Supabase credentials"""
    global SUPABASE_URL, SUPABASE_KEY
    
    if SUPABASE_URL is None or SUPABASE_KEY is None:
        SUPABASE_URL = os.getenv("SUPABASE_URL")
        SUPABASE_KEY = os.getenv("SUPABASE_KEY")
        
        # Validate that credentials are loaded
        if not SUPABASE_URL:
            raise ValueError("SUPABASE_URL not found in environment variables. Please check your .env file.")
        if not SUPABASE_KEY:
            raise ValueError("SUPABASE_KEY not found in environment variables. Please check your .env file.")
        
        # Strip any whitespace from keys
        SUPABASE_URL = SUPABASE_URL.strip()
        SUPABASE_KEY = SUPABASE_KEY.strip()
    
    return SUPABASE_URL, SUPABASE_KEY

# Create base Supabase client (will be enhanced with auth per request)
# Using lazy initialization to avoid import-time errors
_supabase_client: Optional['Client'] = None


def get_supabase_client() -> 'Client':
    """
    Returns the base Supabase client instance
    Note: For authenticated operations, use get_authenticated_client from auth.py
    """
    global _supabase_client
    
    if _supabase_client is None:
        try:
            # Lazy import Supabase - only load when actually needed
            from supabase import create_client
            
            # Lazy load credentials
            url, key = _get_supabase_credentials()
            
            # Validate URL format
            if not url.startswith('http'):
                raise ValueError(f"Invalid SUPABASE_URL format: {url}. Should start with https://")
            
            # Validate key format - Supabase keys should be JWT tokens (start with eyJ) or publishable keys
            if not key or len(key) < 20:
                raise ValueError(f"Invalid SUPABASE_KEY format: Key is too short or empty")
            
            _supabase_client = create_client(url, key)
        except Exception as e:
            url, key = _get_supabase_credentials()
            error_msg = f"Failed to create Supabase client: {str(e)}\n"
            error_msg += f"URL: {url}\n"
            error_msg += f"Key starts with: {key[:20]}...\n"
            error_msg += "\nPlease verify:\n"
            error_msg += "1. Your Supabase project is active\n"
            error_msg += "2. You're using the 'anon public' key (JWT format, starts with 'eyJ...')\n"
            error_msg += "3. DO NOT use the 'publishable' key (sb_publishable_...) - Python SDK doesn't support it yet\n"
            error_msg += "4. The key hasn't been regenerated\n"
            error_msg += "5. Go to Supabase Dashboard > Settings > API > copy the 'anon public' key"
            raise ValueError(error_msg) from e
    
    return _supabase_client


def save_document(
    user_id: str,
    filename: str,
    file_content: str,
    property_name: str = None,
    document_type: str = None,
    vendor: str = None,
    amount: float = None,
    document_date: datetime = None,
    chunks: List[Dict] = None
) -> Dict:
    """
    Saves a document to the database with metadata and chunks (chunked RAG system)
    
    Args:
        user_id: The user who owns this document
        filename: Name of the file
        file_content: The actual text content of the document
        property_name: Which property this document is about
        document_type: Type (invoice, bill, lease, etc.)
        vendor: Vendor name (if applicable)
        amount: Dollar amount (if applicable)
        document_date: Date on the document
        chunks: List of chunk dictionaries with text and embeddings
    
    Returns:
        The saved document data or None on error
    """
    # Import here to avoid circular dependency
    from auth import get_authenticated_client
    supabase = get_authenticated_client()
    
    try:
        # Step 1: Save the document (without embedding - chunks have embeddings)
        document_data = {
            "user_id": user_id,
            "filename": filename,
            "file_content": file_content,
            "property_name": property_name,
            "document_type": document_type,
            "vendor": vendor,
            "amount": amount,
            "document_date": document_date.isoformat() if document_date else None,
            "embedding": None  # No longer storing document-level embedding
        }
        
        # Insert document
        doc_response = supabase.table("documents").insert(document_data).execute()
        
        if not doc_response.data:
            print(f"No data returned from document insert")
            return None
        
        document_id = doc_response.data[0]["id"]
        
        # Step 2: Save chunks if provided (optional - won't break if table doesn't exist)
        if chunks and len(chunks) > 0:
            try:
                chunk_records = []
                for chunk in chunks:
                    chunk_records.append({
                        "document_id": document_id,
                        "user_id": user_id,
                        "chunk_index": chunk.get("chunk_index", 0),
                        "chunk_text": chunk.get("text", ""),
                        "embedding": chunk.get("embedding"),
                        "start_char": chunk.get("start_char", 0)
                    })
                
                # Insert chunks in batch
                if chunk_records:
                    chunks_response = supabase.table("document_chunks").insert(chunk_records).execute()
                    print(f"Saved {len(chunk_records)} chunks for document {document_id}")
            except Exception as chunk_error:
                # Chunks table might not exist yet - that's okay, document is still saved
                print(f"Warning: Could not save chunks (table might not exist): {chunk_error}")
                print("Document saved successfully, but chunks were not saved.")
                print("Run the ADD_CHUNKS_TABLE.sql in Supabase to enable chunking.")
        
        return doc_response.data[0]
            
    except Exception as e:
        print(f"Error saving document: {e}")
        import traceback
        traceback.print_exc()
        return None


def get_user_documents(user_id: str) -> List[Dict]:
    """
    Gets all documents for a specific user
    
    Args:
        user_id: The user ID to fetch documents for
    
    Returns:
        List of all documents belonging to this user
    """
    from auth import get_authenticated_client
    supabase = get_authenticated_client()
    
    try:
        response = supabase.table("documents")\
            .select("*")\
            .eq("user_id", user_id)\
            .order("uploaded_at", desc=True)\
            .execute()
        
        return response.data if response.data else []
    except Exception as e:
        print(f"Error getting user documents: {e}")
        return []


def search_documents_by_property(user_id: str, property_name: str) -> List[Dict]:
    """
    Finds all documents for a specific property
    
    Args:
        user_id: The user ID
        property_name: Name of the property to search for
    
    Returns:
        List of documents for that property
    """
    from auth import get_authenticated_client
    supabase = get_authenticated_client()
    
    try:
        response = supabase.table("documents")\
            .select("*")\
            .eq("user_id", user_id)\
            .ilike("property_name", f"%{property_name}%")\
            .execute()
        
        return response.data if response.data else []
    except Exception as e:
        print(f"Error searching documents by property: {e}")
        return []


def search_documents_semantic(
    query_embedding: List[float],
    match_threshold: float = 0.3,
    match_count: int = 10
) -> List[Dict]:
    """
    Performs semantic search using vector similarity on CHUNKS
    Uses the match_chunks SQL function with RLS (filters by auth.uid() automatically)
    
    Args:
        query_embedding: Vector representation of the user's question
        match_threshold: Minimum similarity score (0.0 to 1.0)
        match_count: How many chunks to return
    
    Returns:
        List of most relevant chunks with similarity scores and document metadata
    """
    from auth import get_authenticated_client
    supabase = get_authenticated_client()
    
    try:
        # match_chunks function uses auth.uid() automatically for security
        response = supabase.rpc(
            "match_chunks",
            {
                "query_embedding": query_embedding,
                "match_threshold": match_threshold,
                "match_count": match_count
            }
        ).execute()
        
        # Format response to match expected structure
        results = []
        if response.data:
            for chunk in response.data:
                results.append({
                    "content": chunk.get("chunk_text", ""),
                    "similarity": chunk.get("similarity", 0.0),
                    "metadata": chunk.get("metadata", {}),
                    "chunk_index": chunk.get("chunk_index", 0),
                    "document_id": chunk.get("document_id")
                })
        
        return results
    except Exception as e:
        print(f"Error in semantic search: {e}")
        import traceback
        traceback.print_exc()
        return []


def delete_document(document_id: str, user_id: str) -> bool:
    """
    Deletes a document (with user verification for security)
    
    Args:
        document_id: ID of document to delete
        user_id: User ID (must own the document)
    
    Returns:
        True if deleted successfully
    """
    from auth import get_authenticated_client
    supabase = get_authenticated_client()
    
    try:
        response = supabase.table("documents")\
            .delete()\
            .eq("id", document_id)\
            .eq("user_id", user_id)\
            .execute()
        
        return len(response.data) > 0 if response.data else False
    except Exception as e:
        print(f"Error deleting document: {e}")
        return False


def get_document_stats(user_id: str) -> Dict:
    """
    Gets statistics about user's documents
    (Total count, properties, document types, etc.)
    
    Args:
        user_id: The user ID
    
    Returns:
        Dictionary with statistics
    """
    docs = get_user_documents(user_id)
    
    if not docs:
        return {
            "total_documents": 0,
            "properties": [],
            "document_types": [],
            "total_amount": 0.0
        }
    
    # Calculate stats
    properties = list(set([d.get("property_name") for d in docs if d.get("property_name")]))
    doc_types = list(set([d.get("document_type") for d in docs if d.get("document_type")]))
    total_amount = sum([float(d.get("amount", 0) or 0) for d in docs])
    
    return {
        "total_documents": len(docs),
        "properties": properties,
        "document_types": doc_types,
        "total_amount": round(total_amount, 2)
    }
