"""Đăng ký / đăng nhập / phiên làm việc."""
from __future__ import annotations

import sqlite3

from flask import Blueprint, jsonify, request, session as flask_session
from werkzeug.security import check_password_hash, generate_password_hash

import app_state
from app_security import mark_session_issued
from app_services import active_home, login_required

bp = Blueprint("auth", __name__)


@bp.post("/api/auth/register")
def register():
    client_ip = request.remote_addr or "unknown"
    if app_state.register_limiter.is_blocked(client_ip):
        return jsonify({
            "error": "TOO_MANY_ATTEMPTS",
            "detail": "Tạo tài khoản quá nhiều lần. Thử lại sau.",
        }), 429
    app_state.register_limiter.record_failure(client_ip)
    payload = request.get_json(force=True, silent=False) or {}
    email = str(payload.get("email", "")).strip().lower()
    password = str(payload.get("password", ""))
    display_name = str(payload.get("display_name", "")).strip()
    home_name = str(payload.get("home_name", "")).strip() or "Nhà của tôi"
    errors = {}
    if "@" not in email or len(email) > 254:
        errors["email"] = "Email không hợp lệ"
    if len(password) < 8:
        errors["password"] = "Mật khẩu cần ít nhất 8 ký tự"
    elif len(password) > 128:
        errors["password"] = "Mật khẩu tối đa 128 ký tự"
    if not display_name or len(display_name) > 80:
        errors["display_name"] = "Tên hiển thị không hợp lệ"
    if not home_name or len(home_name) > 100:
        errors["home_name"] = "Tên nhà không hợp lệ"
    if errors:
        return jsonify({"error": "VALIDATION_ERROR", "fields": errors}), 400
    try:
        user = app_state.db.create_user(email, generate_password_hash(password), display_name)
        home = app_state.db.create_home(user["id"], home_name)
    except sqlite3.IntegrityError:
        return jsonify({"error": "EMAIL_EXISTS", "fields": {"email": "Email đã được đăng ký"}}), 409
    flask_session.clear()
    flask_session["user_id"] = user["id"]
    flask_session["active_home_id"] = home["id"]
    mark_session_issued()
    return jsonify({"user": {"id": user["id"], "email": user["email"], "display_name": user["display_name"]}, "active_home": home}), 201


@bp.post("/api/auth/login")
def login():
    payload = request.get_json(force=True, silent=False) or {}
    email = str(payload.get("email", "")).strip().lower()
    # Khóa theo email: kẻ dò một tài khoản bị chặn, các tài khoản khác không
    # ảnh hưởng. Đánh đổi: người xấu có thể cố tình khóa email của nạn nhân.
    if app_state.login_limiter.is_blocked(email):
        return jsonify({"error": "TOO_MANY_ATTEMPTS", "detail": "Thử lại sau 15 phút"}), 429
    user = app_state.db.get_user_by_email(email)
    if user is None:
        # Email không tồn tại vẫn chạy một lần băm để thời gian phản hồi
        # giống hệt trường hợp sai mật khẩu.
        check_password_hash(app_state.DUMMY_PASSWORD_HASH, str(payload.get("password", "")))
    if not user or not check_password_hash(user["password_hash"], str(payload.get("password", ""))):
        app_state.login_limiter.record_failure(email)
        return jsonify({"error": "INVALID_CREDENTIALS"}), 401
    app_state.login_limiter.reset(email)
    flask_session.clear()
    flask_session["user_id"] = user["id"]
    mark_session_issued()
    homes = app_state.db.list_homes(user["id"])
    if homes:
        flask_session["active_home_id"] = homes[0]["id"]
    return jsonify({
        "ok": True,
        "user": {"id": user["id"], "email": user["email"], "display_name": user["display_name"]},
        "homes": homes,
        "active_home": homes[0] if homes else None,
    })


@bp.post("/api/auth/logout")
def logout():
    flask_session.clear()
    return jsonify({"ok": True})


@bp.get("/api/auth/me")
@login_required
def me():
    user = app_state.db.get_user(int(flask_session["user_id"]))
    home = active_home()
    return jsonify({
        "user": {"id": user["id"], "email": user["email"], "display_name": user["display_name"]},
        "homes": app_state.db.list_homes(user["id"]),
        "active_home": home,
    })
