# Security Audit & Code Review Report
**Project:** An Tâm Home (v2310)
**Date:** 2026-11-01 21:29:09
**Root:** `E:\Downloads\smart-home-wifi-monitor2310\smart-home-wifi-monitor`

## Summary

| Severity | Count |
|----------|-------|
| CRITICAL | 0 |
| HIGH | 0 |
| MEDIUM | 1 |
| LOW | 0 |
| INFO | 4 |
| **Total** | **5** |


## CONFIG (1 findings)

### ⚪ [INFO] mDNS enabled
- **Category:** CONFIG
- **File:** `config.yaml`:0
- **Description:** Service discovery broadcast on LAN
- **Recommendation:** Ensure LAN is trusted; disable if not needed

## CRYPTO (2 findings)

### 🟡 [MEDIUM] Weak Cryptography: Weak cipher mode
- **Category:** CRYPTO
- **File:** `make_report.py`:111
- **CWE:** [CWE-327](https://cwe.mitre.org/data/definitions/327.html)
- **Description:** Use of deprecated/weak cryptographic primitive.
- **Code:**
```
bullet("Sửa công cụ quét bảo mật (tuần 11)", "scripts/full_security_audit.py báo 69 lỗi (10 HIGH) nhưng khi kiểm chứng từng lỗi, khoảng 90% là báo oan: pattern DES khớp cả chữ DESC trong ORDER BY; quét chính regex của nó; dò dependency chỉ theo tên package nên báo oan cả requests>=2.31; pattern Log Android khớp mọi dòng chứa chữ token. Đã sửa 7 lỗi độ chính xác (word boundary, marker nosec, dò version thật, allowlist cột DB đã soát). Sau sửa còn 4 findings, tất cả INFO, đều là thiết kế có chủ đích ghi trong SECURITY.md (mDNS, HTTP trong LAN, hạn dùng certificate pin).")
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

## NETWORK (2 findings)

### ⚪ [INFO] Cleartext HTTP to external host (LAN/NSD — thiết kế ghi trong SECURITY.md §1.6)
- **Category:** NETWORK
- **File:** `android_collector\app\src\main\java\com\example\wificollector\MainActivity.kt`:399
- **CWE:** [CWE-319](https://cwe.mitre.org/data/definitions/319.html)
- **Description:** Found pattern: http://(?!localhost|127\.0\.0\.1|10\.|192\.168\.)
- **Code:**
```
val url = "http://$host:${info.port}"
```
- **Recommendation:** Use HTTPS for all external connections

### ⚪ [INFO] Cleartext traffic in network_security_config (LAN đã ghi trong SECURITY.md §1.6)
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
