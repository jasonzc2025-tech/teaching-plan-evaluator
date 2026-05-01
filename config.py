import os
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
INSTANCE_DIR = BASE_DIR / "instance"
INSTANCE_DIR.mkdir(exist_ok=True)


def _require_env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise RuntimeError(f"必须设置 {name} 环境变量")
    return value


class BaseConfig:
    APP_NAME = "住培临床教案质量智能评审系统"
    VERSION = "V3.2.2"
    SECRET_KEY = _require_env("SECRET_KEY")
    ADMIN_PASSWORD = _require_env("ADMIN_PASSWORD")
    DB_PATH = os.environ.get("DB_PATH", str(INSTANCE_DIR / "eval_records.db"))
    LLM_API_KEY = _require_env("LLM_API_KEY")
    LLM_API_BASE = os.environ.get("LLM_API_BASE", "https://api.deepseek.com/v1/chat/completions")
    LLM_MODEL_NAME = os.environ.get("LLM_MODEL_NAME", "deepseek-chat")
    LLM_TIMEOUT_SEC = int(os.environ.get("LLM_TIMEOUT_SEC", "300"))
    MAX_CONTENT_LENGTH = int(float(os.environ.get("MAX_CONTENT_LENGTH_MB", "20")) * 1024 * 1024)
    ALLOWED_EXTENSIONS = {"docx", "pdf", "txt"}
    MAX_TEXT_LENGTH = 30000
    MIN_TEXT_LENGTH = 50
    DEBUG = False
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    # 测试/排障：为 true 时 /evaluate 对非预期异常返回具体错误信息（勿在生产对公网开启）
    EVAL_EXPOSE_INTERNAL_ERRORS = os.environ.get("EVAL_EXPOSE_INTERNAL_ERRORS", "").lower() in (
        "1",
        "true",
        "yes",
    )
