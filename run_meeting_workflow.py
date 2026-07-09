import os
from pathlib import Path

import pdfplumber
from docx import Document

from src.core.context import PlatformContext
from src.core.workflow_engine import WorkflowEngine


BASE_DIR = os.environ.get(
    "FAI_BASE_DIR",
    "/content/drive/MyDrive/會議紀錄自動化"
)

SLIDE_INPUT_DIR = os.path.join(
    BASE_DIR,
    "input",
    "meeting",
    "slide"
)

TRANSCRIPT_INPUT_DIR = os.path.join(
    BASE_DIR,
    "input",
    "meeting",
    "transcript"
)

OUTPUT_DIR = os.path.join(
    BASE_DIR,
    "output",
    "meeting"
)


def read_pdf(path):
    texts = []

    with pdfplumber.open(path) as pdf:
        for i, page in enumerate(pdf.pages, start=1):
            text = page.extract_text() or ""
            text = text.strip()

            if text:
                texts.append(
                    f"\n\n===== 第 {i} 頁 =====\n\n{text}"
                )

    return "\n".join(texts)


def read_docx(path):
    doc = Document(path)

    texts = []

    for paragraph in doc.paragraphs:
        text = paragraph.text.strip()

        if text:
            texts.append(text)

    return "\n".join(texts)


def find_single_file(folder_path, suffix):
    folder = Path(folder_path)

    if not folder.exists():
        raise FileNotFoundError(f"找不到資料夾：{folder_path}")

    files = sorted([
        p for p in folder.iterdir()
        if p.is_file()
        and not p.name.startswith("~$")
        and p.suffix.lower() == suffix
    ])

    if not files:
        raise FileNotFoundError(
            f"資料夾內沒有 {suffix} 檔案：{folder_path}"
        )

    if len(files) > 1:
        raise ValueError(
            f"資料夾內有多個 {suffix} 檔案，請只保留一個：{folder_path}"
        )

    return files[0]


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

    slide_file = find_single_file(
        SLIDE_INPUT_DIR,
        ".pdf"
    )

    transcript_file = find_single_file(
        TRANSCRIPT_INPUT_DIR,
        ".docx"
    )

    slide_text = read_pdf(slide_file)
    transcript_text = read_docx(transcript_file)

    context = PlatformContext()

    context.set(
        "input",
        "slide_text",
        slide_text
    )

    context.set(
        "input",
        "transcript_text",
        transcript_text
    )

    txt_path = os.path.join(
        OUTPUT_DIR,
        "final_meeting_signoff_yaml.txt"
    )

    docx_path = os.path.join(
        OUTPUT_DIR,
        "final_meeting_signoff_yaml.docx"
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
        "workflows/meeting.yaml"
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
    print("Meeting Workflow 完成")
    print("==============================")
    print(f"Base Dir      : {BASE_DIR}")
    print(f"Slide Input   : {slide_file}")
    print(f"Transcript    : {transcript_file}")
    print(f"Output        : {OUTPUT_DIR}")
    print(f"TXT           : {txt_path}")
    print(f"DOCX          : {result.get('output', 'docx_path')}")


if __name__ == "__main__":
    main()
