"""
ingest.py
Processes documents: extracts text, generates metadata, creates embeddings
WITH safety fixes for PDF extraction, JSON parsing, and metadata normalization
"""

import os
from openai import OpenAI
from dotenv import load_dotenv
from typing import Dict, Optional, List, Tuple
import json
from datetime import datetime
import re
# PyPDF2 imported lazily - only when processing PDFs

load_dotenv()

# Lazy initialization - only create client when needed
_client = None

def get_openai_client():
    """Get OpenAI client (lazy initialization)"""
    global _client
    if _client is None:
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY not found in environment variables. Check your Streamlit Cloud secrets.")
        _client = OpenAI(api_key=api_key)
    return _client


def extract_text_from_file(file_path: str) -> str:
    """
    Extracts text from a file (TXT or PDF)
    
    Args:
        file_path: Path to the file
    
    Returns:
        Extracted text content
    """
    # Check file extension
    if file_path.lower().endswith('.pdf'):
        return extract_text_from_pdf(file_path)
    elif file_path.lower().endswith('.txt'):
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return f.read()
        except Exception as e:
            print(f"Error reading TXT file: {e}")
            return ""
    else:
        # Try reading as text
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return f.read()
        except:
            return ""


def extract_text_from_pdf(file_path: str) -> str:
    """
    Extracts text from a PDF file with safety fixes
    
    Args:
        file_path: Path to PDF file
    
    Returns:
        Extracted text
    """
    try:
        # Lazy import PyPDF2 - only load when actually processing PDFs
        import PyPDF2
        with open(file_path, 'rb') as f:
            pdf_reader = PyPDF2.PdfReader(f)
            text = ""
            for page in pdf_reader.pages:
                # FIX: Handle None from extract_text()
                page_text = page.extract_text()
                text += (page_text or "") + "\n"
            
            # Check if this might be a scanned PDF
            if len(text.strip()) < 50:
                return "ERROR: This appears to be a scanned PDF. OCR required."
            
            return text
    except Exception as e:
        print(f"Error extracting PDF: {e}")
        return ""


def normalize_document_type(doc_type: str) -> str:
    """
    Normalizes document type to consistent format
    
    Args:
        doc_type: Raw document type from AI
    
    Returns:
        Normalized document type
    """
    if not doc_type:
        return None
    
    # Convert to lowercase and replace spaces with underscores
    normalized = doc_type.lower().strip().replace(" ", "_")
    
    # Map common variants
    type_map = {
        "utility_bill": "utility_bill",
        "electric_bill": "utility_bill",
        "water_bill": "utility_bill",
        "gas_bill": "utility_bill",
        "invoice": "invoice",
        "bill": "invoice",
        "lease": "lease",
        "lease_agreement": "lease",
        "rental_agreement": "lease",
        "maintenance_report": "maintenance_report",
        "inspection_report": "inspection_report",
        "property_inspection": "inspection_report",
        "tax_document": "tax_document",
        "insurance": "insurance",
        "insurance_policy": "insurance"
    }
    
    return type_map.get(normalized, normalized)


def clean_amount(amount_value) -> Optional[float]:
    """
    Cleans and converts amount to float
    
    Args:
        amount_value: Raw amount (could be string, float, or None)
    
    Returns:
        Clean float or None
    """
    if amount_value is None or amount_value == "null":
        return None
    
    if isinstance(amount_value, (int, float)):
        return float(amount_value)
    
    if isinstance(amount_value, str):
        # Remove dollar signs, commas
        cleaned = amount_value.replace("$", "").replace(",", "").strip()
        try:
            return float(cleaned)
        except:
            return None
    
    return None


