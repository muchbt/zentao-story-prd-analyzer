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


# ---------------------- 增量分析: 获取修改文件 ----------------------
def get_modified_files(repo_path, last_commit=None):
    if last_commit:
        cmd = ["git", "-C", repo_path, "diff", "--name-only", f"{last_commit}...HEAD"]
    else:
        cmd = ["git", "-C", repo_path, "ls-files"]
    result = subprocess.run(cmd, shell=False, capture_output=True, text=True)
    return result.stdout.strip().split("\n")


# ---------------------- 主流程 ----------------------
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
    parser.add_argument("--incremental", action="store_true", help="增量分析")
    parser.add_argument("--last-commit", default=os.environ.get("LAST_COMMIT"), help="增量分析起始 commit")
    parser.add_argument("--output-root", default="docs", help="PRD/ISSUE 文档输出根目录")
    args = parser.parse_args()

    client = ZentaoClient(
        config_path=args.config,
        profile=args.profile,
    )

    # 自动判断是否需要登录
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

    # 获取禅道数据
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
    except ZentaoError as e:
        err_msg = str(e)
        if any(k in err_msg for k in ("Token 已失效", "token", "登录", "login", "认证", "auth")):
            print(f"[错误] 获取禅道数据失败: {err_msg}")
            print("[提示] 这可能是由于 token 失效或未登录。请尝试添加 --login 参数，或提供 --server + --user + --password 重新登录。")
        else:
            print(f"[错误] 获取禅道数据失败: {err_msg}")
        return 1

    # 阶段一：基础数据输出
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

    # 阶段二：代码分析 + 阶段三：文档生成
    repo_path = args.repo_path
    incremental = args.incremental
    last_commit = args.last_commit if incremental else None
    output_root = args.output_root

    modified_files = get_modified_files(repo_path, last_commit) if incremental else None
    analysis_results = []
    documents = []
    summary_items = []
    writeback = prepare_writeback_status()

    for item in items:
        # 分析
        result = analyze(
            item,
            repo_path=repo_path,
            agent=args.agent,
            modified_files=modified_files,
        )
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

        # 生成文档
        doc = generate_document(item, result, output_root=output_root)
        documents.append({
            "item_id": doc.item_id,
            "document_type": doc.document_type,
            "document_path": doc.document_path,
            "is_diagnostic": doc.is_diagnostic,
        })

        # 汇总项
        summary_items.append(build_summary_item(item, result, doc, writeback))

    # 写入汇总报告
    summary_path = write_summary_report(summary_items, output_root=output_root)

    combined_output = {
        **base_result,
        "analysis": analysis_results,
        "documents": documents,
        "summary_report": summary_path,
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
