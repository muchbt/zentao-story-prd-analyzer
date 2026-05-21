import dataclasses
import json
import os
import re
import subprocess
from typing import Any, Dict, List, Optional


class ZentaoError(Exception):
    """禅道 CLI 基础异常"""
    pass


class ZentaoAuthError(ZentaoError):
    """认证失败或未登录"""
    pass


class ZentaoNotFoundError(ZentaoError):
    """对象不存在"""
    pass


class ZentaoTimeoutError(ZentaoError):
    """请求超时"""
    pass


class ZentaoFormatError(ZentaoError):
    """返回格式异常"""
    pass


class ZentaoCommandError(ZentaoError):
    """命令执行失败"""
    pass


@dataclasses.dataclass
class ZentaoItem:
    """统一的禅道条目数据结构"""

    id: str = ""
    type: str = ""
    title: str = ""
    description: str = ""
    status: str = ""
    priority: str = ""
    project: str = ""
    product: str = ""
    execution: str = ""
    assigned_to: str = ""
    created_by: str = ""
    created_date: str = ""
    keywords: List[str] = dataclasses.field(default_factory=list)
    raw_data: Dict[str, Any] = dataclasses.field(default_factory=dict, repr=False)

    @classmethod
    def from_dict(cls, data: Dict[str, Any], item_type: str = "") -> "ZentaoItem":
        if not isinstance(data, dict):
            raise ZentaoFormatError(
                f"条目数据必须为字典，收到: {type(data).__name__}"
            )

        def _get(*keys, default=""):
            for k in keys:
                if k in data:
                    val = data[k]
                    if val is not None:
                        return str(val)
            return default

        title = _get("title", "name", default="")
        desc = _get("desc", "description", "spec", "steps", "content", default="")
        keywords: List[str] = []
        if title or desc:
            text = f"{title} {desc}"
            words = re.findall(r"[a-zA-Z_]+|\w+", text)
            keywords = [w for w in words if len(w) > 1][:20]

        return cls(
            id=_get("id", "ID", default=""),
            type=item_type or _get("type", "module", default=""),
            title=title,
            description=desc,
            status=_get("status", "stage", default=""),
            priority=_get("pri", "priority", "severity", default=""),
            project=_get("project", "projectName", default=""),
            product=_get("product", "productName", default=""),
            execution=_get("execution", "executionName", default=""),
            assigned_to=_get("assignedTo", "assignedUser", default=""),
            created_by=_get("openedBy", "createdBy", "author", default=""),
            created_date=_get("openedDate", "createdDate", default=""),
            keywords=keywords,
            raw_data=data,
        )


