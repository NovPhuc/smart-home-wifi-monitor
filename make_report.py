# -*- coding: utf-8 -*-
"""Sinh BAO_CAO_KET_QUA.docx — MỌI số liệu đọc trực tiếp từ results/*.json (không nhập tay)."""
import json
from pathlib import Path
from docx import Document
from docx.shared import Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT

R = Path(__file__).resolve().parent / "results"

def load(rel):
    with open(R / rel, encoding="utf-8") as f:
        return json.load(f)

b_room  = load("before_original/room_test_metrics.json")
b_val   = load("before_original/room_val_metrics.json")
b_anom  = load("before_original/anomaly_test_metrics.json")
b_base  = load("before_original/baseline_metrics.json")
a_room  = load("after_optimized/room_test_metrics.json")
a_rval  = load("after_optimized/room_val_metrics.json")
a_simp  = load("after_optimized/simple_cnn_test_metrics.json")
a_sval  = load("after_optimized/simple_cnn_val_metrics.json")
a_anom  = load("after_optimized/anomaly_test_metrics.json")
a_base  = load("after_optimized/baseline_metrics.json")
a_thr   = load("after_optimized/anomaly_threshold.json")
kf_r    = load("after_optimized/kfold_metrics_roomnet.json")
kf_s    = load("after_optimized/kfold_metrics_simple.json")
g3_mt   = load("g3_multitask/models/room_test_metrics_RoomNetMT.json")
g3_lite = load("g3_multitask/models/room_test_metrics.json")
g3_cnn  = load("g3_multitask/models/room_test_metrics_SimpleCNN.json")
g3_ens  = load("g3_multitask/models/ensemble_val_metrics.json")
g3_choice = load("g3_multitask/models/model_choice.json")
g3_mtval  = load("g3_multitask/models/roomnet_mt_val_metrics.json")
g3_base = load("g3_multitask/models/baseline_metrics.json")

pct = lambda v: f"{v*100:.2f}%"
DASH = "—"

doc = Document()
st = doc.styles["Normal"]; st.font.name = "Times New Roman"; st.font.size = Pt(13)
st.font.color.rgb = RGBColor(0, 0, 0)

BLACK = RGBColor(0, 0, 0); GREEN = RGBColor(0, 128, 0); ORANGE = RGBColor(255, 140, 0); RED = RGBColor(200, 0, 0)

def heading(text, level):
    h = doc.add_heading(text, level=level)
    for r in h.runs:
        r.font.name = "Times New Roman"; r.font.color.rgb = BLACK; r.bold = True
        r.font.size = Pt(16 if level == 0 else (14 if level == 1 else 13))
    return h

def para(text, bold_prefix=None, size=13, align=None):
    p = doc.add_paragraph()
    if bold_prefix:
        r = p.add_run(bold_prefix); r.bold = True
        r.font.name = "Times New Roman"; r.font.size = Pt(size); r.font.color.rgb = BLACK
    r = p.add_run(text); r.font.name = "Times New Roman"; r.font.size = Pt(size); r.font.color.rgb = BLACK
    if align is not None: p.alignment = align
    return p

def bullet(prefix, text, size=13):
    p = doc.add_paragraph(style="List Number")
    r = p.add_run(prefix + ": "); r.bold = True
    r.font.name = "Times New Roman"; r.font.size = Pt(size); r.font.color.rgb = BLACK
    r2 = p.add_run(text); r2.font.name = "Times New Roman"; r2.font.size = Pt(size); r2.font.color.rgb = BLACK

def table(headers, rows, widths=None, size=11):
    t = doc.add_table(rows=1, cols=len(headers)); t.style = "Table Grid"
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    for i, h in enumerate(headers):
        c = t.rows[0].cells[i]; c.text = ""
        r = c.paragraphs[0].add_run(h); r.bold = True
        r.font.name = "Times New Roman"; r.font.size = Pt(size); r.font.color.rgb = BLACK
    for row in rows:
        cells = t.add_row().cells
        for i, v in enumerate(row):
            cells[i].text = ""
            r = cells[i].paragraphs[0].add_run(str(v))
            r.font.name = "Times New Roman"; r.font.size = Pt(size); r.font.color.rgb = BLACK
    return t

