# -*- coding: utf-8 -*-
"""Chuyen doi dataset cong khai (UCI WIL / UJIIndoorLoc) ve schema cua project:
timestamp, session_id, device_id, room, AP_XX...

- UCI WIL: 4 phong x 500 mau, 7 AP, khong missing. 5 session (S01-S05),
  moi session = 1 block 100 mau lien tiep cua TUNG phong (train 3/val 1/test 1).
- UJIIndoorLoc: chon toa/floor nhieu mau nhat (BUILDINGID=2, FLOOR=3), chia 6 vung
  bang luoi 2 (longitude, median) x 3 (latitude, tercile) -> Zone1..Zone6.
  6 session (S01-S06), moi session = 1 block mau ke tiep theo thoi gian cua tung vung
  (train 4/val 1/test 1). Gia tri WAP=100 (khong phat hien) -> -100 (quy uoc project).
  validationData.csv (thu sau) -> wifi_fingerprints_temporal_test.csv neu du mau.
Cau hinh sinh ra: config_external_<source>.yaml (deepcopy config.yaml, chi de rooms/topology/sessions).
Nguon + license + trich dan ghi vao meta.json.
"""
from __future__ import annotations
import argparse
import json
from copy import deepcopy
from pathlib import Path

import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parents[1]

SOURCES = {
    "uci_wil": {
        "name": "UCI Wireless Indoor Localization (UCI ID 422)",
        "citation": "Bhatt, R. (2017). Wireless Indoor Localization [Dataset]. UCI Machine Learning Repository. DOI 10.24432/C51880.",
        "license": "CC BY 4.0",
        "url": "https://archive.ics.uci.edu/dataset/422/wireless+indoor+localization",
        "download": "https://archive.ics.uci.edu/static/public/422/wireless+indoor+localization.zip",
    },
    "ujiindoorloc": {
        "name": "UJIIndoorLoc (UCI ID 310)",
        "citation": "Torres-Sospedra, J., Montoliu, R., Martinez-UsO, A., Arnau, T. J., Avariento, J. P. et al. (2014). UJIIndoorLoc [Dataset]. UCI Machine Learning Repository. DOI 10.24432/C5MS59.",
        "license": "CC BY 4.0",
        "url": "https://archive.ics.uci.edu/dataset/310/ujiindoorloc",
        "download": "https://archive.ics.uci.edu/static/public/310/ujiindoorloc.zip",
    },
}


def _chain_topology(rooms: list[str]) -> dict[str, list[str]]:
    topo = {}
    for i, r in enumerate(rooms):
        allowed = [rooms[i - 1], r] if i > 0 else [r]
        if i < len(rooms) - 1:
            allowed.append(rooms[i + 1])
        topo[r] = allowed
    return topo


