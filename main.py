import argparse
import json
import os
import re
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor

from zentao_client import ZentaoClient, ZentaoError


# ---------------------- LLM 调用接口 ----------------------
def call_llm(prompt, agent="codex"):
    """统一调用不同 AGENT 接口"""
    if agent.lower() == "codex":
        import openai
        openai.api_key = os.environ.get("OPENAI_API_KEY")
        response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[{"role": "user", "content": prompt}],
            temperature=0
        )
        text = response['choices'][0]['message']['content']
    elif agent.lower() == "claude":
        text = claude_api_call(prompt)  # placeholder
    elif agent.lower() == "opencode":
        text = opencode_api_call(prompt)  # placeholder
    else:
        text = '{"conclusion": "未知", "reason": "未识别 agent", "suggestion": "", "priority": "中", "prd_md": ""}'
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {"conclusion":"未知","reason":text,"suggestion":"","priority":"中","prd_md":""}

# ---------------------- 获取禅道 story/bug ----------------------
def get_zentao_items(client, project_id, item_type="story", status="open"):
    return client.list_items(
        module=item_type,
        project=project_id,
        status=status,
    )

# ---------------------- 增量分析: 获取修改文件 ----------------------
def get_modified_files(repo_path, last_commit=None):
    if last_commit:
        cmd = ["git", "-C", repo_path, "diff", "--name-only", f"{last_commit}...HEAD"]
    else:
        cmd = ["git", "-C", repo_path, "ls-files"]
    result = subprocess.run(cmd, shell=False, capture_output=True, text=True)
    return result.stdout.strip().split("\n")

# ---------------------- 主动搜索代码库 ----------------------
def collect_code(repo_path, keywords=None, max_files=50, max_lines_per_file=200):
    """
    主动搜索代码库，覆盖 C/C++/Python/Shell/Batch/Makefile/CMake 文件
    可根据关键词优先收集相关文件
    """
    code_snippets = []
    count = 0
    exts = (".c",".cpp",".h",".hpp",".sh",".bat",".py")
    build_files = ("Makefile","CMakeLists.txt")

    for root, _, files in os.walk(repo_path):
        for f in files:
            try:
                path = os.path.join(root,f)
                if f.endswith(exts) or f in build_files:
                    if keywords and not any(kw.lower() in f.lower() for kw in keywords):
                        continue  # 跳过不相关文件
                    with open(path, "r", encoding="utf-8", errors="ignore") as file:
                        lines = file.readlines()[:max_lines_per_file]
                        snippet = f"文件: {path}\n" + "".join(lines)
                        code_snippets.append(snippet)
                        count += 1
                        if count >= max_files:
                            return code_snippets
            except:
                continue
    return code_snippets

# ---------------------- 生成代码摘要 ----------------------
def generate_code_summary(snippets):
    summaries = []
    for snippet in snippets:
        lines = snippet.split("\n")
        summary_lines = []
        for line in lines:
            if re.match(r"\s*(def|class|void|int|float|struct|#|//)", line):
                summary_lines.append(line.strip())
        summaries.append("\n".join(summary_lines))
    return summaries

# ---------------------- 生成高级 LLM Prompt ----------------------
def generate_prompt(item, code_snippets, summaries):
    code_text = "\n---\n".join(code_snippets)
    summary_text = "\n---\n".join(summaries)
    prompt = f"""
你是高级代码分析 AGENT，需要为禅道 story 生成专业 PRD 文档。

任务：
1. 对比 story 描述与代码实现情况，判断是否完成
2. 输出 JSON 格式：
   - conclusion: 完成 / 未完成 / 部分完成
   - reason: 详细分析理由
   - suggestion: 智能修改建议
   - priority: 优先级评分（高/中/低 + 1-10）
   - prd_md: 可直接发布的 Markdown 文档

Markdown 文档要求：
1. 包含 Story ID, 标题, 描述
2. 自动生成"实现差异分析表"，列出：
   - 功能描述
   - 实现状态
   - 修改建议
   - 相关文件/函数
3. 对"未完成"或"部分完成"的功能使用 **粗体或 ⚠️** 高亮
4. 给出优先级评分
5. Markdown 样式清晰，包含目录、章节和代码片段引用

输入：
Story 信息:
ID: {item['id']}
标题: {item['title']}
描述: {item.get('desc','')}

代码摘要（函数/类/注释）:
{summary_text}

代码片段:
{code_text}

要求：
- 严格返回 JSON
- prd_md 为可直接发布的 Markdown 内容
"""
    return prompt

# ---------------------- 创建 PRD 文件 ----------------------
def create_prd_file(item, llm_result, output_dir="prd_docs"):
    os.makedirs(output_dir, exist_ok=True)
    safe_title = "".join(c if c.isalnum() else "_" for c in item['title'])
    path = os.path.join(output_dir,f"{item['id']}_{safe_title}.md")
    with open(path,"w",encoding="utf-8") as f:
        f.write(llm_result.get("prd_md",""))
    return path

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

    # 阶段一输出
    result = {
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

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        print(f"禅道数据已写入: {args.output}")
    else:
        print(json.dumps(result, ensure_ascii=False, indent=2))

    if not args.analyze:
        return 0

    # 以下保持原有分析流程（阶段二/四）
    repo_path = args.repo_path
    incremental = args.incremental
    last_commit = args.last_commit if incremental else None

    modified_files = get_modified_files(repo_path, last_commit)
    for item in items:
        keywords = item.keywords
        code_snippets = collect_code(repo_path, keywords=keywords)
        summaries = generate_code_summary(code_snippets)
        prompt = generate_prompt({
            "id": item.id,
            "title": item.title,
            "desc": item.description,
        }, code_snippets, summaries)
        llm_result = call_llm(prompt, args.agent)
        prd_file = create_prd_file({
            "id": item.id,
            "title": item.title,
        }, llm_result)
        print(f"PRD 文档已生成: {prd_file}")

    report_path = os.path.join("prd_docs", "summary_report.json")
    summary = []
    for item in items:
        safe_title = "".join(c if c.isalnum() else "_" for c in item.title)
        summary.append({
            "id": item.id,
            "title": item.title,
            "prd_file": os.path.join("prd_docs", f"{item.id}_{safe_title}.md")
        })
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    print(f"总结报告已生成: {report_path}")
    return 0

if __name__ == "__main__":
    sys.exit(main())
