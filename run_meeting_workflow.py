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

STEP_OUTPUT_DIR = os.path.join(
    OUTPUT_DIR,
    "steps"
)


def read_pdf(path):
    texts = []

    with pdfplumber.open(path) as pdf:
        for page_number, page in enumerate(
            pdf.pages,
            start=1
        ):
            text = page.extract_text() or ""
            text = text.strip()

            if text:
                texts.append(
                    f"\n\n===== 第 {page_number} 頁 =====\n\n{text}"
                )

    return "\n".join(texts)


def read_docx(path):
    document = Document(path)
    texts = []

    for paragraph in document.paragraphs:
        text = paragraph.text.strip()

        if text:
            texts.append(text)

    return "\n".join(texts)


def find_single_file(folder_path, suffix):
    folder = Path(folder_path)

    if not folder.exists():
        raise FileNotFoundError(
            f"找不到資料夾：{folder_path}"
        )

    files = sorted([
        path
        for path in folder.iterdir()
        if path.is_file()
        and not path.name.startswith("~$")
        and path.suffix.lower() == suffix
    ])

    if not files:
        raise FileNotFoundError(
            f"資料夾內沒有 {suffix} 檔案：{folder_path}"
        )

    if len(files) > 1:
        raise ValueError(
            f"資料夾內有多個 {suffix} 檔案，"
            f"請只保留一個：{folder_path}"
        )

    return files[0]


def save_text(path, content):
    Path(path).parent.mkdir(
        parents=True,
        exist_ok=True
    )

    Path(path).write_text(
        content or "",
        encoding="utf-8"
    )


def main():
    if not os.environ.get("GOOGLE_API_KEY"):
        raise RuntimeError(
            "缺少 GOOGLE_API_KEY，請先設定環境變數。"
        )

    Path(OUTPUT_DIR).mkdir(
        parents=True,
        exist_ok=True
    )

    Path(STEP_OUTPUT_DIR).mkdir(
        parents=True,
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

    slide_text = read_pdf(
        slide_file
    )

    transcript_text = read_docx(
        transcript_file
    )

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

    checkpoint_path = os.path.join(
        OUTPUT_DIR,
        "meeting_checkpoint.json"
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

    result = engine.run(
        context=context,
        checkpoint_path=checkpoint_path,
        artifact_dir=STEP_OUTPUT_DIR,
        resume=True
    )

    final_text = result.get(
        "output",
        "final_text"
    )

    final_txt_path = result.get(
        "output",
        "txt_path"
    )

    save_text(
        final_txt_path,
        final_text
    )

    print("\n==============================")
    print("Meeting Workflow 完成")
    print("==============================")
    print(f"簡報檔案     ：{slide_file}")
    print(f"逐字稿檔案   ：{transcript_file}")
    print(f"Step 成果資料夾：{STEP_OUTPUT_DIR}")
    print(f"Checkpoint   ：{checkpoint_path}")
    print(f"最終 TXT     ：{final_txt_path}")
    print(f"最終 DOCX    ：{result.get('output', 'docx_path')}")


if __name__ == "__main__":
    main()
