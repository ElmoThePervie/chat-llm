"""Non-streaming llama-cpp example (requires model.gguf)."""
from llama_cpp import Llama

llm = Llama(model_path="../../models/model.gguf", n_ctx=2048, verbose=False)
result = llm("Hello! Briefly introduce yourself.", max_tokens=128, stream=False)
print(result["choices"][0]["text"])
