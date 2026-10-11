# results/ — Lưu trữ kết quả thuật toán có tổ chức (đề cương mục 7: "Cấu trúc lưu trữ kết quả thuật toán có tổ chức")

Mọi số liệu trong `BAO_CAO_KET_QUA.docx` đều được đọc trực tiếp từ các JSON trong thư mục này — không có số liệu nhập tay.

## Cấu trúc

```
results/
├── README.md                  ← file này
├── before_original/           ← kết quả pipeline GỐC (commit 7b2f120, trước mọi tối ưu)
│   ├── run_info.txt           ← cách chạy, seed, dữ liệu, protocol để tái lập
│   ├── room_test_metrics.json ← accuracy, macro_f1, confusion matrix, classification report, latency
│   ├── room_val_metrics.json
│   ├── anomaly_test_metrics.json  ← ae_only + hybrid_ae_plus_rules (P/R/F1), samples, threshold
│   ├── anomaly_threshold.json
│   ├── baseline_metrics.json  ← kNN / RandomForest / MLP
│   └── runlogs/               ← stdout/stderr đầy đủ 7 bước pipeline
└── after_optimized/           ← kết quả pipeline SAU tối ưu (cùng định dạng file)
    ├── run_info.txt
    ├── room_test_metrics.json, room_val_metrics.json
    ├── simple_cnn_test_metrics.json, simple_cnn_val_metrics.json  ← baseline CNN "trước cải tiến"
    ├── anomaly_test_metrics.json, anomaly_threshold.json (có thêm train_days/threshold_days/test_days)
    ├── baseline_metrics.json
    ├── kfold_metrics_roomnet.json, kfold_metrics_simple.json  ← K-fold CV (mean ± std, 95% CI)
    └── runlogs/
├── external_uci_wil/          ← kiểm định ngoài UCI Wireless Indoor Localization (DOI 10.24432/C51880)
│   └── room/simple/baseline metrics + meta.json + run_info
└── external_ujiindoorloc/     ← kiểm định ngoài UJIIndoorLoc (DOI 10.24432/C5MS59, 520 AP, lưới 6 vùng)
    └── room/simple/baseline metrics + meta.json + run_info
```

## Tái lập

Mọi script gọi `set_seed(42)` (numpy/torch) và dữ liệu synthetic sinh từ seed cố định trong `config.yaml` → kết quả tái lập được trên cùng máy:
- **before**: `git archive 7b2f120 | giải nén → python scripts/{generate_synthetic_data,prepare_data,train_room,evaluate_room,train_anomaly,evaluate_anomaly,train_baselines}.py`
- **after**: tại gốc project, cùng chuỗi lệnh + `train_simple_cnn/evaluate_simple_cnn` + `evaluate_kfold --folds 5`

## Khác biệt protocol giữa hai lần đo (cần ghi nhận khi so sánh)

1. Dữ liệu: v1 (signature +14/+9, noise σ=3, anomaly 7/loại) → v2 (signature +6/+4, noise σ=6, nhiễu môi trường, missing tương quan 15%, anomaly 50/loại).
2. Đào tạo: bản gốc 35 epochs cố định → bản sau có data augmentation, CosineAnnealingWarmRestarts, early stopping.
3. Đánh giá anomaly: bản gốc đánh giá mọi ngày (có rò rỉ — ngày chọn ngưỡng nằm trong tập đánh giá) → bản sau tách test_days (D13–D14) hoàn toàn khỏi huấn luyện/chọn ngưỡng (Fix A).
→ Do đó các số trước/sau **không so sánh tuyệt đối**; so sánh chính nội tại của bản sau là RoomNetLite vs SimpleCNN trên cùng dữ liệu/cùng split.
