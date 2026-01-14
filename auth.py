"""
auth.py
Handles user authentication with Supabase - with proper session management
"""

import streamlit as st
from database import get_supabase_client
from typing import Optional, Dict

def get_authenticated_client():
    """
    Returns a Supabase client with the current user's session attached
    This ensures RLS policies work correctly
    """
    supabase = get_supabase_client()
    
    # If we have a stored session, restore it
    if 'access_token' in st.session_state and st.session_state.access_token:
        try:
            supabase.auth.set_session(
                st.session_state.access_token,
                st.session_state.refresh_token
            )
        except:
            # Session might be expired, will handle in UI
            pass
    
    return supabase


def sign_up(email: str, password: str) -> Dict:
    """
    Creates a new user account
    
    Args:
        email: User's email
        password: User's password
    
    Returns:
        Response from Supabase with user data
    """
    try:
        supabase = get_supabase_client()
        response = supabase.auth.sign_up({
            "email": email,
            "password": password
        })
        return {"success": True, "data": response}
    except Exception as e:
        return {"success": False, "error": str(e)}


def sign_in(email: str, password: str) -> Dict:
    """
    Logs in an existing user and stores session in Streamlit state
    
    Args:
        email: User's email
        password: User's password
    
    Returns:
        Response with user session or error
    """
    try:
        supabase = get_supabase_client()
        response = supabase.auth.sign_in_with_password({
            "email": email,
            "password": password
        })
        
        # Store session tokens in Streamlit session state for persistence
        if response.session:
            st.session_state.access_token = response.session.access_token
            st.session_state.refresh_token = response.session.refresh_token
        
        return {"success": True, "data": response}
    except Exception as e:
        return {"success": False, "error": str(e)}


def sign_out():
    """
    Logs out the current user and clears session state
    """
    try:
        supabase = get_supabase_client()
        supabase.auth.sign_out()
        
        # Clear session state
        if 'access_token' in st.session_state:
            del st.session_state.access_token
        if 'refresh_token' in st.session_state:
            del st.session_state.refresh_token
        if 'user' in st.session_state:
            del st.session_state.user
        if 'user_id' in st.session_state:
            del st.session_state.user_id
            
        return {"success": True}
    except Exception as e:
        return {"success": False, "error": str(e)}


def get_current_user() -> Optional[Dict]:
    """
    Gets the currently logged-in user
    
    Returns:
        User data if logged in, None otherwise
    """
    try:
        supabase = get_authenticated_client()
        user = supabase.auth.get_user()
        if user and user.user:
            return user.user
        return None
    except Exception as e:
        print(f"Error getting current user: {e}")
        return None


def is_authenticated() -> bool:
    """
    Checks if a user is currently logged in
    
    Returns:
        True if user is logged in, False otherwise
    """
    return 'access_token' in st.session_state and st.session_state.access_token is not None


def get_user_id() -> Optional[str]:
    """
    Gets the current user's ID
    
    Returns:
        User ID string or None
    """
    if 'user_id' in st.session_state:
        return st.session_state.user_id
    
    user = get_current_user()
    if user:
        st.session_state.user_id = user.id
        return user.id
    return None
