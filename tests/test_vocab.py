"""helix_blender_tools/_vocab.py must match the helix-core vocabulary."""
import ast
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


def test_generated_vocab_is_current():
    proc = subprocess.run([sys.executable, str(REPO / "scripts" / "gen_vocab.py"), "--check"],
                          capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr


def test_vocab_module_is_self_contained():
    tree = ast.parse((REPO / "helix_blender_tools" / "_vocab.py").read_text())
    assert not [n for n in ast.walk(tree) if isinstance(n, (ast.Import, ast.ImportFrom))]


def test_old_title_case_names_still_resolve():
    sys.path.insert(0, str(REPO / "helix_blender_tools"))
    import _vocab

    assert _vocab.ALIASES["jump start"] == "jump_start"
    assert _vocab.ALIASES["run backward"] == "run_backwards"
    assert "jump_start" in _vocab.TEMPLATE_NAMES and "jump start" not in _vocab.KNOWN_ANIMATIONS
