import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def load_module():
    spec = importlib.util.spec_from_file_location("make_sbom", ROOT / "tools" / "make_sbom.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_sbom_lists_python_packages_npm_packages_and_downloaded_tools():
    bom = load_module().build()
    assert bom["bomFormat"] == "CycloneDX" and bom["specVersion"] == "1.5"
    purls = [c.get("purl", "") for c in bom["components"]]
    assert any(p.startswith("pkg:pypi/httpx@") for p in purls)
    if (ROOT / "src" / "claudios" / "components" / "npm" / "package-lock.json").is_file():
        assert any(p.startswith("pkg:npm/") for p in purls)
    tools = {c["name"]: c for c in bom["components"] if c["type"] == "application"}
    assert "java" in tools and "node" in tools
    assert len({(c["name"], c["version"]) for c in bom["components"]}) == len(bom["components"])


def test_integrity_values_are_converted_to_hex():
    module = load_module()
    assert module._integrity("sha256-AAEC") == [{"alg": "SHA-256", "content": "000102"}]
    assert module._integrity("md5-AAEC") == [] and module._integrity("nonsense") == []
