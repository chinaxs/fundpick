"""应用配置：统一从环境变量 / .env 读取，集中管理。"""

from functools import lru_cache
from typing import Literal
from urllib.parse import quote_plus, urlsplit

from pydantic import computed_field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """全局配置对象，实例化一次即可（见 get_settings）。"""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ---- 应用 ----
    APP_NAME: str = "fundpick-api"
    APP_ENV: Literal["development", "staging", "production", "test"] = "development"
    DEBUG: bool = False
    VERSION: str = "0.1.0"

    # ---- 服务 ----
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    API_V1_PREFIX: str = "/api/v1"
    CORS_ORIGINS: str = "http://localhost:5174,http://localhost:3000"
    # 留空时开发环境自动放行本机任意端口；生产环境留空即不启用正则匹配
    CORS_ORIGIN_REGEX: str = ""

    # ---- 安全 ----
    SECRET_KEY: str = "change-me"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 120
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # ---- 数据库 ----
    MYSQL_HOST: str = "127.0.0.1"
    MYSQL_PORT: int = 3306
    MYSQL_USER: str = "root"
    MYSQL_PASSWORD: str = ""
    MYSQL_DB: str = "test_study"
    DB_POOL_SIZE: int = 10
    DB_MAX_OVERFLOW: int = 20
    DB_ECHO: bool = False

    # ---- AI（LangChain / LangGraph / deepagents）----
    # 未配置 key 时接口返回 503，不影响服务启动
    AI_ENABLED: bool = False
    OPENAI_API_KEY: str = ""
    OPENAI_BASE_URL: str = "https://api.openai.com/v1"
    AI_MODEL: str = "gpt-4o-mini"
    AI_TEMPERATURE: float = 0.2
    AI_MAX_TOKENS: int | None = None
    AI_TIMEOUT: int = 60
    # 智能体最多推理轮数，防止死循环
    AI_MAX_ITERATIONS: int = 12

    # ---- 日志 ----
    LOG_LEVEL: str = "INFO"

    # ---- 采集调度 ----
    # 由进程内的轻量调度器按 sync_schedules 表触发；多实例部署时靠数据库互斥去重
    SYNC_SCHEDULER_ENABLED: bool = True
    SYNC_SCHEDULER_INTERVAL_SECONDS: int = 60
    AUTO_RECONCILE_ENABLED: bool = True
    AUTO_RECONCILE_INTERVAL_SECONDS: int = 60
    # 日志同时写文件，便于采集/审计留档（相对 services/api）
    LOG_FILE_ENABLED: bool = True

    @model_validator(mode="after")
    def validate_runtime_configuration(self) -> "Settings":
        if self.APP_ENV == "test" and "test" not in self.MYSQL_DB.casefold():
            raise ValueError(
                "APP_ENV=test requires a dedicated MySQL database name containing 'test'"
            )

        if not self.is_production:
            return self

        problems: list[str] = []
        secret = self.SECRET_KEY.strip()
        if len(secret.encode()) < 32 or secret.casefold().startswith("change-me"):
            problems.append("SECRET_KEY must be a unique value of at least 32 bytes")
        if self.DEBUG:
            problems.append("DEBUG must be false")
        if not self.MYSQL_PASSWORD.strip() or self.MYSQL_PASSWORD.casefold() in {
            "password",
            "change-me",
            "root123456",
            "study_app_123456",
        }:
            problems.append("MYSQL_PASSWORD must be set to a non-placeholder secret")
        if not self.MYSQL_USER.strip() or self.MYSQL_USER.casefold() == "root":
            problems.append("MYSQL_USER must be a dedicated non-root account")
        if "test" in self.MYSQL_DB.casefold():
            problems.append("MYSQL_DB must not refer to a test database")
        if self.CORS_ORIGIN_REGEX.strip():
            problems.append("CORS_ORIGIN_REGEX is disabled in production; list explicit origins")
        origins = self.cors_origin_list
        if not origins:
            problems.append("CORS_ORIGINS must list at least one HTTPS origin")
        elif any(
            urlsplit(origin).scheme != "https"
            or not urlsplit(origin).netloc
            or "*" in urlsplit(origin).netloc
            for origin in origins
        ):
            problems.append("CORS_ORIGINS must contain explicit HTTPS origins without wildcards")
        if self.AI_ENABLED and not self.OPENAI_API_KEY.strip():
            problems.append("AI_ENABLED requires OPENAI_API_KEY")
        if problems:
            raise ValueError("Invalid production configuration: " + "; ".join(problems))
        return self

    @computed_field  # type: ignore[prop-decorator]
    @property
    def database_url(self) -> str:
        """SQLAlchemy 异步连接串（asyncmy 驱动）。"""
        user = quote_plus(self.MYSQL_USER)
        password = quote_plus(self.MYSQL_PASSWORD)
        auth = f"{user}:{password}" if password else user
        return (
            f"mysql+asyncmy://{auth}@{self.MYSQL_HOST}:{self.MYSQL_PORT}"
            f"/{self.MYSQL_DB}?charset=utf8mb4"
        )

    @computed_field  # type: ignore[prop-decorator]
    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

    @property
    def cors_origin_regex(self) -> str | None:
        """允许的来源正则。

        开发环境默认放行本机任意端口：浏览器把 localhost / 127.0.0.1 / [::1]
        视为**三个不同的源**，端口也参与比较，逐个枚举必然漏配（这正是
        "localhost:3000 正常、127.0.0.1:3000 报 CORS" 的原因）。
        生产环境不启用该默认值，必须显式配置，避免意外放开。
        """
        if self.CORS_ORIGIN_REGEX:
            return self.CORS_ORIGIN_REGEX
        if self.is_production:
            return None
        return r"^http://(localhost|127\.0\.0\.1|\[::1\])(:\d+)?$"

    @property
    def is_production(self) -> bool:
        return self.APP_ENV == "production"

    @property
    def ai_ready(self) -> bool:
        """AI 能力是否可用：开关打开且配置了 key。"""
        return self.AI_ENABLED and bool(self.OPENAI_API_KEY)


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
