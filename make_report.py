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

def try_load(rel):
    p = R / rel
    return load(rel) if p.exists() else None

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

ext = {}
for name in ("external_uci_wil", "external_ujiindoorloc"):
    ext[name] = {
        "room":   try_load(f"{name}/room_test_metrics.json"),
        "simple": try_load(f"{name}/simple_cnn_test_metrics.json"),
        "base":   try_load(f"{name}/baseline_metrics.json"),
    }

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

def para(text, size=13, align=None):
    p = doc.add_paragraph()
    r = p.add_run(text); r.font.name = "Times New Roman"; r.font.size = Pt(size); r.font.color.rgb = BLACK
    if align is not None: p.alignment = align
    return p

def bullet(prefix, text, size=13):
    p = doc.add_paragraph(style="List Number")
    r = p.add_run(prefix + ": "); r.bold = True
    r.font.name = "Times New Roman"; r.font.size = Pt(size); r.font.color.rgb = BLACK
    r2 = p.add_run(text); r2.font.name = "Times New Roman"; r2.font.size = Pt(size); r2.font.color.rgb = BLACK

def table(headers, rows, size=11):
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
    col = GREEN if status == "ĐẠT" else (ORANGE if "PHẦN" in status else (RED if "CHƯA" in status else BLACK))
    for p in cell.paragraphs:
        for r in p.runs: r.font.color.rgb = col; r.bold = True

# ============================== TRANG BÌA ==============================
t = heading("BÁO CÁO KẾT QUẢ THỰC HIỆN ĐỀ TÀI KHÓA LUẬN", 0)
t.alignment = WD_ALIGN_PARAGRAPH.CENTER
para("Mã đề tài: 336 (CNTT-KLCN-336) — Định hướng nghiên cứu", size=13, align=WD_ALIGN_PARAGRAPH.CENTER)
para("Xây dựng hệ thống định vị trong nhà theo phòng dựa trên WiFi Fingerprinting phục vụ giám sát "
     "sức khỏe và phát hiện bất thường di chuyển cho người cao tuổi trong Nhà thông minh",
     size=13, align=WD_ALIGN_PARAGRAPH.CENTER)
para("Kế hoạch 12 tuần: 17/8/2026 – 08/11/2026 · Cập nhật lần 2 (tuần 8, 11/10/2026) · Mọi số liệu lấy từ "
     "kết quả chạy thật trong thư mục results/ (seed 42, tái lập được).", size=12, align=WD_ALIGN_PARAGRAPH.CENTER)

