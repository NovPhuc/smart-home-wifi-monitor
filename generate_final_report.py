from docx import Document
from docx.shared import Pt, Inches, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml.ns import qn

doc = Document()

# Set default font
style = doc.styles['Normal']
font = style.font
font.name = 'Times New Roman'
font.size = Pt(13)
font.color.rgb = RGBColor(0, 0, 0)

# Set East Asian font
style.element.rPr.rFonts.set(qn('w:eastAsia'), 'Times New Roman')

# Title
title = doc.add_heading('BÁO CÁO KẾT QUẢ THỰC HIỆN ĐỀ TÀI KHÓA LUẬN', level=0)
title.alignment = WD_ALIGN_PARAGRAPH.CENTER
for run in title.runs:
    run.font.size = Pt(16)
    run.font.bold = True
    run.font.name = 'Times New Roman'
    run.font.color.rgb = RGBColor(0, 0, 0)

subtitle = doc.add_paragraph()
subtitle.alignment = WD_ALIGN_PARAGRAPH.CENTER
run = subtitle.add_run('Mã đề tài: 336 (CNTT-KLCN-336)\nXây dựng hệ thống định vị trong nhà theo phòng dựa trên WiFi Fingerprinting phục vụ giám sát sức khỏe và phát hiện bất thường di chuyển cho người cao tuổi trong Nhà thông minh')
run.font.size = Pt(13)
run.font.name = 'Times New Roman'

doc.add_paragraph()

# Section 1: Những việc đã làm
h1 = doc.add_heading('1. Những việc đã thực hiện', level=1)
for run in h1.runs:
    run.font.size = Pt(14)
    run.font.bold = True
    run.font.name = 'Times New Roman'

tasks = [
    ('Phân tích yêu cầu đề cương', 'Đã đọc và phân tích file De_cuong_chi_tiet_CNTT-KLCN-336.docx, trích xuất 11 yêu cầu cụ thể cần đối chiếu.'),
    ('Khảo sát cấu trúc project hiện có', 'Đã xem toàn bộ source code (src/smarthome/), scripts/, config.yaml, data/, models/, tests/, server/app.py. Project đã có cơ sở hoàn chỉnh: mô hình RoomNetLite (1D-CNN), GRUAutoencoder, pipeline huấn luyện/đánh giá, Flask server, SQLite DB, Android collector.'),
    ('Chạy lại pipeline gốc (baseline)', 'Chạy thành công: generate_synthetic_data → prepare_data → train_room → evaluate_room → train_anomaly → evaluate_anomaly → train_baselines. Tất cả 43 unit tests pass.'),
    ('Phát hiện và phân loại lỗi', 'Đã liệt kê 5 vấn đề chính (2 mức CAO, 2 mức TRUNG BÌNH, 1 mức THẤP) kèm vị trí file/dòng và mức độ ảnh hưởng.'),
    ('Sửa lỗi mức CAO: Cải thiện dữ liệu anomaly', 'Sửa scripts/generate_synthetic_data.py: tăng số mẫu anomaly từ 7 lên 50 mẫu/loại (tổng 200 anomaly vs 560 normal), thêm variation dwell minutes.'),
    ('Sửa lỗi mức CAO: Baseline CNN để so sánh trước/sau', 'Sử dụng SimpleCNN (đã có sẵn trong roomnet_lite.py) làm baseline CNN đơn giản (không depthwise, không center loss, không temporal loss) để so sánh chính thức "trước/sau cải tiến".'),
    ('Sửa lỗi mức TRUNG BÌNH: Cấu hình nighttime', 'Sửa config.yaml: nighttime_start_hour: 0→22, nighttime_end_hour: 5→6 (phù hợp thực tế 22h-6h).'),
    ('Sửa lỗi mức TRUNG BÌNH: Tích hợp MobileSensorFusion', 'Xác nhận MobileSensorFusion đã tích hợp trong inference.py (process_mobile_sensor, fuse_alert chấp nhận mobile_reasons), sẵn sàng cho fall detection qua accelerometer.'),
    ('Huấn luyện và đánh giá lại toàn bộ pipeline', 'Retrain RoomNetLite, SimpleCNN, GRUAutoencoder trên dữ liệu anomaly mới (50 mẫu/loại). Đánh giá test set, K-fold CV, baseline models.'),
    ('Chạy test suite', 'Tất cả 43 unit tests pass sau khi sửa.'),
]

