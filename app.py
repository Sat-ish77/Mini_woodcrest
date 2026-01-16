"""
app.py
Main Streamlit application - PropertyAI Demo
WITH proper session management and error handling
"""

import streamlit as st
import os
from pathlib import Path
import auth
import database
import ingest
import qa

# Page config
st.set_page_config(
    page_title="PropertyAI - Document Intelligence",
    page_icon="🏢",
    layout="wide"
)


def init_session_state():
    """Initialize session state variables"""
    if 'user' not in st.session_state:
        st.session_state.user = None
    if 'user_id' not in st.session_state:
        st.session_state.user_id = None
    if 'access_token' not in st.session_state:
        st.session_state.access_token = None
    if 'refresh_token' not in st.session_state:
        st.session_state.refresh_token = None


def login_page():
    """Login/Signup page"""
    st.title("🏢 PropertyAI")
    st.subheader("Property Document Intelligence System")
    
    tab1, tab2 = st.tabs(["Login", "Sign Up"])
    
    with tab1:
        st.write("### Login to your account")
        email = st.text_input("Email", key="login_email")
        password = st.text_input("Password", type="password", key="login_password")
        
        if st.button("Login", type="primary"):
            if email and password:
                with st.spinner("Logging in..."):
                    result = auth.sign_in(email, password)
                    if result["success"]:
                        # Get user info and store in session
                        user = auth.get_current_user()
                        if user:
                            st.session_state.user = user
                            st.session_state.user_id = user.id
                            st.success("✅ Logged in successfully!")
                            st.rerun()
                        else:
                            st.error("Could not retrieve user information. Please try again.")
                    else:
                        error_msg = result.get('error', 'Unknown error')
                        st.error(f"❌ Login failed: {error_msg}")
                        
                        # Helpful hint for common errors
                        if "Invalid login credentials" in error_msg:
                            st.info("💡 Make sure your email and password are correct. If you just signed up, check your email for verification.")
            else:
                st.warning("⚠️ Please enter both email and password")
    
    with tab2:
        st.write("### Create a new account")
        new_email = st.text_input("Email", key="signup_email")
        new_password = st.text_input("Password", type="password", key="signup_password")
        confirm_password = st.text_input("Confirm Password", type="password", key="confirm_password")
        
        if st.button("Sign Up", type="primary"):
            if new_email and new_password and confirm_password:
                if new_password != confirm_password:
                    st.error("❌ Passwords don't match!")
                elif len(new_password) < 6:
                    st.error("❌ Password must be at least 6 characters")
                else:
                    with st.spinner("Creating account..."):
                        result = auth.sign_up(new_email, new_password)
                        if result["success"]:
                            st.success("✅ Account created! Please check your email to verify (or login directly if email verification is disabled).")
                        else:
                            error_msg = result.get('error', 'Unknown error')
                            st.error(f"❌ Signup failed: {error_msg}")
                            
                            if "already registered" in error_msg.lower():
                                st.info("💡 This email is already registered. Try logging in instead.")
            else:
                st.warning("⚠️ Please fill in all fields")


def main_app():
    """Main application after login"""
    
    # Sidebar
    with st.sidebar:
        st.write(f"### Welcome! 👋")
        user_email = st.session_state.user.email if st.session_state.user else "Unknown"
        st.write(f"**User:** {user_email}")
        
        if st.button("Logout", type="secondary"):
            auth.sign_out()
            st.session_state.user = None
            st.session_state.user_id = None
            st.success("Logged out successfully!")
            st.rerun()
        
        st.divider()
        
        # Get user stats
        try:
            stats = database.get_document_stats(st.session_state.user_id)
            st.metric("📄 Total Documents", stats["total_documents"])
            st.metric("💰 Total Amount", f"${stats['total_amount']:,.2f}")
            
            if stats["properties"]:
                st.write("**🏘️ Properties:**")
                for prop in stats["properties"]:
                    st.write(f"- {prop}")
        except Exception as e:
            st.error(f"Error loading stats: {e}")
    
    # Main content
    st.title("🏢 PropertyAI - Document Intelligence")
    
    # Tabs for different features
    tab1, tab2, tab3 = st.tabs(["📤 Upload Documents", "❓ Ask Questions", "📄 View Documents"])
    
    with tab1:
        upload_documents_section()
    
    with tab2:
        ask_questions_section()
    
    with tab3:
        view_documents_section()


