from click.testing import CliRunner

from procurement_ontology.identity import Credentials, IdentityStore


def test_bootstrap_uses_runtime_directory_and_never_prints_password(tmp_path, monkeypatch):
    from procurement_ontology.runtime import main
    monkeypatch.setenv("PROCUREMENT_RUNTIME_DIR", str(tmp_path))
    result = CliRunner().invoke(main, ["bootstrap-admin", "--username", "platform"],
                                input="synthetic-bootstrap-password\nsynthetic-bootstrap-password\n")
    assert result.exit_code == 0, result.output
    assert "synthetic-bootstrap-password" not in result.output
    assert IdentityStore(tmp_path / "control.sqlite3").authenticate(Credentials("platform", "synthetic-bootstrap-password")).scope_id == "platform"
    result = CliRunner().invoke(main, ["bootstrap-admin", "--username", "another"],
                                input="synthetic-bootstrap-password\nsynthetic-bootstrap-password\n")
    assert result.exit_code != 0