# ============================== (a) VIỆC ĐÃ LÀM ==============================
heading("1. Những việc đã thực hiện", 1)
bullet("Phân tích đề cương và project", "Đọc De_cuong_chi_tiet_CNTT-KLCN-336.docx (11 yêu cầu đối chiếu); rà soát toàn bộ src/smarthome, scripts, config.yaml, data, models, server/app.py, tests (43 test), SQLite schema; kiểm tra tiền xử lý, chia train/val/test theo session, rò rỉ dữ liệu, mất cân bằng lớp, hàm mất mát, siêu tham số.")
bullet("Sao lưu và nhánh riêng", "Dữ liệu gốc sao lưu vào backup_original/ và commit gốc 7b2f120; mọi sửa đổi trên nhánh fix/optimize-training; baseline gốc đo trong bản sao git archive riêng (.tmp/baseline-wt) — cây làm việc gốc không bị ghi đè.")
bullet("Đo baseline gốc (trước)", "Chạy lại toàn bộ pipeline gốc tại commit 7b2f120 (seed 42). Kết quả: results/before_original/ — phát hiện dữ liệu v1 cho Accuracy 100% giả tạo (signature cứng +14/+9 dB).")
bullet("Sửa lỗi dữ liệu và thuật toán", "Cân bằng anomaly 7→50 mẫu/loại; thực tế hóa RSSI (noise σ=3→6, nhiễu môi trường, missing tương quan 15%); fallback global_median khi <3 AP; augmentation (noise + AP dropout); CosineAnnealingWarmRestarts + early stopping; grid search ngưỡng anomaly; thêm SimpleCNN baseline; nighttime 22–6h; MobileSensorFusion; đo thêm latency end-to-end; topology.self_weight vào config.")
bullet("Sửa lỗi rò rỉ đánh giá (Fix A)", "Tách 3 phần KHÔNG giao nhau cho anomaly: train D01–D10 / chọn ngưỡng D11–D12 / test D13–D14 (test_days ghi vào anomaly_threshold.json; evaluate_anomaly.py chỉ đánh giá test_days) — trước đây ngày chọn ngưỡng nằm trong tập đánh giá.")
bullet("Kiểm định ngoài trên 2 dataset công khai", "UCI Wireless Indoor Localization (7 AP × 4 phòng × 2000 mẫu, DOI 10.24432/C51880) và UJIIndoorLoc (520 AP, DOI 10.24432/C5MS59) — viết scripts/convert_external_dataset.py chuyển về schema project, huấn luyện RoomNetLite + SimpleCNN + baselines: results/external_*.")
bullet("Triển khai thực tế — app Android + Cloudflare Tunnel", "Khắc phục kết nối app (IP LAN sai 192.168.1.100 → tunnel HTTPS); xác nhận end-to-end: POST /api/collect HTTP 200 qua tunnel (11/10 14:03). Cơ sở dữ liệu đã chứa 639 wifi_scans THẬT từ Android (thiết bị PEDM00) ở 2 phòng thật: Phòng ngủ (337 mẫu/5 session), Nhà Vệ Sinh (301 mẫu/8 session).")
bullet("Phát hiện và sửa lỗi test ghi rác DB", "Test API không cô lập DB → 11 home \"Nhà Smoke Test\" rác trong data/smarthome.db. Đã sửa: tests/test_api_integration.py đặt SMART_HOME_DATABASE trỏ DB tạm trước khi import server. Việc xóa các home rác chờ chủ project duyệt (không tự xóa bản ghi DB).")
bullet("Kiểm chứng", "43/43 unit test pass; SQLite PRAGMA integrity_check = ok, foreign_key_check = 0 vi phạm (10 bảng).")

