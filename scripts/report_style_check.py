"""Tự soát báo cáo theo `avoid.md` (Wikipedia:Signs of AI writing) + soát trích dẫn.

Chạy:  .venv\\Scripts\\python.exe scripts\\report_style_check.py [đường-dẫn.md]

Công cụ này KHÔNG thay thế được Turnitin hay GPTZero. Nó làm đúng ba việc kiểm
được bằng máy, và nói rõ giới hạn:

1. **Dấu hiệu văn phong AI** theo danh sách trong `avoid.md` (từ vựng AI, quy tắc
   số 3, cấu trúc phủ định song song, in đậm quá mức, biến văn xuôi thành gạch đầu
   dòng, câu kết "thách thức và triển vọng", né hệ từ is/are...).
2. **Trùng lặp nội bộ dự án** — câu/dòng dài xuất hiện y nguyên ở cả báo cáo và các
   tài liệu khác trong repo (tự đạo văn). Đây là thứ kiểm được mà không cần
   internet; trùng với nguồn bên ngoài thì phải dùng công cụ chuyên dụng.
3. **Trích dẫn đáng ngờ** — mục tham khảo thiếu năm/nhà xuất bản, DOI/URL sai định
   dạng, hoặc không có nguồn nào cho một khẳng định mang tính số liệu.
"""
from __future__ import annotations

import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_TARGET = ROOT / "BAO_CAO_KHOA_LUAN.md"

# --- 1. Từ vựng AI (avoid.md §3.1) -----------------------------------------
AI_VOCAB = [
    "delve", "tapestry", "beacon", "pivotal", "underscore", "testament",
    "fostering", "vibrant", "multifaceted", "paramount", "overarching",
    "seamless", "robust", "leverage", "realm", "landscape", "navigate",
    "crucial", "vital", "significant role", "key role", "evolving",
]
# Bản dịch tiếng Việt của cùng nhóm từ — báo cáo viết tiếng Việt nên phải bắt cả.
AI_VOCAB_VI = [
    "đóng vai trò then chốt", "đóng vai trò quan trọng", "là minh chứng",
    "làm nổi bật tầm quan trọng", "phản ánh xu hướng rộng lớn",
    "tạo tiền đề cho", "bối cảnh đang phát triển", "không thể thiếu",
    "vô cùng quan trọng", "hết sức quan trọng", "mang tính đột phá",
]

# --- 2. Cấu trúc phủ định song song (avoid.md §3.3) ------------------------
NEGATIVE_PARALLEL = [
    r"không chỉ .{2,60}? mà còn", r"không phải .{2,60}? mà là",
    r"not only .{2,60}? but also", r"không phải là .{2,60}? mà",
    r"thay vì .{2,40}?, (?:mà )?là",
]

# --- 3. Né hệ từ (avoid.md §3.2) -------------------------------------------
COPULA_AVOID = [
    r"\b(?:đóng vai trò như|được xem như|được coi như|đại diện cho|thể hiện cho)\b",
    r"\b(?:serves as|stands as|represents|embodies|constitutes)\b",
]

# --- 4. Câu kết khuôn mẫu (avoid.md §2.7) ----------------------------------
BOILERPLATE_END = [
    r"thách thức phía trước", r"triển vọng trong tương lai",
    r"challenges? (?:lie|remain) ahead", r"future (?:looks|remains) bright",
    r"trong tương lai (?:gần|không xa), .{0,60}? sẽ",
]

# --- 5. Miễn trừ trách nhiệm / hedging (avoid.md §5) -----------------------
HEDGING = [
    r"lưu ý rằng thông tin này có thể thay đổi", r"tùy thuộc vào nguồn",
    r"cần lưu ý rằng", r"điều quan trọng cần lưu ý",
]

# --- 6. Trích dẫn đáng ngờ (avoid.md §6) -----------------------------------
DOI_RE = re.compile(r"10\.\d{4,9}/[-._;()/:A-Za-z0-9]+")
URL_RE = re.compile(r"https?://\S+")
YEAR_RE = re.compile(r"\b(19|20)\d{2}\b")
TRACKING_PARAM_RE = re.compile(r"[?&](utm_source|utm_medium|utm_campaign|fbclid|gclid)=")


def read_lines(path: Path) -> list[str]:
    return path.read_text(encoding="utf-8", errors="ignore").splitlines()


def strip_code_blocks(lines: list[str]) -> list[tuple[int, str]]:
    """Bỏ khối ``` … ``` để không soi code như văn xuôi."""
    result: list[tuple[int, str]] = []
    in_code = False
    for index, line in enumerate(lines, 1):
        if line.lstrip().startswith("```"):
            in_code = not in_code
            continue
        if not in_code:
            result.append((index, line))
    return result


