from pathlib import Path

from src.providers.provider_registry import get_provider


class LLMSkill:
    name = "llm"

    def _build_prompt(
        self,
        prompt_path: str,
        inputs: dict,
    ) -> str:
        prompt_file = Path(prompt_path)

        if not prompt_file.exists():
            raise FileNotFoundError(
                f"找不到 Prompt：{prompt_path}"
            )

        prompt_template = prompt_file.read_text(
            encoding="utf-8"
        ).strip()

        prompt_parts = [prompt_template]

        for key, value in inputs.items():
            prompt_parts.append(
                f"\n\n========================\n"
                f"【輸入資料：{key}】\n"
                f"========================\n"
                f"{value}"
            )

        return "".join(prompt_parts)

    def run(
        self,
        inputs: dict,
        step_config: dict,
    ) -> dict:
        prompt_path = step_config["prompt"]

        provider_name = step_config.get(
            "provider",
            "gemini"
        )

        model = step_config.get("model")

        fallback_models = step_config.get(
            "fallback_models",
            []
        )

        retry = step_config.get(
            "retry",
            3
        )

        sleep_seconds = step_config.get(
            "sleep_seconds",
            10
        )

        prompt = self._build_prompt(
            prompt_path=prompt_path,
            inputs=inputs,
        )

        provider = get_provider(
            provider_name
        )

        result = provider.generate(
            prompt=prompt,
            model=model,
            fallback_models=fallback_models,
            retry=retry,
            sleep_seconds=sleep_seconds,
        )

        return {
            "result": result
        }
