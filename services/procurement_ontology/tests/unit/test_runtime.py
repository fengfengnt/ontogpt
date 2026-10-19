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


def test_backup_command_refuses_a_running_runtime(tmp_path, monkeypatch):
    from filelock import FileLock
    from procurement_ontology.runtime import main
    monkeypatch.setenv("PROCUREMENT_RUNTIME_DIR", str(tmp_path))
    with FileLock(tmp_path / "service.lock", timeout=0):
        result = CliRunner().invoke(main, ["backup", "--destination", str(tmp_path / "backup")])
    assert result.exit_code != 0
    assert "停止" in result.output
    assert not (tmp_path / "backup").exists()


def test_incomplete_restore_cannot_start(tmp_path, monkeypatch):
    import pytest
    from procurement_ontology.runtime import build_app
    import procurement_ontology.store as module
    monkeypatch.setenv("PROCUREMENT_RUNTIME_DIR", str(tmp_path))
    (tmp_path / "restore.incomplete").write_text("test", encoding="utf-8")

    def forbidden_connection(*args, **kwargs):
        raise AssertionError("must reject before touching Fuseki")

    monkeypatch.setattr(module, "FusekiStore", forbidden_connection)
    with pytest.raises(RuntimeError, match="尚未完成"):
        build_app()