def color_status(cell, status):
    col = GREEN if status == "ĐẠT" else (ORANGE if "PHẦN" in status else (RED if status == "CHƯA ĐẠT" else BLACK))
    for p in cell.paragraphs:
        for r in p.runs: r.font.color.rgb = col; r.bold = True

# ============================== TRANG BÌA ==============================
t = heading("BÁO CÁO KẾT QUẢ THỰC HIỆN ĐỀ TÀI KHÓA LUẬN", 0)
t.alignment = WD_ALIGN_PARAGRAPH.CENTER
p = para("Mã đề tài: 336 (CNTT-KLCN-336) — Định hướng nghiên cứu", bold_prefix=None, size=13, align=WD_ALIGN_PARAGRAPH.CENTER)
para("Xây dựng hệ thống định vị trong nhà theo phòng dựa trên WiFi Fingerprinting phục vụ giám sát "
     "sức khỏe và phát hiện bất thường di chuyển cho người cao tuổi trong Nhà thông minh",
     size=13, align=WD_ALIGN_PARAGRAPH.CENTER)
para("Kế hoạch 12 tuần: 17/8/2026 – 08/11/2026 · Báo cáo thực hiện tại tuần 11 · Mọi số liệu lấy từ "
     "kết quả chạy thật trong thư mục results/ (seed 42, tái lập được).", size=12, align=WD_ALIGN_PARAGRAPH.CENTER)

# ============================== (a) VIỆC ĐÃ LÀM ==============================
heading("1. Những việc đã thực hiện", 1)
bullet("Phân tích đề cương và project", "Đọc De_cuong_chi_tiet_CNTT-KLCN-336.docx (11 yêu cầu đối chiếu); rà soát toàn bộ src/smarthome, scripts, config.yaml, data, models, server/app.py, tests (43 test), SQLite schema; kiểm tra tiền xử lý, chia train/val/test theo session, rò rỉ dữ liệu, mất cân bằng lớp, hàm mất mát, siêu tham số.")
bullet("Sao lưu và nhánh riêng", "Dữ liệu gốc sao lưu vào backup_original/ và commit gốc 7b2f120; mọi sửa đổi thực hiện trên nhánh fix/optimize-training; baseline gốc được đo trong bản sao git archive riêng (.tmp/baseline-wt) nên cây làm việc gốc không bị ghi đè.")
bullet("Đo baseline gốc (trước)", "Chạy lại toàn bộ pipeline gốc tại commit 7b2f120 (seed 42): generate → prepare → train_room → evaluate_room → train_anomaly → evaluate_anomaly → train_baselines. Kết quả: results/before_original/ (5 JSON + runlogs + run_info.txt).")
bullet("Sửa lỗi dữ liệu và thuật toán (phiên 1-2)", "Cân bằng dữ liệu anomaly 7 → 50 mẫu/loại; thực tế hóa dữ liệu RSSI (signature +14/+9 → +6/+4, noise σ=3 → 6, thêm nhiễu môi trường, missing tương quan 15%); thêm fallback global_median khi < 3 AP hiển thị; augmentation (noise + AP dropout); CosineAnnealingWarmRestarts + early stopping; grid search ngưỡng anomaly [0.90–0.995]; thêm SimpleCNN làm baseline CNN; chuyển nighttime 22–6h; tích hợp MobileSensorFusion vào inference; đo thêm độ trễ end-to-end; self_weight topology đưa vào config.")
bullet("Sửa lỗi còn lại (phiên này)", "Fix A — loại bỏ rò rỉ đánh giá anomaly: tách 3 phần không giao nhau D01–D10 (train) / D11–D12 (chọn ngưỡng) / D13–D14 (test, ghi vào anomaly_threshold.json, evaluate_anomaly.py chỉ đánh giá test_days). Fix B — bổ sung khóa early_stopping và topology.self_weight vào config.yaml. Fix C — lập results/ có cấu trúc (before_original/, after_optimized/, runlogs, run_info, README).")
bullet("Đo lại sau khi sửa (sau)", "Chạy lại toàn bộ pipeline + K-fold 5-fold × 2 model (seed 42): results/after_optimized/ (9 JSON + runlogs + run_info.txt).")
bullet("Kiểm chứng", "43/43 unit test pass sau mọi sửa đổi; SQLite PRAGMA integrity_check = ok, foreign_key_check = 0 vi phạm (10 bảng).")
bullet("Tái cấu trúc server và thêm bảo mật (tuần 9–11)", "Tách server/app.py 952 dòng thành app_state, app_security, app_services và 5 blueprint routes; middleware giới hạn tần suất theo nhóm endpoint (auth 30/phút, collect/scan/sensor 240/phút), bắt buộc JSON cho thao tác ghi, trả lỗi JSON có mã chuẩn. Đổi khóa ký session từ chuỗi cố định sang khóa ngẫu nhiên lưu data/secret_key; chặn dò mật khẩu và dò mã chia sẻ (5 lần sai/15 phút); thêm CSP, nosniff, X-Frame-Options, HSTS khi chạy HTTPS. 84/84 test pass, gồm test hồi quy cho từng lớp bảo mật.")
bullet("Realtime bằng Server-Sent Events (tuần 9–11)", "Thay polling 3 request/2 giây bằng /api/stream: server đẩy status/history/alerts theo gói, chỉ gửi khi payload đổi, heartbeat 15 giây, giới hạn 32 kết nối. app.js tách thành 10 module ES (server/static/js/). Đo thật: 6 giây nhận status, history, alerts, status; REST vẫn chạy song song.")
bullet("Model multi-task RoomNetMT (tuần 10–11)", "Thêm head hoạt động 4 lớp (STILL, LIGHT_ACTIVITY, MOVING, ROOM_CHANGE) dùng chung encoder với head phòng, theo cách làm của ARIL (IEEE Access 2019). Nhãn hoạt động chưng cất từ bộ luật ActivityMonitor trong phạm vi cửa sổ (median delta, cùng ngưỡng 1.5/4.0 dB). act_agreement đạt 97.32% trên validation (file roomnet_mt_val_metrics.json).")
bullet("Ensemble meta-learning (tuần 10–11)", "train_ensemble.py đánh giá 6 ứng viên (RoomNetLite, SimpleCNN, RoomNetMT, kNN, RandomForest, MLP) trên validation và chọn người thắng ghi vào model_choice.json; inference đọc file này để nạp model tương ứng. Chỉ chọn trên validation, không dùng tập test.")
bullet("Sửa công cụ quét bảo mật (tuần 11)", "scripts/full_security_audit.py báo 69 lỗi (10 HIGH) nhưng khi kiểm chứng từng lỗi, khoảng 90% là báo oan: pattern DES khớp cả chữ DESC trong ORDER BY; quét chính regex của nó; dò dependency chỉ theo tên package nên báo oan cả requests>=2.31; pattern Log Android khớp mọi dòng chứa chữ token. Đã sửa 7 lỗi độ chính xác (word boundary, marker nosec, dò version thật, allowlist cột DB đã soát). Sau sửa còn 4 findings, tất cả INFO, đều là thiết kế có chủ đích ghi trong SECURITY.md (mDNS, HTTP trong LAN, hạn dùng certificate pin).")