def check_ai_style(prose: list[tuple[int, str]]) -> list[tuple[str, int, str]]:
    findings: list[tuple[str, int, str]] = []

    # 6.1 Từ vựng AI.
    # Bỏ `mã nội tuyến` trước khi dò: `Portrait/Landscape/Flat` là hằng số của
    # Android chứ không phải văn phong; bắt nó là báo oan.
    inline_code = re.compile(r"`[^`]*`")
    for line_no, line in prose:
        low = inline_code.sub(" ", line).lower()
        for word in AI_VOCAB + AI_VOCAB_VI:
            if re.search(rf"(?<![\w/]){re.escape(word)}(?![\w/])", low):
                findings.append(("Từ vựng AI", line_no, f'"{word}"'))
                break

    # 6.2 Cấu trúc phủ định song song
    for line_no, line in prose:
        for pattern in NEGATIVE_PARALLEL:
            if re.search(pattern, line, re.IGNORECASE):
                findings.append(("Phủ định song song", line_no, line.strip()[:90]))
                break

    # 6.3 Né hệ từ
    for line_no, line in prose:
        for pattern in COPULA_AVOID:
            if re.search(pattern, line, re.IGNORECASE):
                findings.append(("Né hệ từ", line_no, line.strip()[:90]))
                break

    # 6.4 Câu kết khuôn mẫu
    for line_no, line in prose:
        for pattern in BOILERPLATE_END:
            if re.search(pattern, line, re.IGNORECASE):
                findings.append(("Câu kết khuôn mẫu", line_no, line.strip()[:90]))
                break

    # 6.5 Hedging
    for line_no, line in prose:
        for pattern in HEDGING:
            if re.search(pattern, line, re.IGNORECASE):
                findings.append(("Miễn trừ/hedging", line_no, line.strip()[:90]))
                break

    # 6.6 Quy tắc số 3: ĐÚNG ba thành phần song song nối bằng "và/and".
    # Phải chặt: một danh sách 4-5 mục là văn viết bình thường, không phải dấu
    # hiệu AI. Bản trước chỉ cần thấy "x, y, và z" ở đâu đó trong câu là báo,
    # nên gắn cờ oan cho cả gạch đầu dòng liệt kê.
    for line_no, line in prose:
        stripped = line.strip()
        if re.match(r"^[-*+]\s", stripped) or stripped.startswith("|"):
            continue
        # Bỏ `mã nội tuyến` và nội dung trong ngoặc trước khi tách: tên tham số
        # như (`center_loss_weight`, `temporal_loss_weight`) không phải văn xuôi.
        bare = re.sub(r"`[^`]*`|\([^)]*\)", " ", stripped)
        for sentence in re.split(r"(?<=[.!?])\s+", bare):
            parts = re.split(r",\s*|\s+(?:và|and)\s+", sentence)
            if len(parts) != 3:
                continue
            # Ba thành phần phải song song và ngắn, kiểu "A, B, và C" rỗng nghĩa.
            if all(1 <= len(p.split()) <= 4 for p in parts) and re.search(r"\s(?:và|and)\s", sentence):
                findings.append(("Quy tắc số 3", line_no, sentence.strip()[:90]))
                break

    # 6.7 In đậm quá mức: một dòng có >= 4 cụm **…** hoặc mật độ đậm cao
    for line_no, line in prose:
        bold = re.findall(r"\*\*[^*]+\*\*", line)
        if len(bold) >= 4:
            findings.append(("In đậm quá mức", line_no, f"{len(bold)} cụm in đậm trong một dòng"))

    return findings


def check_listification(prose: list[tuple[int, str]]) -> tuple[int, int]:
    """Đếm tỉ lệ dòng gạch đầu dòng trên tổng dòng văn xuôi."""
    bullets = sum(1 for _n, line in prose if re.match(r"^\s*[-*+]\s+", line))
    total = sum(1 for _n, line in prose if line.strip())
    return bullets, total


