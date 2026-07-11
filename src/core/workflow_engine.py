from pathlib import Path

import yaml

from src.core.context import PlatformContext
from src.skills.skill_registry import get_skill


class WorkflowEngine:

    def __init__(self, workflow_path):
        self.workflow_path = Path(workflow_path)

        if not self.workflow_path.exists():
            raise FileNotFoundError(
                f"找不到 Workflow YAML：{workflow_path}"
            )

        with self.workflow_path.open("r", encoding="utf-8") as file:
            self.workflow = yaml.safe_load(file)

        if not self.workflow:
            raise ValueError(
                f"Workflow YAML 內容為空：{workflow_path}"
            )

        if "name" not in self.workflow:
            raise ValueError(
                f"Workflow YAML 缺少 name：{workflow_path}"
            )

        if "steps" not in self.workflow:
            raise ValueError(
                f"Workflow YAML 缺少 steps：{workflow_path}"
            )

    def _resolve_path(
        self,
        context: PlatformContext,
        path: str
    ):
        """
        根據 context 路徑取得資料。

        範例：
        input.news_text
        memory.slide_summary
        output.final_text
        """
        if "." not in path:
            raise ValueError(
                f"Context 路徑格式錯誤，應為 section.key：{path}"
            )

        section, key = path.split(".", 1)

        return context.get(
            section,
            key
        )

    def _write_path(
        self,
        context: PlatformContext,
        path: str,
        value
    ):
        """
        將資料寫入指定的 Context 路徑。
        """
        if "." not in path:
            raise ValueError(
                f"Context 路徑格式錯誤，應為 section.key：{path}"
            )

        section, key = path.split(".", 1)

        context.set(
            section,
            key,
            value
        )

    def _build_inputs(
        self,
        context: PlatformContext,
        step: dict
    ) -> dict:
        """
        根據 YAML step 的 input mapping，
        從 Context 取出此 Skill 需要的資料。
        """
        inputs = {}

        input_mapping = step.get(
            "input",
            {}
        )

        for input_name, context_path in input_mapping.items():
            value = self._resolve_path(
                context,
                context_path
            )

            if value is None:
                raise ValueError(
                    f"Step「{step.get('id')}」缺少輸入資料："
                    f"{context_path}"
                )

            inputs[input_name] = value

        return inputs

    def _write_outputs(
        self,
        context: PlatformContext,
        step: dict,
        outputs: dict
    ):
        """
        根據 YAML step 的 output mapping，
        將 Skill 回傳結果寫回 Context。
        """
        if not isinstance(outputs, dict):
            raise TypeError(
                f"Step「{step.get('id')}」的 Skill 輸出必須是 dict，"
                f"目前型態為：{type(outputs).__name__}"
            )

        output_mapping = step.get(
            "output",
            {}
        )

        for output_name, context_path in output_mapping.items():
            if output_name not in outputs:
                raise KeyError(
                    f"Step「{step.get('id')}」缺少輸出欄位："
                    f"{output_name}"
                )

            self._write_path(
                context,
                context_path,
                outputs[output_name]
            )

    def _is_file_output(
        self,
        step: dict,
        output_name: str,
        context_path: str
    ) -> bool:
        """
        判斷此輸出是否屬於實體檔案。

        目前判斷規則：
        1. Skill 是 docx。
        2. Skill 輸出名稱為 path。
        3. Context key 以 _path 結尾。
        """
        _, key = context_path.split(".", 1)

        return (
            step.get("skill") == "docx"
            or output_name == "path"
            or key.endswith("_path")
        )

    def _outputs_exist(
        self,
        context: PlatformContext,
        step: dict
    ) -> bool:
        """
        判斷某個 Step 的輸出是否真的存在。

        一般文字輸出：
        Context 中有非空內容即視為存在。

        檔案輸出：
        Context 中有路徑，且實體檔案也必須存在。
        """
        output_mapping = step.get(
            "output",
            {}
        )

        if not output_mapping:
            return False

        for output_name, context_path in output_mapping.items():
            value = self._resolve_path(
                context,
                context_path
            )

            if value is None or value == "":
                return False

            if self._is_file_output(
                step,
                output_name,
                context_path
            ):
                file_path = Path(str(value))

                if not file_path.exists():
                    print(
                        "Checkpoint 有輸出路徑，"
                        f"但實體檔案不存在：{file_path}"
                    )
                    return False

        return True

    def run(
        self,
        context=None,
        checkpoint_path=None,
        resume=True
    ):
        """
        執行 Workflow。

        參數：
        context：
            Launcher 建立的初始 PlatformContext。

        checkpoint_path：
            每一步完成後儲存 Context 的 JSON 路徑。

        resume：
            True 時讀取 checkpoint，並跳過已完成步驟。
            False 時忽略 checkpoint，從頭執行。
        """

        if (
            checkpoint_path
            and resume
            and Path(checkpoint_path).exists()
        ):
            print(
                f"讀取 checkpoint：{checkpoint_path}"
            )

            context = PlatformContext.load_json(
                checkpoint_path
            )

        elif context is None:
            context = PlatformContext()

        print(
            f"\nWorkflow：{self.workflow['name']}"
        )

        for step in self.workflow["steps"]:
            step_id = step.get("id")
            skill_name = step.get("skill")

            if not step_id:
                raise ValueError(
                    "Workflow step 缺少 id"
                )

            if not skill_name:
                raise ValueError(
                    f"Step「{step_id}」缺少 skill"
                )

            print("\n==========")
            print(f"Step：{step_id}")
            print(f"Skill：{skill_name}")

            if (
                resume
                and self._outputs_exist(
                    context,
                    step
                )
            ):
                print(
                    "已存在有效輸出，跳過此步驟"
                )
                continue

            skill = get_skill(
                skill_name
            )

            inputs = self._build_inputs(
                context,
                step
            )

            outputs = skill.run(
                inputs=inputs,
                step_config=step
            )

            self._write_outputs(
                context,
                step,
                outputs
            )

            if checkpoint_path:
                context.save_json(
                    checkpoint_path
                )

                print(
                    f"已儲存 checkpoint：{checkpoint_path}"
                )

        return context
