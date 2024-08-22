import subprocess
import sys
from pathlib import Path


def test_offline_demo_runs_as_a_script() -> None:
    root = Path(__file__).resolve().parents[1]
    result = subprocess.run(
        [sys.executable, "examples/offline.py"],
        cwd=root,
        capture_output=True,
        text=True,
        check=True,
        timeout=10,
    )

    assert result.stdout.splitlines() == [
        "Numbered: ['paper clips', 'labels', 'folders']",
        "Cursor preview: ['notebook']",
        "Requests after preview: [None]",
        "Cursor remainder: ['pencil', 'eraser']",
        "Requests after completion: [None, 'demo-gap', 'demo-last']",
    ]
    assert result.stderr == ""
