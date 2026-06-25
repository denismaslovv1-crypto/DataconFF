from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from rag_core.config import load_dotenv, load_rag_models_config, require_env


class RagConfigTest(unittest.TestCase):
    def test_load_config_and_dotenv(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "config").mkdir()
            (root / ".env").write_text("EMBEDDINGS_API_KEY=test-key\n", encoding="utf-8")
            (root / "config" / "rag_models.json").write_text(
                """
                {
                  "llm": {
                    "provider": "deepseek",
                    "model": "deepseek-v4-flash",
                    "base_url": "https://api.deepseek.com",
                    "api_key_env": "DEEPSEEK_API_KEY"
                  },
                  "embeddings": {
                    "provider": "openai_compatible",
                    "model": "text-embedding-3-small",
                    "base_url": "https://api.openai.com/v1",
                    "api_key_env": "EMBEDDINGS_API_KEY",
                    "batch_size": 8
                  },
                  "vector_store": {
                    "provider": "chroma",
                    "persist_dir": "rag_index/vector_chroma",
                    "collection_name": "methodology_notes"
                  }
                }
                """,
                encoding="utf-8",
            )

            previous = os.environ.pop("EMBEDDINGS_API_KEY", None)
            try:
                config = load_rag_models_config(root)
                self.assertEqual(config.embeddings.model, "text-embedding-3-small")
                self.assertEqual(require_env("EMBEDDINGS_API_KEY"), "test-key")
            finally:
                if previous is not None:
                    os.environ["EMBEDDINGS_API_KEY"] = previous
                else:
                    os.environ.pop("EMBEDDINGS_API_KEY", None)

    def test_require_env_rejects_placeholder(self) -> None:
        previous = os.environ.get("PLACEHOLDER_KEY")
        os.environ["PLACEHOLDER_KEY"] = "replace_me"
        try:
            with self.assertRaises(RuntimeError):
                require_env("PLACEHOLDER_KEY")
        finally:
            if previous is None:
                os.environ.pop("PLACEHOLDER_KEY", None)
            else:
                os.environ["PLACEHOLDER_KEY"] = previous


if __name__ == "__main__":
    unittest.main()