def extract_metadata_with_ai(text: str, filename: str) -> Dict:
    """
    Uses OpenAI to extract structured metadata from document text
    WITH better context and robust JSON parsing
    
    Args:
        text: The document text
        filename: Name of the file
    
    Returns:
        Dictionary with extracted metadata
    """
    # FIX: Use smarter excerpt - first 2000 + last 1000 chars
    text_length = len(text)
    if text_length > 3000:
        excerpt = text[:2000] + "\n...\n" + text[-1000:]
    else:
        excerpt = text
    
    prompt = f"""
You are a document analysis AI. Extract structured information from this property document.

Document filename: {filename}
Document text:
{excerpt}

Extract the following information (use null if not found):
1. property_name: The property address or name (e.g., "123 Oak Street")
2. document_type: Type of document (utility_bill, invoice, lease, maintenance_report, inspection_report, tax_document, insurance)
3. vendor: Vendor or company name (if applicable)
4. amount: Dollar amount as a NUMBER only, no $ or commas (e.g., 1234.56)
5. document_date: Date on the document in YYYY-MM-DD format

Respond ONLY with valid JSON in this exact format (no markdown, no explanations):
{{
    "property_name": "string or null",
    "document_type": "string or null",
    "vendor": "string or null",
    "amount": number or null,
    "document_date": "YYYY-MM-DD or null"
}}
"""
    
    try:
        # Check if API key is available
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY not found. Check Streamlit Cloud secrets configuration.")
        
        client = get_openai_client()
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a precise document metadata extractor. Always respond with valid JSON only. No markdown formatting."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.1
        )
        
        # Parse the JSON response
        metadata_text = response.choices[0].message.content.strip()
        
        # FIX: Robust markdown removal
        if "```json" in metadata_text:
            metadata_text = metadata_text.split("```json")[1].split("```")[0].strip()
        elif "```" in metadata_text:
            # Find content between first ``` and last ```
            parts = metadata_text.split("```")
            if len(parts) >= 3:
                metadata_text = parts[1].strip()
        
        # Try to parse JSON
        metadata = json.loads(metadata_text)
        
        # FIX: Normalize document_type
        if metadata.get("document_type"):
            metadata["document_type"] = normalize_document_type(metadata["document_type"])
        
        # FIX: Clean amount
        if metadata.get("amount"):
            metadata["amount"] = clean_amount(metadata["amount"])
        
        # FIX: Convert date string to datetime object
        if metadata.get("document_date") and metadata["document_date"] != "null":
            try:
                metadata["document_date"] = datetime.strptime(metadata["document_date"], "%Y-%m-%d")
            except:
                metadata["document_date"] = None
        else:
            metadata["document_date"] = None
        
        return metadata
        
    except json.JSONDecodeError as e:
        print(f"JSON parsing error: {e}")
        print(f"Raw response: {metadata_text}")
        # Return empty metadata on JSON error
        return {
            "property_name": None,
            "document_type": None,
            "vendor": None,
            "amount": None,
            "document_date": None
        }
    except Exception as e:
        print(f"Error extracting metadata: {e}")
        import traceback
        traceback.print_exc()  # Print full traceback for debugging
        # Return empty metadata on error
        return {
            "property_name": None,
            "document_type": None,
            "vendor": None,
            "amount": None,
            "document_date": None
        }


def chunk_text(text: str, chunk_size: int = 500, overlap: int = 50) -> List[Dict[str, any]]:
    """
    Splits text into overlapping chunks for better semantic search
    
    Args:
        text: Full document text
        chunk_size: Target size in characters (roughly 300-500 tokens)
        overlap: Number of characters to overlap between chunks
    
    Returns:
        List of chunk dictionaries with text and metadata
    """
    if not text or len(text.strip()) == 0:
        return []
    
    # Split by paragraphs first (better semantic boundaries)
    paragraphs = text.split('\n\n')
    
    chunks = []
    current_chunk = ""
    chunk_index = 0
    
    for para in paragraphs:
        para = para.strip()
        if not para:
            continue
        
        # If adding this paragraph would exceed chunk size, save current chunk
        if current_chunk and len(current_chunk) + len(para) + 2 > chunk_size:
            chunks.append({
                "text": current_chunk.strip(),
                "chunk_index": chunk_index,
                "start_char": len(chunks) * (chunk_size - overlap) if chunks else 0
            })
            chunk_index += 1
            
            # Start new chunk with overlap (last part of previous chunk)
            if overlap > 0 and current_chunk:
                overlap_text = current_chunk[-overlap:].strip()
                current_chunk = overlap_text + "\n\n" + para
            else:
                current_chunk = para
        else:
            # Add paragraph to current chunk
            if current_chunk:
                current_chunk += "\n\n" + para
            else:
                current_chunk = para
    
    # Add the last chunk
    if current_chunk.strip():
        chunks.append({
            "text": current_chunk.strip(),
            "chunk_index": chunk_index,
            "start_char": len(chunks) * (chunk_size - overlap) if chunks else 0
        })
    
    # If we have very long paragraphs, split them further
    final_chunks = []
    for chunk in chunks:
        if len(chunk["text"]) > chunk_size * 1.5:
            # Split long chunks by sentences
            sentences = re.split(r'(?<=[.!?])\s+', chunk["text"])
            temp_chunk = ""
            temp_index = chunk["chunk_index"]
            
            for sentence in sentences:
                if len(temp_chunk) + len(sentence) + 1 > chunk_size:
                    if temp_chunk:
                        final_chunks.append({
                            "text": temp_chunk.strip(),
                            "chunk_index": temp_index,
                            "start_char": chunk["start_char"]
                        })
                        temp_index += 1
                    temp_chunk = sentence
                else:
                    temp_chunk += " " + sentence if temp_chunk else sentence
            
            if temp_chunk.strip():
                final_chunks.append({
                    "text": temp_chunk.strip(),
                    "chunk_index": temp_index,
                    "start_char": chunk["start_char"]
                })
        else:
            final_chunks.append(chunk)
    
    return final_chunks


