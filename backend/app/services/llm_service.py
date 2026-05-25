import json
from collections.abc import Iterator
from pathlib import Path

import httpx

from app.config import get_settings

settings = get_settings()

_llama_instance = None


class LLMService:
    def __init__(self) -> None:
        self._mock = settings.llm_mock
        self._backend = settings.llm_backend.lower().strip()
        self._model_path = Path(settings.llm_model_path)

    @property
    def use_mock(self) -> bool:
        if self._mock:
            return True
        if self._backend == "ollama":
            return False
        return not self._model_path.is_file()

    def _get_llama(self):
        global _llama_instance
        if _llama_instance is None:
            try:
                from llama_cpp import Llama
            except ImportError as exc:
                raise RuntimeError(
                    "llama-cpp-python is not installed. Run: pip install -r requirements-llm.txt "
                    "or set LLM_BACKEND=ollama"
                ) from exc

            try:
                _llama_instance = Llama(
                    model_path=str(self._model_path.resolve()),
                    n_ctx=settings.llm_n_ctx,
                    verbose=False,
                )
            except OSError as exc:
                raise RuntimeError(
                    "Failed to load GGUF model (CPU/instruction mismatch). Options: "
                    "set LLM_BACKEND=ollama and run Ollama, set LLM_MOCK=true, or rebuild "
                    "llama-cpp-python with AVX2 disabled. "
                    f"Model path: {self._model_path.resolve()}"
                ) from exc
        return _llama_instance

    def _ollama_generate(self, prompt: str) -> str:
        url = f"{settings.ollama_base_url.rstrip('/')}/api/generate"
        try:
            with httpx.Client(timeout=300.0) as client:
                resp = client.post(
                    url,
                    json={
                        "model": settings.ollama_model,
                        "prompt": prompt,
                        "stream": False,
                        "options": {"num_predict": settings.llm_max_tokens},
                    },
                )
                resp.raise_for_status()
                return resp.json().get("response", "").strip()
        except httpx.ConnectError as exc:
            raise RuntimeError(
                "Cannot connect to Ollama. Install from https://ollama.com, run "
                f"`ollama pull {settings.ollama_model}`, and ensure it is running."
            ) from exc
        except httpx.HTTPStatusError as exc:
            raise RuntimeError(f"Ollama error: {exc.response.text[:300]}") from exc

    def _ollama_generate_stream(self, prompt: str) -> Iterator[str]:
        url = f"{settings.ollama_base_url.rstrip('/')}/api/generate"
        try:
            with httpx.Client(timeout=300.0) as client:
                with client.stream(
                    "POST",
                    url,
                    json={
                        "model": settings.ollama_model,
                        "prompt": prompt,
                        "stream": True,
                        "options": {"num_predict": settings.llm_max_tokens},
                    },
                ) as resp:
                    resp.raise_for_status()
                    for line in resp.iter_lines():
                        if not line:
                            continue
                        data = json.loads(line)
                        chunk = data.get("response", "")
                        if chunk:
                            yield chunk
        except httpx.ConnectError as exc:
            raise RuntimeError(
                "Cannot connect to Ollama. Install from https://ollama.com, run "
                f"`ollama pull {settings.ollama_model}`, and ensure it is running."
            ) from exc
        except httpx.HTTPStatusError as exc:
            raise RuntimeError(f"Ollama error: {exc.response.text[:300]}") from exc

    def generate(self, prompt: str) -> str:
        if self.use_mock:
            return self._mock_response(prompt)
        if self._backend == "ollama":
            return self._ollama_generate(prompt)

        llm = self._get_llama()
        result = llm(
            prompt,
            max_tokens=settings.llm_max_tokens,
            temperature=0.7,
            stop=["</s>", "\n\nUser:", "\n\nHuman:"],
            echo=False,
            stream=False,
        )
        return result["choices"][0]["text"].strip()

    def generate_stream(self, prompt: str) -> Iterator[str]:
        if self.use_mock:
            text = self._mock_response(prompt)
            chunk_size = 8
            for i in range(0, len(text), chunk_size):
                yield text[i : i + chunk_size]
            return
        if self._backend == "ollama":
            yield from self._ollama_generate_stream(prompt)
            return

        llm = self._get_llama()
        stream = llm(
            prompt,
            max_tokens=settings.llm_max_tokens,
            temperature=0.7,
            stop=["</s>", "\n\nUser:", "\n\nHuman:"],
            echo=False,
            stream=True,
        )
        for chunk in stream:
            piece = chunk["choices"][0]["text"]
            if piece:
                yield piece

    def build_prompt(self, user_message: str) -> str:
        return (
            "You are a helpful assistant in a chat application. "
            "Answer concisely and clearly.\n\n"
            f"User: {user_message}\n\nAssistant:"
        )

    @staticmethod
    def _mock_response(prompt: str) -> str:
        user_part = prompt.split("User:")[-1].split("Assistant:")[0].strip()[:200]
        return (
            f"[Mock LLM — set LLM_MOCK=false and configure LLM_BACKEND]\n\n"
            f"You asked: «{user_part}»\n\n"
            "Use LLM_BACKEND=ollama (with Ollama running) or LLM_BACKEND=llama with a GGUF model."
        )