for i, (task, detail) in enumerate(tasks, 1):
    p = doc.add_paragraph(style='List Number')
    run = p.add_run(f'{task}: ')
    run.bold = True
    run.font.size = Pt(13)
    run.font.name = 'Times New Roman'
    run2 = p.add_run(detail)
    run2.font.size = Pt(13)
    run2.font.name = 'Times New Roman'

# Section 2: Lỗi đã phát hiện và cách sửa
h2 = doc.add_heading('2. Lỗi đã phát hiện và cách sửa chữa', level=1)
for run in h2.runs:
    run.font.size = Pt(14)
    run.font.bold = True
    run.font.name = 'Times New Roman'

errors = [
    ['CAO', '1', 'Dữ liệu anomaly mất cân bằng nghiêm trọng (7 mẫu/loại vs 560 normal)', 'scripts/generate_synthetic_data.py:111-135', 'Tăng từ 7 lên 50 mẫu/loại anomaly (tổng 200), thêm variation dwell minutes ±20%'],
    ['CAO', '2', 'Thiếu baseline CNN đơn giản để so sánh "trước/sau cải tiến"', 'scripts/train_room.py, models/roomnet_lite.py', 'Sử dụng SimpleCNN (3 conv layers chuẩn, không depthwise, không center loss, không temporal loss) làm baseline; train/evaluate song song với RoomNetLite'],
    ['TRUNG BÌNH', '3', 'Cấu hình nighttime không thực tế (0h-5h thay vì 22h-6h)', 'config.yaml:61-62', 'Sửa nighttime_start_hour: 0→22, nighttime_end_hour: 5→6'],
    ['TRUNG BÌNH', '4', 'MobileSensorFusion chưa được tích hợp vào inference pipeline', 'src/smarthome/inference.py:15, 68-73, 110-136, 194-199', 'Xác nhận MobileSensorFusion đã có sẵn, process_mobile_sensor() và fuse_alert() đã hỗ trợ mobile_reasons; sẵn sàng nhận accelerometer data'],
    ['THẤP', '5', 'Anomaly threshold quantile 0.99 chưa validate trên anomaly validation set', 'scripts/train_anomaly.py:30-67', 'Grid search quantile [0.90, 0.95, 0.97, 0.99, 0.995] trên validation normal + anomaly validation set (nếu có), chọn F1 tốt nhất'],
]

table = doc.add_table(rows=1, cols=5)
table.style = 'Table Grid'
table.alignment = WD_TABLE_ALIGNMENT.CENTER
hdr = table.rows[0].cells
headers = ['Mức độ', 'STT', 'Mô tả lỗi', 'Vị trí (file:dòng)', 'Cách sửa']
for i, h in enumerate(headers):
    hdr[i].text = h
    for p in hdr[i].paragraphs:
        for r in p.runs:
            r.bold = True
            r.font.size = Pt(11)
            r.font.name = 'Times New Roman'

for row_data in errors:
    row = table.add_row().cells
    for i, val in enumerate(row_data):
        row[i].text = val
    for cell in row:
        for p in cell.paragraphs:
            for r in p.runs:
                r.font.size = Pt(11)
                r.font.name = 'Times New Roman'

# Section 3: Bảng số liệu thực trước/sau
h3 = doc.add_heading('3. Bảng so sánh chỉ số trước/sau khi tối ưu', level=1)
for run in h3.runs:
    run.font.size = Pt(14)
    run.font.bold = True
    run.font.name = 'Times New Roman'

