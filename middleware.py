from functools import wraps
from flask import request, jsonify, g
from db import get_supabase

def require_auth(f):
    """Validates Supabase JWT from Authorization header and injects user into g.user."""
    @wraps(f)
    def decorated(*args, **kwargs):
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return jsonify({"error": "Missing or invalid Authorization header"}), 401

        token = auth_header.split(" ")[1]
        try:
            supabase = get_supabase()
            user_response = supabase.auth.get_user(token)
            if not user_response or not user_response.user:
                return jsonify({"error": "Invalid or expired token"}), 401
            g.user = user_response.user
            g.token = token
        except Exception as e:
            return jsonify({"error": "Auth failed", "detail": str(e)}), 401

        return f(*args, **kwargs)
    return decorated


def require_admin(f):
    """
    Role check — must be stacked BELOW @require_auth so g.user is already set.
    Expects Supabase user_metadata to contain { role: 'admin' }.

    Correct usage:
        @require_auth
        @require_admin
        def my_route(): ...
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        role = (g.user.user_metadata or {}).get("role", "")
        if role != "admin":
            return jsonify({"error": "Admin access required"}), 403
        return f(*args, **kwargs)
    return decorated

