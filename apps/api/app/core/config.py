"""QuantOS configuration — supports SQLite local demo and PostgreSQL production."""
from __future__ import annotations

import os
import sys
from pathlib import Path


class Settings:
    """Simple settings loader — no pydantic-settings required, works offline."""

    def __init__(self):
        try:
            from dotenv import load_dotenv
            env_path = Path(__file__).resolve().parents[4] / ".env"
            if env_path.exists():
                load_dotenv(env_path)
        except ImportError:
            pass

        self.project_root: Path = Path(__file__).resolve().parents[4]
        self.api_root: Path = Path(__file__).resolve().parents[2]

        raw_db_url = os.getenv("DATABASE_URL", "")
        if raw_db_url.startswith("postgres"):
            self.database_url: str = raw_db_url
            self.db_backend: str = "postgresql"
        else:
            self.database_path: str = os.getenv("DATABASE_PATH", "prismflow.db")
            self.database_url = f"sqlite:///{self.api_root / self.database_path}"
            self.db_backend = "sqlite"

        self.redis_url: str = os.getenv("REDIS_URL", "")

        self.secret_key: str = os.getenv("PRISMFLOW_SECRET_KEY", "dev-insecure-default-key-change-in-prod")
        self.session_ttl_seconds: int = int(os.getenv("SESSION_TTL_SECONDS", "900"))
        self.refresh_ttl_seconds: int = int(os.getenv("REFRESH_TTL_SECONDS", "2592000"))
        self.access_token_ttl_seconds: int = int(os.getenv("ACCESS_TOKEN_TTL_SECONDS", str(self.session_ttl_seconds)))

        self.smtp_host: str = os.getenv("SMTP_HOST", "")
        self.smtp_port: int = int(os.getenv("SMTP_PORT", "587"))
        self.smtp_user: str = os.getenv("SMTP_USER", "")
        self.smtp_password: str = os.getenv("SMTP_PASSWORD", "")
        self.smtp_from: str = os.getenv("SMTP_FROM", self.smtp_user or "no-reply@quantos.local")
        self.smtp_tls: bool = os.getenv("SMTP_TLS", "true").lower() not in {"0", "false", "no"}
        env_name = os.getenv("ENV", os.getenv("NODE_ENV", "development")).lower()
        otp_default = "false" if env_name in {"production", "prod"} else "true"
        self.email_otp_dev_return: bool = os.getenv("EMAIL_OTP_DEV_RETURN", otp_default).lower() in {"1", "true", "yes"}

        self.llm_provider: str = os.getenv("LLM_PROVIDER", "gemini").lower()
        self.gemini_api_key: str = os.getenv("GEMINI_API_KEY", "")
        self.gemini_model: str = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
        self.llm_timeout_seconds: int = int(os.getenv("LLM_TIMEOUT_SECONDS", "20"))
        self.llm_enabled: bool = os.getenv("LLM_ENABLED", "true").lower() in {"1", "true", "yes"}

        self.outputs_root: str = os.getenv("OUTPUTS_ROOT", "outputs")

        self.safe_mode: bool = True
        self.real_money_enabled: bool = False
        self.broker_integration_enabled: bool = False

        self.api_host: str = os.getenv("API_HOST", "127.0.0.1")
        self.api_port: int = int(os.getenv("API_PORT", "8000"))

        cors_raw = os.getenv("CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000")
        self.cors_origins: list[str] = [o.strip() for o in cors_raw.split(",") if o.strip()]

        self.enforce_https: bool = os.getenv("ENFORCE_HTTPS", "false").lower() in {"1", "true", "yes"}
        self.log_file: str = os.getenv("LOG_FILE", str(self.api_root / "quantos_api.log"))

    @property
    def db_file(self) -> Path:
        return self.api_root / getattr(self, "database_path", "prismflow.db")

    @property
    def outputs_dir(self) -> Path:
        p = Path(self.outputs_root)
        return p if p.is_absolute() else self.project_root / p

    def _first_existing_binary(self, env_name: str, names: list[str]) -> Path:
        override = os.getenv(env_name, "")
        if override:
            return Path(override)
        search_dirs = [
            self.project_root / "build" / "Release",
            self.project_root / "build" / "Debug",
            self.project_root / "build" / "RelWithDebInfo",
            self.project_root / "build",
            self.project_root / "build_fresh" / "Release",
            self.project_root / "build_fresh",
        ]
        for d in search_dirs:
            for name in names:
                p = d / name
                if p.exists():
                    return p
        return search_dirs[0] / names[0]

    @property
    def engine_binary(self) -> Path:
        return self._first_existing_binary(
            "ENGINE_BINARY_PATH",
            ["prism_backtest.exe", "prism_backtest"] if sys.platform.startswith("win") else ["prism_backtest", "prism_backtest.exe"],
        )

    @property
    def live_paper_binary(self) -> Path:
        return self._first_existing_binary(
            "LIVE_PAPER_BINARY_PATH",
            ["prism_live_paper_trading.exe", "prism_live_paper_trading"] if sys.platform.startswith("win") else ["prism_live_paper_trading", "prism_live_paper_trading.exe"],
        )

    @property
    def engine_diagnostics(self) -> dict:
        backtest = self.engine_binary
        live = self.live_paper_binary
        return {
            "project_root": str(self.project_root),
            "backtest_binary": str(backtest),
            "backtest_exists": backtest.exists(),
            "live_paper_binary": str(live),
            "live_paper_exists": live.exists(),
            "build_command": "cmake -S . -B build && cmake --build build --config Release",
            "windows_note": "Run from C:\\Users\\Admin\\QuantOS. If Visual Studio generator is used, exe files appear under build\\Release.",
        }

    def is_postgres(self) -> bool:
        return self.db_backend == "postgresql"

    def has_redis(self) -> bool:
        return bool(self.redis_url)

    def has_gemini(self) -> bool:
        return bool(self.gemini_api_key and self.llm_enabled)

    def __repr__(self) -> str:
        return (
            f"Settings(db_backend={self.db_backend}, "
            f"has_redis={self.has_redis()}, "
            f"llm_provider={self.llm_provider}, "
            f"has_gemini={self.has_gemini()}, "
            f"safe_mode={self.safe_mode})"
        )


settings = Settings()