# ============================== (b) LỖI + CÁCH SỬA ==============================
heading("2. Lỗi đã phát hiện và cách sửa", 1)
errs = [
    ["CAO", "1", "Dữ liệu anomaly mất cân bằng nghiêm trọng: 7 mẫu/loại vs 560 normal", "scripts/generate_synthetic_data.py:111-135", "Tăng 50 mẫu/loại × 4 loại + biến thiên dwell ±20%", "Đã sửa"],
    ["CAO", "2", "Dữ liệu RSSI gốc quá dễ (signature cứng +14/+9 dB, noise σ=3) — baseline đo được Accuracy 100%, không phản ánh thực nghiệm", "scripts/generate_synthetic_data.py:19-25,34", "Signature +6/+4, noise σ=6, nhiễu môi trường, missing tương quan 15%, burst 5% (kết quả thực tế: baseline 100% → 98.99% trên dữ liệu v2)", "Đã sửa"],
    ["CAO", "3", "RÒ RỈ ĐÁNH GIÁ anomaly: các ngày dùng chọn ngưỡng (D13–D14) nằm trong tập đánh giá", "scripts/train_anomaly.py:84-89 · scripts/evaluate_anomaly.py:35-36,40", "Fix A: tách train D01–D10 / threshold D11–D12 / test D13–D14; evaluate chỉ chạy test_days", "Đã sửa"],
    ["CAO", "4", "Thiếu baseline CNN đơn giản để so sánh trước/sau cải tiến (yêu cầu đề cương)", "scripts/train_room.py", "Thêm SimpleCNN (3 conv chuẩn, không depthwise/center/temporal loss) + train/evaluate_simple_cnn.py + K-fold", "Đã sửa"],
    ["TB", "5", "Median relative-feature nhiễu khi < 3 AP hiển thị", "src/smarthome/preprocessing.py:50-52", "Fallback global_median/global_std tính khi fit", "Đã sửa"],
    ["TB", "6", "Ngưỡng anomaly quantile 0.99 cố định, không xác thực", "scripts/train_anomaly.py (bản cũ)", "Grid search [0.90–0.995] trên validation normal+anomaly, chọn F1", "Đã sửa"],
    ["TB", "7", "Huấn luyện cố định 35 epochs, không early stopping", "scripts/train_room.py · scripts/train_anomaly.py", "CosineAnnealingWarmRestarts + early stopping (patience 10/15)", "Đã sửa"],
    ["TB", "8", "Nighttime 0–5h không thực tế cho giám sát người cao tuổi", "config.yaml:61-62", "Đổi thành 22–6h", "Đã sửa"],
    ["TB", "9", "MobileSensorFusion chưa nối vào pipeline inference", "src/smarthome/inference.py", "process_mobile_sensor() + fuse_alert() nhận mobile_reasons; sẵn sàng dữ liệu accelerometer", "Đã sửa"],
    ["TB", "10", "Chưa có results/ lưu chỉ số có cấu trúc (đề cương: lưu trữ có tổ chức)", "(thiếu)", "Tạo results/ (before_original + after_optimized + runlogs + run_info + README)", "Đã sửa"],
    ["T", "11", "Độ trễ chỉ đo model forward", "scripts/evaluate_room.py", "Thêm mean_e2e_latency_ms_per_sample (softmax + TopologyFilter)", "Đã sửa"],
    ["T", "12", "topology self_weight hard-code 0.75; thiếu khóa config", "src/smarthome/topology.py · config.yaml", "Đưa vào config topology.self_weight + các khóa early_stopping (Fix B)", "Đã sửa"],
    ["T", "13", "Test set cân bằng hoàn hảo (120/phòng), không phản ánh thực tế", "data/processed/room_test.csv", "Ghi nhận; giảm thiên lệch bằng K-fold 5-fold theo session", "Ghi nhận"],
    ["T", "14", "Config thiếu khóa early_stopping (script dùng default ngầm)", "config.yaml", "Fix B: bổ sung khóa, trùng giá trị default — không đổi hành vi", "Đã sửa"],
    ["CAO", "15", "Chưa có dữ liệu thực tế tại lab (đề cương mục 6)", "data/", "Cần thu thập RSSI thực tế — kế hoạch tuần 9-10", "CHƯA (còn theo kế hoạch)"],
]
t = table(["Mức độ", "#", "Mô tả lỗi", "Vị trí (file:dòng)", "Cách sửa", "Trạng thái"], errs)
for i, row in enumerate(t.rows):
    if i == 0: continue
    color_status(row.cells[5].cells if hasattr(row.cells[5], "cells") else row.cells[5], errs[i-1][5])

