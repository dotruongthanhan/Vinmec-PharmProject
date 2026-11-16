"""Kiểm thử tĩnh bằng AST bảo đảm an toàn hiển thị và tách lớp trong app/ui/."""

import ast
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
_UI_DIR = _ROOT / "app" / "ui"
_COMPONENTS_DIR = _UI_DIR / "components"


def _iter_runtime_statements(nodes: list[ast.stmt]) -> list[ast.AST]:
    """Duyệt mọi nút AST chạy thực tế, bỏ qua nhánh if TYPE_CHECKING."""
    collected: list[ast.AST] = []
    for stmt in nodes:
        if (
            isinstance(stmt, ast.If)
            and isinstance(stmt.test, ast.Name)
            and stmt.test.id == "TYPE_CHECKING"
        ):
            continue
        collected.extend(ast.walk(stmt))
    return collected


def test_ui_files_have_no_unsafe_allow_html() -> None:
    """Toàn bộ tệp trong app/ui/ không chứa unsafe_allow_html."""
    for py_file in sorted(_UI_DIR.rglob("*.py")):
        content = py_file.read_text(encoding="utf-8")
        assert "unsafe_allow_html" not in content, f"{py_file} chứa unsafe_allow_html"


def test_components_no_st_write_and_markdown_only_constant() -> None:
    """Trong app/ui/components/ không gọi st.write; st.markdown chỉ nhận hằng chuỗi."""
    component_files = sorted(_COMPONENTS_DIR.glob("*.py"))
    assert len(component_files) >= 9

    for py_file in component_files:
        tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            if not (
                isinstance(func, ast.Attribute)
                and isinstance(func.value, ast.Name)
                and func.value.id == "st"
            ):
                continue
            assert func.attr != "write", f"{py_file} không được dùng st.write"
            if func.attr == "markdown":
                first_arg: ast.expr | None = node.args[0] if node.args else None
                if first_arg is None:
                    for kw in node.keywords:
                        if kw.arg == "body":
                            first_arg = kw.value
                            break
                is_str_const = isinstance(first_arg, ast.Constant) and isinstance(
                    first_arg.value, str
                )
                assert is_str_const, f"{py_file} gọi st.markdown với đối số không phải hằng chuỗi"


def test_only_streamlit_app_reads_os_env() -> None:
    """Chỉ streamlit_app.py được đọc os.environ hoặc os.getenv."""
    for py_file in sorted(_UI_DIR.rglob("*.py")):
        if py_file == _UI_DIR / "streamlit_app.py":
            continue
        tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Attribute)
                and isinstance(node.value, ast.Name)
                and node.value.id == "os"
                and node.attr in {"environ", "getenv"}
            ):
                raise AssertionError(f"{py_file} đọc os.{node.attr} ngoài streamlit_app.py")
            if isinstance(node, ast.ImportFrom) and node.module == "os":
                imported = {alias.name for alias in node.names}
                assert not (imported & {"environ", "getenv"}), f"{py_file} import env từ os"


def test_pure_ui_modules_do_not_import_streamlit() -> None:
    """view_model.py, labels.py, services.py, state.py không import streamlit."""
    for name in ("view_model.py", "labels.py", "services.py", "state.py"):
        py_file = _UI_DIR / name
        tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert alias.name.split(".")[0] != "streamlit", f"{name} import streamlit"
            elif isinstance(node, ast.ImportFrom) and node.module is not None:
                assert node.module.split(".")[0] != "streamlit", f"{name} import từ streamlit"


def test_only_services_imports_pipeline_or_rules_at_runtime() -> None:
    """Ngoài services.py, các tệp trong app/ui/ không import app.pipeline hay app.rules lúc chạy."""
    for py_file in sorted(_UI_DIR.rglob("*.py")):
        if py_file == _UI_DIR / "services.py":
            continue
        tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
        for node in _iter_runtime_statements(tree.body):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert not alias.name.startswith(("app.pipeline", "app.rules")), (
                        f"{py_file} import {alias.name}"
                    )
            elif isinstance(node, ast.ImportFrom) and node.module is not None:
                assert not node.module.startswith(("app.pipeline", "app.rules")), (
                    f"{py_file} import từ {node.module}"
                )
