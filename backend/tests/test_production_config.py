import os
from pathlib import Path
import subprocess
import sys

import pytest


BACKEND_DIR = Path(__file__).resolve().parents[1]


def load_production_config(
    overrides: dict[str, str] | None = None,
    code: str = "import app.config",
) -> subprocess.CompletedProcess[str]:
    environment = {
        key: value
        for key, value in os.environ.items()
        if not key.startswith("CONTRACTIQ_") and key != "SECRET_KEY"
    }
    environment.update(
        {
            "CONTRACTIQ_ENVIRONMENT": "production",
            "CONTRACTIQ_SECRET_KEY": "s" * 48,
            "CONTRACTIQ_ALLOWED_ORIGINS": "https://contractiq.example.com",
            "CONTRACTIQ_FRONTEND_BASE_URL": "https://contractiq.example.com",
        }
    )
    environment.update(overrides or {})
    return subprocess.run(
        [sys.executable, "-c", code],
        cwd=BACKEND_DIR,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )


def test_production_defaults_disable_public_registration():
    result = load_production_config(
        code=(
            "from app.config import AUTH_ALLOW_REGISTRATION, AUTH_REQUIRE_EMAIL_VERIFICATION; "
            "assert not AUTH_ALLOW_REGISTRATION and AUTH_REQUIRE_EMAIL_VERIFICATION"
        )
    )

    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize(
    ("overrides", "error"),
    [
        ({"CONTRACTIQ_SECRET_KEY": "short"}, "at least 32 characters"),
        ({"CONTRACTIQ_AUTH_COOKIE_SECURE": "false"}, "must be true in production"),
        (
            {"CONTRACTIQ_FRONTEND_BASE_URL": "http://contractiq.example.com"},
            "must use HTTPS",
        ),
        (
            {"CONTRACTIQ_ALLOWED_ORIGINS": "http://contractiq.example.com"},
            "CORS origins must use HTTPS",
        ),
    ],
)
def test_production_rejects_insecure_settings(overrides: dict[str, str], error: str):
    result = load_production_config(overrides)

    assert result.returncode != 0
    assert error in result.stderr
