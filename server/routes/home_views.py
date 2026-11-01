"""Nhà: CRUD, chọn nhà active, chia sẻ bằng mã 6 số, thành viên."""
from __future__ import annotations

import sqlite3

from flask import Blueprint, jsonify, request, session as flask_session

import app_state
from app_services import login_required, require_owned_home_by_id

bp = Blueprint("homes", __name__)


@bp.route("/api/homes", methods=["GET", "POST"])
@login_required
def homes():
    user_id = int(flask_session["user_id"])
    if request.method == "GET":
        return jsonify(app_state.db.list_homes(user_id))
    name = str((request.get_json(force=True) or {}).get("name", "")).strip()
    if not name or len(name) > 100:
        return jsonify({"error": "Tên nhà phải từ 1 đến 100 ký tự"}), 400
    try:
        home = app_state.db.create_home(user_id, name)
    except sqlite3.IntegrityError:
        return jsonify({"error": "Tên nhà đã tồn tại"}), 409
    flask_session["active_home_id"] = home["id"]
    return jsonify(home), 201


@bp.post("/api/homes/<int:home_id>/select")
@login_required
def select_home(home_id: int):
    home = app_state.db.get_home(int(flask_session["user_id"]), home_id)
    if not home:
        return jsonify({"error": "Không tìm thấy nhà"}), 404
    flask_session["active_home_id"] = home_id
    return jsonify({"active_home": home})


@bp.route("/api/homes/<int:home_id>", methods=["PATCH", "DELETE"])
@login_required
def modify_home(home_id: int):
    user_id = int(flask_session["user_id"])
    if request.method == "DELETE":
        if not app_state.db.delete_home(user_id, home_id):
            return jsonify({"error": "Không tìm thấy nhà"}), 404
        if flask_session.get("active_home_id") == home_id:
            flask_session.pop("active_home_id", None)
        app_state.home_engines.pop(home_id, None)
        return jsonify({"ok": True})
    name = str((request.get_json(force=True) or {}).get("name", "")).strip()
    if not name or len(name) > 100:
        return jsonify({"error": "Tên nhà không hợp lệ"}), 400
    try:
        changed = app_state.db.rename_home(user_id, home_id, name)
    except sqlite3.IntegrityError:
        return jsonify({"error": "Tên nhà đã tồn tại"}), 409
    return jsonify({"ok": changed}) if changed else (jsonify({"error": "Không tìm thấy nhà"}), 404)


@bp.get("/api/homes/<int:home_id>/share")
@login_required
def get_share(home_id: int):
    home, error = require_owned_home_by_id(home_id)
    if error:
        return error
    share = app_state.db.active_share(home_id)
    ttl = float(app_state.cfg.get("sharing", {}).get("code_ttl_hours", 24))
    return jsonify({"share": share, "ttl_hours": ttl})


@bp.post("/api/homes/<int:home_id>/share")
@login_required
def rotate_share(home_id: int):
    home, error = require_owned_home_by_id(home_id)
    if error:
        return error
    ttl = float(app_state.cfg.get("sharing", {}).get("code_ttl_hours", 24))
    share = app_state.db.create_share_code(home_id, int(flask_session["user_id"]), ttl)
    return jsonify({"share": share, "ttl_hours": ttl}), 201


@bp.delete("/api/homes/<int:home_id>/share")
@login_required
def drop_share(home_id: int):
    home, error = require_owned_home_by_id(home_id)
    if error:
        return error
    return jsonify({"ok": app_state.db.revoke_share_code(home_id)})


@bp.get("/api/homes/<int:home_id>/members")
@login_required
def members(home_id: int):
    home, error = require_owned_home_by_id(home_id)
    if error:
        return error
    return jsonify(app_state.db.list_home_members(home_id))


@bp.delete("/api/homes/<int:home_id>/members/<int:user_id>")
@login_required
def kick_member(home_id: int, user_id: int):
    home, error = require_owned_home_by_id(home_id)
    if error:
        return error
    return jsonify({"ok": app_state.db.remove_home_member(home_id, user_id)})


@bp.post("/api/homes/join")
@login_required
def join_home():
    payload = request.get_json(force=True, silent=False) or {}
    code = str(payload.get("code", "")).strip()
    if not code.isdigit() or len(code) != 6:
        return jsonify({"error": "Mã chia sẻ gồm 6 chữ số"}), 400
    user_id = int(flask_session["user_id"])
    if app_state.join_code_limiter.is_blocked(str(user_id)):
        return jsonify({"error": "TOO_MANY_ATTEMPTS", "detail": "Thử lại sau 15 phút"}), 429
    try:
        home = app_state.db.join_home_by_code(user_id, code)
    except LookupError as exc:
        # Mã sai/hết hạn là một lần đoán — đếm vào hạn mức dò mã.
        app_state.join_code_limiter.record_failure(str(user_id))
        return jsonify({"error": str(exc)}), 404
    app_state.join_code_limiter.reset(str(user_id))
    flask_session["active_home_id"] = home["id"]
    return jsonify({"joined_home": home})
