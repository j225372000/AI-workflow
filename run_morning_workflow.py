import os
from pathlib import Path

from docx import Document

from src.core.context import PlatformContext
from src.core.workflow_engine import WorkflowEngine


# =====================================
# Base Directory
# =====================================
# Colab：
#   不設定 FAI_BASE_DIR
#   -> 使用 Google Drive
#
# GitHub Actions：
#   env:
#       FAI_BASE_DIR: tests/fixtures
#
# Local：
#   set FAI_BASE_DIR=...
# =====================================

BASE_DIR = os.environ.get(
    "FAI_BASE_DIR",
    "/content/drive/MyDrive/會議紀錄自動化"
)

NEWS_INPUT_DIR = os.path.join(
    BASE_DIR,
    "input",
    "morning",
    "news"
)

OUTPUT_DIR = os.path.join(
    BASE_DIR,
    "output",
    "morning"
)


def read_docx(path):
    doc = Document(path)

    texts = []

    for paragraph in doc.paragraphs:
        text = paragraph.text.strip()

        if text:
            texts.append(text)

    return "\n".join(texts)


def load_news_text():
    folder = Path(NEWS_INPUT_DIR)

    if not folder.exists():
        raise FileNotFoundError(
            f"找不到新聞資料夾：{NEWS_INPUT_DIR}"
        )

    files = sorted([
        p for p in folder.iterdir()
        if p.is_file()
        and not p.name.startswith("~$")
        and p.suffix.lower() == ".docx"
    ])

    if not files:
        raise FileNotFoundError(
            f"新聞資料夾內沒有 .docx 檔案：{NEWS_INPUT_DIR}"
        )

    contents = []

    for file in files:
        text = read_docx(file)

        contents.append(
            f"\n\n===== 新聞檔案：{file.name} =====\n\n{text}"
        )

    return "\n".join(contents)


def save_text(path, content):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    Path(path).write_text(
        content,
        encoding="utf-8"
    )


def main():

    if not os.environ.get("GOOGLE_API_KEY"):
        raise RuntimeError(
            "缺少 GOOGLE_API_KEY，請先設定環境變數。"
        )

    os.makedirs(
        OUTPUT_DIR,
        exist_ok=True
    )

    context = PlatformContext()

    news_text = load_news_text()

    context.set(
        "input",
        "news_text",
        news_text
    )

    txt_path = os.path.join(
        OUTPUT_DIR,
        "final_morning_brief_yaml.txt"
    )

    docx_path = os.path.join(
        OUTPUT_DIR,
        "final_morning_brief_yaml.docx"
    )

    context.set(
        "output",
        "txt_path",
        txt_path
    )

    context.set(
        "output",
        "docx_path",
        docx_path
    )

    engine = WorkflowEngine(
        "workflows/morning.yaml"
    )

    result = engine.run(context)

    final_text = result.get(
        "output",
        "final_text"
    )

    txt_path = result.get(
        "output",
        "txt_path"
    )

    save_text(
        txt_path,
        final_text
    )

    print("\n==============================")
    print("Morning Workflow 完成")
    print("==============================")
    print(f"Base Dir : {BASE_DIR}")
    print(f"Input    : {NEWS_INPUT_DIR}")
    print(f"Output   : {OUTPUT_DIR}")
    print(f"TXT      : {txt_path}")
    print(f"DOCX     : {result.get('output', 'docx_path')}")


if __name__ == "__main__":
    main()
