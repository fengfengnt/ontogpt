"""Local single-process service commands; credentials stay outside Git."""

import os
from ipaddress import ip_network
from contextlib import contextmanager
from pathlib import Path

import click
from filelock import FileLock, Timeout

from .identity import Credentials, IdentityStore

ROOT = Path(__file__).resolve().parents[3]


def runtime_directory():
    path = Path(os.getenv("PROCUREMENT_RUNTIME_DIR", str(ROOT / "services/procurement_ontology/runtime"))).resolve()
    path.mkdir(parents=True, exist_ok=True)
    return path


@contextmanager
def runtime_lock(runtime):
    lock = FileLock(Path(runtime) / "service.lock", timeout=0)
    try:
        lock.acquire()
    except Timeout:
        raise click.ClickException("请先停止该运行目录中的服务，进入维护窗口后再操作") from None
    try:
        yield
    finally:
        lock.release()


@click.group()
def main():
    """采购本体服务本地管理。"""


@main.command("bootstrap-admin")
@click.option("--username", required=True)
@click.password_option()
def bootstrap_admin(username, password):
    """首次创建平台管理员；密码不回显。"""
    try:
        runtime = runtime_directory()
        with runtime_lock(runtime):
            IdentityStore(runtime / "control.sqlite3").bootstrap_admin(Credentials(username, password))
    except ValueError as error:
        raise click.ClickException(str(error)) from None
    click.echo("平台管理员已初始化")


def components(runtime, dataset_prefix=None):
    from dotenv import load_dotenv
    from .maintenance import WriteGate
    from .schema_catalog import SchemaCatalog
    from .store import FusekiStore

    if (runtime / "restore.incomplete").exists():
        raise RuntimeError("恢复尚未完成，禁止启动或启用此目标")
    load_dotenv(os.getenv("PROCUREMENT_ENV_FILE", str(runtime / ".env")), override=False)
    gate = WriteGate()
    identities = IdentityStore(runtime / "control.sqlite3", gate=gate)
    catalog = SchemaCatalog(identities.path, gate=gate)
    store = FusekiStore(os.getenv("PROCUREMENT_FUSEKI_URL", "http://127.0.0.1:3032"),
                        os.getenv("FUSEKI_CREDENTIALS_FILE", str(ROOT / "deploy/fuseki/runtime/credentials.json")),
                        dataset_prefix=dataset_prefix or os.getenv("PROCUREMENT_DATASET_PREFIX", "procurement_"), gate=gate)
    return identities, catalog, store


def build_app(runtime=None):
    from .api import create_app
    from .platform_seed import bootstrap_platform
    from .sso import SSOConfig

    runtime = runtime or runtime_directory()
    identities, catalog, store = components(runtime)
    bootstrap_platform(store)
    return create_app(identities, store, catalog,
                      draft_parent=os.getenv("PROCUREMENT_DRAFT_PARENT", str(ROOT.parent / "procurement-schema-drafts")),
                      frontend_dist=ROOT / "frontend/procurement-ontology/dist", sso_config=SSOConfig.from_env(),
                      public_origin=os.getenv("PROCUREMENT_PUBLIC_ORIGIN"))


@main.command("serve")
@click.option("--port", default=8002, type=click.IntRange(1024, 65535))
def serve(port):
    """仅监听本机；一个进程提供网页、API 和 MCP。"""
    import uvicorn

    runtime = runtime_directory()
    with runtime_lock(runtime):
        app = build_app(runtime)
        proxies = os.getenv("PROCUREMENT_TRUSTED_PROXIES", "127.0.0.1").split(",")
        if any(ip_network(peer.strip()).num_addresses != 1 for peer in proxies):
            raise ValueError("Trusted proxies must be individual IP addresses")
        uvicorn.run(app, host=os.getenv("PROCUREMENT_BIND_HOST", "127.0.0.1"), port=port,
                    log_level="warning", workers=1, proxy_headers=True,
                    forwarded_allow_ips=[str(ip_network(peer.strip()).network_address) for peer in proxies])


@main.command("backup")
@click.option("--destination", required=True, type=click.Path(path_type=Path, file_okay=False))
def backup(destination):
    """停止服务后备份双库，清单最后写入。"""
    from .backup import BackupManager

    runtime = runtime_directory()
    with runtime_lock(runtime):
        if not (runtime / "control.sqlite3").is_file():
            raise click.ClickException("运行目录没有管理库")
        identities, catalog, store = components(runtime)
        BackupManager(store, identities, catalog).backup_service(destination)
    click.echo("备份完成，清单：" + str(destination.resolve() / "manifest.json"))


@main.command("restore")
@click.argument("manifest", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option("--destination", required=True, type=click.Path(path_type=Path, file_okay=False))
@click.option("--dataset-prefix", required=True)
def restore(manifest, destination, dataset_prefix):
    """恢复到新运行目录和空数据集前缀，完成后再切换服务配置。"""
    from .backup import BackupManager

    destination = destination.resolve()
    destination.mkdir(parents=True, exist_ok=True)
    with runtime_lock(destination):
        identities, catalog, store = components(destination, dataset_prefix)
        BackupManager(store, identities, catalog).restore_service(manifest)
    click.echo("恢复验证完成。请设置 PROCUREMENT_RUNTIME_DIR 和 PROCUREMENT_DATASET_PREFIX 后启动新目标。")


if __name__ == "__main__":
    main()
