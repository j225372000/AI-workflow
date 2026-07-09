import os
import time

import google.generativeai as genai



class GeminiProvider:
    name = "gemini"

    def __init__(
        self,
        default_model: str = "models/gemini-2.5-flash-lite",
        fallback_model: str = "models/gemini-2.5-flash-lite",
    ):
        api_key = os.environ.get("GOOGLE_API_KEY")

        if not api_key:
            raise RuntimeError("缺少 GOOGLE_API_KEY，請先設定環境變數。")

        genai.configure(api_key=api_key)

        self.default_model = default_model
        self.fallback_model = fallback_model

    def generate(
        self,
        prompt: str,
        model: str | None = None,
        retry: int = 3,
        sleep_seconds: int = 30,
        **kwargs,
    ) -> str:
        model_name = model or self.default_model
        gemini_model = genai.GenerativeModel(model_name)

        for i in range(retry):
            try:
                response = gemini_model.generate_content(prompt)
                return response.text
            except Exception as e:
                print(f"Gemini 第 {i + 1} 次失敗：{e}")
                time.sleep(sleep_seconds)

        print("改用 Gemini 備援模型")

        fallback = genai.GenerativeModel(self.fallback_model)
        response = fallback.generate_content(prompt)
        return response.text
