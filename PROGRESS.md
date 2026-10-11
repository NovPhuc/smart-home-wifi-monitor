# PROGRESS — Khóa luận 336 (CNTT-KLCN-336)

Phiên làm việc: 2026-10-11 (phiên 3)
Nhánh git: `fix/optimize-training` · Commit gốc (trước tối ưu): `7b2f120`
Sao lưu dữ liệu gốc: `backup_original/` (wifi_fingerprints.csv, location_events.csv, config.yaml)
Căn cứ đánh giá: `De_cuong_chi_tiet_CNTT-KLCN-336.docx` (bản trích xuất: `de_cuong_text.txt`)

## VỊ TRÍ HIỆN TẠI (để tiếp tục nếu bị ngắt)
Đang ở: **Giai đoạn 3 — Đo baseline gốc** (chạy pipeline tại commit `7b2f120` trong git worktree `.tmp/baseline-wt`, kết quả lưu vào `results/before_original/`).

## Giai đoạn 1 — Danh sách việc ✅
- [x] Đọc AGENTS.md, đề cương (trích xuất .docx → de_cuong_text.txt)
- [x] Lập PROGRESS.md (file này)
- [ ] Commit checkpoint trạng thái hiện tại (bảo vệ các sửa lỗi từ phiên 1-2)
- [ ] Giai đoạn 3: Đo baseline gốc → `results/before_original/`
- [ ] Giai đoạn 4: Sửa 3 lỗi còn lại (A: rò rỉ đánh giá anomaly, B: config keys, C: results/ có cấu trúc)
- [ ] Giai đoạn 4: Đo "sau" → `results/after_optimized/` (seed 42 cố định)
- [ ] K-fold 5-fold cho RoomNetLite + SimpleCNN
- [ ] Chạy 43 unit test + PRAGMA integrity_check DB
- [ ] Giai đoạn 5: Viết BAO_CAO_KET_QUA.docx (Times New Roman 13)
- [ ] Cập nhật PROGRESS.md lần cuối + commit

## Giai đoạn 2 — Phân tích ✅ (đã trình bày và được duyệt ở phiên 1-2)

### Cấu trúc project
- `src/smarthome/` — thư viện lõi: models/ (RoomNetLite 1D-CNN, SimpleCNN baseline, GRU Autoencoder), preprocessing.py, dataset.py, anomaly.py (RuleEngine, OnlineAnomalyDetector, MobileSensorFusion), inference.py, topology.py (TopologyFilter), activity.py, mobile_sensor.py, storage.py (SQLite), metrics.py, alerts.py
- `scripts/` — pipeline: generate_synthetic_data → prepare_data → train_room/evaluate_room → train_simple_cnn/evaluate_simple_cnn → train_anomaly/evaluate_anomaly → train_baselines → evaluate_kfold
- `data/` — raw (4800 mẫu WiFi, 8 session, 5 phòng, 12 AP), processed (split 6/1/1 session), anomaly (location_events.csv), smarthome.db (SQLite)
- `server/app.py` — Flask dashboard + REST API; `android_collector/` — app thu thập
- `tests/` — 43 unit test

### Thuật toán huấn luyện (đã kiểm tra)
- **RoomNetLite**: stem → depthwise → pointwise → pool → embedding → classifier. Loss = CE + 0.02·CenterLoss + 0.05·JS(self-consistency). AdamW lr=1e-3, wd=1e-4, CosineAnnealingWarmRestarts, early stopping patience=10.
- **GRU-AE**: encoder GRU(48) → latent tanh(24) → decoder GRU → out. Loss = CE (room one-hot) + 0.7·Huber (continuous). Ngưỡng = quantile reconstruction error trên validation, grid search [0.90–0.995].
- **Tiền xử lý**: RSSI → (absolute [0,1], relative [-1,1] so với median visible, mask) × 12 AP = 36 chiều; missing = −100; fallback global_median khi < 3 AP hiển thị. Preprocessor fit **chỉ trên train** (không rò rỉ).
- **Chia dữ liệu**: theo session (S01–S06 train / S07 val / S08 test) — không giao nhau ✓. Anomaly: theo ngày.
- **Mất cân bằng lớp**: dữ liệu phòng cân bằng (960/phòng); dữ liệu anomaly gốc mất cân bằng nghiêm trọng (7 mẫu/loại vs 560 normal) → đã sửa.
- **Chỉ số**: Accuracy, macro-F1, confusion matrix (phòng); Precision/Recall/F1 (anomaly, ae_only + hybrid); mean_inference_ms + e2e latency.

### Cơ sở dữ liệu (SQLite smarthome.db, schema v2)
- Bảng: users, homes, rooms (_name_key chuẩn hóa NFC lowercase), collector_devices, collection_sessions, wifi_scans, predictions, sensor_samples, alerts; FK ON DELETE CASCADE; index theo (home_id, timestamp).
- Toàn vẹn: sẽ chạy PRAGMA integrity_check + foreign_key_check ở Giai đoạn 4.