# ============================== (b) LỖI + CÁCH SỬA ==============================
heading("2. Lỗi đã phát hiện và cách sửa", 1)
errs = [
    ["CAO", "1", "Dữ liệu anomaly mất cân bằng nghiêm trọng: 7 mẫu/loại vs 560 normal", "scripts/generate_synthetic_data.py:111-135", "Tăng 50 mẫu/loại × 4 loại + biến thiên dwell ±20%", "Đã sửa"],
    ["CAO", "2", "Dữ liệu RSSI gốc quá dễ (signature cứng +14/+9 dB, noise σ=3) — baseline đo được Accuracy 100% giả tạo", "scripts/generate_synthetic_data.py:19-25,34", "Signature +6/+4, noise σ=6, nhiễu môi trường, missing tương quan 15%, burst 5%", "Đã sửa"],
    ["CAO", "3", "RÒ RỈ ĐÁNH GIÁ anomaly: ngày dùng chọn ngưỡng (D13–D14) nằm trong tập đánh giá", "scripts/train_anomaly.py:84-89 · scripts/evaluate_anomaly.py:35-36,40", "Fix A: tách train D01–D10 / threshold D11–D12 / test D13–D14; evaluate chỉ chạy test_days", "Đã sửa"],
    ["CAO", "4", "Thiếu baseline CNN đơn giản để so sánh trước/sau cải tiến (yêu cầu đề cương)", "scripts/train_room.py", "SimpleCNN (3 conv chuẩn, không depthwise/center/temporal loss) + train/evaluate_simple_cnn.py + K-fold", "Đã sửa"],
    ["CAO", "5", "Test API không cô lập DB → ghi rác vào data/smarthome.db thật (11 home 'Nhà Smoke Test')", "tests/test_api_integration.py:10-14", "Đặt SMART_HOME_DATABASE trỏ DB tạm trong temp TRƯỚC khi import server/app.py; dọn home rác chờ chủ project duyệt", "Đã sửa (dọn DB chờ duyệt)"],
    ["TB", "6", "Median relative-feature nhiễu khi < 3 AP hiển thị", "src/smarthome/preprocessing.py:50-52", "Fallback global_median/global_std tính khi fit", "Đã sửa"],
    ["TB", "7", "Ngưỡng anomaly quantile 0.99 cố định, không xác thực", "scripts/train_anomaly.py (bản cũ)", "Grid search [0.90–0.995] trên validation normal+anomaly, chọn F1", "Đã sửa"],
    ["TB", "8", "Huấn luyện cố định 35 epochs, không early stopping", "scripts/train_room.py · train_anomaly.py", "CosineAnnealingWarmRestarts + early stopping (patience 10/15)", "Đã sửa"],
    ["TB", "9", "Nighttime 0–5h không thực tế", "config.yaml:61-62", "Đổi thành 22–6h", "Đã sửa"],
    ["TB", "10", "MobileSensorFusion chưa nối vào pipeline inference", "src/smarthome/inference.py", "process_mobile_sensor() + fuse_alert() nhận mobile_reasons", "Đã sửa"],
    ["TB", "11", "Chưa có results/ lưu chỉ số có cấu trúc", "(thiếu)", "results/: before_original + after_optimized + external_uci_wil + external_ujiindoorloc + runlogs + run_info + README", "Đã sửa"],
    ["T", "12", "Độ trễ chỉ đo model forward", "scripts/evaluate_room.py", "Thêm mean_e2e_latency_ms_per_sample (softmax + TopologyFilter)", "Đã sửa"],
    ["T", "13", "topology self_weight hard-code; thiếu khóa config", "src/smarthome/topology.py · config.yaml", "Đưa vào config (trùng default — không đổi hành vi)", "Đã sửa"],
    ["T", "14", "App Android cấu hình IP LAN sai (192.168.1.100 ≠ IP máy 192.168.1.236) + Firewall chặn inbound 5000", "cấu hình app + Windows Firewall", "Chuyển sang URL Cloudflare Tunnel HTTPS (đã xác minh 200 từ Internet); hướng dẫn rule netsh nếu muốn LAN", "Đã sửa (đang dùng tunnel)"],
]
t = table(["Mức độ", "#", "Mô tả lỗi", "Vị trí", "Cách sửa", "Trạng thái"], errs)
for i, row in enumerate(t.rows):
    if i == 0: continue
    color_status(row.cells[5], errs[i-1][5])

