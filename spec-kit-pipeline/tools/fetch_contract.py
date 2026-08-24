#!/usr/bin/env python3
"""
独立契约拉取工具：从目标站获取 OpenAPI 并存为快照/当前版本。

用法：
  python3 tools/fetch_contract.py --auto-login --save-baseline   # 推荐：用 autotest/.env 账号登录后建基线
  python3 tools/fetch_contract.py --save-baseline                # 需 --token 或环境变量 SPEC_KIT_TOKEN
  python3 tools/fetch_contract.py --path /v3/api-docs            # 自定义 OpenAPI 路径

--auto-login 从 spec-kit-autotest/.env 读取 USERNAME/PASSWORD，调 /auth/login 拿 token（凭据不入库）。
"""
from __future__ import annotations

import argparse
import json
import os
import ssl
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from pipeline import load_config  # noqa: E402
from tools.common import ToolError, atomic_write, digest, redact  # noqa: E402

CONTRACT_DIR = "assets/contract"


def _ssl_ctx(insecure: bool = False) -> ssl.SSLContext:
    ctx = ssl.create_default_context()
    if insecure:
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
    return ctx


def parse_env_file(path: str) -> dict:
    """极简 .env 解析（KEY=VALUE，# 注释），不引入 dotenv 依赖"""
    env = {}
    if not os.path.exists(path):
        return env
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, val = line.partition("=")
            env[key.strip()] = val.strip().strip('"').strip("'")
    return env


def auto_login(base_url: str, env_path: str, timeout: int = 15, insecure: bool = False) -> str:
    """用 autotest/.env 的账号登录，返回 accessToken（不打印任何凭据）"""
    env = parse_env_file(env_path)
    username = env.get("USERNAME") or env.get("SPEC_KIT_USERNAME")
    password = env.get("PASSWORD") or env.get("SPEC_KIT_PASSWORD")
    if not username or not password:
        raise RuntimeError(
            f"{env_path} 中缺少 USERNAME/PASSWORD，无法自动登录；请改用 --token / SPEC_KIT_TOKEN"
        )

    url = base_url.rstrip("/") + "/api/v1/auth/login"
    payload = json.dumps({"username": username, "password": password}).encode("utf-8")
    req = urllib.request.Request(
        url, data=payload, headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, context=_ssl_ctx(insecure), timeout=timeout) as resp:
        body = json.loads(resp.read().decode("utf-8"))
    if body.get("ok") is not True:
        raise RuntimeError(f"登录失败: HTTP {resp.status}")
    token = ((body.get("data") or {}).get("accessToken") or "").strip()
    if not token:
        raise RuntimeError("登录成功但响应中无 accessToken，接口结构可能变化")
    return token


def fetch(spec_url: str, token: str = "", timeout: int = 15, insecure: bool = False) -> dict:
    ctx = _ssl_ctx(insecure)
    headers = {"Accept": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(spec_url, headers=headers)
    print(f"[FETCH] GET {spec_url}" + ("（已认证）" if token else ""))
    with urllib.request.urlopen(req, context=ctx, timeout=timeout) as resp:
        value = json.loads(resp.read().decode("utf-8"))
    validate_openapi(value)
    return value


def validate_openapi(spec: dict) -> None:
    if not isinstance(spec, dict) or not isinstance(spec.get("info"), dict) or not isinstance(spec.get("paths"), dict):
        raise ToolError("响应不是有效的 OpenAPI 文档：缺少 info/paths")
    if not (spec.get("openapi") or spec.get("swagger")):
        raise ToolError("响应不是有效的 OpenAPI 文档：缺少 openapi/swagger 版本")


def save_contract(path: Path, spec: dict, *, overwrite: bool = True) -> None:
    if path.exists() and not overwrite:
        raise ToolError(f"基线已存在，拒绝覆盖: {path}；确认后使用 --force-baseline")
    atomic_write(path, json.dumps(redact(spec), ensure_ascii=False, indent=2) + "\n")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="拉取 Spec-Kit OpenAPI 契约")
    parser.add_argument("--save-baseline", action="store_true", help="同时保存为基线 snapshot.json")
    parser.add_argument("--path", help="OpenAPI 路径（默认取 config.json 的 target.openapi_path）")
    parser.add_argument("--token", default=os.environ.get("SPEC_KIT_TOKEN", ""),
                        help="Bearer token（优先读环境变量 SPEC_KIT_TOKEN；凭据不入库）")
    parser.add_argument("--auto-login", action="store_true",
                        help="从 spec-kit-autotest/.env 读账号自动登录拿 token（推荐）")
    parser.add_argument("--insecure", action="store_true", help="显式允许不校验证书（仅隔离测试环境）")
    parser.add_argument("--force-baseline", action="store_true", help="明确允许覆盖已存在的基线")
    args = parser.parse_args(argv)

    config = load_config()
    if args.insecure and config.get("environment") == "production-like":
        print("[ERROR] production-like 环境禁止 --insecure")
        return 3
    target = config.get("target", {})
    base_url = target.get("base_url", "https://106.54.60.191")
    openapi_path = args.path or target.get("openapi_path", "/api/v1/openapi.json")

    token = args.token
    if not token and args.auto_login:
        env_path = os.path.join(config.get("autotest_dir", ""), ".env")
        try:
            print(f"[LOGIN] 使用 {env_path} 中的账号自动登录...")
            token = auto_login(base_url, env_path, insecure=args.insecure)
            print("[LOGIN] OK，已获取 accessToken")
        except Exception as e:
            print(f"[LOGIN] 失败: {e}")
            print("提示: 可改用 --token 或设置环境变量 SPEC_KIT_TOKEN。")
            return 2
    elif not token:
        print("[WARN] 未提供 token；/api/v1/openapi.json 需要认证，可能拉取失败。可用 --auto-login 或 --token。")

    cfg_dir = (config.get("gates") or {}).get("contract_diff", {}).get("snapshot_dir", CONTRACT_DIR)
    out_dir = os.path.join(config.get("project_root", "."), cfg_dir)
    os.makedirs(out_dir, exist_ok=True)
    baseline_path = Path(out_dir, "snapshot.json")
    if args.save_baseline and baseline_path.exists() and not args.force_baseline:
        print(f"[ERROR] 基线已存在，拒绝覆盖: {baseline_path}；确认后使用 --force-baseline")
        return 2

    url = base_url.rstrip("/") + "/" + openapi_path.lstrip("/")
    try:
        spec = fetch(url, token=token, insecure=args.insecure)
    except Exception as e:
        print(f"[ERROR] 拉取失败: {type(e).__name__}")
        print("提示: 确认 --auto-login 的账号有权限，或 --path 换路径；也可手工放置契约 JSON。")
        return 2

    version = (spec.get("info") or {}).get("version", "?")
    try:
        cur = Path(out_dir, "current.json")
        save_contract(cur, spec)
        print(f"[OK] current.json 已原子保存 (version={version}, sha256={digest(spec)[:12]})")
        if args.save_baseline:
            base = baseline_path
            save_contract(base, spec, overwrite=args.force_baseline)
            print(f"[OK] snapshot.json 基线已建立 (version={version})")
    except ToolError as exc:
        print(f"[ERROR] {exc}")
        return exc.code

    return 0


if __name__ == "__main__":
    sys.exit(main())
