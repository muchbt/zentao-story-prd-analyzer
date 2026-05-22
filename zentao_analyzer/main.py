import argparse
import dataclasses
import json
import os
import sys

from .agent_client import AgentConfig
from .analyzer import analyze
from .app_config import build_runtime_config
from .code_clues import build_search_hints, build_seed_paths, load_clues_file
from .debug_bundle import build_debug_bundle
from .document_generator import generate_document
from .run_logger import RunLogger
from .summary_report import build_summary_item, write_summary_report
from .writeback import prepare_writeback_status
from .zentao_client import ZentaoClient, ZentaoError


def _plain_locations(locations):
    result = []
    for location in locations or []:
        if dataclasses.is_dataclass(location):
            result.append(dataclasses.asdict(location))
        elif isinstance(location, dict):
            result.append(location)
    return result


def _plain_value(value, default=""):
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return default


def main():
    parser = argparse.ArgumentParser(description="zentao-story-prd-analyzer")
    parser.add_argument("--module", default="story", help="禅道模块 (story/requirement/bug/task/ticket/feedback)")
    parser.add_argument("--id", help="禅道条目 ID（指定则获取单条详情）")
    parser.add_argument("--project", default=os.environ.get("PROJECT_ID", "1"), help="项目 ID")
    parser.add_argument("--product", help="产品 ID")
    parser.add_argument("--execution", help="执行 ID")
    parser.add_argument("--status", default="open", help="状态过滤")
    parser.add_argument("--limit", type=int, help="限制列表数量")
    parser.add_argument("--config", help="禅道 CLI 配置文件路径")
    parser.add_argument("--profile", help="禅道 CLI profile")
    parser.add_argument("--login", action="store_true", help="执行登录")
    parser.add_argument("--server", help="禅道服务地址")
    parser.add_argument("--user", help="禅道用户名")
    parser.add_argument("--password", help="禅道密码")
    parser.add_argument("--token", help="禅道 token")
    parser.add_argument("--use-env", action="store_true", help="强制使用环境变量登录")
    parser.add_argument("--output", help="阶段一结果输出 JSON 文件路径（默认 stdout）")
    parser.add_argument("--analyze", action="store_true", help="获取数据后继续执行代码分析和 PRD 生成")
    parser.add_argument("--repo-path", default=os.environ.get("REPO_PATH", "."), help="代码仓库路径")
    parser.add_argument("--agent", default=os.environ.get("LLM_AGENT"), help="LLM Agent")
    parser.add_argument("--model", help="LLM 模型名，显式指定时传给所选 Agent CLI")
    parser.add_argument("--agent-timeout", type=int, help="Agent 调用超时时间，单位秒")
    parser.add_argument("--claude-command", help="Claude CLI 命令，默认 claude")
    parser.add_argument("--codex-command", help="Codex CLI 命令，默认 codex")
    parser.add_argument("--opencode-command", help="OpenCode CLI 命令，默认 opencode")
    parser.add_argument("--claude-prompt-via", choices=["stdin", "arg"], help="Claude prompt 传递方式")
    parser.add_argument("--claude-extra-arg", action="append", help="额外 Claude CLI 参数，可重复")
    parser.add_argument("--verbose", action="store_true", help="输出详细运行日志到 stderr")
    parser.add_argument("--quiet", action="store_true", help="抑制进度日志，stdout 保持机器可读 JSON")
    parser.add_argument("--log-file", help="写入 JSONL 运行日志")
    parser.add_argument("--no-debug-bundle", action="store_true", help="关闭默认 debug bundle")
    parser.add_argument("--debug-bundle-dir", help="debug bundle 输出目录")
    parser.add_argument("--debug-include-code", action="store_true", help="debug bundle 保存代码上下文快照")
    parser.add_argument("--clues", help="搜索建议，逗号分隔，写入 Agent prompt")
    parser.add_argument("--paths", help="种子文件路径，逗号分隔，必须是 repo-path 内文件")
    parser.add_argument("--clues-file", help="按禅道条目 ID 提供代码线索的 JSON 文件")
    parser.add_argument("--output-root", default="docs", help="PRD/ISSUE 文档输出根目录")
    args = parser.parse_args()

    runtime_config = build_runtime_config(args)
    logger = RunLogger(verbose=runtime_config.verbose, quiet=runtime_config.quiet, log_file=runtime_config.log_file)

    client = ZentaoClient(
        config_path=args.config,
        profile=args.profile,
    )

    needs_login = bool(
        args.login
        or (args.server and (args.user or args.password or args.token))
    )

    if needs_login:
        try:
            client.login(
                server=args.server,
                user=args.user,
                password=args.password,
                token=args.token,
                use_env=args.use_env,
            )
            print("禅道登录成功", file=sys.stderr)
        except ZentaoError as e:
            print(f"[错误] 禅道登录失败: {e}", file=sys.stderr)
            return 1

    logger.info("fetch_items", "started", status="running", module=args.module, item_id=args.id or "")
    try:
        if args.id:
            items = [client.get_item(args.module, args.id)]
        else:
            items = client.list_items(
                module=args.module,
                project=args.project,
                product=args.product,
                execution=args.execution,
                status=args.status,
                limit=args.limit,
            )
        logger.info("fetch_items", "done", status="done", count=len(items))
    except ZentaoError as e:
        logger.error("fetch_items", "failed", status="failed", error=str(e))
        err_msg = str(e)
        if any(k in err_msg for k in ("Token 已失效", "token", "登录", "login", "认证", "auth")):
            print(f"[错误] 获取禅道数据失败: {err_msg}", file=sys.stderr)
            print("[提示] Token 已失效或未登录。请在终端执行命令登录后重试：", file=sys.stderr)
            print("  zentao login -s <服务地址> -u <用户名> -p <密码>", file=sys.stderr)
            print("  或在当前命令中添加 --login / --server / --user / --password 参数", file=sys.stderr)
        else:
            print(f"[错误] 获取禅道数据失败: {err_msg}", file=sys.stderr)
        return 2  # AUTH_ERROR

    base_result = {
        "module": args.module,
        "count": len(items),
        "items": [
            {
                "id": item.id,
                "type": item.type,
                "title": item.title,
                "description": item.description,
                "status": item.status,
                "priority": item.priority,
                "project": item.project,
                "product": item.product,
                "execution": item.execution,
                "assigned_to": item.assigned_to,
                "created_by": item.created_by,
                "created_date": item.created_date,
            }
            for item in items
        ],
    }

    if not args.analyze:
        if args.output:
            with open(args.output, "w", encoding="utf-8") as f:
                json.dump(base_result, f, ensure_ascii=False, indent=2)
            print(f"禅道数据已写入: {args.output}", file=sys.stderr)
        else:
            print(json.dumps(base_result, ensure_ascii=False, indent=2))
        return 0

    repo_path = args.repo_path
    output_root = args.output_root

    run_id = args.id or args.project or args.product or "list"
    debug_bundle = build_debug_bundle(
        enabled=runtime_config.debug_bundle_enabled,
        base_dir=runtime_config.debug_bundle_dir,
        module=args.module,
        run_id=run_id,
        include_code=runtime_config.debug_include_code,
    )
    if debug_bundle.enabled and debug_bundle.path:
        logger.add_log_file(os.path.join(debug_bundle.path, "run_log.jsonl"))

    debug_bundle.write_config({
        "args": vars(args),
        "runtime_config": runtime_config.__dict__,
        "environment": {
            "LLM_AGENT": os.environ.get("LLM_AGENT", ""),
            "CLAUDE_COMMAND": os.environ.get("CLAUDE_COMMAND", ""),
            "CODEX_COMMAND": os.environ.get("CODEX_COMMAND", ""),
            "OPENCODE_COMMAND": os.environ.get("OPENCODE_COMMAND", ""),
            "CLAUDE_PROMPT_VIA": os.environ.get("CLAUDE_PROMPT_VIA", ""),
            "ZENTAO_TOKEN": os.environ.get("ZENTAO_TOKEN", ""),
        },
    })
    debug_bundle.write_items(items)

    scan_summary = {
        "repo_path": repo_path,
        "max_seed_files": 3,
        "max_lines_per_seed": 50,
        "max_seed_tokens": 2000,
    }
    debug_bundle.write_scan_summary(scan_summary)
    debug_bundle.write_code_context({
        "repo_path": repo_path,
        "items": [{"id": item.id} for item in items],
    })

    agent_config = AgentConfig(**runtime_config.agent_config_dict())
    clues_by_item = load_clues_file(args.clues_file) if args.clues_file else {}

    def record_debug(kind, item, payload):
        if kind == "prompt":
            debug_bundle.write_prompt(item.id, payload)
        elif kind == "response":
            debug_bundle.write_response(item.id, payload or f"[无响应内容] item={item.id}")

    analysis_results = []
    documents = []
    summary_items = []
    evidence_location_items = []
    all_rejected_seed_paths = []
    writeback = prepare_writeback_status()

    for item in items:
        search_hints = build_search_hints(item.id, cli_clues=args.clues, clues_by_item=clues_by_item)
        seed_paths, rejected_seed_paths = build_seed_paths(item.id, repo_path=repo_path, cli_paths=args.paths, clues_by_item=clues_by_item)
        all_rejected_seed_paths.extend(rejected_seed_paths)

        logger.info("analyze", "started", status="running", item_id=item.id)
        result = analyze(
            item,
            repo_path=repo_path,
            agent=runtime_config.agent,
            agent_config=agent_config,
            debug_recorder=record_debug,
            seed_paths=seed_paths,
            search_hints=search_hints,
            rejected_seed_paths=rejected_seed_paths,
        )
        logger.info("analyze", "done", status="done", item_id=item.id, confidence=result.confidence)
        if result.error and result.error_kind == "timeout":
            current_timeout = runtime_config.agent_timeout
            suggested_timeout = current_timeout * 2
            print(f"[提示] LLM 分析超时（当前超时 {current_timeout} 秒）。可尝试延长超时时间重试：", file=sys.stderr)
            retry_cmd = f"python3 main.py --module {args.module} --id {item.id} --analyze --repo-path {repo_path} --agent {runtime_config.agent} --agent-timeout {suggested_timeout}"
            if args.quiet:
                retry_cmd += " --quiet"
            print(f"  {retry_cmd}", file=sys.stderr)
        seed_locations = getattr(result, "seed_locations", []) or []
        result_rejected = getattr(result, "rejected_seed_paths", []) or []
        for rejected in result_rejected:
            if rejected not in all_rejected_seed_paths:
                all_rejected_seed_paths.append(rejected)
        cited_locations = getattr(result, "cited_evidence_locations", []) or []
        validation_issues = getattr(result, "evidence_validation_issues", []) or []
        evidence_location_items.append({
            "item_id": item.id,
            "seed_locations": _plain_locations(seed_locations),
            "cited_evidence_locations": _plain_locations(cited_locations),
            "evidence_validation_issues": _plain_locations(validation_issues),
        })
        analysis_results.append({
            "item_id": result.item_id,
            "item_type": result.item_type,
            "conclusion": result.conclusion,
            "evidence": result.evidence,
            "gaps": result.gaps,
            "suspected_causes": result.suspected_causes,
            "affected_scope": result.affected_scope,
            "recommendations": result.recommendations,
            "verification": result.verification,
            "priority": result.priority,
            "confidence": result.confidence,
            "error": result.error,
            "error_kind": _plain_value(getattr(result, "error_kind", ""), ""),
        })

        logger.info("generate_docs", "started", status="running", item_id=item.id)
        doc = generate_document(item, result, output_root=output_root)
        logger.info("generate_docs", "done", status="done", item_id=item.id, document_path=doc.document_path)
        documents.append({
            "item_id": doc.item_id,
            "document_type": doc.document_type,
            "document_path": doc.document_path,
            "is_diagnostic": doc.is_diagnostic,
        })

        summary_items.append(
            build_summary_item(
                item,
                result,
                doc,
                writeback,
                seed_location_count=len(seed_locations),
                rejected_seed_path_count=len(result_rejected),
                invalid_evidence_count=len(validation_issues),
                debug_bundle=debug_bundle.path if debug_bundle.enabled and not debug_bundle.error else "",
            )
        )

    summary_path = write_summary_report(summary_items, output_root=output_root)
    logger.info("summary_report", "written", path=summary_path)

    debug_bundle.write_analysis_results(analysis_results)
    debug_bundle.write_documents(documents)
    debug_bundle.write_summary_path(summary_path)
    debug_bundle.write_code_evidence_locations(evidence_location_items)
    debug_bundle.write_rejected_seed_paths(all_rejected_seed_paths)

    combined_output = {
        **base_result,
        "analysis": analysis_results,
        "documents": documents,
        "summary_report": summary_path,
        "debug_bundle": debug_bundle.path if debug_bundle.enabled and not debug_bundle.error else "",
        "debug_bundle_error": debug_bundle.error,
        "log_file": runtime_config.log_file,
    }

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(combined_output, f, ensure_ascii=False, indent=2)
        print(f"分析结果已写入: {args.output}", file=sys.stderr)
    else:
        print(json.dumps(combined_output, ensure_ascii=False, indent=2))

    return 0


if __name__ == "__main__":
    sys.exit(main())
