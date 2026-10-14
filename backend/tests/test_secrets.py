import re
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
KEY_PATTERNS = [
    re.compile(r"AIza[0-9A-Za-z_\-]{35}"),          # Google / Gemini
    re.compile(r"sk-ant-[A-Za-z0-9_\-]{20,}"),      # Anthropic
]


def test_no_api_keys_in_tracked_files():
    tracked = subprocess.run(
        ["git", "ls-files"], cwd=REPO, capture_output=True, text=True, check=True
    ).stdout.splitlines()
    leaks = []
    for name in tracked:
        try:
            text = (REPO / name).read_text()
        except (UnicodeDecodeError, OSError):
            continue
        if any(p.search(text) for p in KEY_PATTERNS):
            leaks.append(name)
    assert leaks == []


EXAMPLE_FILE = REPO / "backend" / ".env.example"
SECRET_NAME = re.compile(r"(KEY|SECRET|PASSWORD|TOKEN)$")


def test_env_example_has_no_secret_values():
    """.env.example is public: secret settings must be listed there, but left empty."""
    leaks = []
    for line in EXAMPLE_FILE.read_text().splitlines():
        if "=" not in line or line.lstrip().startswith("#"):
            continue
        name, value = (part.strip() for part in line.split("=", 1))
        if SECRET_NAME.search(name) and value:
            leaks.append(name)
    assert leaks == [], f"secret values in .env.example: {leaks}"