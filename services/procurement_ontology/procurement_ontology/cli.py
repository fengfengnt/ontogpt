"""Administrative commands call the service rather than editing its databases."""

import os
from pathlib import Path
from urllib.parse import urlsplit

import click
import requests


@click.command(name="activate-schema")
@click.argument("company_id")
@click.argument("category_key")
@click.argument("version")
@click.option("--server-url", envvar="PROCUREMENT_SERVICE_URL", default="http://127.0.0.1:8002")
@click.option("--token-file", envvar="PROCUREMENT_ADMIN_TOKEN_FILE",
              type=click.Path(exists=True, dir_okay=False, path_type=Path))
def activate_schema_command(company_id, category_key, version, server_url, token_file):
    """审核人确认 Git 审阅、测试和部署后，显式启用企业品类版本。"""
    parsed = urlsplit(server_url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc or parsed.username or parsed.password:
        raise click.ClickException("服务地址必须为不含凭据的 HTTP/HTTPS 地址")
    token = token_file.read_text(encoding="utf-8").strip() if token_file else os.getenv("PROCUREMENT_ADMIN_TOKEN")
    if not token:
        raise click.ClickException("请设置 PROCUREMENT_ADMIN_TOKEN_FILE 或管理会话令牌环境变量")
    try:
        with requests.Session() as session:
            session.trust_env = False
            response = session.post(server_url.rstrip("/") + "/v1/manage/schemas/activate",
                                    json={"company_id": company_id, "category_key": category_key, "version": version},
                                    headers={"Authorization": "Bearer " + token}, timeout=30)
            response.raise_for_status()
            result = response.json()
    except requests.RequestException:
        raise click.ClickException("服务激活请求失败，请检查服务状态、身份和已部署版本") from None
    if result.get("version") != version or not result.get("audit_id"):
        raise click.ClickException("服务未返回可核验的激活结果")
    click.echo(f"已启用 {company_id}/{category_key}/{version}；审计 ID：{result['audit_id']}")
