from importlib import import_module


SKILL_REGISTRY = {
    "llm": {
        "module": "src.skills.llm_skill",
        "class": "LLMSkill",
        "description": "讀取 Prompt，呼叫 AI Provider，產生文字結果",
    },
    "docx": {
        "module": "src.skills.docx_skill",
        "class": "DocxSkill",
        "description": "輸出 Word 檔案",
    },
}


def get_skill(skill_name: str):
    if skill_name not in SKILL_REGISTRY:
        raise ValueError(f"未知 Skill：{skill_name}")

    skill_info = SKILL_REGISTRY[skill_name]

    module = import_module(skill_info["module"])
    skill_class = getattr(module, skill_info["class"])

    return skill_class()


def list_skills():
    return {
        name: {
            "description": info.get("description", "")
        }
        for name, info in SKILL_REGISTRY.items()
    }
