from pathlib import Path

from src.skills.base_skill import BaseSkill
from src.providers.provider_registry import get_provider


class LLMSkill(BaseSkill):
    name = "llm"

    def _build_prompt(self, prompt_path: str, inputs: dict) -> str:
        prompt = Path(prompt_path).read_text(encoding="utf-8")

        for key, value in inputs.items():
            prompt += f"\n\n以下為 {key}：\n\n{value}"

        return prompt

    def run(self, inputs: dict, step_config: dict) -> dict:
        prompt_path = step_config["prompt"]

        provider_name = step_config.get("provider", "gemini")
        model = step_config.get("model")
        retry = step_config.get("retry", 3)

        prompt = self._build_prompt(
            prompt_path=prompt_path,
            inputs=inputs
        )

        provider = get_provider(provider_name)

        result = provider.generate(
            prompt=prompt,
            model=model,
            retry=retry
        )

        return {
            "result": result
        }