def upload_documents_section():
    """Document upload interface"""
    st.header("Upload Property Documents")
    st.write("Upload invoices, bills, leases, or any property-related documents.")
    
    uploaded_files = st.file_uploader(
        "Choose files (you can select multiple)",
        type=["txt", "pdf"],
        accept_multiple_files=True,
        help="Supported formats: TXT, PDF. You can upload multiple files at once."
    )
    
    if uploaded_files:
        # Check for duplicates
        try:
            existing_docs = database.get_user_documents(st.session_state.user_id)
            existing_filenames = {doc.get('filename', '').lower() for doc in existing_docs}
            
            new_files = []
            duplicate_files = []
            
            for uploaded_file in uploaded_files:
                if uploaded_file.name.lower() in existing_filenames:
                    duplicate_files.append(uploaded_file.name)
                else:
                    new_files.append(uploaded_file)
            
            if duplicate_files:
                st.warning(f"⚠️ These files already exist and will be skipped: {', '.join(duplicate_files)}")
            
            if new_files:
                st.info(f"📤 Ready to process {len(new_files)} new file(s)")
                
                if st.button("Process All Files", type="primary"):
                    success_count = 0
                    error_count = 0
                    
                    for uploaded_file in new_files:
                        with st.spinner(f"Processing {uploaded_file.name}..."):
                            # Save uploaded file temporarily
                            temp_dir = Path("temp_uploads")
                            temp_dir.mkdir(exist_ok=True)
                            temp_path = temp_dir / uploaded_file.name
                            
                            with open(temp_path, "wb") as f:
                                f.write(uploaded_file.getbuffer())
                            
                            # Process the document
                            result = ingest.process_document(str(temp_path), uploaded_file.name)
                            
                            if "error" in result:
                                st.error(f"❌ Error processing {uploaded_file.name}: {result['error']}")
                                error_count += 1
                            elif not result.get("property_name") and not result.get("document_type") and not result.get("vendor"):
                                # Metadata extraction likely failed - show warning
                                st.warning(f"⚠️ {uploaded_file.name} uploaded but metadata extraction may have failed. Check logs for details.")
                                # Still save it - might be a parsing issue
                            else:
                                # Save to database
                                try:
                                    saved_doc = database.save_document(
                                        user_id=st.session_state.user_id,
                                        filename=result["filename"],
                                        file_content=result["file_content"],
                                        property_name=result["property_name"],
                                        document_type=result["document_type"],
                                        vendor=result["vendor"],
                                        amount=result["amount"],
                                        document_date=result["document_date"],
                                        chunks=result.get("chunks", [])  # Pass chunks instead of embedding
                                    )
                                    
                                    if saved_doc:
                                        success_count += 1
                                        st.success(f"✅ {uploaded_file.name} processed and saved!")
                                    else:
                                        error_count += 1
                                        st.error(f"❌ Failed to save {uploaded_file.name}")
                                except Exception as e:
                                    error_count += 1
                                    st.error(f"❌ Error saving {uploaded_file.name}: {str(e)}")
                            
                            # Clean up temp file
                            try:
                                temp_path.unlink()
                            except:
                                pass
                    
                    # Summary
                    st.success(f"✅ Successfully processed {success_count} file(s)")
                    if error_count > 0:
                        st.warning(f"⚠️ {error_count} file(s) had errors")
                    st.rerun()
        except Exception as e:
            st.error(f"Error checking for duplicates: {str(e)}")