def make_config(rooms: list[str], n_train: int, n_val: int, n_test: int) -> dict:
    with open(ROOT / "config.yaml", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    cfg = deepcopy(cfg)
    cfg["rooms"] = rooms
    cfg["room_topology"] = _chain_topology(rooms)
    cfg["data"]["room_train_sessions"] = n_train
    cfg["data"]["room_val_sessions"] = n_val
    cfg["data"]["room_test_sessions"] = n_test
    return cfg


def convert_uci_wil(raw: Path):
    df = pd.read_csv(raw, sep="\t", header=None)
    if df.shape[1] != 8:
        df = pd.read_csv(raw, sep=None, header=None, engine="python")
    assert df.shape[1] == 8, f"expected 8 columns, got {df.shape[1]}"
    df.columns = [f"W{i}" for i in range(1, 8)] + ["room_id"]
    rooms = sorted(int(r) for r in df.room_id.unique())
    room_names = {r: f"Room{r}" for r in rooms}

    K = 5
    parts = []
    ts = 1_780_000_000.0
    block_size = None
    for r in rooms:
        assert df.room_id.nunique() == len(rooms) and (df.room_id == r).sum() >= K * 20
    for k in range(K):
        sid = f"S{k + 1:02d}"
        for r in rooms:
            sub = df[df.room_id == r].reset_index(drop=True)
            bs = len(sub) // K
            block_size = bs
            blk = sub.iloc[k * bs:(k + 1) * bs]
            m = blk[[f"W{i}" for i in range(1, 8)]].to_numpy(dtype=float)
            d = pd.DataFrame(m, columns=[f"AP_{i:02d}" for i in range(1, 8)])
            d.insert(0, "timestamp", [ts + 2 * j for j in range(len(d))])
            d.insert(1, "session_id", sid)
            d.insert(2, "device_id", "uciwil-phone01")
            d.insert(3, "room", room_names[r])
            ts += 2 * len(d)
            parts.append(d)
    out = pd.concat(parts, ignore_index=True)
    meta = {
        "source": SOURCES["uci_wil"],
        "original_format": "wifi_localization.txt — 2000 hang, tab-separated, 7 cot RSSI dBm + nhan phong 1-4, KHONG gia tri thieu, khong timestamp (tao timestamp gia lien tiep +2s de dap ung schema)",
        "room_mapping": {room_names[r]: r for r in rooms},
        "session_scheme": f"{K} session (S01-S05); session Sk = block thu k gom {block_size} mau lien tiep cua TUNG phong -> moi split deu chua du 4 phong",
        "split_sessions": {"train": 3, "val": 1, "test": 1},
        "rows": int(len(out)),
        "rooms": [room_names[r] for r in rooms],
        "ap_columns": [f"AP_{i:02d}" for i in range(1, 8)],
    }
    return out, meta, [room_names[r] for r in rooms], 3, 1, 1


def convert_ujiindoorloc(train_csv: Path, val_csv: Path | None):
    tr = pd.read_csv(train_csv)
    vc = (tr.BUILDINGID.astype(str) + "-" + tr.FLOOR.astype(str)).value_counts()
    bid, fl = (int(x) for x in vc.idxmax().split("-"))
    sub = tr[(tr.BUILDINGID == bid) & (tr.FLOOR == fl)].copy()

    lon_med = float(sub.LONGITUDE.median())
    lat_q = sub.LATITUDE.quantile([1 / 3, 2 / 3]).astype(float).tolist()

    def zone_of(lon, lat):
        half = 0 if lon <= lon_med else 1
        terc = 0 if lat <= lat_q[0] else (1 if lat <= lat_q[1] else 2)
        return terc * 2 + half  # 0..5

    sub["zone"] = [zone_of(a, b) for a, b in zip(sub.LONGITUDE, sub.LATITUDE)]
    zones = sorted(int(z) for z in sub.zone.unique())
    room_names = {z: f"Zone{z + 1}" for z in zones}
    counts = {z: int((sub.zone == z).sum()) for z in zones}
    min_count = min(counts.values())

    K = 6
    while K > 3 and min_count // K < 25:
        K -= 1

    wap_cols = [f"WAP{i:03d}" for i in range(1, 521)]
    ap_cols = [f"AP_{i:03d}" for i in range(1, 521)]
    parts = []
    block_size = None
    for k in range(K):
        sid = f"S{k + 1:02d}"
        for z in zones:
            s = sub[sub.zone == z].sort_values("TIMESTAMP").reset_index(drop=True)
            bs = len(s) // K
            block_size = bs
            blk = s.iloc[k * bs:(k + 1) * bs]
            m = blk[wap_cols].to_numpy(dtype=float).copy()
            m[m == 100] = -100.0  # quy uoc project: -100 = khong phat hien
            d = pd.DataFrame(m, columns=ap_cols)
            d.insert(0, "timestamp", blk.TIMESTAMP.astype(float).tolist())
            d.insert(1, "session_id", sid)
            d.insert(2, "device_id", "uji-phone01")
            d.insert(3, "room", room_names[z])
            parts.append(d)
    out = pd.concat(parts, ignore_index=True)

    temporal_info = None
    if val_csv is not None and Path(val_csv).exists():
        va = pd.read_csv(val_csv)
        vsub = va[(va.BUILDINGID == bid) & (va.FLOOR == fl)].copy()
        vsub["zone"] = [zone_of(a, b) for a, b in zip(vsub.LONGITUDE, vsub.LATITUDE)]
        vparts = []
        for z in zones:
            s = vsub[vsub.zone == z]
            if len(s) == 0:
                continue
            m = s[wap_cols].to_numpy(dtype=float).copy()
            m[m == 100] = -100.0
            d = pd.DataFrame(m, columns=ap_cols)
            d.insert(0, "timestamp", s.TIMESTAMP.astype(float).tolist())
            d.insert(1, "session_id", "TEMPORAL")
            d.insert(2, "device_id", "uji-phone01")
            d.insert(3, "room", room_names[z])
            vparts.append(d)
        vdf = pd.concat(vparts, ignore_index=True) if vparts else pd.DataFrame()
        if len(vdf) >= 60 and vdf.room.nunique() >= 4:
            temporal_info = {
                "rows": int(len(vdf)),
                "per_room": {k: int(v) for k, v in vdf.room.value_counts().items()},
                "note": "validationData.csv (thu thap sau trainingData) — kiem dinh keo dai theo thoi gian",
            }
        else:
            temporal_info = {"rows": int(len(vdf)), "skipped_reason": "khong du mau (du 60 hang va >=4 vung)"}

    n_train = {6: 4, 5: 3, 4: 2, 3: 2}[K]
    n_val = 1
    meta = {
        "source": SOURCES["ujiindoorloc"],
        "original_format": "trainingData.csv 19937 hang x 529 cot (520 WAP + 9 metadata); gia tri 100 = khong phat hien -> chuyen -100",
        "selection": f"toa nhieu fingerprint nhat: BUILDINGID={bid}, FLOOR={fl} ({int(vc.max())} hang)",
        "zone_grid": {
            "scheme": "2 nua longitude (median) x 3 tercile latitude = 6 vung",
            "longitude_median": lon_med,
            "latitude_terciles": lat_q,
        },
        "room_mapping": {room_names[z]: f"zone={z}" for z in zones},
        "per_zone_rows": counts,
        "session_scheme": f"{K} session (S01-S{K:02d}); session Sk = block thu k ({block_size} mau) sap theo TIMESTAMP cua TUNG vung",
        "split_sessions": {"train": n_train, "val": n_val, "test": K - n_train - n_val},
        "rows": int(len(out)),
        "rooms": [room_names[z] for z in zones],
        "ap_columns": ap_cols,
        "temporal_test": temporal_info,
    }
    return out, meta, [room_names[z] for z in zones], n_train, n_val, K - n_train - n_val, vdf if temporal_info and temporal_info.get("rows", 0) >= 60 else None


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--source", choices=["uci_wil", "ujiindoorloc"], required=True)
    p.add_argument("--raw", required=True, help="wifi_localization.txt (uci_wil) hoac trainingData.csv (ujiindoorloc)")
    p.add_argument("--raw-validation", default=None, help="validationData.csv (ujiindoorloc)")
    p.add_argument("--out-dir", default=None)
    args = p.parse_args()

    out_dir = Path(args.out_dir) if args.out_dir else ROOT / "data" / "external" / args.source
    out_dir.mkdir(parents=True, exist_ok=True)

    if args.source == "uci_wil":
        out, meta, rooms, ntr, nva, nte = convert_uci_wil(Path(args.raw))
        temporal = None
    else:
        out, meta, rooms, ntr, nva, nte, temporal = convert_ujiindoorloc(Path(args.raw), Path(args.raw_validation) if args.raw_validation else None)

    csv_path = out_dir / "wifi_fingerprints.csv"
    out.to_csv(csv_path, index=False)

    cfg = make_config(rooms, ntr, nva, nte)
    cfg_path = ROOT / f"config_external_{args.source}.yaml"
    with open(cfg_path, "w", encoding="utf-8") as f:
        yaml.safe_dump(cfg, f, allow_unicode=True, sort_keys=False)

    meta["output_csv"] = str(csv_path.relative_to(ROOT))
    meta["config"] = cfg_path.name
    if temporal is not None:
        tp = out_dir / "wifi_fingerprints_temporal_test.csv"
        temporal.to_csv(tp, index=False)
        meta["temporal_test"]["file"] = str(tp.relative_to(ROOT))
    with open(out_dir / "meta.json", "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)

    print(f"[{args.source}] rows={len(out)} rooms={rooms} sessions={ntr}+{nva}+{nte} -> {csv_path}")
    if temporal is not None:
        print(f"[{args.source}] temporal test rows={len(temporal)} -> {out_dir / 'wifi_fingerprints_temporal_test.csv'}")
    print(f"[{args.source}] meta -> {out_dir / 'meta.json'}; config -> {cfg_path}")


if __name__ == "__main__":
    main()