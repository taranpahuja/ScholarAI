import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from flask import Blueprint, request, jsonify, g
from db import get_supabase, get_supabase_admin
from middleware import require_auth

auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/signup", methods=["POST"])
def signup():
    """
    Register a new user with Supabase Auth + insert profile into users table.
    Body: { email, password, name, gender, category, family_income, state, course, degree_level, cgpa, ethnicity }
    """
    data = request.get_json()
    required = ["email", "password", "name"]
    missing = [f for f in required if not data.get(f)]
    if missing:
        return jsonify({"error": f"Missing fields: {missing}"}), 400

    supabase = get_supabase()

    # 1. Create auth user
    try:
        auth_response = supabase.auth.sign_up({
            "email": data["email"],
            "password": data["password"]
        })
        user = auth_response.user
        if not user:
            return jsonify({"error": "Signup failed"}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 400

    # 2. Insert user profile (uses service key to bypass RLS on insert)
    admin = get_supabase_admin()
    profile = {
        "id": user.id,
        "name": data.get("name"),
        "email": data.get("email"),
        "gender": data.get("gender"),
        "category": data.get("category"),
        "family_income": data.get("family_income"),
        "state": data.get("state"),
        "course": data.get("course"),
        "degree_level": data.get("degree_level"),
        "cgpa": data.get("cgpa"),
        "ethnicity": data.get("ethnicity"),
    }
    try:
        admin.table("users").insert(profile).execute()
    except Exception as e:
        return jsonify({"error": "Profile creation failed", "detail": str(e)}), 500

    return jsonify({"message": "Signup successful", "user_id": user.id}), 201


@auth_bp.route("/login", methods=["POST"])
def login():
    """
    Login with email/password. Returns access_token and user.
    Body: { email, password }
    """
    data = request.get_json()
    supabase = get_supabase()
    try:
        session = supabase.auth.sign_in_with_password({
            "email": data["email"],
            "password": data["password"]
        })
        return jsonify({
            "access_token": session.session.access_token,
            "refresh_token": session.session.refresh_token,
            "user": {
                "id": session.user.id,
                "email": session.user.email
            }
        }), 200
    except Exception as e:
        return jsonify({"error": "Login failed", "detail": str(e)}), 401


@auth_bp.route("/profile", methods=["GET"])
@require_auth
def get_profile():
    """Returns the authenticated user's profile from the users table."""
    admin = get_supabase_admin()
    result = admin.table("users").select("*").eq("id", g.user.id).single().execute()
    return jsonify(result.data), 200


@auth_bp.route("/profile", methods=["PUT"])
@require_auth
def update_profile():
    """
    Update the authenticated user's profile.
    Body: any subset of user fields.
    """
    data = request.get_json()
    # Remove protected fields
    for key in ["id", "email", "created_at"]:
        data.pop(key, None)

    admin = get_supabase_admin()
    result = admin.table("users").update(data).eq("id", g.user.id).execute()
    return jsonify({"message": "Profile updated", "data": result.data}), 200
