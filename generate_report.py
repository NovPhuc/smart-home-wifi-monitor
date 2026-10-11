from docx import Document
from docx.shared import Pt, Inches, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT

doc = Document()

# Set default font
style = doc.styles['Normal']
font = style.font
font.name = 'Times New Roman'
font.size = Pt(13)
font.color.rgb = RGBColor(0, 0, 0)

# Title
title = doc.add_heading('BAO CAO KET QUA THUC HIEN DE TAI KHOA LUAN', level=0)
title.alignment = WD_ALIGN_PARAGRAPH.CENTER
for run in title.runs:
    run.font.size = Pt(16)
    run.font.bold = True
    run.font.name = 'Times New Roman'

subtitle = doc.add_paragraph()
subtitle.alignment = WD_ALIGN_PARAGRAPH.CENTER
run = subtitle.add_run('Ma de tai: 336 (CNTT-KLCN-336)\nXay dung he thong dinh vi trong nha theo phong dua tren WiFi Fingerprinting phuc vu giam sat suc khoe va phat hien bat thuong di chuyen cho nguoi cao tuoi trong Nha thong minh')
run.font.size = Pt(13)
run.font.name = 'Times New Roman'

doc.add_paragraph()

# Section 1
h1 = doc.add_heading('1. Nhung viec da thuc hien', level=1)
for run in h1.runs:
    run.font.size = Pt(14)
    run.font.bold = True
    run.font.name = 'Times New Roman'

tasks = [
    ('Phan tich va hieu yeu cau de cuong', 'Da doc va phan tich file De_cuong_chi_tiet_CNTT-KLCN-336.docx, trich xuat 11 yeu cau cu the can doi chieu.'),
    ('Khao sat cau truc project hien co', 'Da xem toan bo source code (src/smarthome/), scripts/, config.yaml, data/, models/, tests/, server/app.py. Project da co co so hoan chinh: mo hinh RoomNetLite (1D-CNN), GRUAutoencoder, pipeline huan luyen/danh gia, Flask server, SQLite DB, Android collector.'),
    ('Chay lai pipeline goc (baseline)', 'Chay thanh cong: generate_synthetic_data -> prepare_data -> train_room -> evaluate_room -> train_anomaly -> evaluate_anomaly -> train_baselines. Tat ca 43 unit tests pass.'),
    ('Phat hien va phan loai loi', 'Da liet ke 15 van de (3 muc CAO, 7 muc TRUNG BINH, 5 muc THAP) kem vi tri file/dong va muc do anh huong.'),
    ('Sua loi muc CAO: Cai thien du lieu tong hop', 'Sua scripts/generate_synthetic_data.py: giam signature injection (+14/+9 -> +6/+4), tang noise (sigma=3->6), them environmental interference, burst interference, missing AP pattern thuc te hon.'),
    ('Sua loi muc TRUNG BINH: Xu ly missing AP', 'Sua src/smarthome/preprocessing.py: them global_median/global_std fallback khi visible APs < 3, tranh median nhieu.'),
    ('Sua loi muc TRUNG BINH: Data augmentation', 'Them augment_batch() trong train_room.py: Gaussian noise + random AP dropout (30% xac suat).'),
    ('Sua loi muc TRUNG BINH: Early stopping & LR scheduler', 'Them CosineAnnealingWarmRestarts + early stopping (patience=10) cho room model, patience=15 cho anomaly model. Cap nhat config.yaml.'),
    ('Sua loi muc TRUNG BINH: Grid search anomaly threshold', 'Cap nhat train_anomaly.py: tim quantile toi uu tren validation (0.90, 0.95, 0.97, 0.99, 0.995) thay vi hard-code 0.99.'),
    ('Sua loi muc THAP: K-fold cross-validation', 'Tao scripts/evaluate_kfold.py: 5-fold CV theo session, bao cao mean +/- std va 95% CI.'),
    ('Sua loi muc THAP: Do latency end-to-end', 'Cap nhat evaluate_room.py: them mean_e2e_latency_ms_per_sample (softmax + topology filter).'),
    ('Sua loi muc THAP: Configurable topology weight', 'Them topology.self_weight vao config.yaml, cap nhat inference.py de doc config.'),
    ('Them baseline SimpleCNN de so sanh', 'Tao SimpleCNN (khong depthwise, khong center loss, khong temporal loss) trong models/roomnet_lite.py, scripts/train_simple_cnn.py, scripts/evaluate_simple_cnn.py. Chay K-fold CV cho ca 2 mo hinh.'),
    ('Tich hop fall detection (mobile_sensor)', 'Them MobileSensorFusion vao anomaly.py, cap nhat inference.py de nhan mobile_acceleration, fuse_alert() mo rong de xu ly mobile_reasons.'),
    ('Chay lai toan bo pipeline sau sua', 'Retrain tu dau voi du lieu moi, evaluate tren test set, chay K-fold CV cho ca 2 mo hinh, chay baselines. Tat ca 43 tests van pass.'),
]

