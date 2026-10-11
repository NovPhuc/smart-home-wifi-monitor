# Smart Home WiFi Monitor — Định vị trong nhà theo phòng bằng WiFi Fingerprinting

Hệ thống **room-level indoor localization** bằng lightweight 1D-CNN kết hợp **GRU Autoencoder** phát hiện bất thường
quỹ đạo di chuyển (đứng yên quá lâu, di chuyển bất thường, nghi ngờ té ngã) — phục vụ giám sát an toàn cho người
cao tuổi trong nhà thông minh: **không camera, không thiết bị đeo**, tận dụng router WiFi sẵn có.

> Đề tài khóa luận CNTT mã 336 — Trường Đại học Công Thương TP. Hồ Chí Minh, HK 2026–2027.

## Kiến trúc

```
Android collector (quét WiFi + gia tốc kế)
        │  HTTPS
        ▼
Flask server  ──►  SQLite (multi-home: users, homes, rooms, wifi_scans, predictions, alerts)
   │   │   │
   │   │   └── MobileSensorFusion  (impact + immobility → cảnh báo té ngã)
   │   └────── GRU Autoencoder + RuleEngine  (reconstruction error + luật dwell/topology/đêm)
   └────────── RoomNetLite (1D-CNN depthwise separable) + TopologyFilter (HMM nhẹ)
        ▼
Dashboard web: vị trí theo phòng realtime + cảnh báo WARNING/CRITICAL
```

## Kết quả chính (seed 42, mọi số liệu tái lập được từ `results/`)

| Bài toán | Mô hình | Kết quả |
|---|---|---|
| Phân loại phòng (synthetic, test riêng) | RoomNetLite | Accuracy **98.99%**, Macro F1 99.00%, ~0.03 ms/mẫu |
| So sánh trước/sau cải tiến | SimpleCNN baseline | RoomNetLite **+1.34 pp** trên cùng dữ liệu/split |
| Kiểm định ngoài — UCI WIL (RSSI thật, 7 AP) | RoomNetLite | Accuracy **98.99%** |
| Kiểm định ngoài — UJIIndoorLoc (520 AP, 6 vùng) | RoomNetLite / RF | 81.12% / **92.36%** |
| Phát hiện bất thường (test tách riêng, đã chống rò rỉ) | Hybrid AE + Rules | Precision 100%, Recall 99%, F1 **99.50%** |
| Cross-validation | 5-fold theo session | 97.80% ± 1.06% (95% CI [96.88, 98.73]) |

## Quick start

```bash
pip install -r requirements.txt

# 1. Tạo dữ liệu mô phỏng + chia train/val/test
python scripts/generate_synthetic_data.py
python scripts/prepare_data.py

# 2. Huấn luyện + đánh giá
python scripts/train_room.py            # RoomNetLite
python scripts/train_simple_cnn.py      # baseline CNN
python scripts/train_anomaly.py         # GRU-AE + chọn ngưỡng
python scripts/evaluate_room.py
python scripts/evaluate_anomaly.py
python scripts/train_baselines.py       # kNN / RandomForest / MLP

# 3. Dashboard
python server/app.py                    # http://localhost:5000
```

Thu thập dữ liệu thật: ứng dụng Android trong `android_collector/` → `POST /api/collect` →
huấn luyện riêng cho từng căn nhà bằng `scripts/train_home.py`.

## Cấu trúc repo

```
src/smarthome/     # RoomNetLite, SimpleCNN, GRU-AE, preprocessing, storage (SQLite),
                   # inference realtime, topology filter, rule engine, sensor fusion
scripts/           # pipeline: generate → prepare → train → evaluate → kfold → convert external datasets
server/            # Flask REST API + dashboard
android_collector/ # ứng dụng Android thu thập RSSI
results/           # metrics JSON + runlogs + run_info (before/after + 2 external datasets)
tests/             # 43 unit tests
docs/              # tài liệu phân tích, khảo sát, phương pháp
```

## Ghi chú khoa học

- Chống rò rỉ đánh giá: preprocessor fit chỉ trên train; split theo session; tập test anomaly
  tách hoàn toàn khỏi tập chọn ngưỡng (`anomaly_threshold.json:test_days`).
- So sánh "trước/sau cải tiến": RoomNetLite (depthwise separable + center loss + temporal consistency)
  đối đầu SimpleCNN (3 conv chuẩn) trên cùng dữ liệu và cùng split.
- Trên fingerprint siêu chiều (520 AP — UJIIndoorLoc), RandomForest 92.36% > CNN nhẹ — hạn chế đã ghi nhận
  trong báo cáo, hướng cải thiện: lọc WAP hiếm, tăng hidden channels.

## Giấy phép

MIT — xem [LICENSE](LICENSE).