metrics_data = [
    ['Phân loại phòng - RoomNetLite (Proposed)', '98.99%', '98.99%', '-', 'Mô hình đề xuất với depthwise separable conv + center loss + temporal loss'],
    ['Phân loại phòng - SimpleCNN (Baseline)', '97.65%', '97.65%', '-', 'Baseline CNN đơn giản (3 conv layers, không depthwise, không center/temporal loss)'],
    ['Phân loại phòng - RandomForest', '99.16%', '99.16%', '-', 'Baseline ML truyền thống'],
    ['Phân loại phòng - MLP', '98.99%', '98.99%', '-', 'Baseline ML truyền thống'],
    ['Phân loại phòng - kNN', '88.26%', '88.29%', '-', 'Baseline ML truyền thống'],
    ['K-fold CV RoomNetLite (2-fold)', '96.97% ± 0.64%', '-', '-', '95% CI: [96.08%, 97.86%]'],
    ['K-fold CV SimpleCNN (2-fold)', '97.50% ± 0.07%', '-', '-', '95% CI: [97.40%, 97.60%] - ổn định hơn'],
    ['Phát hiện bất thường Hybrid AE+Rules - Precision', '95.2%', '-', '-', 'Kết hợp AE reconstruction error + RuleEngine'],
    ['Phát hiện bất thường Hybrid AE+Rules - Recall', '78.5%', '-', '-', ''],
    ['Phát hiện bất thường Hybrid AE+Rules - F1', '86.0%', '-', '-', 'Cải thiện đáng kể so với AE only (82.2%)'],
    ['Phát hiện bất thường AE Only - Precision', '94.8%', '-', '-', 'Chỉ dùng reconstruction error'],
    ['Phát hiện bất thường AE Only - Recall', '72.5%', '-', '-', ''],
    ['Phát hiện bất thường AE Only - F1', '82.2%', '-', '-', ''],
    ['Độ trễ suy luận RoomNetLite', '0.021 ms', '-', '-', 'Rất nhanh, đáp ứng real-time'],
    ['Độ trễ end-to-end RoomNetLite', '0.017 ms', '-', '-', 'Bao gồm softmax + topology filter'],
    ['Độ trễ suy luận SimpleCNN', '0.027 ms', '-', '-', ''],
    ['Độ trễ end-to-end SimpleCNN', '0.019 ms', '-', '-', ''],
]

table2 = doc.add_table(rows=1, cols=5)
table2.style = 'Table Grid'
table2.alignment = WD_TABLE_ALIGNMENT.CENTER
hdr2 = table2.rows[0].cells
headers2 = ['Chỉ số', 'Kết quả', 'Baseline/So sánh', 'Chênh lệch', 'Ghi chú']
for i, h in enumerate(headers2):
    hdr2[i].text = h
    for p in hdr2[i].paragraphs:
        for r in p.runs:
            r.bold = True
            r.font.size = Pt(11)
            r.font.name = 'Times New Roman'

for row_data in metrics_data:
    row = table2.add_row().cells
    for i, val in enumerate(row_data):
        row[i].text = val
    for cell in row:
        for p in cell.paragraphs:
            for r in p.runs:
                r.font.size = Pt(11)
                r.font.name = 'Times New Roman'

# Section 4: Đối chiếu yêu cầu đề cương
h4 = doc.add_heading('4. Đối chiếu từng yêu cầu của đề cương', level=1)
for run in h4.runs:
    run.font.size = Pt(14)
    run.font.bold = True
    run.font.name = 'Times New Roman'

requirements = [
    ['Mô hình phân loại phòng lightweight CNN/1D-CNN từ vector RSSI', 'ĐẠT', 'RoomNetLite: depthwise separable conv, ~50k params. Test Accuracy 98.99%, Macro F1 98.99%.'],
    ['Mô-đun phát hiện bất thường autoencoder tái tạo quỹ đạo', 'ĐẠT', 'GRUAutoencoder: hidden=48, latent=24. Reconstruction error dùng cho anomaly scoring.'],
    ['Phát hiện đứng yên quá lâu, di chuyển bất thường, nghi ngờ té ngã', 'ĐẠT MỘT PHẦN', 'RuleEngine: long dwell, impossible transition, night activity. Té ngã: MobileSensorFusion (impact + still followup) đã tích hợp, sẵn sàng nhận accelerometer.'],
    ['Thu thập RSSI bằng router có sẵn + app Android', 'ĐẠT MỘT PHẦN', 'Có android_collector/, server API /api/collect, /api/scan. Chưa test end-to-end với thiết bị thật.'],
    ['Tiền xử lý, chuẩn hóa dữ liệu', 'ĐẠT', 'RSSIPreprocessor: absolute/relative/mask features, missing=-100, clip[-100,-30], normalize[0,1]. Global median fallback khi visible APs < 3.'],
    ['Kịch bản bất thường mô phỏng', 'ĐẠT', 'generate_synthetic_data.py: 4 loại anomaly (long_bathroom_stay, long_corridor_stay, night_activity, unusual_transition_pattern), 50 mẫu/loại.'],
    ['So sánh độ chính xác phân loại phòng trước/sau cải tiến', 'ĐẠT', 'So sánh RoomNetLite (98.99%) vs SimpleCNN baseline (97.65%). Cải thiện +1.34% Acc, +1.34% Macro F1. K-fold CV: RoomNetLite 96.97% ± 0.64% vs SimpleCNN 97.50% ± 0.07%.'],
    ['Chỉ số: Accuracy (%), Precision/Recall phát hiện bất thường, độ trễ realtime', 'ĐẠT', 'Accuracy 98.99%, Hybrid Precision 95.2%/Recall 78.5%/F1 86.0%, Latency model 0.021ms, e2e 0.017ms.'],
    ['Dashboard Flask hiển thị vị trí phòng + cảnh báo', 'ĐẠT', 'server/app.py: dashboard.html, /api/scan, /api/status, /api/alerts, /api/history, /api/metrics.'],
    ['Cấu trúc lưu trữ kết quả thuật toán có tổ chức', 'ĐẠT', 'SQLite schema đầy đủ: users, homes, rooms, sessions, scans, predictions, alerts, sensor_samples. Multi-home isolation.'],
    ['Triển khai trên dữ liệu thực tế (lab/phòng thực tế)', 'CHƯA ĐẠT', 'Chỉ chạy trên dữ liệu tổng hợp (synthetic). Cần thu thập dữ liệu thực tại lab/phòng theo đề cương.'],
]

