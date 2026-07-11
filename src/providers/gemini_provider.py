import os
import time
from typing import Iterable

from google import genai
from google.genai import errors


class GeminiProvider:
    """
    Gemini 模型 Provider。

    功能：
    1. 使用主模型產生內容。
    2. 主模型失敗時，可依序切換備援模型。
    3. 暫時性錯誤會重試同一模型。
    4. 權限或請求格式錯誤會立即停止，不浪費額度。
    """

    name = "gemini"

    # 這類錯誤通常不應靠換模型解決
    NON_RETRYABLE_CODES = {
        400,  # 請求格式錯誤
        401,  # API Key／驗證失敗
        403,  # 無權限
    }

    # 這類錯誤可嘗試備援模型
    FALLBACK_CODES = {
        404,  # 模型不存在或不可用
        429,  # 配額或流量限制
        500,
        502,
        503,
        504,
    }

    def __init__(
        self,
        default_model: str = "gemini-2.5-flash-lite",
        default_fallback_models: Iterable[str] | None = None,
    ):
        api_key = os.environ.get("GOOGLE_API_KEY")

        if not api_key:
            raise RuntimeError(
                "缺少 GOOGLE_API_KEY，請先設定環境變數。"
            )

        self.client = genai.Client(api_key=api_key)
        self.default_model = self._normalize_model_name(default_model)

        if default_fallback_models is None:
            default_fallback_models = [
                "gemini-2.5-flash",
                "gemini-2.5-pro",
            ]

        self.default_fallback_models = self._normalize_model_list(
            default_fallback_models
        )

    @staticmethod
    def _normalize_model_name(model_name: str) -> str:
        """
        新版 google-genai SDK 使用：
            gemini-2.5-flash

        若 YAML 仍寫：
            models/gemini-2.5-flash

        會自動移除 models/。
        """
        if not model_name or not isinstance(model_name, str):
            raise ValueError("模型名稱不得為空。")

        model_name = model_name.strip()

        if model_name.startswith("models/"):
            model_name = model_name[len("models/"):]

        return model_name

    def _normalize_model_list(
        self,
        model_names: Iterable[str],
    ) -> list[str]:
        normalized = []
        seen = set()

        for model_name in model_names:
            clean_name = self._normalize_model_name(model_name)

            if clean_name not in seen:
                normalized.append(clean_name)
                seen.add(clean_name)

        return normalized

    def _build_model_sequence(
        self,
        primary_model: str,
        fallback_models: Iterable[str] | None,
    ) -> list[str]:
        """
        建立不重複的模型執行順序。
        """
        primary_model = self._normalize_model_name(primary_model)

        if fallback_models is None:
            fallback_models = self.default_fallback_models

        model_sequence = [primary_model]
        model_sequence.extend(
            self._normalize_model_list(fallback_models)
        )

        unique_models = []
        seen = set()

        for model_name in model_sequence:
            if model_name not in seen:
                unique_models.append(model_name)
                seen.add(model_name)

        return unique_models

    def _generate_once(
        self,
        prompt: str,
        model_name: str,
    ) -> str:
        response = self.client.models.generate_content(
            model=model_name,
            contents=prompt,
        )

        text = getattr(response, "text", None)

        if not text or not text.strip():
            raise RuntimeError(
                f"模型 {model_name} 未回傳有效文字內容。"
            )

        return text.strip()

    def _run_model_with_retry(
        self,
        prompt: str,
        model_name: str,
        retry: int,
        sleep_seconds: int,
    ) -> str:
        """
        執行單一模型。

        429：
            不在同一模型反覆等待，直接交由外層切換備援模型。

        500／502／503／504：
            可先短暫重試同一模型。

        400／401／403：
            立即停止。
        """
        retry = max(1, int(retry))
        last_error = None

        for attempt in range(1, retry + 1):
            try:
                print(
                    f"使用 Gemini 模型：{model_name} "
                    f"（第 {attempt}/{retry} 次）"
                )

                return self._generate_once(
                    prompt=prompt,
                    model_name=model_name,
                )

            except errors.APIError as exc:
                last_error = exc
                error_code = getattr(exc, "code", None)
                error_message = getattr(exc, "message", str(exc))

                print(
                    f"Gemini 模型失敗：{model_name}\n"
                    f"錯誤碼：{error_code}\n"
                    f"錯誤內容：{error_message}"
                )

                if error_code in self.NON_RETRYABLE_CODES:
                    raise RuntimeError(
                        f"Gemini 請求無法執行，"
                        f"錯誤碼 {error_code}：{error_message}"
                    ) from exc

                # 429 通常繼續嘗試同一模型價值不高，
                # 直接交由 generate() 切換下一個模型。
                if error_code == 429:
                    raise

                # 最後一次已失敗，不再等待
                if attempt >= retry:
                    raise

                wait_seconds = sleep_seconds * attempt

                print(
                    f"{wait_seconds} 秒後重試同一模型。"
                )
                time.sleep(wait_seconds)

            except Exception as exc:
                last_error = exc

                print(
                    f"Gemini 發生非 API 錯誤：{model_name}\n"
                    f"{type(exc).__name__}: {exc}"
                )

                if attempt >= retry:
                    raise

                wait_seconds = sleep_seconds * attempt

                print(
                    f"{wait_seconds} 秒後重試同一模型。"
                )
                time.sleep(wait_seconds)

        if last_error:
            raise last_error

        raise RuntimeError(
            f"Gemini 模型 {model_name} 執行失敗。"
        )

    def generate(
        self,
        prompt: str,
        model: str | None = None,
        fallback_models: Iterable[str] | None = None,
        retry: int = 3,
        sleep_seconds: int = 10,
        **kwargs,
    ) -> str:
        """
        依序執行主模型及備援模型。

        例如：
            主模型：gemini-2.5-flash-lite
            備援一：gemini-2.5-flash
            備援二：gemini-2.5-pro
        """
        if not prompt or not prompt.strip():
            raise ValueError("Prompt 不得為空。")

        primary_model = model or self.default_model

        model_sequence = self._build_model_sequence(
            primary_model=primary_model,
            fallback_models=fallback_models,
        )

        errors_by_model = []

        for index, model_name in enumerate(
            model_sequence,
            start=1,
        ):
            if index == 1:
                print(f"\n使用 Gemini 主模型：{model_name}")
            else:
                print(f"\n切換 Gemini 備援模型：{model_name}")

            try:
                result = self._run_model_with_retry(
                    prompt=prompt,
                    model_name=model_name,
                    retry=retry,
                    sleep_seconds=sleep_seconds,
                )

                print(
                    f"Gemini 模型執行成功：{model_name}"
                )

                return result

            except errors.APIError as exc:
                error_code = getattr(exc, "code", None)
                error_message = getattr(exc, "message", str(exc))

                errors_by_model.append(
                    {
                        "model": model_name,
                        "code": error_code,
                        "message": error_message,
                    }
                )

                if error_code in self.NON_RETRYABLE_CODES:
                    raise RuntimeError(
                        f"Gemini 無法執行：{error_message}"
                    ) from exc

                if error_code not in self.FALLBACK_CODES:
                    raise RuntimeError(
                        f"Gemini 模型 {model_name} 執行失敗，"
                        f"錯誤碼 {error_code}：{error_message}"
                    ) from exc

                print(
                    f"模型 {model_name} 無法使用，"
                    "準備切換下一個模型。"
                )

            except Exception as exc:
                errors_by_model.append(
                    {
                        "model": model_name,
                        "code": None,
                        "message": str(exc),
                    }
                )

                print(
                    f"模型 {model_name} 執行失敗，"
                    "準備切換下一個模型。"
                )

        error_lines = []

        for error_info in errors_by_model:
            error_lines.append(
                f"- {error_info['model']}："
                f"{error_info['code']} "
                f"{error_info['message']}"
            )

        error_summary = "\n".join(error_lines)

        raise RuntimeError(
            "所有 Gemini 主模型及備援模型均執行失敗：\n"
            f"{error_summary}"
        )