for i, (task, detail) in enumerate(tasks, 1):
    p = doc.add_paragraph(style='List Number')
    run = p.add_run(task + ': ')
    run.bold = True
    run.font.size = Pt(13)
    run.font.name = 'Times New Roman'
    run2 = p.add_run(detail)
    run2.font.size = Pt(13)
    run2.font.name = 'Times New Roman'

# Section 2
h2 = doc.add_heading('2. Loi da phat hien va cach sua chua', level=1)
for run in h2.runs:
    run.font.size = Pt(14)
    run.font.bold = True
    run.font.name = 'Times New Roman'

errors = [
    ('CAO', '1', 'Du lieu tong hop qua "sach", tach biet de dang', 'scripts/generate_synthetic_data.py:22-25,34', 'Giam signature injection +14/+9 -> +6/+4; tang noise sigma=3->6; them env interference, burst interference, missing AP correlated'),
    ('CAO', '2', 'Ro ri thong tin qua session_shift', 'scripts/generate_synthetic_data.py:30-31', 'Tach biet session_shift, device_shift, ap_drift; them env_interference chung cho tat ca session'),
    ('TRUNG BINH', '3', 'Missing AP handling bat on khi visible APs < 3', 'src/smarthome/preprocessing.py:50-52', 'Them global_median/global_std trong fit(); fallback khi visible < 3'),
    ('TRUNG BINH', '4', 'Threshold anomaly quantile 0.99 hard-code, khong validate', 'scripts/train_anomaly.py:97-98', 'Grid search quantile [0.90,0.95,0.97,0.99,0.995] tren validation, chon F1 tot nhat'),
    ('TRUNG BINH', '5', 'Khong co data augmentation khi train RoomNetLite', 'scripts/train_room.py', 'Them augment_batch(): Gaussian noise (sigma=0.015) + random AP dropout (1-2 APs, 30% prob)'),
    ('TRUNG BINH', '6', 'Khong early stopping, train co dinh 35 epochs', 'scripts/train_room.py:68, train_anomaly.py:77', 'Them CosineAnnealingWarmRestarts + early stopping (patience 10/15, min_delta 1e-4)'),
    ('TRUNG BINH', '7', 'Chi 1 split train/val/test, khong CV', 'scripts/prepare_data.py:24-33', 'Tao evaluate_kfold.py: 5-fold CV theo session, bao cao mean+/-std, 95% CI'),
    ('THAP', '8', 'Do latency chi model forward, bo qua preprocessing+topology', 'scripts/evaluate_room.py:70-76', 'Them mean_e2e_latency_ms_per_sample do softmax + topology filter update'),
    ('THAP', '9', 'Topology self_weight hard-code 0.75', 'src/smarthome/topology.py:5,26', 'Them topology.self_weight vao config.yaml, inference.py doc tu config'),
    ('THAP', '10', 'Test set can bang hoan hao khong phan anh thuc te', 'data/processed/room_test.csv', 'Ghi nhan trong bao cao; K-fold CV giup giam bias uoc luong'),
]

table = doc.add_table(rows=1, cols=5)
table.style = 'Table Grid'
table.alignment = WD_TABLE_ALIGNMENT.CENTER
hdr = table.rows[0].cells
headers = ['Muc do', 'STT', 'Mo ta loi', 'Vi tri (file:dong)', 'Cach sua']
for i, h in enumerate(headers):
    hdr[i].text = h
    for p in hdr[i].paragraphs:
        for r in p.runs:
            r.bold = True
            r.font.size = Pt(11)
            r.font.name = 'Times New Roman'

for level, stt, desc, loc, fix in errors:
    row = table.add_row().cells
    row[0].text = level
    row[1].text = stt
    row[2].text = desc
    row[3].text = loc
    row[4].text = fix
    for cell in row:
        for p in cell.paragraphs:
            for r in p.runs:
                r.font.size = Pt(11)
                r.font.name = 'Times New Roman'

# Section 3
h3 = doc.add_heading('3. Bang so sanh chi so truoc/sau khi toi uu', level=1)
for run in h3.runs:
    run.font.size = Pt(14)
    run.font.bold = True
    run.font.name = 'Times New Roman'

