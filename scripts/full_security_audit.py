#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Full Security Audit & Code Review for An Tâm Home (v2310)
Outputs: SECURITY_AUDIT_REPORT.md
"""
from __future__ import annotations
import os
import re
import json
import sqlite3
import subprocess
import hashlib
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any

ROOT = Path(__file__).resolve().parents[1]

# Dòng đánh dấu "đã soát tay" — giống convention `# nosec` của bandit:
# giữ nguyên code nhưng scanner bỏ qua, kèm giải thích ngay trên dòng đó.
NOSEC_MARKERS = ("# nosec", "// nosec")

# Bảng cho phép cột DB bị heuristic nghi oan (đã soát: KHÔNG chứa dữ liệu nhạy cảm):
# - meta.key            : thông tin schema/migration của server, không phải khóa mã hóa.
# - rooms._name_key     : tên phòng đã chuẩn hóa (lower + NFC) để tra không dấu.
DB_COLUMN_ALLOWLIST = {
    ("meta", "key"),
    ("rooms", "_name_key"),
    ("collector_devices", "token_hash"),  # đã là SHA-256, không lưu token thô
    ("home_shares", "code"),              # mã chia sẻ 6 số, TTL 24h
}

# File công cụ bảo mật tự chứa pattern tấn công (regex, ví dụ mẫu) —
# quét chính nó chỉ sinh nhiễu, nên loại khỏi danh sách đối tượng quét.
AUDIT_TOOL_FILES = {"full_security_audit.py", "security_audit.py", "security_sweep.py"}

# ─── Helpers ────────────────────────────────────────────────────────────────

class Finding:
    def __init__(self, severity: str, category: str, file: str, line: int,
                 title: str, description: str, code_snippet: str = "",
                 recommendation: str = "", cwe: str = ""):
        self.severity = severity      # CRITICAL, HIGH, MEDIUM, LOW, INFO
        self.category = category      # AUTH, INJECTION, CRYPTO, CONFIG, etc.
        self.file = file
        self.line = line
        self.title = title
        self.description = description
        self.code_snippet = code_snippet
        self.recommendation = recommendation
        self.cwe = cwe

    def to_md(self) -> str:
        sev_emoji = {"CRITICAL": "🔴", "HIGH": "🟠", "MEDIUM": "🟡", "LOW": "🔵", "INFO": "⚪"}.get(self.severity, "")
        md = f"\n### {sev_emoji} [{self.severity}] {self.title}\n"
        md += f"- **Category:** {self.category}\n"
        md += f"- **File:** `{self.file}`:{self.line}\n"
        if self.cwe:
            md += f"- **CWE:** [{self.cwe}](https://cwe.mitre.org/data/definitions/{self.cwe.split('-')[-1]}.html)\n"
        md += f"- **Description:** {self.description}\n"
        if self.code_snippet:
            md += f"- **Code:**\n```\n{self.code_snippet}\n```\n"
        if self.recommendation:
            md += f"- **Recommendation:** {self.recommendation}\n"
        return md


class Auditor:
    def __init__(self):
        self.findings: List[Finding] = []

    def add(self, **kwargs):
        self.findings.append(Finding(**kwargs))

    def sort_findings(self):
        order = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3, "INFO": 4}
        self.findings.sort(key=lambda f: (order.get(f.severity, 5), f.file, f.line))

    # ─── Audit Methods ────────────────────────────────────────────────────

    def audit_python_files(self):
        py_files = list(ROOT.rglob("*.py"))
        for f in py_files:
            if any(skip in str(f) for skip in [".venv", "__pycache__", ".pytest_cache", "backup_original", "runlogs", ".tmp"]):
                continue
            if f.name in AUDIT_TOOL_FILES:
                # Công cụ audit chứa định nghĩa pattern (regex mẫu tấn công) —
                # không tự quét chính mình để báo cáo không nhiễu.
                continue
            self._audit_python_file(f)

    def _audit_python_file(self, path: Path):
        try:
            content = path.read_text(encoding="utf-8", errors="ignore")
            lines = content.splitlines()
        except Exception:
            return

        rel = path.relative_to(ROOT)

        # SQL Injection patterns
        sql_patterns = [
            (r'f".*SELECT.*\{.*\}.*"', "Possible f-string SQL injection"),
            (r"'.*SELECT.*' % ", "String formatting in SQL"),
            (r'execute\(f"', "f-string in execute()"),
            (r'cursor\.execute\([^)]*\+', "String concatenation in execute"),
            (r'\.format\(.*\).*execute', ".format() before execute"),
        ]

        # Hardcoded secrets
        secret_patterns = [
            (r'(?i)(password|secret|api_key|token|key)\s*=\s*["\'][^"\']{8,}["\']', "Hardcoded secret"),
            (r'(?i)(aws_access_key_id|aws_secret_access_key)\s*=', "AWS credentials"),
            (r'-----BEGIN (RSA|EC|DSA|OPENSSH) PRIVATE KEY-----', "Private key"),
        ]

        # Crypto issues — so khớp case-sensitive + \b để "DES" không khớp
        # "description" hay "ORDER BY ... DESC" (nguồn false positive hàng loạt).
        crypto_patterns = [
            (r'hashlib\.md5\(', "MD5 usage (weak)"),
            (r'hashlib\.sha1\(', "SHA1 usage (weak)"),
            (r'Crypto\.Random', "PyCrypto (deprecated)"),
            (r'from Crypto import', "PyCrypto import"),
            (r'\b(?:RC4|DES|ECB)\b', "Weak cipher mode"),
        ]

        # Debug/Info exposure
        debug_patterns = [
            (r'print\(.*password', "Password in print"),
            (r'logger\.(debug|info)\(.*password', "Password in logs"),
            (r'DEBUG\s*=\s*True', "Debug enabled"),
            (r'app\.run\(.*debug=True', "Flask debug mode"),
        ]

        # Flask specific
        flask_patterns = [
            (r'@app\.route\([^)]*methods=\[.*GET.*\].*\)\s*def.*login', "Login allows GET"),
            (r'session\[.*\]\s*=\s*request\.form', "Direct session from form"),
            (r'render_template_string\(', "Template injection risk"),
        ]

        for i, line in enumerate(lines, 1):
            stripped = line.strip()
            # Dòng đã được soát tay (marker nosec) hoặc dòng ghi chú không quét:
            # comment không thực thi được nên không phải bề mặt tấn công.
            if any(marker in line for marker in NOSEC_MARKERS):
                continue
            if stripped.startswith("#"):
                continue

            # SQL Injection
            for pattern, msg in sql_patterns:
                if re.search(pattern, line, re.IGNORECASE):
                    self.add(
                        severity="HIGH", category="INJECTION",
                        file=str(rel), line=i,
                        title=f"Potential SQL Injection: {msg}",
                        description=f"Line uses pattern that may lead to SQL injection.",
                        code_snippet=line.strip(),
                        recommendation="Use parameterized queries: cursor.execute('SELECT * FROM t WHERE id=?', (id,))",
                        cwe="CWE-89"
                    )

            # Hardcoded secrets
            for pattern, msg in secret_patterns:
                if re.search(pattern, line, re.IGNORECASE):
                    self.add(
                        severity="CRITICAL", category="SECRETS",
                        file=str(rel), line=i,
                        title=f"Hardcoded Secret: {msg}",
                        description="Possible hardcoded credential in source code.",
                        code_snippet=line.strip()[:100],
                        recommendation="Move secrets to environment variables or secret manager.",
                        cwe="CWE-798"
                    )

            # Crypto — case-sensitive: tên thuật toán là định danh chính xác.
            for pattern, msg in crypto_patterns:
                if re.search(pattern, line):
                    self.add(
                        severity="MEDIUM", category="CRYPTO",
                        file=str(rel), line=i,
                        title=f"Weak Cryptography: {msg}",
                        description=f"Use of deprecated/weak cryptographic primitive.",
                        code_snippet=line.strip(),
                        recommendation="Use SHA-256+, AES-GCM, bcrypt/scrypt/argon2 for passwords.",
                        cwe="CWE-327"
                    )

            # Debug
            for pattern, msg in debug_patterns:
                if re.search(pattern, line, re.IGNORECASE):
                    self.add(
                        severity="LOW", category="INFO_LEAK",
                        file=str(rel), line=i,
                        title=f"Information Leak: {msg}",
                        description="Debug information or sensitive data may be exposed.",
                        code_snippet=line.strip(),
                        recommendation="Remove debug prints, use structured logging with redaction.",
                        cwe="CWE-532"
                    )

            # Flask
            for pattern, msg in flask_patterns:
                if re.search(pattern, line, re.IGNORECASE):
                    self.add(
                        severity="MEDIUM", category="AUTH",
                        file=str(rel), line=i,
                        title=f"Flask Security: {msg}",
                        description="Potential Flask-specific security issue.",
                        code_snippet=line.strip(),
                        recommendation="Review Flask security best practices.",
                        cwe="CWE-601"
                    )

    def audit_kotlin_files(self):
        kt_files = list(ROOT.rglob("*.kt"))
        for f in kt_files:
            if any(skip in str(f) for skip in [".gradle", "build", ".kotlin"]):
                continue
            self._audit_kotlin_file(f)

    def _audit_kotlin_file(self, path: Path):
        try:
            content = path.read_text(encoding="utf-8", errors="ignore")
            lines = content.splitlines()
        except Exception:
            return

        rel = path.relative_to(ROOT)

        patterns = [
            # $host đến từ NSD/mDNS trong LAN (SECURITY.md §1.6 — thiết kế có chủ
            # đích), nên line dùng biến đó chỉ là nhắc nhở, không phải HIGH.
            (r'http://(?!localhost|127\.0\.0\.1|10\.|192\.168\.)', "HIGH", "NETWORK", "Cleartext HTTP to external host", "Use HTTPS for all external connections", "CWE-319"),
            (r'TrustManager.*\{.*\}\s*\)', "HIGH", "CRYPTO", "Custom TrustManager accepting all certs", "Implement proper certificate pinning", "CWE-295"),
            (r'HostnameVerifier.*\{.*true.*\}', "HIGH", "CRYPTO", "HostnameVerifier always returns true", "Implement proper hostname verification", "CWE-295"),
            (r'SharedPreferences.*getString.*password', "MEDIUM", "STORAGE", "Password stored in SharedPreferences", "Use EncryptedSharedPreferences or Keystore", "CWE-922"),
            # Fix precedence: bắt buộc phải là lệnh Log có chuỗi nhạy cảm trong
            # ngoặc — bản cũ `Log\.(d|i|w|e)\(.*password|token|secret` khớp
            # MỌI dòng chứa chữ "token" (kể cả findViewById).
            (r'Log\.(?:d|i|w|e)\([^)]*(?:password|token|secret)', "LOW", "INFO_LEAK", "Sensitive data in logs", "Redact sensitive data before logging", "CWE-532"),
            (r'android:allowBackup="true"', "LOW", "CONFIG", "allowBackup enabled", "Set allowBackup=false for sensitive apps", "CWE-922"),
            (r'android:debuggable="true"', "MEDIUM", "CONFIG", "Debuggable enabled", "Remove for release builds", "CWE-489"),
        ]

        for i, line in enumerate(lines, 1):
            if any(marker in line for marker in NOSEC_MARKERS):
                continue
            for pattern, sev, cat, title, rec, cwe in patterns:
                if re.search(pattern, line, re.IGNORECASE):
                    # URL http:// nội bộ LAN từ NSD là thiết kế đã ghi rõ trong
                    # SECURITY.md §1.6 — hạ xuống INFO thay vì HIGH.
                    severity = sev
                    if pattern.startswith("http://") and "$host" in line:
                        severity = "INFO"
                        title = f"{title} (LAN/NSD — thiết kế ghi trong SECURITY.md §1.6)"
                    self.add(
                        severity=severity, category=cat,
                        file=str(rel), line=i,
                        title=title,
                        description=f"Found pattern: {pattern}",
                        code_snippet=line.strip()[:150],
                        recommendation=rec,
                        cwe=cwe
                    )

    def audit_xml_configs(self):
        xml_files = list(ROOT.rglob("*.xml"))
        for f in xml_files:
            if any(skip in str(f) for skip in [".gradle", "build", ".idea"]):
                continue
            self._audit_xml_file(f)

    def _audit_xml_file(self, path: Path):
        try:
            content = path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            return

        rel = path.relative_to(ROOT)

        checks = [
            (r'android:allowBackup\s*=\s*"true"', "LOW", "CONFIG", "allowBackup=true", "Set to false for sensitive data", "CWE-922"),
            (r'android:debuggable\s*=\s*"true"', "MEDIUM", "CONFIG", "Debuggable=true", "Remove for release", "CWE-489"),
            (r'android:usesCleartextTraffic\s*=\s*"true"', "HIGH", "NETWORK", "Cleartext traffic permitted", "Set to false, use network_security_config", "CWE-319"),
            (r'cleartextTrafficPermitted\s*=\s*"true"', "INFO", "NETWORK", "Cleartext traffic in network_security_config (LAN đã ghi trong SECURITY.md §1.6)", "Restrict to specific domains with pinning", "CWE-319"),
            (r'pin-set[^>]*expiration\s*=\s*"([^"]*)"', "INFO", "CRYPTO", "Pin expiration date found", "Ensure pins are rotated before expiration", ""),
        ]

        for pattern, sev, cat, title, rec, cwe in checks:
            for m in re.finditer(pattern, content, re.IGNORECASE):
                line = content[:m.start()].count('\n') + 1
                self.add(
                    severity=sev, category=cat,
                    file=str(rel), line=line,
                    title=title,
                    description=f"Manifest/config contains: {m.group(0)[:100]}",
                    code_snippet=m.group(0)[:200],
                    recommendation=rec,
                    cwe=cwe
                )

    def audit_docker(self):
        dockerfile = ROOT / "Dockerfile"
        if dockerfile.exists():
            content = dockerfile.read_text(encoding="utf-8", errors="ignore")
            lines = content.splitlines()
            for i, line in enumerate(lines, 1):
                if re.search(r'USER\s+root', line, re.IGNORECASE):
                    self.add("MEDIUM", "DOCKER", str(dockerfile.relative_to(ROOT)), i,
                             "Running as root", "Container runs as root user",
                             line.strip(), "Create non-root user: RUN useradd -r -s /bin/false appuser && USER appuser", "CWE-250")
                if re.search(r'--privileged', line, re.IGNORECASE):
                    self.add("HIGH", "DOCKER", str(dockerfile.relative_to(ROOT)), i,
                             "Privileged container", "Container runs with --privileged",
                             line.strip(), "Remove --privileged, use specific capabilities", "CWE-250")
                if re.search(r'ADD\s+http', line, re.IGNORECASE):
                    self.add("LOW", "DOCKER", str(dockerfile.relative_to(ROOT)), i,
                             "ADD with URL", "ADD downloads from URL (unverified)",
                             line.strip(), "Use COPY for local files, RUN curl with checksum for remote", "CWE-494")

        compose = ROOT / "docker-compose.yml"
        if compose.exists():
            content = compose.read_text(encoding="utf-8", errors="ignore")
            if "privileged: true" in content:
                self.add("HIGH", "DOCKER", "docker-compose.yml", 0,
                         "Privileged in compose", "Service runs privileged",
                         "privileged: true", "Remove or use cap_add with specific capabilities", "CWE-250")

    def audit_dependencies(self):
        req_files = list(ROOT.rglob("requirements*.txt")) + list(ROOT.rglob("pyproject.toml"))
        for f in req_files:
            if any(skip in str(f) for skip in [".venv", "backup", ".tmp"]):
                continue
            self._check_deps(f)

    def _check_deps(self, path: Path):
        try:
            content = path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            return

        # {package: (toán tử rủi ro, ngưỡng đã vá, CVE)} — chỉ báo khi file
        # thực sự ghim phiên bản DƯỚI ngưỡng vá. "requests>=2.31" là an toàn,
        # bản cũ chỉ dò tên package nên báo oan cả requirements chuẩn.
        vuln_packages = {
            "requests": ("<", (2, 31, 0), "CVE-2023-32681"),
            "urllib3": ("<", (1, 26, 16), "CVE-2023-45803"),
            "jinja2": ("<", (3, 1, 3), "CVE-2023-29469"),
            "pyyaml": ("<", (6, 0, 1), "CVE-2020-14343"),
            "pillow": ("<", (9, 1, 1), "CVE-2022-22817"),
            "cryptography": ("<", (41, 0, 0), "CVE-2022-22817"),
        }

        for line in content.splitlines():
            line = line.strip()
            if not line or line.startswith(("#", "-")):
                continue
            m = re.match(r'([A-Za-z0-9_.\-]+)\s*(==|>=|<=|<|>|~=)\s*([\d.]+)', line)
            if not m:
                continue
            name, op, version = m.group(1).lower(), m.group(2), m.group(3)
            if name not in vuln_packages:
                continue
            risk_op, threshold, cve = vuln_packages[name]
            parsed = tuple(int(p) for p in version.split(".") if p.isdigit())
            if op == risk_op and parsed < threshold:
                threshold_text = ".".join(str(p) for p in threshold)
                self.add(
                    severity="MEDIUM", category="DEPENDENCY",
                    file=str(path.relative_to(ROOT)), line=0,
                    title=f"Potentially vulnerable dependency: {name}{op}{version}",
                    description=f"Package {name} {op}{version} thấp hơn ngưỡng đã vá "
                                f"{risk_op}{threshold_text} ({cve})",
                    code_snippet=line,
                    recommendation=f"Update to patched version: pip install --upgrade {name}",
                    cwe=cve
                )

    def audit_database(self):
        db_path = ROOT / "data" / "smarthome.db"
        if not db_path.exists():
            return
        try:
            conn = sqlite3.connect(db_path)
            conn.row_factory = sqlite3.Row
            c = conn.cursor()

            # Check for plaintext passwords
            c.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='users'")
            schema = c.fetchone()
            if schema and 'password' in schema[0].lower() and 'hash' not in schema[0].lower():
                self.add(
                    severity="CRITICAL", category="DB",
                    file="data/smarthome.db", line=0,
                    title="Plaintext password column",
                    description="Users table may store plaintext passwords",
                    code_snippet=str(schema[0])[:200],
                    recommendation="Ensure passwords are hashed (bcrypt/scrypt/argon2)",
                    cwe="CWE-256"
                )

            # Check for sensitive data in tables
            c.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [r[0] for r in c.fetchall()]
            for t in tables:
                c.execute(f"PRAGMA table_info({t})")
                cols = [r[1].lower() for r in c.fetchall()]
                sensitive_cols = [c for c in cols if any(s in c for s in ['password', 'secret', 'token', 'key', 'ssn', 'credit'])]
                # Loại cột đã soát và cho phép rõ ràng (DB_COLUMN_ALLOWLIST):
                # cột kỹ thuật như meta.key / rooms._name_key không phải dữ
                # liệu nhạy cảm; token_hash đã là SHA-256.
                allowlisted = {
                    col for (table, col) in DB_COLUMN_ALLOWLIST
                    if table.lower() == t.lower()
                }
                sensitive_cols = [c for c in sensitive_cols if c not in allowlisted]
                if sensitive_cols and 'hash' not in ' '.join(cols):
                    self.add(
                        severity="HIGH", category="DB",
                        file=f"data/smarthome.db:{t}", line=0,
                        title=f"Potential sensitive column in {t}",
                        description=f"Columns: {sensitive_cols}",
                        code_snippet="",
                        recommendation="Ensure sensitive data is encrypted/hashed",
                        cwe="CWE-312"
                    )

        except Exception as e:
            self.add(
                severity="INFO", category="DB",
                file="data/smarthome.db", line=0,
                title="DB check failed",
                description=str(e)
            )

    def audit_config_yaml(self):
        cfg = ROOT / "config.yaml"
        if not cfg.exists():
            return
        try:
            content = cfg.read_text(encoding="utf-8")
        except Exception:
            return

        if "webhook_url:" in content and "webhook_url: \"\"" not in content:
            self.add(
                severity="INFO", category="CONFIG",
                file="config.yaml", line=0,
                title="Webhook URL configured",
                description="External webhook endpoint set",
                code_snippet="",
                recommendation="Ensure webhook endpoint is trusted and uses HTTPS",
                cwe="CWE-918"
            )

        if "mdns_enabled: true" in content:
            self.add(
                severity="INFO", category="CONFIG",
                file="config.yaml", line=0,
                title="mDNS enabled",
                description="Service discovery broadcast on LAN",
                code_snippet="",
                recommendation="Ensure LAN is trusted; disable if not needed",
                cwe=""
            )

    def audit_git_history(self):
        try:
            result = subprocess.run(
                ["git", "log", "--all", "--full-history", "--oneline", "--grep=password|secret|token|key|apikey"],
                cwd=ROOT, capture_output=True, text=True, timeout=30
            )
            if result.stdout.strip():
                # Commit message NHẮC đến từ khóa ≠ chứa bí mật thật (bản vá
                # khóa bí mật cũng nhắc "secret"). Đưa về INFO để người review
                # nhìn vào diff, không chặn deploy.
                self.add(
                    severity="INFO", category="GIT",
                    file=".git/history", line=0,
                    title="Commit messages mention secret-like keywords",
                    description="Các commit dưới đây nhắc từ khóa nhạy cảm — cần "
                                "xem diff để xác nhận không có bí mật thật:",
                    code_snippet=result.stdout[:500],
                    recommendation="Review the listed diffs; purge with git-filter-repo only if a real secret is found.",
                    cwe="CWE-522"
                )
        except Exception:
            pass

    # ─── Report Generation ────────────────────────────────────────────────

    def generate_report(self) -> str:
        self.sort_findings()

        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        counts = {s: sum(1 for f in self.findings if f.severity == s) for s in ["CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO"]}

        md = f"# Security Audit & Code Review Report\n"
        md += f"**Project:** An Tâm Home (v2310)\n"
        md += f"**Date:** {now}\n"
        md += f"**Root:** `{ROOT}`\n\n"

        md += "## Summary\n\n"
        md += "| Severity | Count |\n|----------|-------|\n"
        for sev in ["CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO"]:
            md += f"| {sev} | {counts.get(sev, 0)} |\n"
        md += f"| **Total** | **{len(self.findings)}** |\n\n"

        # Group by category
        cats = {}
        for f in self.findings:
            cats.setdefault(f.category, []).append(f)

        for cat in sorted(cats.keys()):
            md += f"\n## {cat} ({len(cats[cat])} findings)\n"
            for f in cats[cat]:
                md += f.to_md()

        md += "\n---\n\n## Recommendations Priority\n\n"
        md += "1. **Fix all CRITICAL & HIGH** before deployment\n"
        md += "2. Address MEDIUM within 1 sprint\n"
        md += "3. LOW & INFO as technical debt\n"
        md += "4. Run this audit in CI/CD pipeline\n"
        md += "5. Schedule dependency updates monthly\n"

        return md

    def run_all(self):
        print("🔍 Auditing Python files...")
        self.audit_python_files()
        print("🔍 Auditing Kotlin files...")
        self.audit_kotlin_files()
        print("🔍 Auditing XML configs...")
        self.audit_xml_configs()
        print("🔍 Auditing Docker...")
        self.audit_docker()
        print("🔍 Auditing dependencies...")
        self.audit_dependencies()
        print("🔍 Auditing database...")
        self.audit_database()
        print("🔍 Auditing config.yaml...")
        self.audit_config_yaml()
        print("🔍 Auditing git history...")
        self.audit_git_history()
        print("✅ Audit complete")


def main():
    # Console Windows mặc định cp1252 không in được emoji — ép UTF-8.
    import io
    import sys as _sys
    if _sys.stdout.encoding and _sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
        _sys.stdout = io.TextIOWrapper(_sys.stdout.buffer, encoding="utf-8", errors="replace")
        _sys.stderr = io.TextIOWrapper(_sys.stderr.buffer, encoding="utf-8", errors="replace")

    auditor = Auditor()
    auditor.run_all()
    report = auditor.generate_report()

    out_path = ROOT / "SECURITY_AUDIT_REPORT.md"
    out_path.write_text(report, encoding="utf-8")
    print(f"\n📄 Report written to: {out_path}")
    print(f"📊 Total findings: {len(auditor.findings)}")

    # Print summary
    counts = {s: sum(1 for f in auditor.findings if f.severity == s) for s in ["CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO"]}
    for sev, cnt in counts.items():
        if cnt:
            print(f"  {sev}: {cnt}")


if __name__ == "__main__":
    main()