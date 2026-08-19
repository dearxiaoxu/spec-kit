#!/usr/bin/env python3
"""
Spec-Kit 迭代流水线主入口（骨架）

以测试为主、AI 协助的开发-测试迭代门禁编排：
  需求分级 → SDD 同步基线 → AI 编码 → 【自动门禁】→ 测试验证 → 人工审批 → 交付归档

用法：
  python3 pipeline.py --list                     # 列出全部门禁
  python3 pipeline.py --dry-run                  # 演练：只做启动校验，不真正执行门禁
  python3 pipeline.py                            # 跑全部启用门禁
  python3 pipeline.py --gate contract_diff       # 只跑单个门禁
  python3 pipeline.py --fetch-contract           # 拉取目标站 OpenAPI 存为 current.json
  python3 pipeline.py --stage code               # 按阶段筛选（plan/code/test/release，骨架阶段仅提示）

退出码：0=全部通过；1=存在失败；2=配置/用法错误；3=阻断性门禁失败
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime
from typing import Dict, List, Optional

# 允许直接以脚本方式运行（python3 pipeline.py）
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from gates import ALL_GATES
from gates.base import GateResult, GateSetupError

CONFIG_FILE = "config.json"
REPORT_DIR = "report"


def load_config() -> Dict:
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), CONFIG_FILE)
    if not os.path.exists(path):
        print(f"[FATAL] 缺少配置文件 {CONFIG_FILE}")
        sys.exit(2)
    with open(path, "r", encoding="utf-8") as f:
        cfg = json.load(f)
    cfg.setdefault("project_root", os.path.dirname(os.path.abspath(__file__)))
    return cfg


def run_gate(gate_cls, config: Dict, dry_run: bool = False) -> Optional[GateResult]:
    name = gate_cls.name
    try:
        gate = gate_cls(config, ctx={})
        gate.init()
        if not gate.enabled():
            return GateResult(name=name, passed=True, skipped=True, detail="门禁在 config 中已禁用")
        if dry_run:
            # 演练模式：只做启动校验（init），不真正执行门禁逻辑，避免副作用
            return GateResult(name=name, passed=True, skipped=True, detail=f"dry-run 演练通过（init 校验 OK）")
        return gate.run()
    except GateSetupError as e:
        return GateResult(name=name, passed=True, skipped=True, detail=f"跳过: {e}")
    except Exception as e:
        return GateResult(
            name=name,
            passed=False,
            blocking=bool(getattr(gate_cls, "blocking", False)),
            detail=f"门禁执行异常: {e}",
        )


def result_mark(result: GateResult) -> str:
    """将 GateResult 转成人可读状态；跳过必须与通过严格区分。"""
    if result.skipped:
        return "SKIP"
    return "PASS" if result.passed else "FAIL"


def write_report(results: List[GateResult], config: Dict) -> str:
    report_dir = config.get("report_dir", REPORT_DIR)
    os.makedirs(report_dir, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    base = os.path.join(report_dir, f"pipeline-{ts}")

    payload = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "results": [r.to_dict() for r in results],
        "summary": {
            "total": len(results),
            "passed": sum(1 for r in results if r.passed and not r.skipped),
            "failed": sum(1 for r in results if not r.passed),
            "skipped": sum(1 for r in results if r.skipped),
        },
    }
    json_path = base + ".json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    md = ["# Spec-Kit 流水线运行报告", ""]
    for r in results:
        mark = result_mark(r)
        md.append(f"## [{mark}] {r.name}")
        md.append(f"- {r.detail}")
        if r.issues:
            md.append("- issues:")
            for it in r.issues[:10]:
                md.append(f"  - {it[:160]}")
        md.append("")
    md_path = base + ".md"
    with open(md_path, "w", encoding="utf-8") as f:
        f.write("\n".join(md))

    print(f"\n[REPORT] {json_path}")
    print(f"[REPORT] {md_path}")
    return json_path


def fetch_contract(config: Dict, token: str = "", auto_login: bool = False) -> None:
    """拉取目标站 OpenAPI 存为 assets/contract/current.json（委托 tools/fetch_contract.py）"""
    import subprocess
    tool = os.path.join(config.get("project_root", "."), "tools", "fetch_contract.py")
    cmd = ["/opt/homebrew/bin/python3", tool]
    if token:
        cmd += ["--token", token]
    if auto_login:
        cmd += ["--auto-login"]
    subprocess.run(cmd, cwd=config.get("project_root", "."))


def main() -> int:
    parser = argparse.ArgumentParser(description="Spec-Kit 迭代流水线（骨架）")
    parser.add_argument("--list", action="store_true", help="列出全部门禁")
    parser.add_argument("--gate", help="只运行指定门禁（如 contract_diff）")
    parser.add_argument("--dry-run", action="store_true", help="演练模式：仅初始化校验，不执行门禁")
    parser.add_argument("--fetch-contract", action="store_true", help="拉取目标站 OpenAPI 到 current.json")
    parser.add_argument("--token", default=os.environ.get("SPEC_KIT_TOKEN", ""),
                        help="拉取契约用的 Bearer token（优先读环境变量 SPEC_KIT_TOKEN；凭据不入库）")
    parser.add_argument("--auto-login", action="store_true",
                        help="--fetch-contract 时从 spec-kit-autotest/.env 读账号自动登录拿 token")
    parser.add_argument("--script", help="覆盖 e2e_regression 的 npm script（如 test:unit 快速验证）")
    parser.add_argument("--stage", help="按阶段筛选（骨架阶段仅提示，不做过滤）")
    args = parser.parse_args()

    config = load_config()

    if args.script:
        config.setdefault("gates", {}).setdefault("e2e_regression", {})["script"] = args.script

    if args.list:
        print("可用门禁：")
        import sys as _sys
        for cls in ALL_GATES:
            mod_doc = (_sys.modules.get(cls.__module__).__doc__ or "").strip()
            first_line = mod_doc.splitlines()[0] if mod_doc else ""
            print(f"  - {cls.name:<20} blocking={cls.blocking}  （{first_line}）")
        return 0

    if args.fetch_contract:
        fetch_contract(config, token=args.token, auto_login=args.auto_login)
        return 0

    # 选择要跑的门禁
    if args.gate:
        selected = [c for c in ALL_GATES if c.name == args.gate]
        if not selected:
            print(f"[FATAL] 未知门禁: {args.gate}，用 --list 查看")
            return 2
        gates = selected
    else:
        gates = ALL_GATES

    if args.stage:
        print(f"[NOTE] 阶段过滤（{args.stage}）在骨架阶段不生效，全部启用门禁都会运行；后续可按阶段拆分流水线。")

    results: List[GateResult] = []
    failed_any = False
    blocked = False

    for cls in gates:
        name = cls.name
        print(f"\n==> 门禁 [{name}] ...")
        result = run_gate(cls, config, dry_run=args.dry_run)
        results.append(result)

        mark = result_mark(result)
        print(f"    [{mark}] {result.detail}")
        for it in result.issues[:5]:
            print(f"      - {it[:140]}")
        if not result.passed:
            failed_any = True
            if result.blocking:
                blocked = True
                print(f"    [BLOCK] 阻断性门禁 {name} 失败，流水线中断")
                break

    write_report(results, config)

    if blocked:
        print("\n[RESULT] FAILED（阻断性门禁失败）")
        return 3
    if failed_any:
        print("\n[RESULT] FAILED（存在失败项，见报告）")
        return 1
    if results and all(result.skipped for result in results):
        print("\n[RESULT] COMPLETED（全部门禁均跳过）")
        return 0
    print("\n[RESULT] ALL PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