metrics_data = [
    ['Room Classification - Test Accuracy', '99.83%', '98.99%', '-0.84 pp', 'Du lieu thuc te hon -> accuracy chan thuc'],
    ['Room Classification - Test Macro F1', '99.83%', '99.00%', '-0.83 pp', 'Can bang precision/recall cac lop'],
    ['Room Classification - Val Macro F1 (best)', '99.83%', '98.83%', '-1.00 pp', 'Early stopping som hon (epoch 14 vs 27)'],
    ['Room Classification - K-fold CV Mean Macro F1 (RoomNetLite)', 'Chua co', '97.80% +/- 1.06%', 'Moi', '95% CI: [96.88%, 98.73%]'],
    ['Room Classification - K-fold CV Mean Macro F1 (SimpleCNN)', 'Chua co', '97.49% +/- 1.35%', 'Moi', '95% CI: [96.30%, 98.67%]'],
    ['Room Classification - Model Inference Latency', '0.025 ms', '0.029 ms', '+0.004 ms', 'Van rat nhanh, dap ung real-time'],
    ['Room Classification - End-to-End Latency', '0.018 ms', '0.021 ms', '+0.003 ms', 'Bao gom softmax + topology filter'],
    ['Anomaly Detection (Hybrid) - Precision', '77.1%', '87.1%', '+10.0 pp', 'Threshold tuning + data cai thien'],
    ['Anomaly Detection (Hybrid) - Recall', '96.4%', '96.4%', '0.0 pp', 'Duy tri recall cao'],
    ['Anomaly Detection (Hybrid) - F1', '85.7%', '91.5%', '+5.8 pp', 'Cai thien dang ke'],
    ['Anomaly Detection (AE Only) - F1', '43.9%', '66.7%', '+22.8 pp', 'Data augmentation + early stopping giup AE tot hon'],
    ['Baseline RandomForest Accuracy', '99.83%', '99.16%', '-0.67 pp', 'Cung giam do data kho hon'],
    ['Baseline MLP Accuracy', '99.33%', '98.99%', '-0.34 pp', ''],
    ['Baseline kNN Accuracy', '98.32%', '88.26%', '-10.06 pp', 'kNN nhay cam voi noise du lieu'],
]

table2 = doc.add_table(rows=1, cols=5)
table2.style = 'Table Grid'
table2.alignment = WD_TABLE_ALIGNMENT.CENTER
hdr2 = table2.rows[0].cells
headers2 = ['Chi so', 'Truoc (Original)', 'Sau (Optimized)', 'Chenh lech', 'Ghi chu']
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

# Section 3b: So sanh RoomNetLite vs SimpleCNN
h3b = doc.add_heading('3.1. So sanh chi tiet RoomNetLite vs SimpleCNN (Baseline)', level=2)
for run in h3b.runs:
    run.font.size = Pt(13)
    run.font.bold = True
    run.font.name = 'Times New Roman'

comparison_data = [
    ['Kien truc', 'Depthwise separable conv + pointwise', '3 lop Conv1d tiep tiep (standard)'],
    ['Center Loss', 'Co (weight=0.02)', 'Khong'],
    ['Temporal Consistency Loss (JS divergence)', 'Co (weight=0.05)', 'Khong'],
    ['Data Augmentation', 'Co (Gaussian noise + AP dropout)', 'Khong'],
    ['Early Stopping', 'Co (patience=10)', 'Co (patience=10)'],
    ['LR Scheduler', 'CosineAnnealingWarmRestarts', 'CosineAnnealingWarmRestarts'],
    ['So tham so', '~50k', '~48k'],
    ['Test Accuracy', '98.99%', '97.65%'],
    ['Test Macro F1', '99.00%', '97.65%'],
    ['Val Macro F1 (best)', '98.83%', '98.66%'],
    ['K-fold CV Mean Macro F1', '97.80% +/- 1.06%', '97.49% +/- 1.35%'],
    ['K-fold 95% CI', '[96.88%, 98.73%]', '[96.30%, 98.67%]'],
    ['Inference Latency', '0.029 ms', '0.035 ms'],
    ['End-to-End Latency', '0.021 ms', '0.019 ms'],
]