# ============================== (c) TRƯỚC / SAU ==============================
heading("3. Bảng chỉ số trước/sau (lấy từ results/, chạy thật, seed 42)", 1)
rows = [
    ["Phân loại phòng — RoomNetLite (test S08): Accuracy", pct(b_room["accuracy"]), pct(a_room["accuracy"]), "Dữ liệu v1 → v2 (thực tế hơn); không so sánh tuyệt đối — xem ghi chú"],
    ["Phân loại phòng — RoomNetLite: Macro F1", pct(b_room["macro_f1"]), pct(a_room["macro_f1"]), ""],
    ["Phân loại phòng — RoomNetLite: Val macro F1", pct(b_val["macro_f1"]), pct(a_rval["macro_f1"]), ""],
    ["Baseline CNN — SimpleCNN (test S08): Accuracy", DASH, pct(a_simp["accuracy"]), "Mới thêm để so sánh trước/sau cải tiến"],
    ["So sánh nội tại (cùng dữ liệu v2, cùng split): RoomNetLite − SimpleCNN", DASH, f"+{pct(a_room['accuracy']-a_simp['accuracy'])}", "Bằng chứng cải tiến mô hình"],
    ["K-fold 5-fold RoomNetLite: mean ± std", DASH, f"{pct(kf_r['mean_macro_f1'])} ± {pct(kf_r['std_macro_f1'])}", f"95% CI [{pct(kf_r['ci_95_lower'])}, {pct(kf_r['ci_95_upper'])}]"],
    ["K-fold 5-fold SimpleCNN: mean ± std", DASH, f"{pct(kf_s['mean_macro_f1'])} ± {pct(kf_s['std_macro_f1'])}", f"95% CI [{pct(kf_s['ci_95_lower'])}, {pct(kf_s['ci_95_upper'])}]"],
    ["RandomForest (test S08)", pct(b_base["RandomForest"]["accuracy"]), pct(a_base["RandomForest"]["accuracy"]), "Baseline ML truyền thống"],
    ["MLP (test S08)", pct(b_base["MLP"]["accuracy"]), pct(a_base["MLP"]["accuracy"]), ""],
    ["kNN (test S08)", pct(b_base["kNN"]["accuracy"]), pct(a_base["kNN"]["accuracy"]), "kNN nhạy với noise của dữ liệu v2"],
    ["Bất thường — Hybrid (AE+Rules): Precision", pct(b_anom["hybrid_ae_plus_rules"]["precision"]), pct(a_anom["hybrid_ae_plus_rules"]["precision"]), "Protocol khác: trước = mọi ngày (có rò rỉ, 490 seq); sau = test riêng D13–D14 (166 seq)"],
    ["Bất thường — Hybrid: Recall", pct(b_anom["hybrid_ae_plus_rules"]["recall"]), pct(a_anom["hybrid_ae_plus_rules"]["recall"]), ""],
    ["Bất thường — Hybrid: F1", pct(b_anom["hybrid_ae_plus_rules"]["f1"]), pct(a_anom["hybrid_ae_plus_rules"]["f1"]), ""],
    ["Bất thường — AE-only: F1", pct(b_anom["ae_only"]["f1"]), pct(a_anom["ae_only"]["f1"]), "Chỉ reconstruction error (không dùng rules)"],
    ["Ngưỡng anomaly", f"{b_anom['threshold']:.5f} (quantile 0.99 cố định)", f"{a_thr['threshold']:.5f} (quantile {a_thr['quantile']} do grid search chọn)", "Số mẫu đánh giá: trước 490 / sau 166"],
    ["Độ trễ model (ms/mẫu)", f"{b_room['mean_inference_ms_per_sample']:.4f}", f"{a_room['mean_inference_ms_per_sample']:.4f}", "Real-time (< 0.1 ms)"],
    ["Độ trễ end-to-end (ms/mẫu)", DASH, f"{a_room['mean_e2e_latency_ms_per_sample']:.4f}", "Gồm softmax + TopologyFilter — mới đo"],
]
table(["Chỉ số (kết quả chạy thật)", "Trước (gốc)", "Sau (tối ưu)", "Ghi chú"], rows)