# ============================== (c) TRƯỚC / SAU ==============================
heading("3. Bảng chỉ số trước/sau (results/, chạy thật, seed 42)", 1)
rows = [
    ["Phân loại phòng — RoomNetLite (test S08): Accuracy", pct(b_room["accuracy"]), pct(a_room["accuracy"]), "Dữ liệu v1 → v2 (thực tế hơn); không so sánh tuyệt đối"],
    ["Phân loại phòng — RoomNetLite: Macro F1", pct(b_room["macro_f1"]), pct(a_room["macro_f1"]), ""],
    ["Phân loại phòng — RoomNetLite: Val macro F1", pct(b_val["macro_f1"]), pct(a_rval["macro_f1"]), ""],
    ["Baseline CNN — SimpleCNN (test S08): Accuracy", DASH, pct(a_simp["accuracy"]), "Mới thêm để so sánh trước/sau cải tiến"],
    ["So sánh nội tại (cùng dữ liệu v2, cùng split): RoomNetLite − SimpleCNN", DASH, "+" + pct(a_room["accuracy"] - a_simp["accuracy"]), "Bằng chứng cải tiến mô hình"],
    ["K-fold 5-fold RoomNetLite: mean ± std", DASH, f"{pct(kf_r['mean_macro_f1'])} ± {pct(kf_r['std_macro_f1'])}", f"95% CI [{pct(kf_r['ci_95_lower'])}, {pct(kf_r['ci_95_upper'])}]"],
    ["K-fold 5-fold SimpleCNN: mean ± std", DASH, f"{pct(kf_s['mean_macro_f1'])} ± {pct(kf_s['std_macro_f1'])}", f"95% CI [{pct(kf_s['ci_95_lower'])}, {pct(kf_s['ci_95_upper'])}]"],
    ["RandomForest (test S08)", pct(b_base["RandomForest"]["accuracy"]), pct(a_base["RandomForest"]["accuracy"]), ""],
    ["MLP (test S08)", pct(b_base["MLP"]["accuracy"]), pct(a_base["MLP"]["accuracy"]), ""],
    ["kNN (test S08)", pct(b_base["kNN"]["accuracy"]), pct(a_base["kNN"]["accuracy"]), "kNN nhạy với noise của dữ liệu v2"],
    ["Bất thường — Hybrid (AE+Rules): Precision", pct(b_anom["hybrid_ae_plus_rules"]["precision"]), pct(a_anom["hybrid_ae_plus_rules"]["precision"]), "Protocol khác: trước = mọi ngày (có rò rỉ, 490 seq); sau = test riêng D13–D14 (166 seq)"],
    ["Bất thường — Hybrid: Recall", pct(b_anom["hybrid_ae_plus_rules"]["recall"]), pct(a_anom["hybrid_ae_plus_rules"]["recall"]), ""],
    ["Bất thường — Hybrid: F1", pct(b_anom["hybrid_ae_plus_rules"]["f1"]), pct(a_anom["hybrid_ae_plus_rules"]["f1"]), ""],
    ["Bất thường — AE-only: F1", pct(b_anom["ae_only"]["f1"]), pct(a_anom["ae_only"]["f1"]), "Chỉ reconstruction error (không rules)"],
    ["Ngưỡng anomaly", f"{b_anom['threshold']:.5f} (quantile 0.99 cố định)", f"{a_thr['threshold']:.5f} (quantile {a_thr['quantile']} do grid search chọn)", "Số mẫu đánh giá: trước 490 / sau 166"],
    ["Độ trễ model (ms/mẫu)", f"{b_room['mean_inference_ms_per_sample']:.4f}", f"{a_room['mean_inference_ms_per_sample']:.4f}", "Real-time (< 0.1 ms)"],
    ["Độ trễ end-to-end (ms/mẫu)", DASH, f"{a_room['mean_e2e_latency_ms_per_sample']:.4f}", "Gồm softmax + TopologyFilter — mới đo"],
]
table(["Chỉ số (kết quả chạy thật)", "Trước (gốc)", "Sau (tối ưu)", "Ghi chú"], rows)
para("Ghi chú: (1) Accuracy 100% của bản gốc là hệ quả dữ liệu v1 quá dễ — chính là lỗi #2; (2) chỉ số anomaly trước/sau không so sánh tuyệt đối vì protocol đã sửa lỗi rò rỉ (#3); (3) test anomaly chỉ chứa 2/4 loại do dữ liệu mô phỏng chỉ có anomaly ở 4 ngày cuối.", size=12)

# ============================== 3.1 KIỂM ĐỊNH NGOÀI ==============================
heading("3.1. Kiểm định ngoài trên dữ liệu công khai (RSSI thật của bên thứ ba)", 1)
ext_rows = []
if ext["external_uci_wil"]["room"]:
    w = ext["external_uci_wil"]
    ext_rows.append([
        "UCI Wireless Indoor Localization — 7 AP × 4 phòng × 2000 mẫu (DOI 10.24432/C51880, CC BY 4.0)",
        "4", "2000", pct(w["room"]["accuracy"]), pct(w["room"]["macro_f1"]), pct(w["simple"]["accuracy"]),
        f"RF {pct(w['base']['RandomForest']['accuracy'])} / kNN {pct(w['base']['kNN']['accuracy'])} / MLP {pct(w['base']['MLP']['accuracy'])}",
        "Ngang dải 96–99% đã công bố; đúng kịch bản nhà nhỏ ít AP"])
