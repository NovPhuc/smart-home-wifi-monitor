"""Kiểm tra cấu trúc frontend sau khi tách ``app.js`` thành ES modules.

Các test này không chạy trình duyệt; chúng bắt những lỗi tĩnh dễ tái phát:
import sai đường dẫn, vòng import, template quên ``type="module"``, service
worker thiếu file trong app shell, hoặc JS dùng ID không có trong HTML.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "server" / "static"
TEMPLATES = ROOT / "server" / "templates"
MODULES = sorted((STATIC / "js").glob("*.js"))

STATIC_IMPORT_RE = re.compile(r"""from\s+['"](\./[^'"]+)['"]""")
DYNAMIC_IMPORT_RE = re.compile(r"""import\(\s*['"](\./[^'"]+)['"]\s*\)""")
DOM_ID_RE = re.compile(r"""\$\(\s*'([^']+)'\s*\)""")
HTML_ID_RE = re.compile(r'\bid="([^"]+)"')
APP_SCRIPT_RE = re.compile(r"<script\b[^>]*\bsrc=\"/static/app\.js\"[^>]*>")


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def module_imports(module: Path) -> set[Path]:
    source = read(module)
    specifiers = STATIC_IMPORT_RE.findall(source) + DYNAMIC_IMPORT_RE.findall(source)
    return {(module.parent / specifier).resolve() for specifier in specifiers}


def test_app_entry_only_loads_main_module():
    entry = read(STATIC / "app.js")
    assert len(entry.splitlines()) < 30
    assert "import('/static/js/main.js')" in entry


def test_every_module_import_resolves():
    for module in MODULES:
        for target in module_imports(module):
            assert target.is_file(), f"{module.name} import thiếu file {target}"


def test_module_graph_has_no_cycles():
    graph = {module.resolve(): module_imports(module) for module in MODULES}
    visiting: set[Path] = set()
    visited: set[Path] = set()

    def visit(node: Path, stack: list[Path]) -> None:
        if node in visiting:
            cycle = " -> ".join(path.name for path in stack + [node])
            raise AssertionError(f"vòng import: {cycle}")
        if node in visited:
            return
        visiting.add(node)
        for dependency in graph.get(node, set()):
            visit(dependency, stack + [node])
        visiting.remove(node)
        visited.add(node)

    for node in graph:
        visit(node, [])


@pytest.mark.parametrize("template", ["dashboard.html", "index.html"])
def test_templates_load_app_as_es_module(template):
    html = read(TEMPLATES / template)
    script_tags = APP_SCRIPT_RE.findall(html)
    assert script_tags, f"{template} không nạp /static/app.js"
    for tag in script_tags:
        assert 'type="module"' in tag, f"{template} nạp app.js như script thường"


def test_service_worker_precaches_every_module():
    service_worker = read(STATIC / "service-worker.js")
    shell_match = re.search(r"const APP_SHELL = \[(.*?)\];", service_worker, re.S)
    assert shell_match, "không tìm thấy APP_SHELL trong service-worker.js"
    shell = set(re.findall(r"'([^']+)'", shell_match.group(1)))
    expected = {"/static/app.js"} | {f"/static/js/{module.name}" for module in MODULES}
    assert expected <= shell, f"APP_SHELL thiếu: {sorted(expected - shell)}"
    assert re.search(r"const CACHE_NAME = 'an-tam-home-v\d+';", service_worker)
    assert "url.pathname.startsWith('/api/')" in service_worker


def test_every_dom_id_used_by_js_exists_in_a_template():
    js = "\n".join(read(module) for module in MODULES)
    html = "\n".join(read(template) for template in TEMPLATES.glob("*.html"))
    used = set(DOM_ID_RE.findall(js))
    defined = set(HTML_ID_RE.findall(html))
    missing = sorted(used - defined)
    assert not missing, f"JS dùng ID không có trong template: {missing}"