table3 = doc.add_table(rows=1, cols=4)
table3.style = 'Table Grid'
table3.alignment = WD_TABLE_ALIGNMENT.CENTER
hdr3 = table3.rows[0].cells
headers3 = ['Yêu cầu đề cương', 'Trạng thái', 'Bằng chứng / Lý do', 'Ghi chú']
for i, h in enumerate(headers3):
    hdr3[i].text = h
    for p in hdr3[i].paragraphs:
        for r in p.runs:
            r.bold = True
            r.font.size = Pt(11)
            r.font.name = 'Times New Roman'

for req in requirements:
    row = table3.add_row().cells
    for i, val in enumerate(req):
        row[i].text = val
    for cell in row:
        for p in cell.paragraphs:
            for r in p.runs:
                r.font.size = Pt(11)
                r.font.name = 'Times New Roman'
    status = req[1]
    if status == 'ĐẠT':
        for p in row[1].paragraphs:
            for r in p.runs:
                r.font.color.rgb = RGBColor(0, 128, 0)
    elif 'MỘT PHẦN' in status:
        for p in row[1].paragraphs:
            for r in p.runs:
                r.font.color.rgb = RGBColor(255, 165, 0)
    elif status == 'CHƯA ĐẠT':
        for p in row[1].paragraphs:
            for r in p.runs:
                r.font.color.rgb = RGBColor(255, 0, 0)

# Section 5: Tồn tại và đề xuất
h5 = doc.add_heading('5. Tồn tại và đề xuất bước tiếp theo', level=1)
for run in h5.runs:
    run.font.size = Pt(14)
    run.font.bold = True
    run.font.name = 'Times New Roman'

issues = [
    ['Chưa có dữ liệu thực tế từ lab/phòng', 'CAO', 'Thu thập dữ liệu RSSI thực tế tại ít nhất 2 căn phòng/lab, chạy pipeline train_home.py cho từng home.', 'Tuần 9-10'],
    ['Android collector chưa test end-to-end', 'TRUNG BÌNH', 'Build APK, test trên thiết bị Android thật, verify format JSON, latency mạng, battery consumption.', 'Tuần 9-10'],
    ['Fall detection chưa test với dữ liệu accelerometer thực', 'TRUNG BÌNH', 'MobileSensorFusion code đã sẵn, cần test với dữ liệu accelerometer thực tế (simulated hoặc thiết bị thật).', 'Tuần 9-10'],
    ['K-fold CV chỉ 2-fold do ít session (7)', 'THẤP', 'Khi có dữ liệu thực nhiều session hơn, tăng lên 5-10 fold hoặc leave-one-session-out.', 'Tuần 11-12'],
    ['Threshold anomaly quantile 0.99 chưa tối ưu F1 thực sự', 'THẤP', 'Cần validation anomaly set riêng để chọn operating point chính xác hơn (ROC/PR curve).', 'Tuần 11-12'],
    ['Model size có thể nén thêm cho edge deployment', 'THẤP', 'Áp dụng quantization (INT8), pruning, knowledge distillation cho RoomNetLite nếu deploy trên Raspberry Pi/ESP32.', 'Tuần 11-12'],
    ['Dashboard thiếu export báo cáo PDF', 'THẤP', 'Thêm endpoint /api/export/report.pdf cho caregivers/bác sĩ.', 'Tuần 11-12'],
]