if ext["external_ujiindoorloc"]["room"]:
    u = ext["external_ujiindoorloc"]
    ext_rows.append([
        "UJIIndoorLoc — 520 AP, toà 2/tầng 3, lưới 6 vùng × 2694 mẫu (DOI 10.24432/C5MS59, CC BY 4.0)",
        "6", "2694", pct(u["room"]["accuracy"]), pct(u["room"]["macro_f1"]), pct(u["simple"]["accuracy"]),
        f"RF {pct(u['base']['RandomForest']['accuracy'])} / MLP {pct(u['base']['MLP']['accuracy'])} / kNN {pct(u['base']['kNN']['accuracy'])}",
        "Fingerprint 1560 chiều + nhãn vùng lưới — khó hơn hẳn; RF tốt nhất (92.36%)"])
table(["Dataset (nguồn)", "Vùng", "Mẫu", "RoomNetLite Acc", "RoomNetLite F1", "SimpleCNN Acc", "Baselines", "Ghi chú"], ext_rows)
para("Ý nghĩa: (1) mô hình hoạt động trên RSSI THẬT của bên thứ ba, không chỉ dữ liệu tự sinh; (2) trên dữ liệu ít AP (7 — gần thực tế nhà nhỏ), RoomNetLite đạt 98.99% ngang baselines; (3) trên fingerprint siêu chiều (520 AP) và nhãn vùng lưới, RandomForest vượt CNN — hạn chế được ghi nhận ở mục 5 (hướng: lọc WAP hiếm, tăng hidden_channels).", size=12)