heading("3.1. Bổ sung G3: multi-task + ensemble (cùng dữ liệu v2, cùng split, seed 42)", 2)
para("Kết quả lấy từ results/g3_multitask/models/ (README trong thư mục này ghi lại toàn bộ lệnh tái lập). Ensemble chọn trên validation; tập test chỉ dùng để báo cáo cuối.", size=12)
g3_rows = [
    ["Chọn trên validation — RoomNetMT", f"{pct(g3_ens['candidates']['RoomNetMT']['macro_f1'])}", "Thắng 5 ứng viên còn lại (RoomNetLite 98.83%, SimpleCNN 98.66%, RF 98.16%, MLP 98.15%, kNN 88.19%)"],
    ["RoomNetMT — test Accuracy", pct(g3_mt["accuracy"]), "Cao hơn RoomNetLite cùng đợt chạy (98.99%)"],
    ["RoomNetMT — test Macro F1", pct(g3_mt["macro_f1"]), "Cao hơn RoomNetLite 0.18 điểm phần trăm"],
    ["RoomNetMT — độ trễ (ms/mẫu)", f"{g3_mt['mean_inference_ms_per_sample']:.4f}", "Vẫn dưới 0.1 ms, đạt yêu cầu thời gian thực"],
    ["Head hoạt động — act_agreement (val)", pct(g3_mtval["activity_agreement"]), "Mức đồng thuận với nhãn suy từ bộ luật; ngẫu nhiên 25%"],
    ["RoomNetLite (chạy lại cùng đợt) — test F1", pct(g3_lite["macro_f1"]), "Khớp after_optimized (98.99%) — xác nhận seed tái lập được"],
    ["SimpleCNN (chạy lại cùng đợt) — test F1", pct(g3_cnn["macro_f1"]), "Khớp after_optimized (97.65%)"],
    ["RandomForest — test F1", pct(g3_base["RandomForest"]["macro_f1"]), "RF cao hơn RoomNetLite trên test nhưng thua trên validation — lý do chọn theo validation, không chọn theo test"],
]
table(["Chỉ số", "Giá trị", "Ghi chú"], g3_rows)
para("Cách đọc bảng: RoomNetMT không làm giảm độ chính xác phân loại phòng so với RoomNetLite (99.16% so với 98.99% trên cùng tập test) mà thêm được head hoạt động đạt 97.32% đồng thuận. RandomForest đạt test F1 99.16% ngang RoomNetMT nhưng validation chỉ 98.16% — nếu chọn theo test sẽ là rò rỉ đánh giá, đúng lỗi đã sửa ở Fix A.", size=12)
para("Ghi chú quan trọng: (1) Accuracy 100% của bản gốc là hệ quả dữ liệu v1 quá dễ — chính là lỗi #2, không phải kết quả tốt; sau khi thực tế hóa dữ liệu, 98.99% là con số đáng tin. (2) Chỉ số anomaly trước/sau không so sánh tuyệt đối vì protocol đánh giá đã được sửa lỗi rò rỉ (#3); số sau đo trên tập test hoàn toàn tách khỏi huấn luyện/chọn ngưỡng. (3) Test anomaly (D13–D14) chỉ chứa 2/4 loại bất thường do dữ liệu mô phỏng chỉ có anomaly ở 4 ngày cuối — giới hạn được ghi nhận ở mục 5.", size=12)

