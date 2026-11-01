"""Phòng và thiết bị thu thập."""
from __future__ import annotations

import sqlite3

from flask import Blueprint, jsonify, request

import app_state
from app_services import finite_float, login_required, require_active_home, require_owned_home

bp = Blueprint("rooms", __name__)


@bp.route("/api/rooms", methods=["GET", "POST"])
@login_required
def rooms():
    home, error = require_owned_home() if request.method == "POST" else require_active_home()
    if error:
        return error
    if request.method == "GET":
        return jsonify(app_state.db.list_rooms(home["id"]))
    payload = request.get_json(force=True) or {}
    name = str(payload.get("name", "")).strip()
    if not name or len(name) > 80:
        return jsonify({"error": "Tên phòng phải từ 1 đến 80 ký tự"}), 400
    try:
        dwell = finite_float(
            payload.get("max_dwell_minutes", 60),
            field="max_dwell_minutes", minimum=1, maximum=1440,
        )
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    try:
        room = app_state.db.create_room(home["id"], name, dwell)
    except sqlite3.IntegrityError:
        return jsonify({"error": "Tên phòng đã tồn tại"}), 409
    app_state.db.set_model_status(home["id"], "NOT_TRAINED")
    app_state.home_engines.pop(home["id"], None)
    return jsonify(room), 201


@bp.route("/api/rooms/<int:room_id>", methods=["PATCH", "DELETE"])
@login_required
def modify_room(room_id: int):
    home, error = require_owned_home()
    if error:
        return error
    if request.method == "DELETE":
        changed = app_state.db.delete_room(home["id"], room_id)
    else:
        payload = request.get_json(force=True) or {}
        name = str(payload.get("name", "")).strip()
        if not name or len(name) > 80:
            return jsonify({"error": "Tên phòng không hợp lệ"}), 400
        try:
            dwell = finite_float(
                payload.get("max_dwell_minutes", 60),
                field="max_dwell_minutes", minimum=1, maximum=1440,
            )
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400
        try:
            changed = app_state.db.update_room(home["id"], room_id, name, dwell)
        except sqlite3.IntegrityError:
            return jsonify({"error": "Tên phòng đã tồn tại"}), 409
    if not changed:
        return jsonify({"error": "Không tìm thấy phòng"}), 404
    app_state.db.set_model_status(home["id"], "NOT_TRAINED")
    app_state.home_engines.pop(home["id"], None)
    return jsonify({"ok": True})


@bp.route("/api/devices", methods=["GET", "POST"])
@login_required
def devices():
    home, error = require_owned_home() if request.method == "POST" else require_active_home()
    if error:
        return error
    if request.method == "GET":
        return jsonify(app_state.db.list_devices(home["id"]))
    payload = request.get_json(force=True) or {}
    name = str(payload.get("name", "Điện thoại Android")).strip()[:80] or "Điện thoại Android"
    # ``platform`` do client tự khai và được hiển thị lại trên dashboard:
    # cắt độ dài để không có cột lạ hoặc chuỗi rác rất dài trong DB.
    platform = str(payload.get("platform", "android")).strip()[:40] or "android"
    device, token = app_state.db.create_device(home["id"], name, platform)
    return jsonify({"device": device, "token": token, "message": "Token chỉ hiển thị một lần"}), 201


@bp.delete("/api/devices/<int:device_id>")
@login_required
def revoke_device(device_id: int):
    home, error = require_owned_home()
    if error:
        return error
    return jsonify({"ok": app_state.db.revoke_device(home["id"], device_id)})
