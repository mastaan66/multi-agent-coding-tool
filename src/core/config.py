"""Central configuration using pydantic settings."""

from pathlib import Path

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # --- LLM Configuration ---
    openai_api_key: str = ""
    openai_model_name: str = "gpt-4o"
    openai_temperature: float = 0.2

    # --- Pipeline Settings ---
    max_review_iterations: int = 3
    max_test_fix_iterations: int = 3

    # --- Output ---
    output_dir: str = "output"

    # --- Dry Run ---
    dry_run: bool = False

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}

    @property
    def output_path(self) -> Path:
        """Return the resolved output directory path."""
        return Path(self.output_dir).resolve()


def save_api_key(api_key: str) -> None:
    """Save or update the OpenAI API key in the .env file."""
    env_path = Path(".env")
    lines: list[str] = []

    if env_path.exists():
        lines = env_path.read_text(encoding="utf-8").splitlines()

    # Update existing key or append
    found = False
    for i, line in enumerate(lines):
        if line.strip().startswith("OPENAI_API_KEY"):
            lines[i] = f"OPENAI_API_KEY={api_key}"
            found = True
            break

    if not found:
        lines.append(f"OPENAI_API_KEY={api_key}")

    env_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


# Global settings instance
settings = Settings()
