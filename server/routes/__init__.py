"""Đăng ký toàn bộ route API vào Flask app.

Mỗi module một domain; đường dẫn và hành vi giữ nguyên như bản app.py cũ để
app Android và dashboard PWA không bị vỡ.
"""
from __future__ import annotations

from flask import Flask


def register_routes(app: Flask) -> None:
    from routes import auth_views, home_views, room_views, track_views, training_views

    app.register_blueprint(auth_views.bp)
    app.register_blueprint(home_views.bp)
    app.register_blueprint(room_views.bp)
    app.register_blueprint(track_views.bp)
    app.register_blueprint(training_views.bp)
