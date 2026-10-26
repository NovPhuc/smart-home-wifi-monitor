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

## Phiên 4 (2026-10-23): chia sẻ nhà + tự tìm máy chủ
Yêu cầu: nhiều tài khoản theo dõi 1 nhà qua mã 6 số; app điện thoại tự tìm IP máy chủ qua tài khoản, không gõ IP.

Đã làm (tất cả đã chạy thật, pytest 47/47 + assembleDebug BUILD SUCCESSFUL):
- `src/smarthome/storage.py`: thêm bảng `home_shares` + `home_members`; `list_homes`/`get_home` tính cả nhà được chia sẻ (role owner/member); hàm create_share_code (rotate, TTL 24h), active_share, revoke_share_code, join_home_by_code (idempotent), list/remove_member.
- `server/app.py`: helper `require_owned_home()` + `require_mutation_context()` — thành viên "chỉ xem" (status/history/alerts/config/metrics/rooms GET), mọi ghi (phòng, thiết bị, collect, scan, sensor, demo, train, reset, export) về owner; endpoint mới GET/POST/DELETE `/api/homes/<id>/share`, GET/DELETE `/api/homes/<id>/members[/<uid>]`, POST `/api/homes/join`; login trả về user+homes+active_home.
- Quảng bá mDNS `_antam._tcp` khi chạy `server/app.py` (zeroconf; MATN_ASCII do console). Xác nhận chạy thật: "Dang quang ba _antam._tcp tren cong 5000".
- Web: nút "Chia sẻ / tham gia" (dialog shareDialog: nhập mã tham gia; tạo/rotate/thu hồi mã + danh sách thành viên); member-mode ẩn khu quản trị (account.css).
- Android `MainActivity.kt` + `activity_main.xml`: NSD dò `_antam._tcp.` tự điền URL máy chủ; đăng nhập cookie (java.net.CookieManager, khôi phục phiên từ SharedPreferences); tham gia nhà bằng mã; chủ nhà tạo mã chia sẻ ngay trên app; token ghép nối trở thành tùy chọn.
- 4 test API mới (share-flow quyền member, mã không hợp lệ/hết hạn/rotate, mã hết hạn theo thời gian, gỡ thành viên) → 43 → 47 test, tất cả pass.
- Sửa môi trường build (máy này): `local.properties` sdk.dir → `E:\Android`; `gradle.properties` org.gradle.java.home → `C:/Program Files/Android/Android Studio/jbr`; thiếu import `java.net.CookieHandler` trong MainActivity.kt (lỗi code thật, đã sửa).

Cảnh báo còn lại:
- `resolveService`/`NsdServiceInfo.host`/`WifiManager.startScan` deprecated (chỉ warning, hoạt động tới API 34; migrate khi cần).
- Session cookie khôi phục theo SECRET_KEY của server; đổi key → app phải đăng nhập lại.
- Mã chia sẻ 6 số không có rate-limit thu thử (khoảng không gian 10^6, TTL 24h) — chấp nhận được cho nội bộ gia đình; cần lockout nếu mở rộng.