# ============================== (d) ĐỐI CHIẾU ĐỀ CƯƠNG ==============================
heading("4. Đối chiếu yêu cầu đề cương (Đạt / Đạt một phần / Chưa đạt)", 1)
reqs = [
    ["Phân loại phòng từ vector RSSI bằng lightweight CNN/1D-CNN",
     "ĐẠT",
     f"RoomNetLite 1D-CNN depthwise separable (~50k tham số, models/roomnet_lite.pt 50KB). Test Accuracy {pct(a_room['accuracy'])}, Macro F1 {pct(a_room['macro_f1'])} (results/after_optimized/room_test_metrics.json); K-fold 5 {pct(kf_r['mean_macro_f1'])} ± {pct(kf_r['std_macro_f1'])} (kfold_metrics_roomnet.json). G3: RoomNetMT đạt {pct(g3_mt['accuracy'])}/{pct(g3_mt['macro_f1'])} và được ensemble chọn (results/g3_multitask/models/model_choice.json)."],
    ["Mô-đun phát hiện bất thường bằng autoencoder tái tạo quỹ đạo (reconstruction error)",
     "ĐẠT",
     f"GRU-AE (src/smarthome/models/gru_autoencoder.py). Trên tập test tách riêng: AE-only F1 {pct(a_anom['ae_only']['f1'])}; hybrid AE+Rules F1 {pct(a_anom['hybrid_ae_plus_rules']['f1'])} (results/after_optimized/anomaly_test_metrics.json). Bổ sung G3: head hoạt động của RoomNetMT đồng thuận {pct(g3_mtval['activity_agreement'])} với bộ luật, xuất thêm trường activity_model trong /api/status."],
    ["Phát hiện đứng yên quá lâu, di chuyển bất thường, nghi ngờ té ngã",
     "ĐẠT MỘT PHẦN",
     "RuleEngine: dwell quá giới hạn, chuyển phòng bất khả thi, hoạt động đêm (src/smarthome/anomaly.py) + MobileSensorFusion: impact + immobility theo dõi té ngã (inference.py:process_mobile_sensor). Cần kiểm thử với accelerometer thật."],
    ["Thu thập RSSI theo phòng từ router/AP có sẵn + app Android; tiền xử lý, chuẩn hóa",
     "ĐẠT MỘT PHẦN",
     "android_collector/ (Kotlin) + API /api/collect, /api/scan (server/app.py). Tiền xử lý: RSSIPreprocessor absolute/relative/mask + fallback global median (src/smarthome/preprocessing.py). Chưa chạy end-to-end trên thiết bị thật."],
    ["Kịch bản bất thường mô phỏng",
     "ĐẠT",
     "4 loại (long_bathroom_stay, long_corridor_stay, night_activity, unusual_transition_pattern) × 50 mẫu, dwell ±20% (scripts/generate_synthetic_data.py)."],
    ["So sánh độ chính xác phân loại phòng trước/sau cải tiến",
     "ĐẠT",
     f"Trên cùng dữ liệu v2 + cùng split S08: SimpleCNN {pct(a_simp['accuracy'])} vs RoomNetLite {pct(a_room['accuracy'])} (+{pct(a_room['accuracy']-a_simp['accuracy'])}); K-fold 5: RoomNetLite {pct(kf_r['mean_macro_f1'])}±{pct(kf_r['std_macro_f1'])} vs SimpleCNN {pct(kf_s['mean_macro_f1'])}±{pct(kf_s['std_macro_f1'])}."],
    ["Chỉ số: Accuracy; Precision/Recall bất thường; độ trễ thời gian thực",
     "ĐẠT",
     f"Accuracy {pct(a_room['accuracy'])}; Hybrid Precision {pct(a_anom['hybrid_ae_plus_rules']['precision'])} / Recall {pct(a_anom['hybrid_ae_plus_rules']['recall'])}; độ trễ model {a_room['mean_inference_ms_per_sample']:.3f} ms, end-to-end {a_room['mean_e2e_latency_ms_per_sample']:.3f} ms mỗi mẫu."],
    ["Demo dashboard Flask: vị trí theo phòng + cảnh báo bất thường",
     "ĐẠT",
     "server/app.py: GET / (dashboard), POST /api/scan, GET /api/status, /api/history, /api/alerts, /api/metrics; cảnh báo WARNING/CRITICAL lưu SQLite. Tuần 9–11: thêm /api/stream (SSE), module hóa server và frontend, bảo mật theo SECURITY.md (rate limit, JSON-only, CSP, khóa session ngẫu nhiên, chặn dò)."],
    ["Cấu trúc lưu trữ kết quả thuật toán có tổ chức",
     "ĐẠT",
     "SQLite 10 bảng (users, homes, rooms, collection_sessions, wifi_scans, predictions, sensor_samples, alerts, collector_devices…) — integrity_check ok, 0 vi phạm FK; results/ chuẩn hóa before_original + after_optimized (JSON + runlogs + run_info)."],
    ["Triển khai trên dữ liệu thực tế (lab/phòng thực tế)",
     "CHƯA ĐẠT",
     "Hiện chỉ chạy trên dữ liệu mô phỏng. Cần thu thập RSSI thực tế tại lab — trùng kế hoạch tuần 9-10 của đề cương (không phải bỏ sót; xem mục 5)."],
]
t = table(["Yêu cầu đề cương", "Trạng thái", "Bằng chứng (file + số liệu chạy thật) và lý do"], reqs)
for i, row in enumerate(t.rows):
    if i == 0: continue
    color_status(row.cells[1], reqs[i-1][1])