### Bảng lỗi phát hiện (file:dòng — mức độ — trạng thái)
| # | Lỗi | Vị trí | Mức độ | Trạng thái |
|---|-----|--------|--------|------------|
| 1 | Dữ liệu anomaly mất cân bằng nghiêm trọng (7/loại vs 560 normal) | scripts/generate_synthetic_data.py:111-135 | CAO | ✅ Đã sửa (phiên 2): 50 mẫu/loại + biến thiên dwell ±20% |
| 2 | Thiếu baseline CNN đơn giản để so sánh "trước/sau cải tiến" (yêu cầu đề cương) | scripts/train_room.py | CAO | ✅ Đã sửa (phiên 2): SimpleCNN + train/evaluate_simple_cnn.py + kfold |
| 3 | Median relative-feature nhiễu khi < 3 AP hiển thị | src/smarthome/preprocessing.py:50-52 | TRUNG BÌNH | ✅ Đã sửa (phiên 1): fallback global_median/global_std |
| 4 | Ngưỡng anomaly quantile 0.99 hard-code, không validate | scripts/train_anomaly.py (cũ:97-98) | TRUNG BÌNH | ✅ Đã sửa (phiên 1): grid search [0.90–0.995] trên val normal+anomaly |
| 5 | Train cố định 35 epochs, không early stopping | scripts/train_room.py:68, train_anomaly.py:77 | TRUNG BÌNH | ✅ Đã sửa (phiên 1): early stopping + CosineAnnealingWarmRestarts |
| 6 | Nighttime 0–5h không thực tế cho giám sát người cao tuổi | config.yaml:61-62 | TRUNG BÌNH | ✅ Đã sửa (phiên 2): 22–6h |
| 7 | MobileSensorFusion chưa nối vào inference pipeline | src/smarthome/inference.py | TRUNG BÌNH | ✅ Đã sửa (phiên 1): process_mobile_sensor + fuse_alert nhận mobile_reasons |
| 8 | **Rò rỉ đánh giá anomaly: các ngày dùng chọn ngưỡng (D13-D14) nằm trong tập đánh giá** | scripts/train_anomaly.py:84-89, scripts/evaluate_anomaly.py:27,40 | **CAO** | 🔧 Sẽ sửa trong Giai đoạn 4 phiên này (Fix A) |
| 9 | Độ trễ chỉ đo model forward, thiếu e2e | scripts/evaluate_room.py:70-76 | THẤP | ✅ Đã sửa (phiên 1): thêm mean_e2e_latency_ms_per_sample |
| 10 | topology self_weight hard-code 0.75 | src/smarthome/topology.py:5,26 | THẤP | ✅ Đã sửa (phiên 1): config topology.self_weight (script đọc config) |
| 11 | Test set cân bằng hoàn hảo, không phản ánh thực tế | data/processed/room_test.csv | THẤP | 📝 Ghi nhận — giảm thiên lệch bằng K-fold CV |
| 12 | **Chưa có results/ lưu chỉ số có cấu trúc** (đề cương: "cấu trúc lưu trữ kết quả có tổ chức") | (thiếu) | TRUNG BÌNH | 🔧 Sẽ làm trong phiên này (Fix C) |
| 13 | config.yaml thiếu khóa early_stopping_patience/min_delta và topology.self_weight (script dùng default .get()) | config.yaml | THẤP | 🔧 Sẽ làm (Fix B — chỉ rõ ràng tài liệu, không đổi hành vi) |
| 14 | Chưa có dữ liệu thực tế tại lab (đề cương mục 6) | data/ | CAO | ❌ CHƯA ĐẠT — cần thu thập thực tế (tuần 9-10 theo kế hoạch) |

## Giai đoạn 3 — Đo baseline gốc ⏳
- Phương pháp: `git worktree add --detach .tmp/baseline-wt 7b2f120` (code + dữ liệu gốc, không ảnh hưởng cây làm việc) → chạy pipeline: generate → prepare → train_room → evaluate_room → train_anomaly → evaluate_anomaly → train_baselines → copy metrics vào `results/before_original/` + run_info.txt → remove worktree.
- Seed cố định 42 (config.yaml gốc). Python 3.14.5, torch CPU.

## Giai đoạn 4 — Sửa lỗi phiên này + đo "sau" ⏳
- **Fix A (lỗi #8 — quan trọng nhất)**: tách 3 phần KHÔNG giao nhau cho anomaly: train D01-D10 (AE, chỉ normal) / threshold D11-D12 (normal + anomaly để chọn ngưỡng) / test D13-D14 (chỉ dùng để đánh giá, ghi `test_days` vào anomaly_threshold.json; evaluate_anomaly.py lọc theo đó, tương thích ngược với JSON cũ). → loại bỏ rò rỉ "chọn ngưỡng trên chính dữ liệu đánh giá".
- **Fix B (#13)**: thêm lại khóa `early_stopping_patience/min_delta` (10/1e-4 room, 15/1e-4 anomaly) và `topology.self_weight: 0.75` vào config.yaml — trùng giá trị default mà script đang dùng, không đổi hành vi.
- **Fix C (#12)**: tạo `results/` (README + before_original/ + after_optimized/ + run_info.txt mỗi bên).
- Đo "sau": chạy lại toàn bộ pipeline (seed 42) với Fix A/B; kfold 5-fold × 2 model; pytest 43 test; PRAGMA integrity DB.

## Giai đoạn 5 — Báo cáo ⏳
- `BAO_CAO_KET_QUA.docx`: (a) việc đã làm; (b) lỗi + cách sửa; (c) bảng trước/sau **đọc trực tiếp từ results/*.json** (không nhập tay số liệu); (d) đối chiếu 11 yêu cầu đề cương (Đạt/Đạt một phần/Chưa đạt + bằng chứng đường dẫn + số liệu); (e) tồn tại + đề xuất; + bảng tiến độ 12 tuần. Font Times New Roman 13 (bảng 11-12).

## Ghi chú ràng buộc đang áp dụng
- Làm trên nhánh `fix/optimize-training` (đã có từ phiên 1), dữ liệu gốc trong `backup_original/` và commit gốc `7b2f120` không bị ghi đè (baseline chạy trong worktree riêng).
- Không git push. Không sửa/xóa bản ghi dữ liệu, không đổi schema DB trong phiên này.
- Số liệu trong báo cáo chỉ lấy từ JSON kết quả chạy thật trong `results/`.
