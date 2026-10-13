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