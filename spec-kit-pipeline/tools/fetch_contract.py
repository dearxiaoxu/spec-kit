#!/usr/bin/env python3
"""
独立契约拉取工具：从目标站获取 OpenAPI 并存为快照/当前版本。

用法：
  python3 tools/fetch_contract.py                       # 拉取到 assets/contract/current.json
  python3 tools/fetch_contract.py --save-baseline       # 拉取并存为基线 snapshot.json（首次建基线用）
  python3 tools/fetch_contract.py --path /v3/api-docs   # 自定义 OpenAPI 路径
"""
from __future__ import annotations

import argparse
import json
import os
import ssl
import sys
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from pipeline import load_config  # noqa: E402

CONTRACT_DIR = "assets/contract"


def fetch(spec_url: str, token: str = "", timeout: int = 15) -> dict:
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    headers = {"Accept": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(spec_url, headers=headers)
    print(f"[FETCH] GET {spec_url}" + ("（带 Bearer token）" if token else ""))
    with urllib.request.urlopen(req, context=ctx, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser(description="拉取 Spec-Kit OpenAPI 契约")
    parser.add_argument("--save-baseline", action="store_true", help="同时保存为基线 snapshot.json")
    parser.add_argument("--path", help="OpenAPI 路径（默认取 config.json 的 target.openapi_path）")
    parser.add_argument("--token", default=os.environ.get("SPEC_KIT_TOKEN", ""),
                        help="Bearer token（优先读环境变量 SPEC_KIT_TOKEN；凭据不入库，对齐测试方案 §3.3）")
    args = parser.parse_args()

    config = load_config()
    target = config.get("target", {})
    base_url = target.get("base_url", "https://106.54.60.191")
    openapi_path = args.path or target.get("openapi_path", "/v3/api-docs")

    cfg_dir = (config.get("gates") or {}).get("contract_diff", {}).get("snapshot_dir", CONTRACT_DIR)
    out_dir = os.path.join(config.get("project_root", "."), cfg_dir)
    os.makedirs(out_dir, exist_ok=True)

    url = base_url.rstrip("/") + "/" + openapi_path.lstrip("/")
    try:
        spec = fetch(url, token=args.token)
    except Exception as e:
        print(f"[ERROR] 拉取失败: {e}")
        print("提示: 目标站可能未暴露 OpenAPI；可 --path 换路径，或设 SPEC_KIT_TOKEN 后重试（/api/v1/openapi.json 返回 401 需认证）。")
        return 2

    version = (spec.get("info") or {}).get("version", "?")
    cur = os.path.join(out_dir, "current.json")
    with open(cur, "w", encoding="utf-8") as f:
        json.dump(spec, f, ensure_ascii=False, indent=2)
    print(f"[OK] current.json 已保存 (version={version})")

    if args.save_baseline:
        base = os.path.join(out_dir, "snapshot.json")
        with open(base, "w", encoding="utf-8") as f:
            json.dump(spec, f, ensure_ascii=False, indent=2)
        print(f"[OK] snapshot.json 基线已建立 (version={version})")

    return 0


if __name__ == "__main__":
    sys.exit(main())