def check_citations(text: str) -> list[tuple[str, str]]:
    findings: list[tuple[str, str]] = []
    references = re.search(r"##\s*11\.\s*T[ÀA]I LIỆU THAM KH[ẢA]O(.*?)(?=\n##\s|\Z)", text, re.S)
    block = references.group(1) if references else ""

    if not block.strip():
        findings.append(("Trích dẫn", "Không tìm thấy mục Tài liệu tham khảo"))
        return findings

    # Chỉ lấy dòng được ĐÁNH SỐ (1. 2. 3. …). Dòng ghi chú in nghiêng hay dòng
    # nối tiếp của một mục không phải là một tài liệu tham khảo riêng.
    entries = [line for line in block.splitlines() if re.match(r"^\s*\d+\.\s+\S", line)]
    for entry in entries:
        has_year = bool(YEAR_RE.search(entry))
        has_link = bool(URL_RE.search(entry) or DOI_RE.search(entry))
        if not has_year:
            findings.append(("Thiếu năm", entry.strip()[:100]))
        if not has_link:
            # Không phải lỗi: nhiều báo cáo chỉ ghi tên hội nghị + số trang.
            # Ghi thành gợi ý để không làm nhiễu danh sách vấn đề thật.
            findings.append(("(gợi ý) chưa có DOI/URL", entry.strip()[:100]))
    if len(entries) < 8:
        findings.append(("Quá ít nguồn", f"chỉ có {len(entries)} mục — báo cáo khóa luận thường cần 15-30"))

    for match in TRACKING_PARAM_RE.finditer(text):
        findings.append(("URL còn tham số theo dõi", match.group(0)))
    return findings


def check_self_overlap(target: Path, prose: list[tuple[int, str]]) -> list[tuple[int, str]]:
    """Câu dài trùng y nguyên với tài liệu khác trong repo (tự đạo văn)."""
    others = []
    for pattern in ("docs/*.md", "*.md"):
        others.extend(ROOT.glob(pattern))
    others = [p for p in set(others) if p != target and p.is_file()]

    other_sentences: dict[str, str] = {}
    for path in others:
        try:
            body = path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        for sentence in re.split(r"(?<=[.!?])\s+|\n\n", body):
            cleaned = " ".join(sentence.split())
            if len(cleaned) >= 120:
                other_sentences[cleaned] = path.name

    hits: list[tuple[int, str]] = []
    for line_no, line in prose:
        for sentence in re.split(r"(?<=[.!?])\s+", line):
            cleaned = " ".join(sentence.split())
            if len(cleaned) >= 120 and cleaned in other_sentences:
                hits.append((line_no, f"trùng với {other_sentences[cleaned]}: {cleaned[:70]}…"))
    return hits


def main() -> int:
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_TARGET
    if not target.is_file():
        print(f"Không thấy file: {target}")
        return 2

    text = target.read_text(encoding="utf-8", errors="ignore")
    lines = read_lines(target)
    prose = strip_code_blocks(lines)

    print("=" * 74)
    print(f"SOÁT BÁO CÁO — {target.name}")
    print("=" * 74)
    words = len(re.findall(r"\S+", " ".join(line for _n, line in prose)))
    print(f"  dòng văn xuôi : {len(prose)} / {len(lines)} (đã bỏ khối code)")
    print(f"  số từ         : ~{words}")
    print()

    findings = check_ai_style(prose)
    grouped = Counter(kind for kind, _n, _d in findings)
    print("1. Dấu hiệu văn phong AI (theo avoid.md)")
    if not findings:
        print("   không phát hiện")
    for kind, count in grouped.most_common():
        print(f"   {kind:26} {count:3} chỗ")
        for k, line_no, detail in findings:
            if k == kind:
                print(f"        dòng {line_no}: {detail}")
                break
    print()

    bullets, total = check_listification(prose)
    ratio = (bullets / total * 100) if total else 0
    print("2. Tỉ lệ gạch đầu dòng (avoid.md §4 — biến văn xuôi thành danh sách)")
    print(f"   {bullets}/{total} dòng = {ratio:.0f}%  (báo cáo nên dưới ~35%)")
    print()

    cites = check_citations(text)
    print("3. Trích dẫn")
    if not cites:
        print("   không có vấn đề")
    for kind, detail in cites[:10]:
        print(f"   {kind:26} {detail}")
    print()

    overlap = check_self_overlap(target, prose)
    print("4. Trùng lặp nội bộ dự án (tự đạo văn)")
    if not overlap:
        print("   không có câu dài nào trùng y nguyên tài liệu khác trong repo")
    for line_no, detail in overlap[:8]:
        print(f"   dòng {line_no}: {detail}")
    print()

    print("-" * 74)
    print("GIỚI HẠN: công cụ này chỉ bắt dấu hiệu bề mặt và trùng lặp nội bộ.")
    print("Không thay được Turnitin (đối chiếu kho văn bản toàn cầu) hay GPTZero.")
    print("Muốn kiểm đạo văn thật thì phải nộp qua hệ thống của trường.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