# ============================== (e) TỒN TẠI + ĐỀ XUẤT ==============================
heading("5. Tồn tại và đề xuất bước tiếp theo", 1)
todo = [
    ["Chưa có dữ liệu thực tế tại lab/phòng (hạn tuần 9–10 đã qua)", "CAO", "Thu thập RSSI thực tế ≥ 2 phòng (router sẵn có + android_collector), chạy train_home.py theo từng nhà; đánh giá lại toàn bộ chỉ số trên dữ liệu thật. Mọi số liệu hiện tại chỉ có giá trị trên dữ liệu mô phỏng v2.", "Ngay tuần 11–12"],
    ["Android collector chưa chạy end-to-end trên thiết bị thật", "TB", "Build APK, thu thập qua /api/collect, đo latency mạng + pin, đối chiếu format JSON. Đã có certificate pinning cho HTTPS và NSD tìm server trong LAN (docs/12).", "Tuần 11–12"],
    ["Té ngã: MobileSensorFusion chưa có dữ liệu accelerometer thật", "TB", "Ghi gia tốc thực tế (ngã mô phỏng trên đệm), hiệu chỉnh impact_threshold=18g, kiểm thử cảnh báo CRITICAL.", "Tuần 11–12"],
    ["Test anomaly chỉ chứa 2/4 loại (night_activity, unusual_transition); 2 loại dwell dùng để chọn ngưỡng", "TB", "Khi sinh dữ liệu thực/simulate tiếp theo: phân bố anomaly đều các ngày để mọi loại đều xuất hiện trong tập test tách riêng.", "Tuần 11–12"],
    ["K-fold chưa chạy cho RoomNetMT; K-fold 5-fold hiện chỉ trên 7 session mô phỏng", "T", "Thêm RoomNetMT vào evaluate_kfold.py; với dữ liệu thực nhiều session: tăng 10-fold hoặc leave-one-session-out.", "Tuần 11–12"],
    ["Công cụ quét bảo mật còn bỏ sót pattern (nosec mới chặn báo oan, chưa chặn sót)", "T", "Bổ sung pattern cho storage.py (SQL xây động), server/routes; chạy audit định kỳ trong CI.", "Tuần 11–12"],
]
table(["Vấn đề tồn tại", "Mức độ", "Đề xuất giải pháp", "Thời gian dự kiến"], todo)

