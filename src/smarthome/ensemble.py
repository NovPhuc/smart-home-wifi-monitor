"""Meta-learning kiểu FIND3: chọn model tốt nhất THEO TỪNG BỘ DỮ LIỆU.

Không có model nào thắng mọi căn nhà (đặc điểm lan sóng WiFi khác nhau giữa
các nhà). Vì vậy huấn luyện nhiều ứng viên rồi chọn người thắng trên tập
VALIDATION — tuyệt đối không dùng tập test để chọn (tránh rò rỉ đánh giá,
đúng nguyên tắc đã sửa ở Fix A phiên trước).
"""
from __future__ import annotations


def select_best_candidate(metrics: dict[str, dict]) -> tuple[str, dict]:
    """Chọn ứng viên có (macro_f1, accuracy) cao nhất trên validation.

    Trả về ``(tên, chỉ_số)``. Tie-break theo accuracy, sau đó theo tên để
    kết quả xác định được với cùng seed.
    """
    if not metrics:
        raise ValueError("Không có ứng viên nào để chọn")
    ranked = sorted(
        metrics.items(),
        key=lambda kv: (kv[1]["macro_f1"], kv[1]["accuracy"], kv[0]),
        reverse=True,
    )
    return ranked[0]


def candidate_feature_kind(name: str) -> str:
    """Kiểu đầu vào mà candidate cần lúc suy luận.

    - torch models: cửa sổ tensor ``[features, time]``.
    - sklearn models: cửa sổ duỗi phẳng ``[features * time]`` (thứ tự
      features-major — trùng khớp ``numpy().reshape(-1)`` lúc huấn luyện).
    """
    return "window_tensor" if name in {"RoomNetLite", "SimpleCNN", "RoomNetMT"} else "flattened_window"