class ZentaoClient:
    """禅道 CLI 封装客户端"""

    MODULE_MAP = {
        "story": "story",
        "requirement": "requirement",
        "bug": "bug",
        "task": "task",
        "ticket": "ticket",
        "feedback": "feedback",
    }

    def __init__(
        self,
        config_path: Optional[str] = None,
        profile: Optional[str] = None,
        timeout: Optional[int] = None,
    ):
        self.config_path = config_path or os.environ.get("ZENTAO_CONFIG_FILE")
        self.profile = profile or os.environ.get("ZENTAO_PROFILE")
        self.timeout = timeout or int(os.environ.get("ZENTAO_TIMEOUT", "30000"))

    def _build_base_args(self) -> List[str]:
        args = ["zentao"]
        if self.config_path:
            args.extend(["--config", self.config_path])
        if self.timeout:
            args.extend(["--timeout", str(self.timeout)])
        args.extend(["--format", "json", "--machine-readable"])
        return args

    @staticmethod
    def _sanitize_cmd(cmd_list: List[str]) -> str:
        """将命令列表转为字符串，并对敏感字段脱敏"""
        cmd_str = " ".join(cmd_list)
        cmd_str = re.sub(r"(-p\s+|--password\s+)\S+", r"\1***", cmd_str)
        cmd_str = re.sub(r"(-t\s+|--token\s+)\S+", r"\1***", cmd_str)
        return cmd_str

    def _run(self, args: List[str]) -> Any:
        cmd = self._build_base_args() + args
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="ignore",
                timeout=(self.timeout / 1000 + 10) if self.timeout else 60,
            )
        except subprocess.TimeoutExpired as exc:
            raise ZentaoTimeoutError(
                f"执行禅道命令超时: {self._sanitize_cmd(cmd)}"
            ) from exc
        except FileNotFoundError as exc:
            raise ZentaoCommandError(
                "未找到 zentao 命令，请确认禅道 CLI 已安装并在 PATH 中"
            ) from exc

        stderr = result.stderr.strip() if result.stderr else ""
        stdout = result.stdout.strip() if result.stdout else ""

        if result.returncode != 0:
            safe_stderr = re.sub(
                r"(password|token)\s*[:=]\s*\S+",
                r"\1: ***",
                stderr,
                flags=re.IGNORECASE,
            )
            raise ZentaoCommandError(
                f"禅道命令执行失败 (rc={result.returncode}): {self._sanitize_cmd(cmd)}\n"
                f"stderr: {safe_stderr}\nstdout: {stdout[:500]}"
            )

        if not stdout:
            return {}

        try:
            data = json.loads(stdout)
        except json.JSONDecodeError as exc:
            # login/profile 命令有时返回纯文本成功信息，而非 JSON
            if "login" in cmd or "profile" in cmd:
                return {"success": True, "message": stdout}
            raise ZentaoFormatError(
                f"无法解析禅道返回的 JSON: {self._sanitize_cmd(cmd)}\n"
                f"原始输出前 500 字符: {stdout[:500]}"
            ) from exc

        if isinstance(data, dict):
            err_msg = data.get("error") or data.get("message")
            if err_msg and not data.get("id"):
                err_str = str(err_msg)
                if any(k in err_str for k in ("登录", "login", "认证", "auth", "未登录", "unauthorized")):
                    raise ZentaoAuthError(f"禅道认证失败: {err_str}")
                if any(k in err_str for k in ("不存在", "not found", "找不到")):
                    raise ZentaoNotFoundError(f"禅道对象不存在: {err_str}")
                raise ZentaoCommandError(f"禅道返回错误: {err_str}")

        return data

    def login(
        self,
        server: Optional[str] = None,
        user: Optional[str] = None,
        password: Optional[str] = None,
        token: Optional[str] = None,
        use_env: bool = False,
    ) -> Dict[str, Any]:
        """登录禅道服务。优先从参数获取；缺失字段再从环境变量读取。"""
        if use_env or not (server and (user or token)):
            server = server or os.environ.get("ZENTAO_SERVER")
            user = user or os.environ.get("ZENTAO_USER")
            token = token or os.environ.get("ZENTAO_TOKEN")
        # 无论 use_env 还是部分参数缺失，password 都允许从环境变量补齐
        password = password or os.environ.get("ZENTAO_PASSWORD")

        if not server:
            raise ZentaoAuthError("未提供禅道服务地址 (server 或环境变量 ZENTAO_SERVER)")

        args = ["login", "-s", server]
        if token:
            args.extend(["-t", token])
        elif user and password:
            args.extend(["-u", user, "-p", password])
        elif user:
            args.extend(["-u", user])
        else:
            raise ZentaoAuthError("登录禅道需要提供用户名+密码 或 token")

        return self._run(args)

    def get_profile(self) -> Dict[str, Any]:
        args = ["profile"]
        if self.profile:
            args.append(self.profile)
        return self._run(args)

    def _switch_profile(self) -> None:
        if not self.profile:
            return
        result = self._run(["profile", self.profile])
        if not result.get("success"):
            raise ZentaoAuthError(f"切换 profile 失败: {self.profile}")

    def get_item(
        self,
        module: str,
        item_id: str,
        fields: Optional[List[str]] = None,
    ) -> ZentaoItem:
        self._switch_profile()
        mapped_module = self.MODULE_MAP.get(module, module)
        args = ["get", mapped_module, item_id]
        if fields:
            args.extend(["--pick", ",".join(fields)])
        data = self._run(args)
        if not isinstance(data, dict):
            raise ZentaoFormatError(f"获取 {module} {item_id} 时返回非字典数据")
        return ZentaoItem.from_dict(data, item_type=module)

    def list_items(
        self,
        module: str,
        project: Optional[str] = None,
        product: Optional[str] = None,
        execution: Optional[str] = None,
        status: Optional[str] = None,
        limit: Optional[int] = None,
        fields: Optional[List[str]] = None,
    ) -> List[ZentaoItem]:
        self._switch_profile()
        mapped_module = self.MODULE_MAP.get(module, module)
        args = ["list", mapped_module]
        if project:
            args.extend(["--project", str(project)])
        if product:
            args.extend(["--product", str(product)])
        if execution:
            args.extend(["--execution", str(execution)])
        if status:
            args.extend(["--filter", f"status={status}"])
        if limit:
            args.extend(["--limit", str(limit)])
        if fields:
            args.extend(["--pick", ",".join(fields)])

        data = self._run(args)
        raw_list = data
        if isinstance(data, dict):
            for key in ("data", "list", "items", "result"):
                if key in data and isinstance(data[key], list):
                    raw_list = data[key]
                    break
        if not isinstance(raw_list, list):
            raise ZentaoFormatError(f"列表接口返回非列表数据: {type(raw_list).__name__}")

        items: List[ZentaoItem] = []
        for entry in raw_list:
            try:
                items.append(ZentaoItem.from_dict(entry, item_type=module))
            except ZentaoFormatError:
                continue
        return items
