# Chương 3: Phương pháp đề xuất

## 3.1. Kiến trúc tổng thể

```
Android WiFi Collector
       │ RSSI
       ▼
Absolute + Relative RSSI + Missing Mask
       │
       ▼
RoomNet-Lite (1D-CNN + Depthwise Sep)
       │ probabilities
       ▼
Topology-aware Bayesian Filter
       │ room sequence
       ├───────────────┐
       ▼               ▼
GRU Autoencoder    Rule Engine
       │               │
       └──────┬────────┘
              ▼
       NORMAL / WARNING / CRITICAL
```

## 3.2. Mô hình phân loại phòng (RoomNet-Lite)

### Kiến trúc
- **Input**: `[B, 3M, T]` với M số AP, T window size
- **Stem**: Conv1D + BatchNorm + ReLU
- **Depthwise**: Depthwise Conv1D + BatchNorm + ReLU
- **Pointwise**: 1x1 Conv + BatchNorm + ReLU
- **Pool**: Adaptive Avg Pool 1D
- **Embedding**: Linear + ReLU + Dropout
- **Classifier**: Linear → `num_rooms`

### Hàm mất mát
```
L = CE + λ_center × CenterLoss + λ_temporal × JSConsistency
```

## 3.3. Mô-đun phát hiện bất thường (GRU Autoencoder)

### Kiến trúc
- **Encoder**: GRU → Linear → latent
- **Decoder**: Linear → GRU → Linear reconstruction
- **Input**: room one-hot + normalized dwell + sin/cos time + confidence

### Hàm mất mát
```
L_AE = α × room_CE + β × Huber(continuous_features)
```

### Ngưỡng bất thường
```
Threshold = Q_0.99(normal_validation_scores)
```

## 3.4. Rule Engine

- **Dwell-time**: so sánh với ngưỡng tối đa theo phòng
- **Impossible transition**: kiểm tra topology căn nhà
- **Nighttime behavior**: phát hiện chuyển động bất thường ban đêm

## 3.5. Fusion

Kết hợp điểm bất thường từ GRU-AE và rule engine để tạo mức cảnh báo:
- `NORMAL`: không bất thường
- `WARNING`: bất thường từ rule hoặc AE
- `CRITICAL`: cả rule và AE cùng kích hoạt