def create_embedding(text: str) -> Optional[List[float]]:
    """
    Creates a vector embedding of the text using OpenAI
    This converts text into 1536 numbers that represent its meaning
    
    Args:
        text: Text to embed
    
    Returns:
        List of 1536 floats (the embedding vector) or None on error
    """
    try:
        # Truncate text if too long (OpenAI has token limits)
        max_chars = 8000
        if len(text) > max_chars:
            text = text[:max_chars]
        
        client = get_openai_client()
        response = client.embeddings.create(
            model="text-embedding-3-small",
            input=text
        )
        
        embedding = response.data[0].embedding
        
        # FIX: Verify dimension
        if len(embedding) != 1536:
            print(f"WARNING: Embedding dimension is {len(embedding)}, expected 1536")
            return None
        
        return embedding
        
    except Exception as e:
        print(f"Error creating embedding: {e}")
        return None


def process_document(file_path: str, filename: str) -> Dict:
    """
    Full pipeline: Extract text → Get metadata → Chunk text → Create embeddings for chunks
    
    Args:
        file_path: Path to the document file
        filename: Name of the file
    
    Returns:
        Dictionary with all extracted data, chunks, and chunk embeddings
    """
    print(f"Processing document: {filename}")
    
    # Step 1: Extract text
    text = extract_text_from_file(file_path)
    if not text:
        return {"error": "Could not extract text from file"}
    
    if text.startswith("ERROR:"):
        return {"error": text}
    
    print(f"  [OK] Extracted {len(text)} characters")
    
    # Step 2: Extract metadata using AI
    metadata = extract_metadata_with_ai(text, filename)
    if metadata.get("property_name") or metadata.get("document_type") or metadata.get("vendor"):
        print(f"  [OK] Extracted metadata: {metadata.get('document_type', 'unknown')}")
    else:
        print(f"  [WARNING] Metadata extraction returned empty values - check OpenAI API key and logs")
    
    # Step 3: Chunk the text
    chunks = chunk_text(text, chunk_size=500, overlap=50)
    print(f"  [OK] Created {len(chunks)} chunks")
    
    # Step 4: Create embeddings for each chunk
    chunk_embeddings = []
    for i, chunk in enumerate(chunks):
        embedding = create_embedding(chunk["text"])
        if embedding:
            chunk_embeddings.append({
                "chunk_index": chunk["chunk_index"],
                "text": chunk["text"],
                "embedding": embedding,
                "start_char": chunk.get("start_char", 0)
            })
            print(f"  [OK] Created embedding for chunk {i+1}/{len(chunks)}")
        else:
            print(f"  [WARNING] Failed to create embedding for chunk {i+1}")
    
    if not chunk_embeddings:
        print(f"  [WARNING] No embeddings created, document will not be searchable")
    
    # Return everything
    return {
        "filename": filename,
        "file_content": text,
        "property_name": metadata.get("property_name"),
        "document_type": metadata.get("document_type"),
        "vendor": metadata.get("vendor"),
        "amount": metadata.get("amount"),
        "document_date": metadata.get("document_date"),
        "chunks": chunk_embeddings  # List of chunks with embeddings
    }