def ask_questions_section():
    """Question answering interface"""
    st.header("Ask Questions About Your Documents")
    st.write("Ask anything about your property documents. I'll search and provide accurate answers.")
    
    # Example questions
    with st.expander("💡 Example Questions"):
        st.write("""
        - What was the total spent on HVAC services?
        - Which property had utility bills over $400?
        - When does the lease for 123 Oak Street expire?
        - Show me all invoices from Superior HVAC
        - What maintenance was done in January 2024?
        - How much is the monthly rent for Oak Street?
        """)
    
    question = st.text_input(
        "Your question:",
        placeholder="e.g., What was the total amount paid to vendors last month?"
    )
    
    if st.button("Get Answer", type="primary") and question:
        with st.spinner("🔍 Searching documents and generating answer..."):
            result = qa.answer_question(question, st.session_state.user_id)
            
            # Display answer
            st.write("### Answer:")
            
            # Color code based on confidence
            if result["confidence"] == "high":
                st.success(result["answer"])
            elif result["confidence"] == "medium":
                st.info(result["answer"])
            elif result["confidence"] == "low" or result["confidence"] == "none":
                st.warning(result["answer"])
            else:
                st.error(result["answer"])
            
            # Show sources
            if result["sources"]:
                st.write("### 📚 Sources:")
                for i, source in enumerate(result["sources"], 1):
                    with st.expander(f"📄 Document {i}: {source['filename']} (Relevance: {source['similarity']:.1%})"):
                        st.write(f"**Property:** {source['property'] or 'N/A'}")
                        st.write(f"**Type:** {source['type'] or 'N/A'}")
                        if source.get('vendor'):
                            st.write(f"**Vendor:** {source['vendor']}")
                        if source.get('amount'):
                            st.write(f"**Amount:** ${source['amount']:.2f}")


def view_documents_section():
    """View all uploaded documents"""
    st.header("Your Documents")
    
    try:
        docs = database.get_user_documents(st.session_state.user_id)
    except Exception as e:
        st.error(f"Error loading documents: {e}")
        return
    
    if not docs:
        st.info("📭 No documents uploaded yet. Go to the Upload tab to add documents.")
        return
    
    # Filters
    col1, col2 = st.columns(2)
    with col1:
        properties = list(set([d.get("property_name") for d in docs if d.get("property_name")]))
        property_filter = st.selectbox(
            "Filter by property:",
            ["All"] + properties
        )
    with col2:
        types = list(set([d.get("document_type") for d in docs if d.get("document_type")]))
        type_filter = st.selectbox(
            "Filter by type:",
            ["All"] + types
        )
    
    # Apply filters
    filtered_docs = docs
    if property_filter != "All":
        filtered_docs = [d for d in filtered_docs if d.get("property_name") == property_filter]
    if type_filter != "All":
        filtered_docs = [d for d in filtered_docs if d.get("document_type") == type_filter]
    
    st.write(f"Showing **{len(filtered_docs)}** documents")
    
    # Display documents
    for doc in filtered_docs:
        doc_id = doc.get('id')
        filename = doc.get('filename', 'Unknown')
        
        with st.expander(f"📄 {filename} - {doc.get('property_name', 'Unknown Property')}"):
            col1, col2 = st.columns([3, 1])
            with col1:
                st.write(f"**Type:** {doc.get('document_type', 'N/A')}")
                st.write(f"**Vendor:** {doc.get('vendor', 'N/A')}")
                amount = doc.get('amount', 0)
                st.write(f"**Amount:** ${amount:.2f}" if amount else "**Amount:** N/A")
                date_str = doc.get('document_date', 'N/A')
                st.write(f"**Date:** {date_str}")
                uploaded = (doc.get('uploaded_at') or "")[:10]
                st.write(f"**Uploaded:** {uploaded if uploaded else 'N/A'}")
            
            with col2:
                if st.button("🗑️ Delete", key=f"delete_{doc_id}", type="secondary"):
                    if database.delete_document(doc_id, st.session_state.user_id):
                        st.success(f"✅ Deleted {filename}")
                        st.rerun()
                    else:
                        st.error("❌ Failed to delete document")
            
            st.write("**Content Preview:**")
            content = doc.get('file_content', '')
            st.text(content[:500] + ("..." if len(content) > 500 else ""))


def main():
    """Main function"""
    init_session_state()
    
    # Check if user is logged in
    if not auth.is_authenticated():
        login_page()
    else:
        # Try to restore user info if not in session state
        if st.session_state.user is None:
            user = auth.get_current_user()
            if user:
                st.session_state.user = user
                st.session_state.user_id = user.id
        
        main_app()


if __name__ == "__main__":
    main()
