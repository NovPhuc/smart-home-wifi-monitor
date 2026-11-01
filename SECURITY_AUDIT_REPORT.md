# Security Audit & Code Review Report
**Project:** An Tâm Home (v2310)
**Date:** 2026-11-01 16:58:29
**Root:** `E:\Downloads\smart-home-wifi-monitor2310\smart-home-wifi-monitor`

## Summary

| Severity | Count |
|----------|-------|
| CRITICAL | 0 |
| HIGH | 10 |
| MEDIUM | 47 |
| LOW | 10 |
| INFO | 2 |
| **Total** | **69** |


## CONFIG (1 findings)

### ⚪ [INFO] mDNS enabled
- **Category:** CONFIG
- **File:** `config.yaml`:0
- **Description:** Service discovery broadcast on LAN
- **Recommendation:** Ensure LAN is trusted; disable if not needed

## CRYPTO (45 findings)

### 🟡 [MEDIUM] Weak Cryptography: Weak cipher mode
- **Category:** CRYPTO
- **File:** `create_clean_db.py`:119
- **CWE:** [CWE-327](https://cwe.mitre.org/data/definitions/327.html)
- **Description:** Use of deprecated/weak cryptographic primitive.
- **Code:**
```
CREATE INDEX IF NOT EXISTS idx_predictions_home_time ON predictions(home_id, timestamp DESC);
```
- **Recommendation:** Use SHA-256+, AES-GCM, bcrypt/scrypt/argon2 for passwords.

### 🟡 [MEDIUM] Weak Cryptography: Weak cipher mode
- **Category:** CRYPTO
- **File:** `create_clean_db.py`:120
- **CWE:** [CWE-327](https://cwe.mitre.org/data/definitions/327.html)
- **Description:** Use of deprecated/weak cryptographic primitive.
- **Code:**
```
CREATE INDEX IF NOT EXISTS idx_alerts_home_time ON alerts(home_id, timestamp DESC);
```
- **Recommendation:** Use SHA-256+, AES-GCM, bcrypt/scrypt/argon2 for passwords.

### 🟡 [MEDIUM] Weak Cryptography: Weak cipher mode
- **Category:** CRYPTO
- **File:** `create_clean_db.py`:121
- **CWE:** [CWE-327](https://cwe.mitre.org/data/definitions/327.html)
- **Description:** Use of deprecated/weak cryptographic primitive.
- **Code:**
```
CREATE INDEX IF NOT EXISTS idx_sensor_home_time ON sensor_samples(home_id, timestamp DESC);
```
- **Recommendation:** Use SHA-256+, AES-GCM, bcrypt/scrypt/argon2 for passwords.

### 🟡 [MEDIUM] Weak Cryptography: Weak cipher mode
- **Category:** CRYPTO
- **File:** `generate_report.py`:99
- **CWE:** [CWE-327](https://cwe.mitre.org/data/definitions/327.html)
- **Description:** Use of deprecated/weak cryptographic primitive.
- **Code:**
```
for level, stt, desc, loc, fix in errors:
```
- **Recommendation:** Use SHA-256+, AES-GCM, bcrypt/scrypt/argon2 for passwords.

### 🟡 [MEDIUM] Weak Cryptography: Weak cipher mode
- **Category:** CRYPTO
- **File:** `generate_report.py`:103
- **CWE:** [CWE-327](https://cwe.mitre.org/data/definitions/327.html)
- **Description:** Use of deprecated/weak cryptographic primitive.
- **Code:**
```
row[2].text = desc
```
- **Recommendation:** Use SHA-256+, AES-GCM, bcrypt/scrypt/argon2 for passwords.

### 🟡 [MEDIUM] Weak Cryptography: Weak cipher mode
- **Category:** CRYPTO
- **File:** `scripts\build_location_events.py`:22
- **CWE:** [CWE-327](https://cwe.mitre.org/data/definitions/327.html)
- **Description:** Use of deprecated/weak cryptographic primitive.
- **Code:**
```
p = argparse.ArgumentParser(description="Compress chronological room predictions into completed room visits for GRU-AE training")
```
- **Recommendation:** Use SHA-256+, AES-GCM, bcrypt/scrypt/argon2 for passwords.

### 🟡 [MEDIUM] Weak Cryptography: Weak cipher mode
- **Category:** CRYPTO
- **File:** `scripts\full_security_audit.py`:24
- **CWE:** [CWE-327](https://cwe.mitre.org/data/definitions/327.html)
- **Description:** Use of deprecated/weak cryptographic primitive.
- **Code:**
```
title: str, description: str, code_snippet: str = "",
```
- **Recommendation:** Use SHA-256+, AES-GCM, bcrypt/scrypt/argon2 for passwords.

### 🟡 [MEDIUM] Weak Cryptography: Weak cipher mode
- **Category:** CRYPTO
- **File:** `scripts\full_security_audit.py`:31
- **CWE:** [CWE-327](https://cwe.mitre.org/data/definitions/327.html)
- **Description:** Use of deprecated/weak cryptographic primitive.
- **Code:**
```
self.description = description
```
- **Recommendation:** Use SHA-256+, AES-GCM, bcrypt/scrypt/argon2 for passwords.

### 🟡 [MEDIUM] Weak Cryptography: Weak cipher mode
- **Category:** CRYPTO
- **File:** `scripts\full_security_audit.py`:43
- **CWE:** [CWE-327](https://cwe.mitre.org/data/definitions/327.html)
- **Description:** Use of deprecated/weak cryptographic primitive.
- **Code:**
```
md += f"- **Description:** {self.description}\n"
```
- **Recommendation:** Use SHA-256+, AES-GCM, bcrypt/scrypt/argon2 for passwords.

### 🟡 [MEDIUM] Weak Cryptography: PyCrypto import
- **Category:** CRYPTO
- **File:** `scripts\full_security_audit.py`:101
- **CWE:** [CWE-327](https://cwe.mitre.org/data/definitions/327.html)
- **Description:** Use of deprecated/weak cryptographic primitive.
- **Code:**
```
(r'from Crypto import', "PyCrypto import"),
```
- **Recommendation:** Use SHA-256+, AES-GCM, bcrypt/scrypt/argon2 for passwords.

### 🟡 [MEDIUM] Weak Cryptography: Weak cipher mode
- **Category:** CRYPTO
- **File:** `scripts\full_security_audit.py`:102
- **CWE:** [CWE-327](https://cwe.mitre.org/data/definitions/327.html)
- **Description:** Use of deprecated/weak cryptographic primitive.
- **Code:**
```
(r'RC4|DES|ECB', "Weak cipher mode"),
```
- **Recommendation:** Use SHA-256+, AES-GCM, bcrypt/scrypt/argon2 for passwords.

### 🟡 [MEDIUM] Weak Cryptography: Weak cipher mode
- **Category:** CRYPTO
- **File:** `scripts\full_security_audit.py`:130
- **CWE:** [CWE-327](https://cwe.mitre.org/data/definitions/327.html)
- **Description:** Use of deprecated/weak cryptographic primitive.
- **Code:**
```
description=f"Line uses pattern that may lead to SQL injection.",
```
- **Recommendation:** Use SHA-256+, AES-GCM, bcrypt/scrypt/argon2 for passwords.

### 🟡 [MEDIUM] Weak Cryptography: Weak cipher mode
- **Category:** CRYPTO
- **File:** `scripts\full_security_audit.py`:143
- **CWE:** [CWE-327](https://cwe.mitre.org/data/definitions/327.html)
- **Description:** Use of deprecated/weak cryptographic primitive.
- **Code:**
```
description="Possible hardcoded credential in source code.",
```
- **Recommendation:** Use SHA-256+, AES-GCM, bcrypt/scrypt/argon2 for passwords.

### 🟡 [MEDIUM] Weak Cryptography: Weak cipher mode
- **Category:** CRYPTO
- **File:** `scripts\full_security_audit.py`:156
- **CWE:** [CWE-327](https://cwe.mitre.org/data/definitions/327.html)
- **Description:** Use of deprecated/weak cryptographic primitive.
- **Code:**
```
description=f"Use of deprecated/weak cryptographic primitive.",
```
- **Recommendation:** Use SHA-256+, AES-GCM, bcrypt/scrypt/argon2 for passwords.

### 🟡 [MEDIUM] Weak Cryptography: Weak cipher mode
- **Category:** CRYPTO
- **File:** `scripts\full_security_audit.py`:169
- **CWE:** [CWE-327](https://cwe.mitre.org/data/definitions/327.html)
- **Description:** Use of deprecated/weak cryptographic primitive.
- **Code:**
```
description="Debug information or sensitive data may be exposed.",
```
- **Recommendation:** Use SHA-256+, AES-GCM, bcrypt/scrypt/argon2 for passwords.

### 🟡 [MEDIUM] Weak Cryptography: Weak cipher mode
- **Category:** CRYPTO
- **File:** `scripts\full_security_audit.py`:182
- **CWE:** [CWE-327](https://cwe.mitre.org/data/definitions/327.html)
- **Description:** Use of deprecated/weak cryptographic primitive.
- **Code:**
```
description="Potential Flask-specific security issue.",
```
- **Recommendation:** Use SHA-256+, AES-GCM, bcrypt/scrypt/argon2 for passwords.

### 🟡 [MEDIUM] Weak Cryptography: Weak cipher mode
- **Category:** CRYPTO
- **File:** `scripts\full_security_audit.py`:221
- **CWE:** [CWE-327](https://cwe.mitre.org/data/definitions/327.html)
- **Description:** Use of deprecated/weak cryptographic primitive.
- **Code:**
```
description=f"Found pattern: {pattern}",
```
- **Recommendation:** Use SHA-256+, AES-GCM, bcrypt/scrypt/argon2 for passwords.

### 🟡 [MEDIUM] Weak Cryptography: Weak cipher mode
- **Category:** CRYPTO
- **File:** `scripts\full_security_audit.py`:257
- **CWE:** [CWE-327](https://cwe.mitre.org/data/definitions/327.html)
- **Description:** Use of deprecated/weak cryptographic primitive.
- **Code:**
```
description=f"Manifest/config contains: {m.group(0)[:100]}",
```
- **Recommendation:** Use SHA-256+, AES-GCM, bcrypt/scrypt/argon2 for passwords.

### 🟡 [MEDIUM] Weak Cryptography: Weak cipher mode
- **Category:** CRYPTO
- **File:** `scripts\full_security_audit.py`:320
- **CWE:** [CWE-327](https://cwe.mitre.org/data/definitions/327.html)
- **Description:** Use of deprecated/weak cryptographic primitive.
- **Code:**
```
description=f"Package {name} may have known vulnerability {cve}",
```
- **Recommendation:** Use SHA-256+, AES-GCM, bcrypt/scrypt/argon2 for passwords.

### 🟡 [MEDIUM] Weak Cryptography: Weak cipher mode
- **Category:** CRYPTO
- **File:** `scripts\full_security_audit.py`:343
- **CWE:** [CWE-327](https://cwe.mitre.org/data/definitions/327.html)
- **Description:** Use of deprecated/weak cryptographic primitive.
- **Code:**
```
description="Users table may store plaintext passwords",
```
- **Recommendation:** Use SHA-256+, AES-GCM, bcrypt/scrypt/argon2 for passwords.

### 🟡 [MEDIUM] Weak Cryptography: Weak cipher mode
- **Category:** CRYPTO
- **File:** `scripts\full_security_audit.py`:361
- **CWE:** [CWE-327](https://cwe.mitre.org/data/definitions/327.html)
- **Description:** Use of deprecated/weak cryptographic primitive.
- **Code:**
```
description=f"Columns: {sensitive_cols}",
```
- **Recommendation:** Use SHA-256+, AES-GCM, bcrypt/scrypt/argon2 for passwords.

### 🟡 [MEDIUM] Weak Cryptography: Weak cipher mode
- **Category:** CRYPTO
- **File:** `scripts\full_security_audit.py`:372
- **CWE:** [CWE-327](https://cwe.mitre.org/data/definitions/327.html)
- **Description:** Use of deprecated/weak cryptographic primitive.
- **Code:**
```
description=str(e)
```
- **Recommendation:** Use SHA-256+, AES-GCM, bcrypt/scrypt/argon2 for passwords.

### 🟡 [MEDIUM] Weak Cryptography: Weak cipher mode
- **Category:** CRYPTO
- **File:** `scripts\full_security_audit.py`:389
- **CWE:** [CWE-327](https://cwe.mitre.org/data/definitions/327.html)
- **Description:** Use of deprecated/weak cryptographic primitive.
- **Code:**
```
description="External webhook endpoint set",
```
- **Recommendation:** Use SHA-256+, AES-GCM, bcrypt/scrypt/argon2 for passwords.

### 🟡 [MEDIUM] Weak Cryptography: Weak cipher mode
- **Category:** CRYPTO
- **File:** `scripts\full_security_audit.py`:400
- **CWE:** [CWE-327](https://cwe.mitre.org/data/definitions/327.html)
- **Description:** Use of deprecated/weak cryptographic primitive.
- **Code:**
```
description="Service discovery broadcast on LAN",
```
- **Recommendation:** Use SHA-256+, AES-GCM, bcrypt/scrypt/argon2 for passwords.

### 🟡 [MEDIUM] Weak Cryptography: Weak cipher mode
- **Category:** CRYPTO
- **File:** `scripts\full_security_audit.py`:417
- **CWE:** [CWE-327](https://cwe.mitre.org/data/definitions/327.html)
- **Description:** Use of deprecated/weak cryptographic primitive.
- **Code:**
```
description="Commits mention secrets/passwords",
```
- **Recommendation:** Use SHA-256+, AES-GCM, bcrypt/scrypt/argon2 for passwords.

### 🟡 [MEDIUM] Weak Cryptography: Weak cipher mode
- **Category:** CRYPTO
- **File:** `scripts\jsonl_to_csv.py`:11
- **CWE:** [CWE-327](https://cwe.mitre.org/data/definitions/327.html)
- **Description:** Use of deprecated/weak cryptographic primitive.
- **Code:**
```
p = argparse.ArgumentParser(description="Convert Android collection JSONL into wide RSSI fingerprint CSV")
```
- **Recommendation:** Use SHA-256+, AES-GCM, bcrypt/scrypt/argon2 for passwords.

### 🟡 [MEDIUM] Weak Cryptography: Weak cipher mode
- **Category:** CRYPTO
- **File:** `scripts\security_sweep.py`:28
- **CWE:** [CWE-327](https://cwe.mitre.org/data/definitions/327.html)
- **Description:** Use of deprecated/weak cryptographic primitive.
- **Code:**
```
# tiết lộ gì và cũng không thao tác trên dữ liệu của ai. Idempotent by design.
```
- **Recommendation:** Use SHA-256+, AES-GCM, bcrypt/scrypt/argon2 for passwords.

### 🟡 [MEDIUM] Weak Cryptography: Weak cipher mode
- **Category:** CRYPTO
- **File:** `scripts\train_home.py`:68
- **CWE:** [CWE-327](https://cwe.mitre.org/data/definitions/327.html)
- **Description:** Use of deprecated/weak cryptographic primitive.
- **Code:**
```
raise ValueError("Need at least three session codes collected in every room")
```
- **Recommendation:** Use SHA-256+, AES-GCM, bcrypt/scrypt/argon2 for passwords.

### 🟡 [MEDIUM] Weak Cryptography: Weak cipher mode
- **Category:** CRYPTO
- **File:** `scripts\train_home.py`:78
- **CWE:** [CWE-327](https://cwe.mitre.org/data/definitions/327.html)
- **Description:** Use of deprecated/weak cryptographic primitive.
- **Code:**
```
parser = argparse.ArgumentParser(description="Train an isolated room model from one SQLite home")
```
- **Recommendation:** Use SHA-256+, AES-GCM, bcrypt/scrypt/argon2 for passwords.

### 🟡 [MEDIUM] Weak Cryptography: Weak cipher mode
- **Category:** CRYPTO
- **File:** `server\security_middleware.py`:112
- **CWE:** [CWE-327](https://cwe.mitre.org/data/definitions/327.html)
- **Description:** Use of deprecated/weak cryptographic primitive.
- **Code:**
```
oldest = sorted(
```
- **Recommendation:** Use SHA-256+, AES-GCM, bcrypt/scrypt/argon2 for passwords.

### 🟡 [MEDIUM] Weak Cryptography: Weak cipher mode
- **Category:** CRYPTO
- **File:** `server\security_middleware.py`:116
- **CWE:** [CWE-327](https://cwe.mitre.org/data/definitions/327.html)
- **Description:** Use of deprecated/weak cryptographic primitive.
- **Code:**
```
for key, _window in oldest[:overflow]:
```
- **Recommendation:** Use SHA-256+, AES-GCM, bcrypt/scrypt/argon2 for passwords.

### 🟡 [MEDIUM] Weak Cryptography: Weak cipher mode
- **Category:** CRYPTO
- **File:** `server\security_middleware.py`:305
- **CWE:** [CWE-327](https://cwe.mitre.org/data/definitions/327.html)
- **Description:** Use of deprecated/weak cryptographic primitive.
- **Code:**
```
"max-age=31536000; includeSubDomains",
```
- **Recommendation:** Use SHA-256+, AES-GCM, bcrypt/scrypt/argon2 for passwords.

### 🟡 [MEDIUM] Weak Cryptography: Weak cipher mode
- **Category:** CRYPTO
- **File:** `server\security_middleware.py`:323
- **CWE:** [CWE-327](https://cwe.mitre.org/data/definitions/327.html)
- **Description:** Use of deprecated/weak cryptographic primitive.
- **Code:**
```
_ERROR_CODES = {
```
- **Recommendation:** Use SHA-256+, AES-GCM, bcrypt/scrypt/argon2 for passwords.

### 🟡 [MEDIUM] Weak Cryptography: Weak cipher mode
- **Category:** CRYPTO
- **File:** `server\security_middleware.py`:353
- **CWE:** [CWE-327](https://cwe.mitre.org/data/definitions/327.html)
- **Description:** Use of deprecated/weak cryptographic primitive.
- **Code:**
```
code = _ERROR_CODES.get(error.code or 500, "HTTP_ERROR")
```
- **Recommendation:** Use SHA-256+, AES-GCM, bcrypt/scrypt/argon2 for passwords.

### 🟡 [MEDIUM] Weak Cryptography: Weak cipher mode
- **Category:** CRYPTO
- **File:** `server\security_middleware.py`:357
- **CWE:** [CWE-327](https://cwe.mitre.org/data/definitions/327.html)
- **Description:** Use of deprecated/weak cryptographic primitive.
- **Code:**
```
error.description or "Yêu cầu không hợp lệ",
```
- **Recommendation:** Use SHA-256+, AES-GCM, bcrypt/scrypt/argon2 for passwords.

### 🟡 [MEDIUM] Weak Cryptography: Weak cipher mode
- **Category:** CRYPTO
- **File:** `src\smarthome\storage.py`:150
- **CWE:** [CWE-327](https://cwe.mitre.org/data/definitions/327.html)
- **Description:** Use of deprecated/weak cryptographic primitive.
- **Code:**
```
CREATE INDEX IF NOT EXISTS idx_predictions_home_time ON predictions(home_id, timestamp DESC);
```
- **Recommendation:** Use SHA-256+, AES-GCM, bcrypt/scrypt/argon2 for passwords.

### 🟡 [MEDIUM] Weak Cryptography: Weak cipher mode
- **Category:** CRYPTO
- **File:** `src\smarthome\storage.py`:151
- **CWE:** [CWE-327](https://cwe.mitre.org/data/definitions/327.html)
- **Description:** Use of deprecated/weak cryptographic primitive.
- **Code:**
```
CREATE INDEX IF NOT EXISTS idx_alerts_home_time ON alerts(home_id, timestamp DESC);
```
- **Recommendation:** Use SHA-256+, AES-GCM, bcrypt/scrypt/argon2 for passwords.

### 🟡 [MEDIUM] Weak Cryptography: Weak cipher mode
- **Category:** CRYPTO
- **File:** `src\smarthome\storage.py`:152
- **CWE:** [CWE-327](https://cwe.mitre.org/data/definitions/327.html)
- **Description:** Use of deprecated/weak cryptographic primitive.
- **Code:**
```
CREATE INDEX IF NOT EXISTS idx_sensor_home_time ON sensor_samples(home_id, timestamp DESC);
```
- **Recommendation:** Use SHA-256+, AES-GCM, bcrypt/scrypt/argon2 for passwords.

### 🟡 [MEDIUM] Weak Cryptography: Weak cipher mode
- **Category:** CRYPTO
- **File:** `src\smarthome\storage.py`:347
- **CWE:** [CWE-327](https://cwe.mitre.org/data/definitions/327.html)
- **Description:** Use of deprecated/weak cryptographic primitive.
- **Code:**
```
ORDER BY created_at DESC LIMIT 1
```
- **Recommendation:** Use SHA-256+, AES-GCM, bcrypt/scrypt/argon2 for passwords.

### 🟡 [MEDIUM] Weak Cryptography: Weak cipher mode
- **Category:** CRYPTO
- **File:** `src\smarthome\storage.py`:556
- **CWE:** [CWE-327](https://cwe.mitre.org/data/definitions/327.html)
- **Description:** Use of deprecated/weak cryptographic primitive.
- **Code:**
```
"SELECT timestamp, wifi_hash FROM wifi_scans WHERE collection_session_id=? ORDER BY id DESC LIMIT 1",
```
- **Recommendation:** Use SHA-256+, AES-GCM, bcrypt/scrypt/argon2 for passwords.

### 🟡 [MEDIUM] Weak Cryptography: Weak cipher mode
- **Category:** CRYPTO
- **File:** `src\smarthome\storage.py`:651
- **CWE:** [CWE-327](https://cwe.mitre.org/data/definitions/327.html)
- **Description:** Use of deprecated/weak cryptographic primitive.
- **Code:**
```
"SELECT * FROM predictions WHERE home_id=? ORDER BY timestamp DESC LIMIT ?", (home_id, int(limit))
```
- **Recommendation:** Use SHA-256+, AES-GCM, bcrypt/scrypt/argon2 for passwords.

### 🟡 [MEDIUM] Weak Cryptography: Weak cipher mode
- **Category:** CRYPTO
- **File:** `src\smarthome\storage.py`:686
- **CWE:** [CWE-327](https://cwe.mitre.org/data/definitions/327.html)
- **Description:** Use of deprecated/weak cryptographic primitive.
- **Code:**
```
"SELECT * FROM alerts WHERE home_id=? ORDER BY timestamp DESC LIMIT ?", (home_id, int(limit))
```
- **Recommendation:** Use SHA-256+, AES-GCM, bcrypt/scrypt/argon2 for passwords.

### 🟡 [MEDIUM] Weak Cryptography: Weak cipher mode
- **Category:** CRYPTO
- **File:** `tests\test_algorithms.py`:111
- **CWE:** [CWE-327](https://cwe.mitre.org/data/definitions/327.html)
- **Description:** Use of deprecated/weak cryptographic primitive.
- **Code:**
```
def test_anomaly_feature_builder_encodes_unknown_room_safely():
```
- **Recommendation:** Use SHA-256+, AES-GCM, bcrypt/scrypt/argon2 for passwords.

### 🟡 [MEDIUM] Weak Cryptography: Weak cipher mode
- **Category:** CRYPTO
- **File:** `tests\test_api_integration.py`:409
- **CWE:** [CWE-327](https://cwe.mitre.org/data/definitions/327.html)
- **Description:** Use of deprecated/weak cryptographic primitive.
- **Code:**
```
def test_invalid_expired_and_rotated_share_codes(client):
```
- **Recommendation:** Use SHA-256+, AES-GCM, bcrypt/scrypt/argon2 for passwords.

### ⚪ [INFO] Pin expiration date found
- **Category:** CRYPTO
- **File:** `android_collector\app\src\main\res\xml\network_security_config.xml`:26
- **Description:** Manifest/config contains: pin-set expiration="2027-11-01"
- **Code:**
```
pin-set expiration="2027-11-01"
```
- **Recommendation:** Ensure pins are rotated before expiration

## DB (2 findings)

### 🟠 [HIGH] Potential sensitive column in meta
- **Category:** DB
- **File:** `data/smarthome.db:meta`:0
- **CWE:** [CWE-312](https://cwe.mitre.org/data/definitions/312.html)
- **Description:** Columns: ['key']
- **Recommendation:** Ensure sensitive data is encrypted/hashed

### 🟠 [HIGH] Potential sensitive column in rooms
- **Category:** DB
- **File:** `data/smarthome.db:rooms`:0
- **CWE:** [CWE-312](https://cwe.mitre.org/data/definitions/312.html)
- **Description:** Columns: ['_name_key']
- **Recommendation:** Ensure sensitive data is encrypted/hashed

## DEPENDENCY (3 findings)

### 🟡 [MEDIUM] Potentially vulnerable dependency: requests<2.31.0
- **Category:** DEPENDENCY
- **File:** `.tmp\baseline-wt\requirements.txt`:0
- **CWE:** [CVE-2023-32681](https://cwe.mitre.org/data/definitions/32681.html)
- **Description:** Package requests may have known vulnerability CVE-2023-32681
- **Code:**
```
Found requests in requirements.txt
```
- **Recommendation:** Update to patched version: pip install --upgrade requests

### 🟡 [MEDIUM] Potentially vulnerable dependency: requests<2.31.0
- **Category:** DEPENDENCY
- **File:** `requirements-docker.txt`:0
- **CWE:** [CVE-2023-32681](https://cwe.mitre.org/data/definitions/32681.html)
- **Description:** Package requests may have known vulnerability CVE-2023-32681
- **Code:**
```
Found requests in requirements-docker.txt
```
- **Recommendation:** Update to patched version: pip install --upgrade requests

### 🟡 [MEDIUM] Potentially vulnerable dependency: requests<2.31.0
- **Category:** DEPENDENCY
- **File:** `requirements.txt`:0
- **CWE:** [CVE-2023-32681](https://cwe.mitre.org/data/definitions/32681.html)
- **Description:** Package requests may have known vulnerability CVE-2023-32681
- **Code:**
```
Found requests in requirements.txt
```
- **Recommendation:** Update to patched version: pip install --upgrade requests

## INFO_LEAK (10 findings)

### 🔵 [LOW] Sensitive data in logs
- **Category:** INFO_LEAK
- **File:** `android_collector\app\src\main\java\com\example\wificollector\MainActivity.kt`:148
- **CWE:** [CWE-532](https://cwe.mitre.org/data/definitions/532.html)
- **Description:** Found pattern: Log\.(d|i|w|e)\(.*password|token|secret
- **Code:**
```
private lateinit var collectorToken: EditText
```
- **Recommendation:** Redact sensitive data before logging

### 🔵 [LOW] Sensitive data in logs
- **Category:** INFO_LEAK
- **File:** `android_collector\app\src\main\java\com\example\wificollector\MainActivity.kt`:191
- **CWE:** [CWE-532](https://cwe.mitre.org/data/definitions/532.html)
- **Description:** Found pattern: Log\.(d|i|w|e)\(.*password|token|secret
- **Code:**
```
collectorToken = findViewById(R.id.collectorToken)
```
- **Recommendation:** Redact sensitive data before logging

### 🔵 [LOW] Sensitive data in logs
- **Category:** INFO_LEAK
- **File:** `android_collector\app\src\main\java\com\example\wificollector\MainActivity.kt`:211
- **CWE:** [CWE-532](https://cwe.mitre.org/data/definitions/532.html)
- **Description:** Found pattern: Log\.(d|i|w|e)\(.*password|token|secret
- **Code:**
```
collectorToken.setText(prefs.getString("collectorToken", ""))
```
- **Recommendation:** Redact sensitive data before logging

### 🔵 [LOW] Sensitive data in logs
- **Category:** INFO_LEAK
- **File:** `android_collector\app\src\main\java\com\example\wificollector\MainActivity.kt`:355
- **CWE:** [CWE-532](https://cwe.mitre.org/data/definitions/532.html)
- **Description:** Found pattern: Log\.(d|i|w|e)\(.*password|token|secret
- **Code:**
```
.putString("collectorToken", collectorToken.text.toString().trim())
```
- **Recommendation:** Redact sensitive data before logging

### 🔵 [LOW] Sensitive data in logs
- **Category:** INFO_LEAK
- **File:** `android_collector\app\src\main\java\com\example\wificollector\MainActivity.kt`:572
- **CWE:** [CWE-532](https://cwe.mitre.org/data/definitions/532.html)
- **Description:** Found pattern: Log\.(d|i|w|e)\(.*password|token|secret
- **Code:**
```
val hasToken = collectorToken.text.toString().trim().isNotEmpty()
```
- **Recommendation:** Redact sensitive data before logging

### 🔵 [LOW] Sensitive data in logs
- **Category:** INFO_LEAK
- **File:** `android_collector\app\src\main\java\com\example\wificollector\MainActivity.kt`:574
- **CWE:** [CWE-532](https://cwe.mitre.org/data/definitions/532.html)
- **Description:** Found pattern: Log\.(d|i|w|e)\(.*password|token|secret
- **Code:**
```
if (!hasToken && !hasSession) {
```
- **Recommendation:** Redact sensitive data before logging

### 🔵 [LOW] Sensitive data in logs
- **Category:** INFO_LEAK
- **File:** `android_collector\app\src\main\java\com\example\wificollector\MainActivity.kt`:715
- **CWE:** [CWE-532](https://cwe.mitre.org/data/definitions/532.html)
- **Description:** Found pattern: Log\.(d|i|w|e)\(.*password|token|secret
- **Code:**
```
val authToken = collectorToken.text.toString().trim()
```
- **Recommendation:** Redact sensitive data before logging

### 🔵 [LOW] Sensitive data in logs
- **Category:** INFO_LEAK
- **File:** `android_collector\app\src\main\java\com\example\wificollector\MainActivity.kt`:725
- **CWE:** [CWE-532](https://cwe.mitre.org/data/definitions/532.html)
- **Description:** Found pattern: Log\.(d|i|w|e)\(.*password|token|secret
- **Code:**
```
if (authToken.isNotEmpty()) {
```
- **Recommendation:** Redact sensitive data before logging

### 🔵 [LOW] Sensitive data in logs
- **Category:** INFO_LEAK
- **File:** `android_collector\app\src\main\java\com\example\wificollector\MainActivity.kt`:726
- **CWE:** [CWE-532](https://cwe.mitre.org/data/definitions/532.html)
- **Description:** Found pattern: Log\.(d|i|w|e)\(.*password|token|secret
- **Code:**
```
conn.setRequestProperty("Authorization", "Bearer $authToken")
```
- **Recommendation:** Redact sensitive data before logging

### 🔵 [LOW] Information Leak: Debug enabled
- **Category:** INFO_LEAK
- **File:** `scripts\full_security_audit.py`:110
- **CWE:** [CWE-532](https://cwe.mitre.org/data/definitions/532.html)
- **Description:** Debug information or sensitive data may be exposed.
- **Code:**
```
(r'app\.run\(.*debug=True', "Flask debug mode"),
```
- **Recommendation:** Remove debug prints, use structured logging with redaction.

## INJECTION (6 findings)

### 🟠 [HIGH] Potential SQL Injection: Possible f-string SQL injection
- **Category:** INJECTION
- **File:** `scripts\full_security_audit.py`:82
- **CWE:** [CWE-89](https://cwe.mitre.org/data/definitions/89.html)
- **Description:** Line uses pattern that may lead to SQL injection.
- **Code:**
```
(r'f".*SELECT.*\{.*\}.*"', "Possible f-string SQL injection"),
```
- **Recommendation:** Use parameterized queries: cursor.execute('SELECT * FROM t WHERE id=?', (id,))

### 🟠 [HIGH] Potential SQL Injection: String formatting in SQL
- **Category:** INJECTION
- **File:** `scripts\full_security_audit.py`:83
- **CWE:** [CWE-89](https://cwe.mitre.org/data/definitions/89.html)
- **Description:** Line uses pattern that may lead to SQL injection.
- **Code:**
```
(r"'.*SELECT.*' % ", "String formatting in SQL"),
```
- **Recommendation:** Use parameterized queries: cursor.execute('SELECT * FROM t WHERE id=?', (id,))

### 🟠 [HIGH] Potential SQL Injection: .format() before execute
- **Category:** INJECTION
- **File:** `scripts\full_security_audit.py`:86
- **CWE:** [CWE-89](https://cwe.mitre.org/data/definitions/89.html)
- **Description:** Line uses pattern that may lead to SQL injection.
- **Code:**
```
(r'\.format\(.*\).*execute', ".format() before execute"),
```
- **Recommendation:** Use parameterized queries: cursor.execute('SELECT * FROM t WHERE id=?', (id,))

### 🟠 [HIGH] Potential SQL Injection: f-string in execute()
- **Category:** INJECTION
- **File:** `scripts\full_security_audit.py`:353
- **CWE:** [CWE-89](https://cwe.mitre.org/data/definitions/89.html)
- **Description:** Line uses pattern that may lead to SQL injection.
- **Code:**
```
c.execute(f"PRAGMA table_info({t})")
```
- **Recommendation:** Use parameterized queries: cursor.execute('SELECT * FROM t WHERE id=?', (id,))

### 🟠 [HIGH] Potential SQL Injection: f-string in execute()
- **Category:** INJECTION
- **File:** `src\smarthome\storage.py`:185
- **CWE:** [CWE-89](https://cwe.mitre.org/data/definitions/89.html)
- **Description:** Line uses pattern that may lead to SQL injection.
- **Code:**
```
connection.execute(f"PRAGMA user_version = {int(SCHEMA_VERSION)}")
```
- **Recommendation:** Use parameterized queries: cursor.execute('SELECT * FROM t WHERE id=?', (id,))

### 🟠 [HIGH] Potential SQL Injection: Possible f-string SQL injection
- **Category:** INJECTION
- **File:** `tests\test_algorithms.py`:358
- **CWE:** [CWE-89](https://cwe.mitre.org/data/definitions/89.html)
- **Description:** Line uses pattern that may lead to SQL injection.
- **Code:**
```
f"SELECT COUNT(*) FROM {table} WHERE {key}=?", (home["id"],)
```
- **Recommendation:** Use parameterized queries: cursor.execute('SELECT * FROM t WHERE id=?', (id,))

## NETWORK (2 findings)

### 🟠 [HIGH] Cleartext HTTP to external host
- **Category:** NETWORK
- **File:** `android_collector\app\src\main\java\com\example\wificollector\MainActivity.kt`:399
- **CWE:** [CWE-319](https://cwe.mitre.org/data/definitions/319.html)
- **Description:** Found pattern: http://(?!localhost|127\.0\.0\.1|10\.|192\.168\.)
- **Code:**
```
val url = "http://$host:${info.port}"
```
- **Recommendation:** Use HTTPS for all external connections

### 🟠 [HIGH] Cleartext traffic in network_security_config
- **Category:** NETWORK
- **File:** `android_collector\app\src\main\res\xml\network_security_config.xml`:12
- **CWE:** [CWE-319](https://cwe.mitre.org/data/definitions/319.html)
- **Description:** Manifest/config contains: cleartextTrafficPermitted="true"
- **Code:**
```
cleartextTrafficPermitted="true"
```
- **Recommendation:** Restrict to specific domains with pinning

---

## Recommendations Priority

1. **Fix all CRITICAL & HIGH** before deployment
2. Address MEDIUM within 1 sprint
3. LOW & INFO as technical debt
4. Run this audit in CI/CD pipeline
5. Schedule dependency updates monthly
