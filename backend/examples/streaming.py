"""Streaming llama-cpp example (requires model.gguf)."""
from llama_cpp import Llama

llm = Llama(model_path="../../models/model.gguf", n_ctx=2048, verbose=False)
stream = llm("Hello! Briefly introduce yourself.", max_tokens=128, stream=True)
for chunk in stream:
    print(chunk["choices"][0]["text"], end="", flush=True)
print()