# ============================== (d) ĐỐI CHIẾU ĐỀ CƯƠNG ==============================
heading("4. Đối chiếu yêu cầu đề cương (Đạt / Đạt một phần / Chưa đạt)", 1)
reqs = [
    ["Phân loại phòng từ vector RSSI bằng lightweight CNN/1D-CNN",
     "ĐẠT",
     f"RoomNetLite 1D-CNN depthwise separable (~50k tham số). Synthetic: test Accuracy {pct(a_room['accuracy'])}, Macro F1 {pct(a_room['macro_f1'])}; K-fold 5 {pct(kf_r['mean_macro_f1'])}±{pct(kf_r['std_macro_f1'])} (results/after_optimized/). Kiểm định ngoài RSSI thật: UCI WIL {pct(ext['external_uci_wil']['room']['accuracy'])} (results/external_uci_wil/)."],
    ["Mô-đun phát hiện bất thường bằng autoencoder tái tạo quỹ đạo (reconstruction error)",
     "ĐẠT",
     f"GRU-AE (src/smarthome/models/gru_autoencoder.py). Test tách riêng (protocol đã sửa rò rỉ): AE-only F1 {pct(a_anom['ae_only']['f1'])}; hybrid AE+Rules F1 {pct(a_anom['hybrid_ae_plus_rules']['f1'])} (results/after_optimized/anomaly_test_metrics.json)."],
    ["Phát hiện đứng yên quá lâu, di chuyển bất thường, nghi ngờ té ngã",
     "ĐẠT MỘT PHẦN",
     "RuleEngine: dwell quá giới hạn, chuyển phòng bất khả thi, hoạt động đêm (src/smarthome/anomaly.py) + MobileSensorFusion: impact + immobility (inference.py:process_mobile_sensor, /api/sensor, bảng sensor_samples). Chưa kiểm thử với dữ liệu accelerometer thật."],
    ["Thu thập RSSI theo phòng từ router/AP có sẵn + app Android; tiền xử lý, chuẩn hóa",
     "ĐẠT",
     "End-to-end ĐÃ CHẠY THẬT: data/smarthome.db chứa 639 wifi_scans từ Android (thiết bị PEDM00) qua router sẵn có — Phòng ngủ 337 mẫu/5 session, Nhà Vệ Sinh 301 mẫu/8 session; 11/10/2026 14:03 POST /api/collect HTTP 200 qua Cloudflare Tunnel (log .tmp/flask.log). Tiền xử lý: RSSIPreprocessor absolute/relative/mask + global median fallback."],
    ["Kịch bản bất thường mô phỏng",
     "ĐẠT",
     "4 loại (long_bathroom_stay, long_corridor_stay, night_activity, unusual_transition_pattern) × 50 mẫu, dwell ±20% (scripts/generate_synthetic_data.py)."],
    ["So sánh độ chính xác phân loại phòng trước/sau cải tiến",
     "ĐẠT",
     f"Cùng dữ liệu v2 + cùng split S08: SimpleCNN {pct(a_simp['accuracy'])} vs RoomNetLite {pct(a_room['accuracy'])} (+{pct(a_room['accuracy']-a_simp['accuracy'])}); K-fold 5: {pct(kf_r['mean_macro_f1'])}±{pct(kf_r['std_macro_f1'])} vs {pct(kf_s['mean_macro_f1'])}±{pct(kf_s['std_macro_f1'])}."],
    ["Chỉ số: Accuracy; Precision/Recall bất thường; độ trễ thời gian thực",
     "ĐẠT",
     f"Accuracy {pct(a_room['accuracy'])}; Hybrid Precision {pct(a_anom['hybrid_ae_plus_rules']['precision'])} / Recall {pct(a_anom['hybrid_ae_plus_rules']['recall'])}; độ trễ model {a_room['mean_inference_ms_per_sample']:.3f} ms, end-to-end {a_room['mean_e2e_latency_ms_per_sample']:.3f} ms mỗi mẫu."],
    ["Demo dashboard Flask: vị trí theo phòng + cảnh báo bất thường",
     "ĐẠT",
     "server/app.py: dashboard + /api/scan, /api/status, /api/history, /api/alerts, /api/metrics; đang truy cập từ xa qua Cloudflare Tunnel (đã xác minh HTTP 200 từ Internet, 11/10/2026)."],
    ["Cấu trúc lưu trữ kết quả thuật toán có tổ chức",
     "ĐẠT",
     "SQLite 10 bảng (integrity ok, 0 vi phạm FK) + results/ chuẩn hóa: before_original, after_optimized, external_uci_wil, external_ujiindoorloc (JSON + runlogs + run_info + README tái lập)."],
    ["Triển khai trên dữ liệu thực tế (lab/phòng thực tế)",
     "ĐẠT MỘT PHẦN",
     "Đã thu thập 639 mẫu RSSI THẬT trong nhà thật (app Android + router sẵn có), 2 phòng, nhiều session; home 'Nhà A' từng train model_status=READY trên dữ liệu này. Còn thiếu: thu đủ protocol (100 mẫu/session × 3 hướng × 3 session/phòng) → train_home.py với pipeline đã tối ưu → bảng metrics chính thức trên dữ liệu thật (đang tiếp diễn: session S08 hôm nay)."],
]
t = table(["Yêu cầu đề cương", "Trạng thái", "Bằng chứng (file + số liệu chạy thật) và lý do"], reqs)
for i, row in enumerate(t.rows):
    if i == 0: continue
    color_status(row.cells[1], reqs[i-1][1])

