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
        if "." not in path:
            raise ValueError(
                f"Context 路徑格式錯誤，應為 section.key：{path}"
            )

        section, key = path.split(".", 1)
        return context.get(section, key)

    def _write_path(
        self,
        context: PlatformContext,
        path: str,
        value
    ):
        if "." not in path:
            raise ValueError(
                f"Context 路徑格式錯誤，應為 section.key：{path}"
            )

        section, key = path.split(".", 1)
        context.set(section, key, value)

    def _build_inputs(
        self,
        context: PlatformContext,
        step: dict
    ) -> dict:
        inputs = {}

        for input_name, context_path in step.get("input", {}).items():
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
        if not isinstance(outputs, dict):
            raise TypeError(
                f"Step「{step.get('id')}」的輸出必須是 dict，"
                f"目前型態為：{type(outputs).__name__}"
            )

        for output_name, context_path in step.get("output", {}).items():
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
        output_mapping = step.get("output", {})

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
                        "Context 有輸出路徑，"
                        f"但實體檔案不存在：{file_path}"
                    )
                    return False

        return True

    def _get_artifact_path(
        self,
        step: dict,
        artifact_dir
    ):
        """
        根據 YAML 的 artifact 欄位，
        取得該 Step 中間成果的實際儲存位置。
        """
        artifact_name = step.get("artifact")

        if not artifact_name or not artifact_dir:
            return None

        return Path(artifact_dir) / artifact_name

    def _load_artifact(
        self,
        context: PlatformContext,
        step: dict,
        artifact_path: Path
    ):
        """
        將既有 Step 成果讀回 Context。

        目前 artifact 適用於只有一個文字輸出的 Step。
        """
        output_mapping = step.get("output", {})

        if len(output_mapping) != 1:
            raise ValueError(
                f"Step「{step.get('id')}」使用 artifact 時，"
                "目前僅支援單一輸出欄位。"
            )

        output_name, context_path = next(
            iter(output_mapping.items())
        )

        value = artifact_path.read_text(
            encoding="utf-8"
        )

        self._write_path(
            context,
            context_path,
            value
        )

        return {
            output_name: value
        }

    def _save_artifact(
        self,
        step: dict,
        outputs: dict,
        artifact_path: Path
    ):
        """
        將 Step 的文字輸出另存為獨立檔案。
        """
        output_mapping = step.get("output", {})

        if len(output_mapping) != 1:
            raise ValueError(
                f"Step「{step.get('id')}」使用 artifact 時，"
                "目前僅支援單一輸出欄位。"
            )

        output_name = next(
            iter(output_mapping.keys())
        )

        if output_name not in outputs:
            raise KeyError(
                f"Step「{step.get('id')}」缺少可儲存的輸出："
                f"{output_name}"
            )

        value = outputs[output_name]

        if value is None:
            raise ValueError(
                f"Step「{step.get('id')}」輸出為空，無法儲存 artifact。"
            )

        artifact_path.parent.mkdir(
            parents=True,
            exist_ok=True
        )

        artifact_path.write_text(
            str(value),
            encoding="utf-8"
        )

    def run(
        self,
        context=None,
        checkpoint_path=None,
        artifact_dir=None,
        resume=True
    ):
        """
        執行 Workflow。

        checkpoint_path：
            儲存整體 Context 的 JSON。

        artifact_dir：
            儲存每一個 Step 的獨立文字成果。

        resume：
            True 時，優先讀取已存在的 Step artifact，
            並跳過不需要重新執行的步驟。
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

        if artifact_dir:
            Path(artifact_dir).mkdir(
                parents=True,
                exist_ok=True
            )

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

            artifact_path = self._get_artifact_path(
                step,
                artifact_dir
            )

            # 有獨立 Step 成果時，直接讀回 Context。
            if (
                resume
                and artifact_path
                and artifact_path.exists()
            ):
                self._load_artifact(
                    context,
                    step,
                    artifact_path
                )

                print(
                    f"已載入既有 Step 輸出：{artifact_path}"
                )
                continue

            # 沒有設定 artifact 的 Step，
            # 才使用原本的 Context／實體檔案判斷。
            if (
                resume
                and artifact_path is None
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

            if artifact_path:
                self._save_artifact(
                    step,
                    outputs,
                    artifact_path
                )

                print(
                    f"已儲存 Step 輸出：{artifact_path}"
                )

            if checkpoint_path:
                context.save_json(
                    checkpoint_path
                )

                print(
                    f"已儲存 checkpoint：{checkpoint_path}"
                )

        return context
