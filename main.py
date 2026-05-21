import argparse
import json
import os
import subprocess
import sys

from zentao_client import ZentaoClient, ZentaoError
from analyzer import analyze
from document_generator import generate_document
from summary_report import build_summary_item, write_summary_report
from writeback import prepare_writeback_status
from agent_client import AgentConfig
from app_config import build_runtime_config
from debug_bundle import build_debug_bundle
from run_logger import RunLogger, redact_sensitive


def get_modified_files(repo_path, last_commit=None):
    if last_commit:
        cmd = ["git", "-C", repo_path, "diff", "--name-only", f"{last_commit}...HEAD"]
    else:
        cmd = ["git", "-C", repo_path, "ls-files"]
    result = subprocess.run(cmd, shell=False, capture_output=True, text=True)
    return result.stdout.strip().split("\n")


def main():
    parser = argparse.ArgumentParser(description="zentao-story-prd-analyzer")
    parser.add_argument("--module", default="story", help="禅道模块 (story/requirement/bug/task/ticket/feedback)")
    parser.add_argument("--id", help="禅道条目 ID（指定则获取单条详情）")
    parser.add_argument("--project", default=os.environ.get("PROJECT_ID","1"), help="项目 ID")
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
    parser.add_argument("--repo-path", default=os.environ.get("REPO_PATH","."), help="代码仓库路径")
    parser.add_argument("--agent", default=os.environ.get("LLM_AGENT","codex"), help="LLM Agent")
    parser.add_argument("--model", help="LLM 模型名，OpenAI/Codex 使用")
    parser.add_argument("--agent-timeout", type=int, help="Agent 调用超时时间，单位秒")
    parser.add_argument("--claude-command", help="Claude CLI 命令，默认 claude")
    parser.add_argument("--claude-prompt-via", choices=["stdin", "arg"], help="Claude prompt 传递方式")
    parser.add_argument("--claude-extra-arg", action="append", help="额外 Claude CLI 参数，可重复")
    parser.add_argument("--verbose", action="store_true", help="输出详细运行日志到 stderr")
    parser.add_argument("--quiet", action="store_true", help="抑制进度日志，stdout 保持机器可读 JSON")
    parser.add_argument("--log-file", help="写入 JSONL 运行日志")
    parser.add_argument("--no-debug-bundle", action="store_true", help="关闭默认 debug bundle")
    parser.add_argument("--debug-bundle-dir", help="debug bundle 输出目录")
    parser.add_argument("--debug-include-code", action="store_true", help="debug bundle 保存代码上下文快照")
    parser.add_argument("--incremental", action="store_true", help="增量分析")
    parser.add_argument("--last-commit", default=os.environ.get("LAST_COMMIT"), help="增量分析起始 commit")
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
            print(f"[错误] 禅道登录失败: {e}")
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
            print("[提示] 这可能是由于 token 失效或未登录。请尝试添加 --login 参数，或提供 --server + --user + --password 重新登录。", file=sys.stderr)
        else:
            print(f"[错误] 获取禅道数据失败: {err_msg}", file=sys.stderr)
        return 1

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
                "keywords": item.keywords,
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
    incremental = args.incremental
    last_commit = args.last_commit if incremental else None
    output_root = args.output_root

    run_id = args.id or args.project or args.product or "list"
    debug_bundle = build_debug_bundle(
        enabled=runtime_config.debug_bundle_enabled,
        base_dir=runtime_config.debug_bundle_dir,
        module=args.module,
        run_id=run_id,
        include_code=runtime_config.debug_include_code,
    )
    debug_bundle.write_config({
        "args": vars(args),
        "runtime_config": runtime_config.__dict__,
        "environment": {
            "LLM_AGENT": os.environ.get("LLM_AGENT", ""),
            "OPENAI_MODEL": os.environ.get("OPENAI_MODEL", ""),
            "OPENAI_API_KEY": os.environ.get("OPENAI_API_KEY", ""),
            "CLAUDE_COMMAND": os.environ.get("CLAUDE_COMMAND", ""),
            "CLAUDE_PROMPT_VIA": os.environ.get("CLAUDE_PROMPT_VIA", ""),
            "ZENTAO_TOKEN": os.environ.get("ZENTAO_TOKEN", ""),
        },
    })
    debug_bundle.write_items(items)

    modified_files = get_modified_files(repo_path, last_commit) if incremental else None

    scan_summary = {
        "repo_path": repo_path,
        "incremental": incremental,
        "last_commit": last_commit or "",
        "modified_files": modified_files or [],
        "modified_file_count": len(modified_files or []),
        "max_files": 50,
        "max_lines_per_file": 200,
        "max_total_tokens": 8000,
    }
    debug_bundle.write_scan_summary(scan_summary)
    debug_bundle.write_code_context({
        "repo_path": repo_path,
        "items": [{"id": item.id, "keywords": item.keywords} for item in items],
        "modified_files": modified_files or [],
    })

    agent_config = AgentConfig(**runtime_config.agent_config_dict())

    def record_debug(kind, item, payload):
        if kind == "prompt":
            debug_bundle.write_prompt(item.id, payload)
        elif kind == "response":
            debug_bundle.write_response(item.id, payload)

    analysis_results = []
    documents = []
    summary_items = []
    writeback = prepare_writeback_status()

    for item in items:
        logger.info("analyze", "started", status="running", item_id=item.id)
        result = analyze(
            item,
            repo_path=repo_path,
            agent=runtime_config.agent,
            modified_files=modified_files,
            agent_config=agent_config,
            debug_recorder=record_debug,
        )
        logger.info("analyze", "done", status="done", item_id=item.id, confidence=result.confidence)
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

        summary_items.append(build_summary_item(item, result, doc, writeback))

    summary_path = write_summary_report(summary_items, output_root=output_root)
    logger.info("summary_report", "written", path=summary_path)

    debug_bundle.write_analysis_results(analysis_results)
    debug_bundle.write_documents(documents)
    debug_bundle.write_summary_path(summary_path)

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