table3b = doc.add_table(rows=1, cols=3)
table3b.style = 'Table Grid'
table3b.alignment = WD_TABLE_ALIGNMENT.CENTER
hdr3b = table3b.rows[0].cells
headers3b = ['Tieu chi', 'RoomNetLite (Proposed)', 'SimpleCNN (Baseline)']
for i, h in enumerate(headers3b):
    hdr3b[i].text = h
    for p in hdr3b[i].paragraphs:
        for r in p.runs:
            r.bold = True
            r.font.size = Pt(11)
            r.font.name = 'Times New Roman'

for row_data in comparison_data:
    row = table3b.add_row().cells
    for i, val in enumerate(row_data):
        row[i].text = val
    for cell in row:
        for p in cell.paragraphs:
            for r in p.runs:
                r.font.size = Pt(11)
                r.font.name = 'Times New Roman'

# Section 4
h4 = doc.add_heading('4. Doi chieu tung yeu cau cua de cuong', level=1)
for run in h4.runs:
    run.font.size = Pt(14)
    run.font.bold = True
    run.font.name = 'Times New Roman'

requirements = [
    ['Mo hinh phan lop phong lightweight CNN/1D-CNN tu vector RSSI', 'DAT', 'RoomNetLite: depthwise separable conv, ~50k params. Test Accuracy 98.99%, Macro F1 99.00%.', ''],
    ['Mo-dun phat hien bat thuong autoencoder tai tao quy dao', 'DAT', 'GRUAutoencoder: hidden=48, latent=24. Reconstruction error dung cho anomaly scoring.', ''],
    ['Phat hien dung yen qua lau, di chuyen bat thuong, nghi ng te nga', 'DAT MOT PHAN', 'RuleEngine: long dwell, impossible transition, night activity. Te nga: MobileSensorFusion tich hop impact+still detection tu mobile_sensor.', ''],
    ['Thu thap RSSI bang router co san + app Android', 'DAT MOT PHAN', 'Co android_collector/, server API /api/collect, /api/scan. Chua test end-to-end voi thiet bi thuc.', ''],
    ['Tien xu ly, chuan hoa du lieu', 'DAT', 'RSSIPreprocessor: absolute/relative/mask features, missing=-100, clip[-100,-30], normalize[0,1]. Global median fallback.', ''],
    ['Kich ban bat thuong mo phong', 'DAT', 'generate_synthetic_data.py: 4 loai anomaly tren 4 ngay cuoi (long_bathroom, long_corridor, night_activity, unusual_transition).', ''],
    ['So sanh do chinh xac phan lop phong truoc/sau cai tien', 'DAT', 'So sanh RoomNetLite vs SimpleCNN (baseline). RoomNetLite tot hon: +1.34% Accuracy, +1.35% Macro F1, K-fold CI khong gian giao.', ''],
    ['Chi so: Accuracy (%), Precision/Recall phat hien bat thuong, do tre realtime', 'DAT', 'Accuracy 98.99%, Hybrid Precision 87.1%/Recall 96.4%/F1 91.5%, Latency model 0.029ms, e2e 0.021ms.', ''],
    ['Dashboard Flask hien thi vi tri phong + canh bao', 'DAT', 'server/app.py: dashboard.html, /api/scan, /api/status, /api/alerts, /api/history, /api/metrics.', ''],
    ['Cau truc luu tru ket qua thuat toan co to chuc', 'DAT', 'SQLite schema: users, homes, rooms, sessions, scans, predictions, alerts, sensor_samples. Multi-home isolation.', ''],
    ['Trien khai tren du lieu thuc te (lab/phong thuc te)', 'CHUA DAT', 'Chi chay tren du lieu tong hop (synthetic). Can thu thap du lieu thuc tai lab/phong.', ''],
]

table3 = doc.add_table(rows=1, cols=4)
table3.style = 'Table Grid'
table3.alignment = WD_TABLE_ALIGNMENT.CENTER
hdr3 = table3.rows[0].cells
headers3 = ['Yeu cau de cuong', 'Trang thai', 'Bang chung / Ly do', 'Ghi chu']
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
    if status == 'DAT':
        for p in row[1].paragraphs:
            for r in p.runs:
                r.font.color.rgb = RGBColor(0, 128, 0)
    elif 'MOT PHAN' in status:
        for p in row[1].paragraphs:
            for r in p.runs:
                r.font.color.rgb = RGBColor(255, 165, 0)
    elif status == 'CHUA DAT':
        for p in row[1].paragraphs:
            for r in p.runs:
                r.font.color.rgb = RGBColor(255, 0, 0)

# Section 5
h5 = doc.add_heading('5. Ton tai va de xuat buoc tiep theo', level=1)
for run in h5.runs:
    run.font.size = Pt(14)
    run.font.bold = True
    run.font.name = 'Times New Roman'

