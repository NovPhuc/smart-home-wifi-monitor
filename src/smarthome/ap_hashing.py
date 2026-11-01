from __future__ import annotations

import hashlib
import json

__all__ = ["hash_bssid", "wifi_hash"]


def hash_bssid(bssid: str) -> str:
    """Băm BSSID thành tên AP thống nhất giữa Android và PC.

    = "AP_" + 12 ký tự hex đầu của SHA-256(bssid viết thường, UTF-8) —
    khớp `hashBssid` phía Kotlin với BSSID chuẩn mà Android trả về (chữ
    thường). Viết thường trước khi băm để script PC (netsh trả BSSID chữ
    hoa) và điện thoại cho CÙNG tên AP với cùng một thiết bị.

    Vector kiểm chứng (đặc tả GĐ3):
        aa:bb:cc:dd:ee:ff -> AP_c1582e87c802
        00:11:22:33:44:55 -> AP_66fd6ef831e4
    """
    digest = hashlib.sha256(bssid.strip().lower().encode("utf-8")).hexdigest()
    return "AP_" + digest[:12]


def wifi_hash(wifi: dict[str, float]) -> str:
    """Băm nội dung fingerprint để phát hiện bản ghi trùng từ client cũ.

    Client cũ không gửi ``scan_timestamp``; hai lần gửi liên tiếp cùng nội dung
    RSSI (scan cache của Android trả lại kết quả cũ) sẽ có cùng hash. Công thức
    khớp với ``storage._wifi_hash`` của bản 1006: json.dumps sort_keys + compact,
    SHA-256 full hex — hai bản cho CÙNG giá trị hash trên cùng dữ liệu.
    """
    canonical = json.dumps(
        {str(key): float(value) for key, value in wifi.items()},
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