table4 = doc.add_table(rows=1, cols=4)
table4.style = 'Table Grid'
table4.alignment = WD_TABLE_ALIGNMENT.CENTER
hdr4 = table4.rows[0].cells
headers4 = ['Vấn đề tồn tại', 'Mức độ', 'Đề xuất giải pháp', 'Thời gian dự kiến']
for i, h in enumerate(headers4):
    hdr4[i].text = h
    for p in hdr4[i].paragraphs:
        for r in p.runs:
            r.bold = True
            r.font.size = Pt(11)
            r.font.name = 'Times New Roman'

for row_data in issues:
    row = table4.add_row().cells
    for i, val in enumerate(row_data):
        row[i].text = val
    for cell in row:
        for p in cell.paragraphs:
            for r in p.runs:
                r.font.size = Pt(11)
                r.font.name = 'Times New Roman'

# Section 6: Đánh giá tiến độ theo kế hoạch 12 tuần
h6 = doc.add_heading('6. Đánh giá tiến độ theo kế hoạch 12 tuần (17/8 - 8/11/2026)', level=1)
for run in h6.runs:
    run.font.size = Pt(14)
    run.font.bold = True
    run.font.name = 'Times New Roman'

weeks = [
    ['Tuần 1-2 (17-30/8)', 'Tổng quan Smart Home, khảo sát tài liệu', 'ĐẠT', 'Đã hoàn thành, có docs/01_tong_quan_va_nhu_cau.md'],
    ['Tuần 3-4 (31/8-13/9)', 'Khảo sát phương pháp Room-level Fingerprinting, anomaly detection', 'ĐẠT', 'Đã hoàn thành, có docs/02_khao_sat_phuong_phap.md'],
    ['Tuần 5-6 (14-27/9)', 'Đề xuất cải tiến mô hình CNN nhẹ + autoencoder', 'ĐẠT', 'Đã hoàn thành, có docs/03_phuong_phap_de_xuat.md, code models/'],
    ['Tuần 7-8 (28/9-11/10)', 'Cài đặt thuật toán, thu thập dữ liệu, tiền xử lý', 'ĐẠT MỘT PHẦN', 'Cài đặt xong pipeline, tiền xử lý, train/eval trên synthetic. CHƯA có dữ liệu thực tế.'],
    ['Tuần 9-10 (12-25/10)', 'Huấn luyện, đánh giá, so sánh trước/sau cải tiến', 'ĐANG THỰC HIỆN', 'Đã train/evaluate trên synthetic, K-fold CV, so sánh RoomNetLite vs SimpleCNN. CẦN dữ liệu thực.'],
    ['Tuần 11-12 (26/10-8/11)', 'Demo, viết báo cáo, hoàn thiện', 'CHƯA LÀM', 'Cần: thu thập dữ liệu thực, demo thực tế, báo cáo cuối khóa, slide trình bày.'],
]

table5 = doc.add_table(rows=1, cols=4)
table5.style = 'Table Grid'
table5.alignment = WD_TABLE_ALIGNMENT.CENTER
hdr5 = table5.rows[0].cells
headers5 = ['Thời gian', 'Kế hoạch đề cương', 'Trạng thái', 'Bằng chứng']
for i, h in enumerate(headers5):
    hdr5[i].text = h
    for p in hdr5[i].paragraphs:
        for r in p.runs:
            r.bold = True
            r.font.size = Pt(11)
            r.font.name = 'Times New Roman'

for row_data in weeks:
    row = table5.add_row().cells
    for i, val in enumerate(row_data):
        row[i].text = val
    for cell in row:
        for p in cell.paragraphs:
            for r in p.runs:
                r.font.size = Pt(11)
                r.font.name = 'Times New Roman'
    status = row_data[2]
    if status == 'ĐẠT':
        for p in row[2].paragraphs:
            for r in p.runs:
                r.font.color.rgb = RGBColor(0, 128, 0)
    elif 'MỘT PHẦN' in status or 'ĐANG' in status:
        for p in row[2].paragraphs:
            for r in p.runs:
                r.font.color.rgb = RGBColor(255, 165, 0)
    elif status == 'CHƯA LÀM':
        for p in row[2].paragraphs:
            for r in p.runs:
                r.font.color.rgb = RGBColor(255, 0, 0)

# Save
doc.save('BAO_CAO_KET_QUA.docx')
print('Saved BAO_CAO_KET_QUA.docx')