import ast
from pathlib import Path

_SERVICE_ROOT = Path(__file__).resolve().parent.parent / "services" / "nutrition"


def _imported_top_level_modules(path: Path) -> set[str]:
    tree = ast.parse(path.read_text())
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module.split(".")[0])
    return modules


def test_only_providers_package_imports_vendor_sdks():
    """task 2/3's acceptance: chat.py (and everything else outside
    providers/) depends on the ChatLLMClient/TranscriptionClient
    protocols only — never `anthropic` or `openai` directly."""
    offenders = []
    for path in _SERVICE_ROOT.rglob("*.py"):
        if "providers" in path.relative_to(_SERVICE_ROOT).parts:
            continue
        modules = _imported_top_level_modules(path)
        if "anthropic" in modules or "openai" in modules:
            offenders.append(str(path))
    assert offenders == []
