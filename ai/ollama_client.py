import logging

logger = logging.getLogger(__name__)

class OllamaClient:
    def __init__(self, base_url: str, model: str):
        self.base_url = base_url
        self.model = model

    def generate(self, prompt: str) -> str:
        # TODO: Implement Ollama client generator
        logger.info(f"Generating completion for prompt with model {self.model}")
        return "Not implemented"