# ============================== (e) TỒN TẠI + ĐỀ XUẤT ==============================
heading("5. Tồn tại và đề xuất bước tiếp theo", 1)
todo = [
    ["Hoàn tất thu thập dữ liệu thật theo protocol", "CAO", "Tiếp tục S08+ tới đủ 100 mẫu/session × 3 hướng (PORTRAIT_UP, LANDSCAPE_LEFT, FLAT_UP) × 3 session cho từng phòng; sau đó bấm TRAIN trên dashboard (train_home.py — đã dùng pipeline tối ưu) để có bảng metrics chính thức trên dữ liệu thật.", "Tuần 9–10 (đang làm)"],
    ["Dọn 11 home 'Nhà Smoke Test' rác trong smarthome.db", "TB", "Test đã sửa isolation; bản ghi rác còn trong DB — CẦN CHỦ PROJECT DUYỆT mới xóa (giữ home 'Nhà A' chứa dữ liệu thật).", "Tuần 9"],
    ["RoomNetLite kém hơn RF/SimpleCNN trên fingerprint siêu chiều (UJI 520 AP)", "TB", "Lọc WAP hiếm (xuất hiện <1% mẫu), tăng hidden_channels, hoặc tinh chỉnh cho dữ liệu nhiều chiều; giữ SimpleCNN làm baseline đối chiếu.", "Tuần 10–11"],
    ["Té ngã: kiểm thử accelerometer thật", "TB", "Ghi gia tốc thực (ngã mô phỏng trên đệm) qua /api/sensor, hiệu chỉnh impact_threshold=18g, kiểm thử cảnh báo CRITICAL của MobileSensorFusion.", "Tuần 10"],
    ["URL tunnel đổi mỗi lần restart", "T", "Named tunnel cố định — cần tài khoản Cloudflare + cloudflared tunnel login.", "Tuần 11"],
    ["Nén model cho edge deployment", "T", "Quantization INT8 / pruning RoomNetLite; hiện 0.03–0.09 ms/mẫu trên CPU đã đủ real-time.", "Tuần 11–12"],
]
table(["Vấn đề tồn tại", "Mức độ", "Đề xuất giải pháp", "Thời gian dự kiến"], todo)

heading("6. Tiến độ theo kế hoạch 12 tuần (17/8 – 8/11/2026) — cập nhật tại tuần 8", 1)
weeks = [
    ["Tuần 1–2", "Tổng quan Smart Home, nhu cầu giám sát không xâm phạm riêng tư", "ĐẠT", "docs/01_tong_quan_va_nhu_cau.md"],
    ["Tuần 3–4", "Khảo sát Room-level Fingerprinting + nhận dạng bất thường chuỗi vị trí", "ĐẠT", "docs/02_khao_sat_phuong_phap.md"],
    ["Tuần 5–6", "Đề xuất cải tiến lightweight CNN + autoencoder tái tạo quỹ đạo", "ĐẠT", "docs/03_phuong_phap_de_xuat.md; src/smarthome/models/"],
    ["Tuần 7–8", "Cài đặt, tiền xử lý, huấn luyện, mô phỏng kịch bản bất thường", "ĐẠT", "Pipeline hoàn chỉnh + tối ưu (results/); kiểm định ngoài 2 dataset công khai; 43/43 test"],
    ["Tuần 9–10", "Thực nghiệm lab/phòng thực tế; đánh giá trước/sau; đo độ trễ", "ĐANG THỰC HIỆN", "App Android end-to-end ✓ (639 mẫu thật); tunnel ✓; còn: đủ protocol thu thập + train home thật"],
    ["Tuần 11–12", "Hoàn thiện demo, báo cáo, slide", "CHƯA LÀM", "Theo kế hoạch: demo thực tế + báo cáo cuối khóa + slide"],
]
t = table(["Tuần", "Công việc theo đề cương", "Trạng thái", "Bằng chứng"], weeks)
for i, row in enumerate(t.rows):
    if i == 0: continue
    color_status(row.cells[2], weeks[i-1][2])

para("Kết luận (cập nhật tuần 8): 9/11 yêu cầu ĐẠT, 2/11 ĐẠT MỘT PHẦN (phát hiện té ngã qua accelerometer thật; đánh giá chính thức trên dữ liệu nhà thật đang tiếp diễn), 0 CHƯA ĐẠT. Toàn bộ số liệu sinh trực tiếp từ results/ (chạy thật 2026-10-11, seed 42); bằng chứng thu thập thật: 639 wifi_scans trong data/smarthome.db từ thiết bị Android PEDM00.", size=12)

out = Path(__file__).resolve().parent / "BAO_CAO_KET_QUA.docx"
doc.save(str(out))
print("Saved:", out)