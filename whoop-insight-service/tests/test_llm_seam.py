import ast
from pathlib import Path

_SERVICE_ROOT = Path(__file__).resolve().parent.parent / "services" / "insight"


def _imports_anthropic(path: Path) -> bool:
    tree = ast.parse(path.read_text())
    for node in ast.walk(tree):
        if isinstance(node, ast.Import) and any(a.name == "anthropic" for a in node.names):
            return True
        if isinstance(node, ast.ImportFrom) and node.module == "anthropic":
            return True
    return False


def test_only_providers_package_imports_anthropic():
    """task 2's acceptance: generate.py (and everything else outside
    providers/) depends on the LLMClient protocol only — checked by
    actual `import`/`from` statements, not by a substring match, which
    would also flag config.py's `anthropic_api_key` field name and
    llm.py's docstring mentioning `providers/anthropic_client.py`."""
    offenders = [
        str(path)
        for path in _SERVICE_ROOT.rglob("*.py")
        if "providers" not in path.relative_to(_SERVICE_ROOT).parts and _imports_anthropic(path)
    ]
    assert offenders == []
