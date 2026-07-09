from src.utils import docx_writer


class DocxSkill:
    name = "docx"

    def run(self, inputs: dict, step_config: dict) -> dict:
        text = inputs["text"]
        output_path = inputs["output_path"]
        mode = step_config.get("mode", "morning")

        if mode == "morning":
            docx_writer.write_morning_docx(
                text,
                output_path
            )

        elif mode == "signoff":
            docx_writer.write_signoff_docx(
                text,
                output_path
            )

        else:
            raise ValueError(f"不支援的 docx mode：{mode}")

        return {
            "path": output_path
        }