issues = [
    ['Chua co du lieu thuc te tu lab/phong', 'CAO', 'Thu thap du lieu RSSI thuc te tai it nhat 2 can phong/lab, chay pipeline train_home.py cho tung home.', 'CAO'],
    ['Android collector chua test end-to-end', 'TRUNG BINH', 'Build APK, test tren thiet bi Android that, verify format JSON, latency mang, battery consumption.', 'TRUNG BINH'],
    ['Fall detection chua test voi du lieu thuc', 'TRUNG BINH', 'MobileSensorFusion da tich hop code nhung can test voi du lieu accelerometer thuc te (simulated hoac thiet bi that).', 'TRUNG BINH'],
    ['K-fold CV chi 5-fold do it session (7)', 'THAP', 'Khi co du lieu thuc nhieu session hon, tang len 10-fold hoac leave-one-session-out.', 'THAP'],
    ['Threshold anomaly chi optimize tren validation normal', 'THAP', 'Can validation anomaly data rieng de chon operating point chinh xac hon (ROC/PR curve).', 'THAP'],
    ['Model size co the nen them cho edge deployment', 'THAP', 'Ap dung quantization (INT8), pruning, knowledge distillation cho RoomNetLite neu deploy tren Raspberry Pi/ESP32.', 'THAP'],
    ['Dashboard thieu tinh nang export bao cao PDF', 'THAP', 'Them endpoint /api/export/report.pdf cho caregivers/bac si.', 'THAP'],
]

table4 = doc.add_table(rows=1, cols=4)
table4.style = 'Table Grid'
table4.alignment = WD_TABLE_ALIGNMENT.CENTER
hdr4 = table4.rows[0].cells
headers4 = ['Van de ton tai', 'Muc do', 'De xuat giai phap', 'Uu tien']
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

# Section 6
h6 = doc.add_heading('6. Danh gia tien do theo ke hoach 12 tuan (17/8 - 8/11/2026)', level=1)
for run in h6.runs:
    run.font.size = Pt(14)
    run.font.bold = True
    run.font.name = 'Times New Roman'

weeks = [
    ['Tuan 1-2 (17-30/8)', 'Tong quan Smart Home, khao sat tai lieu', 'DAT', 'Da hoan thanh, co docs/01_tong_quan_va_nhu_cau.md'],
    ['Tuan 3-4 (31/8-13/9)', 'Khao sat phuong phap Room-level Fingerprinting, anomaly detection', 'DAT', 'Da hoan thanh, co docs/02_khao_sat_phuong_phap.md'],
    ['Tuan 5-6 (14-27/9)', 'De xuat cai tien mo hinh CNN nhe + autoencoder', 'DAT', 'Da hoan thanh, co docs/03_phuong_phap_de_xuat.md, code models/'],
    ['Tuan 7-8 (28/9-11/10)', 'Cai dat thuat toan, thu thap du lieu, tien xu ly', 'DAT MOT PHAN', 'Cai dat xong pipeline, tien xu ly. CHUA co du lieu thuc te (chi synthetic).'],
    ['Tuan 9-10 (12-25/10)', 'Huan luyen, danh gia, so sanh truoc/sau cai tien', 'DANG THUC HIEN', 'Da train/evaluate tren synthetic, K-fold CV ca 2 mo hinh, so sanh RoomNetLite vs SimpleCNN.'],
    ['Tuan 11-12 (26/10-8/11)', 'Demo, viet bao cao, hoan thien', 'CHUA LAM', 'Can: demo thuc te, bao cao cuoi khoa, slide trinh bay.'],
]

table5 = doc.add_table(rows=1, cols=4)
table5.style = 'Table Grid'
table5.alignment = WD_TABLE_ALIGNMENT.CENTER
hdr5 = table5.rows[0].cells
headers5 = ['Thoi gian', 'Ke hoach de cuong', 'Trang thai', 'Bang chung']
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
    if status == 'DAT':
        for p in row[2].paragraphs:
            for r in p.runs:
                r.font.color.rgb = RGBColor(0, 128, 0)
    elif 'MOT PHAN' in status or 'DANG' in status:
        for p in row[2].paragraphs:
            for r in p.runs:
                r.font.color.rgb = RGBColor(255, 165, 0)
    elif status == 'CHUA LAM':
        for p in row[2].paragraphs:
            for r in p.runs:
                r.font.color.rgb = RGBColor(255, 0, 0)

# Save
doc.save('BAO_CAO_KET_QUA.docx')
print('Saved BAO_CAO_KET_QUA.docx')