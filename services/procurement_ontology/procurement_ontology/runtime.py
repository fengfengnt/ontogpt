"""Local single-process service commands; credentials stay outside Git."""

import os
from pathlib import Path

import click

from .identity import Credentials, IdentityStore

ROOT = Path(__file__).resolve().parents[3]


def runtime_directory():
    path = Path(os.getenv("PROCUREMENT_RUNTIME_DIR", str(ROOT / "services/procurement_ontology/runtime"))).resolve()
    path.mkdir(parents=True, exist_ok=True)
    return path


@click.group()
def main():
    """采购本体服务本地管理。"""


@main.command("bootstrap-admin")
@click.option("--username", required=True)
@click.password_option()
def bootstrap_admin(username, password):
    """首次创建平台管理员；密码不回显。"""
    try:
        IdentityStore(runtime_directory() / "control.sqlite3").bootstrap_admin(Credentials(username, password))
    except ValueError as error:
        raise click.ClickException(str(error)) from None
    click.echo("平台管理员已初始化")


def build_app():
    from dotenv import load_dotenv

    from .api import create_app
    from .platform_seed import bootstrap_platform
    from .schema_catalog import SchemaCatalog
    from .store import FusekiStore

    runtime = runtime_directory()
    load_dotenv(os.getenv("PROCUREMENT_ENV_FILE", str(runtime / ".env")), override=False)
    identities = IdentityStore(runtime / "control.sqlite3")
    catalog = SchemaCatalog(identities.path)
    store = FusekiStore(os.getenv("PROCUREMENT_FUSEKI_URL", "http://127.0.0.1:3032"),
                        os.getenv("FUSEKI_CREDENTIALS_FILE", str(ROOT / "deploy/fuseki/runtime/credentials.json")))
    bootstrap_platform(store)
    return create_app(identities, store, catalog,
                      draft_parent=os.getenv("PROCUREMENT_DRAFT_PARENT", str(ROOT.parent / "procurement-schema-drafts")),
                      frontend_dist=ROOT / "frontend/procurement-ontology/dist")


@main.command("serve")
@click.option("--port", default=8002, type=click.IntRange(1024, 65535))
def serve(port):
    """仅监听本机；一个进程提供网页、API 和 MCP。"""
    import uvicorn

    uvicorn.run(build_app(), host="127.0.0.1", port=port, log_level="warning", workers=1)


if __name__ == "__main__":
    main()
