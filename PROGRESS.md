# PROGRESS — Khóa luận 336 (CNTT-KLCN-336)

Phiên làm việc: 2026-10-11 (phiên 3) — **HOÀN THÀNH CẢ 5 GIAI ĐOẠN**
Nhánh git: `fix/optimize-training` · Commit gốc (trước tối ưu): `7b2f120` · Checkpoint fix phiên 1-2: `7ac19a8`
Sao lưu dữ liệu gốc: `backup_original/` + commit gốc (không bao giờ bị ghi đè — baseline chạy trong bản sao git archive `.tmp/baseline-wt`)
Căn cứ đánh giá: `De_cuong_chi_tiet_CNTT-KLCN-336.docx` (bản trích xuất: `de_cuong_text.txt`)

## KẾT QUẢ TỔNG (chạy thật 2026-10-11, seed 42, tái lập được — mọi số liệu từ `results/`)

| Chỉ số | Trước (gốc, `results/before_original/`) | Sau (tối ưu, `results/after_optimized/`) |
|---|---|---|
| RoomNetLite test Accuracy | 100.00% (dữ liệu v1 quá dễ — lỗi #2) | **98.99%** |
| RoomNetLite test Macro F1 | 100.00% | **99.00%** |
| SimpleCNN baseline test Accuracy | — (chưa có) | 97.65% → **cải tiến +1.34pp** |
| K-fold 5 RoomNetLite | — | 97.80% ± 1.06% [96.88, 98.73] |
| K-fold 5 SimpleCNN | — | 97.49% ± 1.35% [96.30, 98.67] |
| Anomaly Hybrid F1 (protocol cũ: mọi ngày, có rò rỉ / sau: test riêng D13-D14) | 91.53% (490 seq) | **99.50%** (166 seq, P=100%, R=99%) |
| Anomaly AE-only F1 | 43.90% | **98.48%** |
| Độ trễ model / e2e | 0.0270 ms / — | 0.0309 ms / 0.0252 ms |
| RandomForest / MLP / kNN | 99.83 / 99.33 / 98.32% | 99.16 / 98.99 / 88.26% |
| Unit test | 43/43 | **43/43** · DB integrity ok, 0 FK violation |

## Giai đoạn 1 — Danh sách việc ✅
Đọc AGENTS.md + đề cương; lập PROGRESS.md; commit checkpoint `7ac19a8` (bảo vệ fix phiên 1-2).

## Giai đoạn 2 — Phân tích ✅ (phiên 1-2, đã được duyệt)
- Cấu trúc: src/smarthome (models, preprocessing, dataset, anomaly+MobileSensorFusion, inference, topology, activity, mobile_sensor, storage SQLite, metrics, alerts) · scripts pipeline · server Flask · android_collector · tests 43.
- Thuật toán: RoomNetLite (CE + CenterLoss 0.02 + JS temporal 0.05), GRU-AE (CE room + 0.7·Huber), TopologyFilter, RuleEngine; preprocessor fit chỉ trên train ✓; split session 6/1/1 ✓.
- 15 lỗi phát hiện — bảng đầy đủ ở mục "Bảng lỗi" bên dưới; đều kèm file:dòng.

## Giai đoạn 3 — Đo baseline gốc ✅ (2026-10-11)
- `git archive 7b2f120` (trừ android_collector/ do đường dẫn >260 ký tự) → `.tmp/baseline-wt`; chạy đủ 7 bước pipeline gốc, seed 42 → `results/before_original/` (5 JSON + runlogs + run_info.txt).
- Phát hiện подтвер nhận: dữ liệu v1 cho Accuracy 100% (giả tạo), anomaly protocol cũ có rò rỉ.

## Giai đoạn 4 — Sửa lỗi + đo "sau" ✅ (2026-10-11)
- **Fix A (lỗi #8 — rò rỉ đánh giá)**: train_anomaly.py tách train D01-D10 / threshold D11-D12 / test D13-D14 (không giao nhau); ghi `test_days` vào anomaly_threshold.json; evaluate_anomaly.py chỉ đánh giá test_days (tương thích JSON cũ).
- **Fix B (#13-14)**: config.yaml bổ sung early_stopping_patience/min_delta (10/1e-4 room, 15/1e-4 anomaly) + topology.self_weight 0.75 (trùng default — không đổi hành vi).
- **Fix C (#12)**: results/ chuẩn hóa (before_original + after_optimized + runlogs + run_info.txt + README.md tái lập).
- Đo "sau": full pipeline + K-fold 5 × 2 model → `results/after_optimized/` (9 JSON + 11 runlogs + run_info.txt).
- Kiểm chứng: 43/43 pytest pass; SQLite integrity ok, foreign_key_check 0 vi phạm (10 bảng).

## Giai đoạn 5 — Báo cáo ✅ (2026-10-11)
- `BAO_CAO_KET_QUA.docx` (Times New Roman 13, bảng 11): (a) việc đã làm; (b) 15 lỗi + cách sửa; (c) bảng trước/sau **sinh trực tiếp từ results/*.json** qua `make_report.py`; (d) đối chiếu 11 yêu cầu: 9 ĐẠT, 2 ĐẠT MỘT PHẦN, 1 CHƯA ĐẠT (dữ liệu thực tế — tuần 9-10); (e) tồn tại + đề xuất; + tiến độ 12 tuần.

## Bảng lỗi (file:dòng — mức độ — trạng thái)
| # | Lỗi | Vị trí | Mức độ | Trạng thái |
|---|-----|--------|--------|------------|
| 1 | Anomaly imbalance 7/loại vs 560 normal | generate_synthetic_data.py:111-135 | CAO | ✅ 50/loại + dwell ±20% |
| 2 | Dữ liệu v1 quá dễ (baseline 100%) | generate_synthetic_data.py:19-25,34 | CAO | ✅ v2 thực tế (98.99%) |
| 3 | Rò rỉ: ngày chọn ngưỡng nằm trong tập đánh giá | train_anomaly.py + evaluate_anomaly.py | CAO | ✅ Fix A — tách 3 phần |
| 4 | Thiếu baseline CNN cho so sánh trước/sau | scripts/train_room.py | CAO | ✅ SimpleCNN + kfold |
| 5 | Median nhiễu khi <3 AP | preprocessing.py:50-52 | TB | ✅ global fallback |
| 6 | Quantile 0.99 cố định | train_anomaly.py (cũ) | TB | ✅ grid search |
| 7 | Không early stopping | train_room/anomaly.py | TB | ✅ + Cosine restarts |
| 8 | Nighttime 0-5h | config.yaml:61-62 | TB | ✅ 22-6h |
| 9 | MobileSensorFusion chưa nối inference | inference.py | TB | ✅ process_mobile_sensor |
| 10 | Không có results/ có cấu trúc | (thiếu) | TB | ✅ Fix C |
| 11 | Thiếu đo e2e latency | evaluate_room.py | T | ✅ đã đo |
| 12 | self_weight hard-code | topology.py + config | T | ✅ vào config |
| 13 | Test set cân bằng giả tạo | room_test.csv | T | 📝 ghi nhận + kfold |
| 14 | Config thiếu khóa early_stopping | config.yaml | T | ✅ Fix B |
| 15 | Chưa có dữ liệu thực tế lab | data/ | CAO | ❌ CHƯA — tuần 9-10 theo kế hoạch |

## Còn lại (theo kế hoạch đề cương)
1. **Tuần 9-10**: thu thập RSSI thực tế ≥2 phòng lab (android_collector + /api/collect) → train_home.py → đánh giá lại trên dữ liệu thật; test Android end-to-end; kiểm thử té ngã với accelerometer thật; sinh anomaly phân bố đều các ngày.
2. **Tuần 11-12**: K-fold 10/leave-one-session-out trên dữ liệu thực; quantization/pruning nếu cần edge; hoàn thiện demo + slide.

## Vị trí kết thúc phiên
5/5 giai đoạn hoàn thành. Bài toán "tối ưu + sửa lỗi + báo cáo đối chiếu đề cương trên dữ liệu mô phỏng" đã đóng; bước kế tiếp bắt buộc cần **thiết bị/thu thập thực tế** (ngoài phạm vi phần mềm).
