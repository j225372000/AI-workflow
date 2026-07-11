from copy import deepcopy
from pathlib import Path
import json

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

        return context.get(
            section,
            key
        )

    def _resolve_item_path(
        self,
        item,
        path: str
    ):
        """
        解析 for_each 單筆資料。

        例如：
        item.content
        item.filename
        item.classification
        """
        if path == "item":
            return item

        if not path.startswith("item."):
            raise ValueError(
                f"無效的 item 路徑：{path}"
            )

        keys = path.split(".")[1:]
        value = item

        for key in keys:
            if not isinstance(value, dict):
                raise ValueError(
                    f"無法從非 dict 資料解析：{path}"
                )

            if key not in value:
                raise KeyError(
                    f"item 缺少欄位「{key}」：{path}"
                )

            value = value[key]

        return value

    def _resolve_reference(
        self,
        context: PlatformContext,
        reference: str,
        item=None
    ):
        if reference == "item" or reference.startswith("item."):
            if item is None:
                raise ValueError(
                    f"非 for_each Step 不可使用 item 路徑：{reference}"
                )

            return self._resolve_item_path(
                item,
                reference
            )

        return self._resolve_path(
            context,
            reference
        )

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

        context.set(
            section,
            key,
            value
        )

    def _build_inputs(
        self,
        context: PlatformContext,
        step: dict,
        item=None
    ) -> dict:
        inputs = {}

        for input_name, reference in step.get("input", {}).items():
            value = self._resolve_reference(
                context=context,
                reference=reference,
                item=item
            )

            if value is None:
                raise ValueError(
                    f"Step「{step.get('id')}」缺少輸入資料："
                    f"{reference}"
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
                f"Step「{step.get('id')}」輸出必須是 dict，"
                f"目前為：{type(outputs).__name__}"
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

            if isinstance(value, list) and not value:
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
        output_mapping = step.get("output", {})

        if len(output_mapping) != 1:
            raise ValueError(
                f"Step「{step.get('id')}」使用 artifact 時，"
                "目前只支援單一輸出。"
            )

        output_name, context_path = next(
            iter(output_mapping.items())
        )

        if artifact_path.suffix.lower() == ".json":
            with artifact_path.open(
                "r",
                encoding="utf-8"
            ) as file:
                value = json.load(file)
        else:
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
        output_mapping = step.get("output", {})

        if len(output_mapping) != 1:
            raise ValueError(
                f"Step「{step.get('id')}」使用 artifact 時，"
                "目前只支援單一輸出。"
            )

        output_name = next(
            iter(output_mapping.keys())
        )

        if output_name not in outputs:
            raise KeyError(
                f"Step「{step.get('id')}」缺少輸出：{output_name}"
            )

        value = outputs[output_name]

        artifact_path.parent.mkdir(
            parents=True,
            exist_ok=True
        )

        if artifact_path.suffix.lower() == ".json":
            with artifact_path.open(
                "w",
                encoding="utf-8"
            ) as file:
                json.dump(
                    value,
                    file,
                    ensure_ascii=False,
                    indent=2
                )
        else:
            artifact_path.write_text(
                str(value),
                encoding="utf-8"
            )

    def _run_single_step(
        self,
        context: PlatformContext,
        step: dict,
        skill
    ) -> dict:
        inputs = self._build_inputs(
            context=context,
            step=step
        )

        return skill.run(
            inputs=inputs,
            step_config=step
        )

    def _run_foreach_step(
        self,
        context: PlatformContext,
        step: dict,
        skill
    ) -> dict:
        """
        逐筆執行同一個 Skill。

        YAML 範例：

        for_each: input.news_list
        input:
          text: item.content
        collect:
          include_item: true
          result_key: classification
        output:
          result: memory.classified_news
        """
        collection_path = step["for_each"]

        collection = self._resolve_path(
            context,
            collection_path
        )

        if not isinstance(collection, list):
            raise TypeError(
                f"Step「{step.get('id')}」的 for_each 資料必須是 list，"
                f"目前為：{type(collection).__name__}"
            )

        collect_config = step.get(
            "collect",
            {}
        )

        include_item = collect_config.get(
            "include_item",
            False
        )

        result_key = collect_config.get(
            "result_key",
            "result"
        )

        collected_results = []
        total = len(collection)

        for index, item in enumerate(
            collection,
            start=1
        ):
            print(
                f"處理第 {index}/{total} 筆"
            )

            inputs = self._build_inputs(
                context=context,
                step=step,
                item=item
            )

            item_outputs = skill.run(
                inputs=inputs,
                step_config=step
            )

            if not isinstance(item_outputs, dict):
                raise TypeError(
                    f"Step「{step.get('id')}」第 {index} 筆輸出"
                    "必須是 dict。"
                )

            if include_item:
                if isinstance(item, dict):
                    collected_item = deepcopy(item)
                else:
                    collected_item = {
                        "item": item
                    }

                if len(item_outputs) == 1:
                    only_value = next(
                        iter(item_outputs.values())
                    )

                    collected_item[result_key] = only_value
                else:
                    collected_item.update(
                        item_outputs
                    )

                collected_results.append(
                    collected_item
                )

            else:
                if len(item_outputs) == 1:
                    collected_results.append(
                        next(iter(item_outputs.values()))
                    )
                else:
                    collected_results.append(
                        item_outputs
                    )

        # LLMSkill 的標準輸出名稱為 result。
        return {
            "result": collected_results
        }

    def _merge_current_runtime_context(
        self,
        saved_context: PlatformContext,
        current_context: PlatformContext
    ):
        """
        使用本次 Launcher 提供的 input、output 路徑與 metadata，
        覆蓋 checkpoint 中可能過時的執行環境資料。
        """
        current_data = current_context.to_dict()

        for section in [
            "input",
            "output",
            "metadata"
        ]:
            for key, value in current_data.get(section, {}).items():
                saved_context.set(
                    section,
                    key,
                    value
                )

        return saved_context

    def run(
        self,
        context=None,
        checkpoint_path=None,
        artifact_dir=None,
        resume=True
    ):
        if context is None:
            context = PlatformContext()

        if (
            checkpoint_path
            and resume
            and Path(checkpoint_path).exists()
        ):
            saved_context = PlatformContext.load_json(
                checkpoint_path
            )

            saved_signature = saved_context.get(
                "metadata",
                "source_signature"
            )

            current_signature = context.get(
                "metadata",
                "source_signature"
            )

            if (
                saved_signature
                and current_signature
                and saved_signature != current_signature
            ):
                print(
                    "輸入資料已變更，忽略舊 checkpoint，"
                    "本次將重新執行 Workflow。"
                )

            else:
                print(
                    f"讀取 checkpoint：{checkpoint_path}"
                )

                context = self._merge_current_runtime_context(
                    saved_context=saved_context,
                    current_context=context
                )

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
                    "Workflow Step 缺少 id"
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

            if step.get("for_each"):
                outputs = self._run_foreach_step(
                    context=context,
                    step=step,
                    skill=skill
                )
            else:
                outputs = self._run_single_step(
                    context=context,
                    step=step,
                    skill=skill
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
