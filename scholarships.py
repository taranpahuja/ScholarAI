import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from flask import Blueprint, request, jsonify
from db import get_supabase_admin
from middleware import require_auth

scholarships_bp = Blueprint("scholarships", __name__)


@scholarships_bp.route("/", methods=["GET"])
@require_auth
def list_scholarships():
    """
    List all scholarships with optional filters.
    Query params: location, min_amount, max_amount, deadline_before, search
    """
    admin = get_supabase_admin()
    query = admin.table("scholarships").select("*")

    location = request.args.get("location")
    if location:
        query = query.ilike("location", f"%{location}%")

    search = request.args.get("search")
    if search:
        query = query.ilike("scholarship_name", f"%{search}%")

    deadline = request.args.get("deadline_before")
    if deadline:
        query = query.lte("deadline", deadline)

    result = query.order("created_at", desc=True).execute()
    return jsonify({"scholarships": result.data, "count": len(result.data)}), 200


@scholarships_bp.route("/<scholarship_id>", methods=["GET"])
@require_auth
def get_scholarship(scholarship_id):

    
    """Get a single scholarship by ID."""
    admin = get_supabase_admin()
    result = admin.table("scholarships").select("*").eq("id", scholarship_id).single().execute()
    if not result.data:
        return jsonify({"error": "Scholarship not found"}), 404
    return jsonify(result.data), 200
