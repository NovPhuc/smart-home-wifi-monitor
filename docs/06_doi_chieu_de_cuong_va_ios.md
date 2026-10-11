# Đối chiếu đề cương và phương án iPhone

Tài liệu này ánh xạ các tiêu chí trong đề cương KLCN với thành phần đã cài đặt. Trạng thái "sẵn sàng" nghĩa là code và luồng kiểm thử đã có; không đồng nghĩa kết quả dữ liệu tổng hợp được dùng thay cho thực nghiệm thật.

## Ma trận đáp ứng tiêu chí

| Tiêu chí đề cương | Thành phần thực hiện | Trạng thái |
|---|---|---|
| Tổng quan Smart Home, quyền riêng tư và người cao tuổi | `docs/01_tong_quan_va_nhu_cau.md` | Sẵn sàng |
| Khảo sát room-level fingerprinting và phát hiện bất thường | `docs/02_khao_sat_phuong_phap.md` | Sẵn sàng |
| Mô tả RSSI, 1D-CNN, Autoencoder và ví dụ | `docs/03_phuong_phap_de_xuat.md`, notebooks | Sẵn sàng |
| Tiền xử lý fingerprint | Absolute RSSI, Relative RSSI, Missing Mask trong `preprocessing.py` | Sẵn sàng |
| Phân loại phòng CNN/1D-CNN nhẹ | `RoomNetLite` và pipeline train/evaluate | Sẵn sàng |
| Thành phần cải tiến | Bayesian topology filter, relative RSSI, center/temporal loss | Sẵn sàng |
| Phát hiện bất thường | GRU Autoencoder kết hợp rule engine | Sẵn sàng |
| Phát hiện bất động/chuyển động | `ActivityMonitor` từ biến động RSSI | Sẵn sàng |
| Bổ sung cảm biến điện thoại | `MobileSensorMonitor` và `/api/sensor` | Sẵn sàng |
| Accuracy và Macro F1 phân loại phòng | `evaluate_room.py`, `models/room_test_metrics.json` | Sẵn sàng |
| Precision/Recall/F1 bất thường | `evaluate_anomaly.py`, `models/anomaly_test_metrics.json` | Sẵn sàng |
| Đo độ trễ thời gian thực | `mean_inference_ms_per_sample`, `/api/metrics` | Sẵn sàng |
| So sánh baseline | kNN, Random Forest, MLP trong `train_baselines.py` | Sẵn sàng |
| Dashboard Flask | Sơ đồ phòng, trạng thái, timeline, cảnh báo, metric | Sẵn sàng |
| Tổ chức lưu kết quả | `models/*.json`, `data/processed/*.jsonl` | Sẵn sàng |
| Thu RSSI Android | `android_collector/` và `/api/collect` | Sẵn sàng để thu |
| Dữ liệu thực tế tại nhà/lab | Cần tiến hành theo từng session/ngày và train lại model | Bắt buộc bổ sung |

## Kiến trúc đa thiết bị

```text
Android / ESP32 / Access Point
        │ nhiều BSSID + RSSI
        ▼
WiFi fingerprint → RoomNet-Lite → vị trí phòng
                                   │
iPhone PWA → gia tốc kế ───────────┤
                                   ▼
                     Activity + GRU-AE + Rules
                                   ▼
                     Dashboard / cảnh báo / metric
```

## Giới hạn iPhone

iOS không cung cấp API công khai cho ứng dụng thông thường quét toàn bộ access point và RSSI xung quanh. Một iPhone có thể đọc hạn chế thông tin mạng đang kết nối trong một số điều kiện entitlement/quyền, nhưng dữ liệu đó không đủ tạo fingerprint nhiều AP tương đương Android.

Ứng dụng vì vậy triển khai iPhone theo hai vai trò:

1. PWA cài từ Safari để xem vị trí, cảnh báo và kết quả thực nghiệm.
2. Sensor Bridge gửi gia tốc tuyến tính sau khi người dùng chủ động cấp quyền.

PWA cần HTTPS để cài đặt ổn định và xin quyền cảm biến. Safari có thể tạm dừng JavaScript khi ứng dụng xuống nền; không nên coi iPhone PWA là cảm biến nền liên tục.

## Điều kiện nghiệm thu thực nghiệm

- Thu nhiều session độc lập ở từng phòng, nhiều ngày và nhiều vị trí cầm điện thoại.
- Chia train/validation/test theo session hoặc ngày, không chia ngẫu nhiên từng dòng.
- Báo cáo Accuracy, Macro F1, confusion matrix và độ trễ trên test set thật.
- Với bất thường, báo cáo Precision, Recall, F1 và mô tả rõ cách tạo nhãn/kịch bản.
- So sánh RoomNet-Lite với kNN, Random Forest và MLP trên cùng cách chia dữ liệu.
- Không mô tả cảnh báo va chạm hoặc bất động là xác nhận té ngã y khoa.
