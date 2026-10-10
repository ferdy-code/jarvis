import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parents[1]


def setting_names(path: str) -> set[str]:
    return set(re.findall(r"JARVIS_[A-Z_]+", (ROOT / path).read_text(encoding="utf-8")))


def test_the_readme_documents_every_setting_and_only_those():
    assert setting_names("README.md") == setting_names("src/jarvis/config.py")
