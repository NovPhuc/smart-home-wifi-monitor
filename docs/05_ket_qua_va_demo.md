# Chương 5: Kết quả và Demo

## 5.1. Kết quả phân loại phòng

| Mô hình | Accuracy | Macro F1 |
|---|---|---|
| RoomNet-Lite | ~99.66% | ~99.67% |
| kNN | ~98.32% | - |
| Random Forest | ~99.83% | - |
| MLP | ~99.33% | - |

## 5.2. Kết quả phát hiện bất thường

| Phương pháp | Precision | Recall | F1 |
|---|---|---|---|
| GRU AE only | ~0.64 | - | - |
| Hybrid (AE + Rules) | ~0.77 | ~0.96 | ~0.86 |

## 5.3. Độ trễ xử lý

- RoomNet-Lite inference: < 50ms trên CPU
- End-to-end pipeline: < 100ms
- Phù hợp thời gian thực

## 5.4. Demo Dashboard

Chạy server:
```bash
$env:PYTHONPATH="src"
python server/app.py
```

Truy cập: `http://127.0.0.1:5000`

Chức năng:
- Hiển thị vị trí hiện tại theo phòng
- Đồ thị confidence
- Lịch sử di chuyển real-time
- Cảnh báo WARNING/CRITICAL
- Meter anomaly score
