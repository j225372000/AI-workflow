from pathlib import Path
import yaml

from src.core.context import PlatformContext
from src.skills.skill_registry import get_skill


class WorkflowEngine:

    def __init__(self, workflow_path):
        self.workflow_path = Path(workflow_path)

        if not self.workflow_path.exists():
            raise FileNotFoundError(workflow_path)

        with open(self.workflow_path, "r", encoding="utf-8") as f:
            self.workflow = yaml.safe_load(f)

    def _resolve_path(self, context: PlatformContext, path: str):
        section, key = path.split(".", 1)
        return context.get(section, key)

    def _write_path(self, context: PlatformContext, path: str, value):
        section, key = path.split(".", 1)
        context.set(section, key, value)

    def _build_inputs(self, context: PlatformContext, step: dict) -> dict:
        inputs = {}

        for input_name, context_path in step.get("input", {}).items():
            inputs[input_name] = self._resolve_path(context, context_path)

        return inputs

    def _write_outputs(self, context: PlatformContext, step: dict, outputs: dict):
        output_mapping = step.get("output", {})

        for output_name, context_path in output_mapping.items():
            self._write_path(
                context,
                context_path,
                outputs.get(output_name)
            )

    def run(self, context=None):
        if context is None:
            context = PlatformContext()

        print(f"\nWorkflow：{self.workflow['name']}")

        for step in self.workflow["steps"]:
            skill_name = step["skill"]

            print("\n==========")
            print(f"Step：{step['id']}")
            print(f"Skill：{skill_name}")

            skill = get_skill(skill_name)

            inputs = self._build_inputs(context, step)

            outputs = skill.run(
                inputs=inputs,
                step_config=step
            )

            self._write_outputs(context, step, outputs)

        return context
