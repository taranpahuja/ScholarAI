import sys
import os
import uuid

# Ensure parent directory is on path so llm_service, db, middleware resolve correctly
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from flask import Blueprint, request, jsonify, g
from db import get_supabase_admin
from middleware import require_auth, require_admin
from llm_service import parse_unstructured_guidelines

admin_bp = Blueprint("admin", __name__)


@admin_bp.route("/scholarships", methods=["POST"])
@require_auth
@require_admin
def create_scholarship():
    """
    Create a new scholarship.
    Body: all scholarship fields. If 'raw_guidelines' text is provided,
    MegaLLM will parse and auto-fill structured fields.
    """
    data = request.get_json()
    admin = get_supabase_admin()

    # If raw unstructured guidelines are provided, parse them with LLM
    raw_guidelines = data.pop("raw_guidelines", None)
    if raw_guidelines:
        try:
            parsed = parse_unstructured_guidelines(raw_guidelines)
            # Merge parsed fields (don't overwrite explicitly set fields)
            for k, v in parsed.items():
                if k not in data and v is not None:
                    data[k] = v
            data["raw_json"] = parsed
        except Exception as e:
            return jsonify({"error": "LLM guideline parsing failed", "detail": str(e)}), 500

    result = admin.table("scholarships").insert(data).execute()
    return jsonify({"message": "Scholarship created", "data": result.data}), 201


@admin_bp.route("/scholarships/<scholarship_id>", methods=["PUT"])
@require_auth
@require_admin
def update_scholarship(scholarship_id):
    """Update an existing scholarship."""
    data = request.get_json()
    data.pop("id", None)
    data.pop("created_at", None)

    admin = get_supabase_admin()
    result = admin.table("scholarships").update(data).eq("id", scholarship_id).execute()
    return jsonify({"message": "Scholarship updated", "data": result.data}), 200


@admin_bp.route("/scholarships/<scholarship_id>", methods=["DELETE"])
@require_auth
@require_admin
def delete_scholarship(scholarship_id):
    """Delete a scholarship and cascade eligibility results."""
    admin = get_supabase_admin()
    # Delete eligibility results first (if no cascade set in DB)
    admin.table("eligibility_results").delete().eq("scholarship_id", scholarship_id).execute()
    admin.table("scholarships").delete().eq("id", scholarship_id).execute()
    return jsonify({"message": "Scholarship deleted"}), 200


@admin_bp.route("/scholarships/upload-file", methods=["POST"])
@require_auth
@require_admin
def upload_scholarship_file():
    """
    Upload a document file to Supabase Storage and register it in admin_uploads.
    Also attempts LLM extraction of eligibility criteria from the file text.
    Multipart form: file + scholarship_id
    """
    if "file" not in request.files:
        return jsonify({"error": "No file part"}), 400

    file = request.files["file"]
    scholarship_id = request.form.get("scholarship_id")
    if not scholarship_id:
        return jsonify({"error": "scholarship_id is required"}), 400

    filename = f"{uuid.uuid4()}_{file.filename}"
    file_bytes = file.read()

    admin = get_supabase_admin()

    # Upload to Supabase Storage bucket named 'scholarship-docs'
    try:
        storage_response = admin.storage.from_("scholarship-docs").upload(
            path=filename,
            file=file_bytes,
            file_options={"content-type": file.content_type}
        )
        public_url = admin.storage.from_("scholarship-docs").get_public_url(filename)
    except Exception as e:
        return jsonify({"error": "File upload failed", "detail": str(e)}), 500

    # Save record in admin_uploads
    upload_record = {
        "scholarship_id": scholarship_id,
        "file_url": public_url,
        "uploaded_by": g.user.id
    }
    admin.table("admin_uploads").insert(upload_record).execute()

    return jsonify({
        "message": "File uploaded successfully",
        "file_url": public_url,
        "filename": filename
    }), 201


@admin_bp.route("/stats", methods=["GET"])
@require_auth
@require_admin
def stats():
    """Basic dashboard stats for admin."""
    admin = get_supabase_admin()

    total_users = admin.table("users").select("id", count="exact").execute()
    total_scholarships = admin.table("scholarships").select("id", count="exact").execute()
    total_evaluations = admin.table("eligibility_results").select("id", count="exact").execute()
    eligible_count = admin.table("eligibility_results").select("id", count="exact").eq("eligible", True).execute()

    return jsonify({
        "total_users": total_users.count,
        "total_scholarships": total_scholarships.count,
        "total_evaluations": total_evaluations.count,
        "eligible_results": eligible_count.count,
    }), 200
