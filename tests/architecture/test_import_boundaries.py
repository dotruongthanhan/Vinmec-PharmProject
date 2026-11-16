import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FORBIDDEN = {
    "streamlit",
    "langgraph",
    "langchain",
    "psycopg",
    "sqlalchemy",
    "httpx",
    "requests",
    "openai",
}


def test_core_import_boundaries() -> None:
    violations = []
    for folder in ("domain", "core", "calc", "rules", "deid"):
        for path in (ROOT / "app" / folder).rglob("*.py"):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                modules = []
                if isinstance(node, ast.Import):
                    modules = [alias.name for alias in node.names]
                elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
                    modules = [node.module]
                for module in modules:
                    if module.split(".")[0] in FORBIDDEN:
                        violations.append(f"{path.relative_to(ROOT)}:{node.lineno}: {module}")
    assert violations == []


def environment_violations(source: str) -> list[int]:
    tree = ast.parse(source)
    os_names = {"os"}
    env_names = set()
    getenv_names = set()
    dotenv_names = {"dotenv"}
    loader_names = {"load_dotenv"}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "os":
                    os_names.add(alias.asname or alias.name)
                if alias.name == "dotenv":
                    dotenv_names.add(alias.asname or alias.name)
        elif isinstance(node, ast.ImportFrom):
            for alias in node.names:
                name = alias.asname or alias.name
                if node.module == "os" and alias.name == "environ":
                    env_names.add(name)
                if node.module == "os" and alias.name == "getenv":
                    getenv_names.add(name)
                if node.module in {"dotenv", "dotenv.main"} and alias.name == "load_dotenv":
                    loader_names.add(name)
    violations = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and node.id in env_names | getenv_names | loader_names:
            violations.append(node.lineno)
        elif isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
            if (node.value.id in os_names and node.attr in {"environ", "getenv"}) or (
                node.value.id in dotenv_names and node.attr == "load_dotenv"
            ):
                violations.append(node.lineno)
    return violations


def test_environment_access_only_in_config() -> None:
    violations = []
    for path in (ROOT / "app").rglob("*.py"):
        relative = path.relative_to(ROOT / "app")
        # Ngoại lệ hiện có: giao diện đọc CDSS_CASE_DIR; T11 không sửa file này.
        if relative.parts[0] == "config" or relative == Path("ui/streamlit_app.py"):
            continue
        for line in environment_violations(path.read_text(encoding="utf-8")):
            violations.append(f"{relative}:{line}")
    assert violations == []


def test_environment_guard_handles_aliases() -> None:
    for source in [
        "import os as system\nsystem.environ['X']",
        "from os import getenv as read_env\nread_env('X')",
        "from os import environ as env\nenv.get('X')",
        "import dotenv as d\nd.load_dotenv()",
        "from dotenv import load_dotenv as load\nload()",
    ]:
        assert environment_violations(source)