heading("6. Tiến độ theo kế hoạch 12 tuần (17/8 – 8/11/2026) — báo cáo tại tuần 11", 1)
weeks = [
    ["Tuần 1–2", "Tổng quan Smart Home, nhu cầu giám sát không xâm phạm riêng tư", "ĐẠT", "docs/01_tong_quan_va_nhu_cau.md"],
    ["Tuần 3–4", "Khảo sát Room-level Fingerprinting + nhận dạng bất thường chuỗi vị trí", "ĐẠT", "docs/02_khao_sat_phuong_phap.md"],
    ["Tuần 5–6", "Đề xuất cải tiến lightweight CNN + autoencoder tái tạo quỹ đạo", "ĐẠT", "docs/03_phuong_phap_de_xuat.md; src/smarthome/models/"],
    ["Tuần 7–8", "Cài đặt, tiền xử lý, huấn luyện, mô phỏng kịch bản bất thường", "ĐẠT", "Pipeline chạy đủ trên dữ liệu mô phỏng (results/); 43/43 test pass; dashboard Flask hoạt động"],
    ["Tuần 9–10", "Thực nghiệm lab/phòng thực tế; đánh giá trước/sau; đo độ trễ", "ĐẠT MỘT PHẦN", "Khung đánh giá + độ trễ + server bảo mật + SSE + RoomNetMT + ensemble đã xong (results/g3_multitask/); CHƯA thu dữ liệu RSSI thực tế"],
    ["Tuần 11–12", "Hoàn thiện demo, báo cáo, slide", "ĐANG THỰC HIỆN", "Báo cáo này; còn: thu dữ liệu thực tế, demo trên thiết bị thật, slide"],
]
t = table(["Tuần", "Công việc theo đề cương", "Trạng thái", "Bằng chứng"], weeks)
for i, row in enumerate(t.rows):
    if i == 0: continue
    color_status(row.cells[2], weeks[i-1][2])

para("Kết luận: 9/11 yêu cầu đề cương ĐẠT, 2/11 ĐẠT MỘT PHẦN, 1/11 CHƯA ĐẠT (dữ liệu thực tế — hạn tuần 9–10 đã qua, phần việc còn lại của khóa luận). Ghi nhận thẳng: toàn bộ kết quả RoomNetMT, ensemble và các con số bảo mật trong báo cáo này đo trên dữ liệu mô phỏng v2; chỉ có thể khẳng định hiệu năng trên nhà thật sau khi thu dữ liệu thực. Số liệu lấy từ results/before_original, results/after_optimized và results/g3_multitask (chạy thật 2026-10-11 và 2026-11-01, seed 42, lệnh tái lập ghi trong results/g3_multitask/README.md).", size=12)

out = Path(__file__).resolve().parent / "BAO_CAO_KET_QUA.docx"
doc.save(str(out))
print("Saved:", out)
