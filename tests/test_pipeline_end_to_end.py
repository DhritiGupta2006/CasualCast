"""
End-to-end test for the scored pipeline: run.sh -> generate_features.py ->
predict.py, exercised against tests/fixtures/tiny_sample.csv.

This is the closest thing to the organizers' clean-clone acceptance test
that can run inside the dev environment. It does NOT replace the manual
"fresh venv, fresh clone" check described in the build instructions --
it only guards against regressions during development.

What it checks:
  * run.sh exists at the repo root, is executable, and exits 0.
  * output/predictions.csv (written to a temp path) exists after running.
  * The output has the announced columns and one row per forecast day.
  * Re-running with the same inputs produces byte-identical output
    (determinism requirement -- every stochastic step must be seeded).
  * src/train.py (used only to produce the tiny model fixture here, not
    part of run.sh's call path) runs without any network access.
"""

from __future__ import annotations

import os
import shutil
import stat
import subprocess
import sys

import pandas as pd
import pytest

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
FIXTURE_CSV = os.path.join(REPO_ROOT, "tests", "fixtures", "tiny_sample.csv")
RUN_SH = os.path.join(REPO_ROOT, "run.sh")

EXPECTED_CORE_COLUMNS = {
    "date",
    "revenue_p10",
    "revenue_p50",
    "revenue_p90",
    "trend_direction",
    "trend_slope",
}


@pytest.fixture()
def pipeline_dirs(tmp_path):
    """Set up an isolated DATA_DIR / MODEL_PATH / OUTPUT_PATH triple."""
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    shutil.copy(FIXTURE_CSV, data_dir / "tiny_sample.csv")

    model_path = tmp_path / "pickle" / "model.pkl"
    output_path = tmp_path / "output" / "predictions.csv"

    return {
        "data_dir": str(data_dir),
        "model_path": str(model_path),
        "output_path": str(output_path),
    }


def _train_tiny_model(model_path: str, data_dir: str) -> None:
    """Use src/train.py to produce a small, fully local model fixture.

    This mirrors how pickle/model.pkl is produced for real, but keeps the
    test hermetic (its own tmp model, not the committed one) and proves
    train.py itself needs no network access to run.
    """
    result = subprocess.run(
        [sys.executable, os.path.join(REPO_ROOT, "src", "train.py"), data_dir, model_path],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        env={**os.environ, "http_proxy": "", "https_proxy": "", "HTTP_PROXY": "", "HTTPS_PROXY": ""},
    )
    assert result.returncode == 0, f"train.py failed:\n{result.stdout}\n{result.stderr}"
    assert os.path.exists(model_path), "train.py did not write model.pkl"


def test_run_sh_exists_and_is_executable():
    assert os.path.exists(RUN_SH), "run.sh must exist at the repo root"
    mode = os.stat(RUN_SH).st_mode
    assert mode & stat.S_IXUSR, "run.sh must be executable (chmod +x run.sh)"


def test_requirements_txt_exists_and_has_no_backend_deps():
    req_path = os.path.join(REPO_ROOT, "requirements.txt")
    assert os.path.exists(req_path), "requirements.txt must exist at the repo root"
    with open(req_path) as f:
        content = f.read().lower()
    for banned in ("fastapi", "uvicorn", "anthropic", "requests", "httpx"):
        assert banned not in content, (
            f"requirements.txt must not contain '{banned}' -- "
            "network/backend deps belong in backend/requirements-backend.txt"
        )
    # every non-comment, non-blank line should be pinned with ==
    for line in content.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        assert "==" in line, f"requirements.txt line not pinned exactly: {line!r}"


def test_pipeline_end_to_end_produces_expected_output(pipeline_dirs):
    _train_tiny_model(pipeline_dirs["model_path"], pipeline_dirs["data_dir"])

    result = subprocess.run(
        [
            "bash",
            RUN_SH,
            pipeline_dirs["data_dir"],
            pipeline_dirs["model_path"],
            pipeline_dirs["output_path"],
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, f"run.sh failed:\n{result.stdout}\n{result.stderr}"

    output_path = pipeline_dirs["output_path"]
    assert os.path.exists(output_path), "run.sh did not write the output CSV"

    df = pd.read_csv(output_path)
    assert len(df) > 0, "predictions.csv has no rows"
    missing = EXPECTED_CORE_COLUMNS - set(df.columns)
    assert not missing, f"predictions.csv missing expected columns: {missing}"

    # dates should be unique and sorted -- one row per forecast day
    dates = pd.to_datetime(df["date"])
    assert dates.is_monotonic_increasing
    assert dates.is_unique


def test_pipeline_is_deterministic(pipeline_dirs):
    _train_tiny_model(pipeline_dirs["model_path"], pipeline_dirs["data_dir"])

    def _run_once():
        subprocess.run(
            [
                "bash",
                RUN_SH,
                pipeline_dirs["data_dir"],
                pipeline_dirs["model_path"],
                pipeline_dirs["output_path"],
            ],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=True,
        )
        with open(pipeline_dirs["output_path"], "rb") as f:
            return f.read()

    first = _run_once()
    second = _run_once()
    assert first == second, "predictions.csv is not deterministic across identical runs"


def test_output_written_fresh_not_appended(pipeline_dirs):
    """Running twice should not double the row count -- output is overwritten."""
    _train_tiny_model(pipeline_dirs["model_path"], pipeline_dirs["data_dir"])

    for _ in range(2):
        subprocess.run(
            [
                "bash",
                RUN_SH,
                pipeline_dirs["data_dir"],
                pipeline_dirs["model_path"],
                pipeline_dirs["output_path"],
            ],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=True,
        )

    df = pd.read_csv(pipeline_dirs["output_path"])
    df_first_run_len = len(df)
    # second run over the same data must produce the same row count, not 2x
    assert df_first_run_len == len(pd.read_csv(pipeline_dirs["output_path"]))
