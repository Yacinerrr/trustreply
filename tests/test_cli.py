from pathlib import Path

from typer.testing import CliRunner

from trustreply.cli.main import app

runner = CliRunner()


def test_version() -> None:
    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0
    assert result.stdout.strip() == "0.0.1"


def test_ingest_command(policies_dir: Path) -> None:
    result = runner.invoke(app, ["ingest", str(policies_dir)])
    assert result.exit_code == 0
    assert "Extracted" in result.stdout
    assert "2 file(s)" in result.stdout


def test_ingest_missing_path(tmp_path: Path) -> None:
    result = runner.invoke(app, ["ingest", str(tmp_path / "missing")])
    assert result.exit_code == 1
