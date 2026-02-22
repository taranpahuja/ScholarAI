import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from flask import Blueprint, request, jsonify, g
from db import get_supabase_admin
from middleware import require_auth
from llm_service import evaluate_eligibility

eligibility_bp = Blueprint("eligibility", __name__)


@eligibility_bp.route("/check/<scholarship_id>", methods=["POST"])
@require_auth
def check_eligibility(scholarship_id):
    """
    Evaluate the authenticated user's eligibility for a specific scholarship.
    Calls MegaLLM for reasoning and stores result in eligibility_results table.
    
    Returns:
        verdict, confidence_score, matched/unmatched criteria, explanation, recommendations
    """
    admin = get_supabase_admin()

    # 1. Fetch user profile
    user_result = admin.table("users").select("*").eq("id", g.user.id).single().execute()
    if not user_result.data:
        return jsonify({"error": "User profile not found. Please complete your profile."}), 404

    # 2. Fetch scholarship
    scholarship_result = admin.table("scholarships").select("*").eq("id", scholarship_id).single().execute()
    if not scholarship_result.data:
        return jsonify({"error": "Scholarship not found"}), 404

    user_profile = user_result.data
    scholarship = scholarship_result.data

    # 3. Check if already evaluated (return cached result to save LLM calls)
    existing = admin.table("eligibility_results") \
        .select("*") \
        .eq("user_id", g.user.id) \
        .eq("scholarship_id", scholarship_id) \
        .maybe_single() \
        .execute()

    force_refresh = request.args.get("refresh", "false").lower() == "true"
    if existing.data and not force_refresh:
        return jsonify({
            "cached": True,
            "result": existing.data
        }), 200

    # 4. Call MegaLLM for evaluation
    try:
        llm_result = evaluate_eligibility(user_profile, scholarship)
    except Exception as e:
        return jsonify({"error": "LLM evaluation failed", "detail": str(e)}), 500

    # 5. Map verdict to boolean eligible field
    verdict = llm_result.get("verdict", "NOT_ELIGIBLE")
    is_eligible = verdict == "ELIGIBLE"

    # 6. Persist result in eligibility_results
    record = {
        "user_id": g.user.id,
        "scholarship_id": scholarship_id,
        "eligible": is_eligible,
        "eligibility_explanation": llm_result.get("explanation", ""),
        "confidence_score": llm_result.get("confidence_score", 0.0),
        "eligibility_percentage": llm_result.get("eligibility_percentage") or round(llm_result.get("confidence_score", 0.0) * 100),
    }

    try:
        if existing.data:
            # Update existing record
            admin.table("eligibility_results") \
                .update(record) \
                .eq("user_id", g.user.id) \
                .eq("scholarship_id", scholarship_id) \
                .execute()
        else:
            admin.table("eligibility_results").insert(record).execute()
    except Exception as e:
        return jsonify({"error": "Failed to save result", "detail": str(e)}), 500

    return jsonify({
        "cached": False,
        "result": {
            **record,
            "verdict": verdict,
            "matched_criteria": llm_result.get("matched_criteria", []),
            "unmatched_criteria": llm_result.get("unmatched_criteria", []),
            "unclear_criteria": llm_result.get("unclear_criteria", []),
            "recommendations": llm_result.get("recommendations", []),
            "scholarship_name": scholarship.get("scholarship_name"),
            "scholarship_amount": scholarship.get("amount"),
        }
    }), 200


@eligibility_bp.route("/bulk-check", methods=["POST"])
@require_auth
def bulk_check():
    """
    Evaluate the authenticated user against multiple scholarships at once.
    Body: { scholarship_ids: [uuid, uuid, ...] }
    Runs evaluations sequentially and returns a summary list.
    """
    data = request.get_json()
    scholarship_ids = data.get("scholarship_ids", [])
    if not scholarship_ids:
        return jsonify({"error": "scholarship_ids list is required"}), 400
    if len(scholarship_ids) > 10:
        return jsonify({"error": "Max 10 scholarships per bulk check"}), 400

    admin = get_supabase_admin()

    user_result = admin.table("users").select("*").eq("id", g.user.id).single().execute()
    if not user_result.data:
        return jsonify({"error": "User profile not found"}), 404
    user_profile = user_result.data

    results = []
    for sid in scholarship_ids:
        scholarship_result = admin.table("scholarships").select("*").eq("id", sid).single().execute()
        if not scholarship_result.data:
            results.append({"scholarship_id": sid, "error": "Not found"})
            continue

        scholarship = scholarship_result.data
        try:
            llm_result = evaluate_eligibility(user_profile, scholarship)
            verdict = llm_result.get("verdict", "NOT_ELIGIBLE")

            record = {
                "user_id": g.user.id,
                "scholarship_id": sid,
                "eligible": verdict == "ELIGIBLE",
                "eligibility_explanation": llm_result.get("explanation", ""),
                "confidence_score": llm_result.get("confidence_score", 0.0),
            }
            admin.table("eligibility_results").upsert(record, on_conflict="user_id,scholarship_id").execute()

            results.append({
                "scholarship_id": sid,
                "scholarship_name": scholarship.get("scholarship_name"),
                "amount": scholarship.get("amount"),
                "verdict": verdict,
                "confidence_score": llm_result.get("confidence_score"),
                "explanation": llm_result.get("explanation"),
                "recommendations": llm_result.get("recommendations", []),
            })
        except Exception as e:
            results.append({"scholarship_id": sid, "error": str(e)})

    return jsonify({"results": results}), 200


@eligibility_bp.route("/my-results", methods=["GET"])
@require_auth
def my_results():
    """
    Get all past eligibility evaluations for the authenticated user.
    Joins with scholarships for name and amount.
    """
    admin = get_supabase_admin()
    result = admin.table("eligibility_results") \
        .select("*, scholarships(scholarship_name, amount, deadline, link)") \
        .eq("user_id", g.user.id) \
        .order("created_at", desc=True) \
        .execute()

    return jsonify({"results": result.data}), 200


@eligibility_bp.route("/my-results/<scholarship_id>", methods=["GET"])
@require_auth
def get_single_result(scholarship_id):
    """Get a specific eligibility result for the authenticated user."""
    admin = get_supabase_admin()
    result = admin.table("eligibility_results") \
        .select("*, scholarships(*)") \
        .eq("user_id", g.user.id) \
        .eq("scholarship_id", scholarship_id) \
        .maybe_single() \
        .execute()

    if not result.data:
        return jsonify({"error": "No evaluation found. Run /check first."}), 404
    return jsonify(result.data), 200
