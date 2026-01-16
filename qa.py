"""
qa.py
Question-answering system using RAG (Retrieval Augmented Generation)
WITH improved context handling and "I don't know" logic
"""

import os
from openai import OpenAI
from dotenv import load_dotenv
from typing import List, Dict
from database import search_documents_semantic
from ingest import create_embedding

load_dotenv()

# Lazy initialization - only create client when needed
_client = None

def get_openai_client():
    """Get OpenAI client (lazy initialization)"""
    global _client
    if _client is None:
        _client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    return _client


def answer_question(question: str, user_id: str) -> Dict:
    """
    Answers a question using RAG:
    1. Convert question to embedding
    2. Find relevant documents
    3. Generate answer using only those documents
    4. Return answer with sources
    
    Args:
        question: User's question
        user_id: Current user ID (for display purposes, RLS handles security)
    
    Returns:
        Dictionary with answer and source documents
    """
    
    # Step 1: Enhance question for better semantic matching
    # Add context keywords that might help match property documents
    enhanced_question = question
    if "bill" in question.lower():
        enhanced_question += " utility invoice payment amount cost"
    if "oak" in question.lower() or "street" in question.lower() or "property" in question.lower():
        enhanced_question += " property address location"
    
    print(f"Creating embedding for question: {question}")
    query_embedding = create_embedding(enhanced_question)
    
    if not query_embedding:
        return {
            "answer": "Sorry, I encountered an error processing your question.",
            "sources": [],
            "confidence": "error"
        }
    
    # Step 2: Search for relevant documents (lower threshold for better recall)
    print("Searching for relevant documents...")
    relevant_docs = search_documents_semantic(
        query_embedding=query_embedding,
        match_threshold=0.3,  # Lower threshold (30%) to catch more documents
        match_count=10  # Get more candidates to filter
    )
    
    print(f"Found {len(relevant_docs)} relevant documents")
    
    # Step 3: Check if we found any relevant documents
    if not relevant_docs or len(relevant_docs) == 0:
        return {
            "answer": "I don't know based on the available documents. I couldn't find any relevant information to answer your question.",
            "sources": [],
            "confidence": "none"
        }
    
    # Filter to top 5 most relevant and check if top similarity is reasonable
    relevant_docs = relevant_docs[:5]
    top_similarity = relevant_docs[0].get("similarity", 0) if relevant_docs else 0
    
    # Only reject if similarity is very low (below 0.4)
    if top_similarity < 0.4:
        return {
            "answer": "I don't know based on the available documents. The information I found doesn't seem relevant enough to provide a confident answer.",
            "sources": [],
            "confidence": "low"
        }
    
    # Step 4: Build context from relevant CHUNKS (IMPROVED)
    context = ""
    seen_documents = set()  # Track which documents we've seen
    
    for i, chunk in enumerate(relevant_docs, 1):
        metadata = chunk.get("metadata", {})
        chunk_text = chunk.get("content", "")
        similarity = chunk.get("similarity", 0)
        document_id = chunk.get("document_id")
        chunk_index = chunk.get("chunk_index", 0)
        
        # Group chunks by document for better context
        doc_key = f"{metadata.get('filename', 'Unknown')}_{document_id}"
        is_new_doc = doc_key not in seen_documents
        seen_documents.add(doc_key)
        
        if is_new_doc:
            context += f"\n--- Document: {metadata.get('filename', 'Unknown')} ---\n"
            context += f"Property: {metadata.get('property_name', 'Unknown')}\n"
            context += f"Type: {metadata.get('document_type', 'Unknown')}\n"
            if metadata.get('vendor'):
                context += f"Vendor: {metadata.get('vendor')}\n"
            if metadata.get('amount'):
                context += f"Amount: ${metadata.get('amount')}\n"
            if metadata.get('document_date'):
                context += f"Date: {metadata.get('document_date')}\n"
            context += f"Relevant sections:\n"
        
        # Add chunk with its relevance score
        context += f"  [Section {chunk_index + 1}, Relevance: {similarity:.1%}]\n"
        context += f"  {chunk_text}\n"
    
    # Step 5: Create the prompt for GPT
    system_prompt = """You are PropertyAI, a helpful assistant that answers questions about property documents.

CRITICAL RULES:
1. Answer ONLY using information from the provided documents
2. Look carefully at ALL documents - even if similarity is lower, they might still contain the answer
3. Pay special attention to:
   - Property names (e.g., "Oak Street", "Maple Avenue")
   - Document types (e.g., "electric bill", "utility bill", "invoice")
   - Amounts and dates
   - Vendor names
4. If the question asks about a specific property, look for documents matching that property name
5. If you find the answer, provide it clearly with the exact amount and source
6. If the documents don't contain enough information, say: "I don't know based on the available documents."
7. Never make up information or assume anything

When citing numbers (amounts, dates), always mention which document/property they came from."""

    user_prompt = f"""Question: {question}

Available documents:
{context}

Instructions:
- Read through ALL documents carefully
- If the question mentions a specific property name (like "Oak Street"), look for documents with that property name
- If the question asks about a bill type (like "electric bill"), look for documents with that document type
- Extract the exact amount, date, and other details from the matching documents
- Provide a clear, direct answer with the specific information found

Please answer the question using ONLY the information above. If the answer is not clearly stated in the documents, say you don't know."""

    # Step 6: Generate answer using GPT
    print("Generating answer...")
    try:
        client = get_openai_client()
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.2  # Lower temperature = more focused answers
        )
        
        answer = response.choices[0].message.content
        
        # Determine confidence based on similarity scores
        avg_similarity = sum(d.get("similarity", 0) for d in relevant_docs) / len(relevant_docs)
        
        if avg_similarity > 0.75:
            confidence = "high"
        elif avg_similarity > 0.6:
            confidence = "medium"
        else:
            confidence = "low"
        
        # Format sources for display (chunks grouped by document)
        sources = []
        seen_docs = {}
        for chunk in relevant_docs:
            metadata = chunk.get("metadata", {})
            document_id = chunk.get("document_id")
            chunk_index = chunk.get("chunk_index", 0)
            similarity = chunk.get("similarity", 0)
            
            # Group chunks by document
            if document_id not in seen_docs:
                seen_docs[document_id] = {
                    "filename": metadata.get("filename", "Unknown"),
                    "property": metadata.get("property_name"),
                    "type": metadata.get("document_type"),
                    "vendor": metadata.get("vendor"),
                    "amount": metadata.get("amount"),
                    "similarity": similarity,  # Use highest similarity chunk
                    "chunks": []
                }
            
            # Track which chunks from this document were used
            seen_docs[document_id]["chunks"].append(chunk_index)
            # Update similarity if this chunk is more relevant
            if similarity > seen_docs[document_id]["similarity"]:
                seen_docs[document_id]["similarity"] = similarity
        
        # Convert to list format
        for doc_data in seen_docs.values():
            chunk_info = f" (sections: {', '.join(map(str, sorted(set(doc_data['chunks']))))})" if doc_data["chunks"] else ""
            sources.append({
                "filename": doc_data["filename"] + chunk_info,
                "property": doc_data["property"],
                "type": doc_data["type"],
                "vendor": doc_data["vendor"],
                "amount": doc_data["amount"],
                "similarity": doc_data["similarity"]
            })
        
        return {
            "answer": answer,
            "sources": sources,
            "confidence": confidence
        }
        
    except Exception as e:
        print(f"Error generating answer: {e}")
        return {
            "answer": f"Sorry, I encountered an error: {str(e)}",
            "sources": [],
            "confidence": "error"
        }
