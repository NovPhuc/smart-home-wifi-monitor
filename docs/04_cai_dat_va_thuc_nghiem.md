# Chương 4: Cài đặt và thực nghiệm

## 4.1. Môi trường thực hiện

- **Router WiFi**: gia dụng (TP-Link, ASUS, v.v.)
- **Smartphone**: Android 8+ với quyền Wi-Fi và Location
- **Backend**: Python 3.10+, PyTorch, Flask
- **Frontend**: HTML/CSS/JS dashboard real-time

## 4.2. Thu thập dữ liệu

### Dữ liệu thật (Android)
1. Mở app Android Collector
2. Chọn phòng và bấm "COLLECT ONE SCAN"
3. Dữ liệu được ghi vào `data/raw/android_scans.jsonl`
4. Chuyển sang CSV: `python scripts/jsonl_to_csv.py`

### Dữ liệu mô phỏng
```bash
python scripts/generate_synthetic_data.py
python scripts/prepare_data.py
```

## 4.3. Huấn luyện mô hình

```bash
python scripts/train_room.py
python scripts/evaluate_room.py
python scripts/train_baselines.py
python scripts/train_anomaly.py
python scripts/evaluate_anomaly.py
```

## 4.4. Đánh giá

### RoomNet-Lite
- Accuracy
- Macro F1-score
- Confusion matrix
- Inference latency

### Anomaly Detection
- Precision / Recall / F1
- False alarms/day
- Detection delay

## 4.5. Kịch bản thử nghiệm

- Normal: di chuyển bình thường giữa các phòng
- Anomaly: đứng yên lâu, chuyển phòng không hợp lý, hoạt động ban đêm
