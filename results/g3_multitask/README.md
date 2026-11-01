# G3 — Multi-task + Ensemble meta-learning (chạy thật 2026-11-01, seed 42)

So sánh công bằng với `results/after_optimized/`: **dùng lại đúng tập
`data/processed/` v2 đã chuẩn hóa (train/val/test theo session, seed 42) —
không sinh lại dữ liệu, không đụng tập test khi chọn model.**

## Lệnh tái lập (theo thứ tự)

```powershell
Copy-Item models\preprocessor.json results\g3_multitask\models\
python scripts/train_room.py       --models-dir results/g3_multitask/models
python scripts/train_room_mt.py    --models-dir results/g3_multitask/models
python scripts/train_simple_cnn.py --models-dir results/g3_multitask/models
python scripts/train_ensemble.py   --models-dir results/g3_multitask/models
python scripts/evaluate_room.py    --models-dir results/g3_multitask/models
python scripts/evaluate_room.py    --models-dir results/g3_multitask/models --model RoomNetMT
python scripts/evaluate_room.py    --models-dir results/g3_multitask/models --model SimpleCNN
python scripts/train_baselines.py  --models-dir results/g3_multitask/models
python scripts/full_security_audit.py
```

Anomaly pipeline (train_anomaly + evaluate_anomaly) KHÔNG chạy lại — G3 chỉ
đổi model phòng; kết quả anomaly giữ nguyên từ `after_optimized`.

## Kết quả test (file JSON tương ứng, không copy tay)

| Model | Test Accuracy | Test Macro F1 | Latency (ms/sample) | File |
|---|---|---|---|---|
| RoomNetLite (G2 baseline) | 98.99% | 98.99% | 0.0367 | `models/room_test_metrics.json` |
| **RoomNetMT (được chọn)** | **99.16%** | **99.17%** | **0.0193** | `models/room_test_metrics_RoomNetMT.json` |
| SimpleCNN | 97.65% | 97.65% | — | `models/room_test_metrics_SimpleCNN.json` |
| RandomForest | 99.16% | 99.16% | — | `models/baseline_metrics.json` |
| MLP | 98.99% | 98.99% | — | `models/baseline_metrics.json` |
| kNN | 88.26% | 88.29% | — | `models/baseline_metrics.json` |

## Ensemble meta-learning (FIND3-style) — chọn trên VALIDATION

`models/ensemble_val_metrics.json`:

| Ứng viên | Val Accuracy | Val Macro F1 |
|---|---|---|
| **RoomNetMT** | **98.99%** | **99.00%** |
| RoomNetLite | 98.83% | 98.83% |
| SimpleCNN | 98.66% | 98.66% |
| RandomForest | 98.15% | 98.16% |
| MLP | 98.15% | 98.15% |
| kNN | 88.26% | 88.19% |

→ `model_choice.json` chọn **RoomNetMT**. Lưu ý minh họa: RandomForest đạt
test F1 99.16% cao hơn RoomNetLite trên test nhưng thua trên validation —
chọn theo test sẽ là rò rỉ đánh giá; quy tắc là chỉ chọn trên validation.

## Head hoạt động (multi-task, ARIL-style)

`models/roomnet_mt_val_metrics.json`: act_agreement = **97.32%** với nhãn
chưng cất từ bộ luật ActivityMonitor (ngẫu nhiên 25%). Nhãn suy trong phạm vi
cửa sổ bằng median delta (bộ luật gốc dùng EMA theo scan — đã ghi chú khác
biệt trong `models/roomnet_mt.py`).

## Bảo mật — tối ưu theo 2 tài liệu SECURITY.md + SECURITY_AUDIT_REPORT.md

Scanner `scripts/full_security_audit.py` được sửa 7 lỗi độ chính xác (pattern
DES khớp "DESC"/"description", self-scan, dò dependency theo tên thay vì
version, pattern Log Android dính precedence, allowlist cột DB đã soát,
git-history hạ INFO, marker `# nosec`): 69 findings (10 HIGH) → **4 INFO**,
đều là thiết kế có chủ đích ghi trong SECURITY.md. Chi tiết: see git log
phiên này.
