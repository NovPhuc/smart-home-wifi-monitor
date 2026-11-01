# 10. Quá trình xây dựng và phát triển ứng dụng

> Tài liệu trình bày cách hệ thống An Tâm Home — WiFi Care được xây dựng và phát triển,
> từ khảo sát đến triển khai. Dùng làm nguồn cho Chương "Triển khai" của báo cáo khóa luận.

## 1. Lộ trình tổng thể (7 giai đoạn)

| Giai đoạn | Nội dung chính | Sản phẩm |
|---|---|---|
| 1. Khảo sát & thiết kế | So sánh Camera / Wearable / WiFi Sensing; chọn passive RSSI mức phòng; thiết kế use case (Rose), kiến trúc 5 tầng | `docs/02`, `docs/09`, model Rose `.mdl` |
| 2. Dựng pipeline dữ liệu tổng hợp | Sinh dữ liệu v2 thực tế hóa (signature phòng +6/+4 dB, noise σ=6, missing tương quan 15%, burst 5%, seed 42): 4.800 fingerprints + 760 sự kiện quỹ đạo | `scripts/generate_synthetic_data.py`, `data/raw/` |
| 3. Xây dựng mô hình | RoomNet-Lite (depthwise separable + Center Loss + temporal JS) + GRU-AE + Rule Engine + Bayes; baselines kNN/RF/MLP; K-fold 5 | `src/smarthome/models/`, `scripts/train_*.py`, `results/` |
| 4. Xây dựng ứng dụng | Flask REST API (10 bảng SQLite), dashboard PWA, app Android (Kotlin, foreground service) | `server/`, `android_collector/` |
| 5. Thu dữ liệu thật | Session S01–S08 qua Cloudflare Tunnel: 638 scans (Phòng ngủ 337, Nhà Vệ Sinh 301); model home "Nhà A" READY | `data/smarthome.db`, `models/homes/3/` |
| 6. Tối ưu độ tin cậy (GĐ0–GĐ5) | Chống trùng 2 lớp, timestamp chuẩn, AP hashing, DEVICE_OFFLINE, /api/health, SECRET_KEY, nhãn data_source, .gitignore | 68 unit test, commits `e4a768b`→`dd5aa7e` |
| 7. Mở rộng & hoàn thiện | Chia sẻ nhà mã 6 số, webhook CRITICAL, heatmap, UML Rational Rose đầy đủ, báo cáo chuẩn cử nhân | commits `15e4957`→`a991a13` |

## 2. Công cụ theo từng giai đoạn

- **Thiết kế**: Rational Rose 2006 (UML — qua COM automation), matplotlib (sơ đồ use case/statechart PNG), draw.io (tham khảo).
- **Dữ liệu**: Python (csv/json/sqlite3), seed 42 tái lập; script chuyển UCI WIL + UJIIndoorLoc về schema đề tài.
- **Huấn luyện**: PyTorch CPU, AdamW + CosineAnnealingWarmRestarts + early stopping; grid search quantile 0,90–0,995 cho ngưỡng AE.
- **Kiểm thử**: pytest (43 → 68 test), test thời gian giả lập cho DEVICE_OFFLINE, test webhook bằng HTTP server cục bộ.
- **Triển khai**: Cloudflare Quick Tunnel (HTTPS không cần IP public), run_server.ps1, Start-Process độc lập.
- **Báo cáo**: python-docx / python-pptx sinh tự động từ `results/*.json`; markitdown.

## 3. Vòng lặp "xây — đo — sửa" đáng chú ý

1. **F1 100% giả tạo** → thực tế hóa dữ liệu v2 ngay từ đầu → con số đáng tin (98,99%).
2. **Rò rỉ protocol** (ngày chọn ngưỡng nằm trong tập test) → Fix A: train D01–D10 / ngưỡng D11–D12 / test D13–D14 tách riêng → F1 91,53% → 99,50% trung thực.
3. **Session đơn-phòng** (S01–S08 chỉ đứng 1 phòng) → tập test nhà thật mất lớp → protocol S09 đi qua tất cả các phòng.
4. **Scan trùng tính vào hiệu chuẩn** → chống trùng 2 lớp (client scan_timestamp + server hash), 7 test riêng.
5. **Meter gauge vô hình** (className bị ghi đè) → phát hiện khi audit motion, sửa bằng scaleX + class đúng.

## 4. Kiểm chứng cuối

- pytest **68/68 pass** · DB integrity ok (638 scans thật nguyên vẹn) · server chạy code mới · tunnel HTTPS health 200.
- Số liệu chính: phân loại phòng **98,99%** (K-fold 97,80%±1,06%) · bất thường **F1 99,50%** (P 100%/R 99%) · latency e2e **0,025 ms/mẫu**.
