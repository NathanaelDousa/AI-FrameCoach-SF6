"""The user's model choice and API keys, saved in their profile (never in the repo).

Windows: %APPDATA%\\FrameCoach\\config.json
macOS:   ~/Library/Application Support/FrameCoach/config.json
Linux:   ~/.config/framecoach/config.json
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from .llm import PROVIDERS


def default_config_dir() -> Path:
    if env := os.environ.get("FRAMECOACH_CONFIG_DIR"):
        return Path(env).expanduser()
    if sys.platform == "win32":
        return Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming")) / "FrameCoach"
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "FrameCoach"
    return Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "framecoach"


def mask_key(key: str) -> str:
    return f"...{key[-4:]}" if len(key) > 8 else "set"


@dataclass
class UserSettings:
    provider: str = ""  # empty until the user has made a choice on first launch
    models: dict[str, str] = field(default_factory=dict)
    api_keys: dict[str, str] = field(default_factory=dict)

    @property
    def configured(self) -> bool:
        return self.provider in PROVIDERS

    def model_for(self, provider: str) -> str:
        return self.models.get(provider) or PROVIDERS[provider].default_model

    def key_for(self, provider: str) -> str:
        """A saved key wins; otherwise fall back to the usual environment variable."""
        info = PROVIDERS[provider]
        return self.api_keys.get(provider) or (os.environ.get(info.key_env, "") if info.key_env else "")

    def public(self) -> dict:
        """Everything the browser may see. API keys are only ever shown masked."""
        return {
            "configured": self.configured,
            "provider": self.provider,
            "providers": [
                {
                    "id": info.id,
                    "label": info.label,
                    "needs_key": info.needs_key,
                    "has_key": bool(self.key_for(info.id)),
                    "key_hint": mask_key(key) if (key := self.key_for(info.id)) else "",
                    "key_url": info.key_url,
                    "model": self.model_for(info.id),
                    "suggested_models": list(info.suggested_models),
                }
                for info in PROVIDERS.values()
            ],
        }


class SettingsStore:
    def __init__(self, config_dir: Path | None = None):
        self.path = (config_dir or default_config_dir()) / "config.json"

    def load(self) -> UserSettings:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError):
            return UserSettings()
        return UserSettings(
            provider=data.get("provider", "") if data.get("provider") in PROVIDERS else "",
            models={k: v for k, v in data.get("models", {}).items() if k in PROVIDERS and isinstance(v, str)},
            api_keys={k: v for k, v in data.get("api_keys", {}).items() if k in PROVIDERS and isinstance(v, str)},
        )

    def save(self, settings: UserSettings) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        data = {"provider": settings.provider, "models": settings.models, "api_keys": settings.api_keys}
        # Write to a temp file first so a crash never leaves a half-written config.
        fd, tmp = tempfile.mkstemp(dir=self.path.parent, prefix=".config-", suffix=".json")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            if os.name != "nt":
                os.chmod(tmp, 0o600)  # API keys: readable by this user only
            os.replace(tmp, self.path)
        except BaseException:
            Path(tmp).unlink(missing_ok=True)
            raise
