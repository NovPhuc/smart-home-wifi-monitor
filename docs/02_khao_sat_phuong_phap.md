# Chương 2: Khảo sát các phương pháp

## 2.1. WiFi Fingerprinting

- **Định vị mức phòng**: sử dụng đặc trưng RSSI từ các AP có sẵn
- **Tiền xử lý**: absolute RSSI, relative RSSI, visibility mask
- **Mô hình học**: kNN, Random Forest, MLP, CNN, RNN

## 2.2. Phát hiện bất thường di chuyển

- **Dwell-time analysis**: thời gian đứng yên bất thường
- **Transition analysis**: chuyển phòng phi vật lý
- **Trajectory modeling**: học chuỗi hành vi bình thường bằng autoencoder

## 2.3. So sánh với các phương pháp hiện có

| Phương pháp | Ưu điểm | Nhược điểm |
|---|---|---|
| Camera-based | Độ chính xác cao | Xâm phạm riêng tư, chi phí cao |
| Wearable sensors | Theo dõi liên tục | Phải đeo, pin hạn chế |
| WiFi sensing | Không xâm phạm, tận hưởng hạ tầng có sẵn | Phụ thuộc môi trường, cần tinh chỉnh |
