import hashlib
import json
import os
from pathlib import Path

from docx import Document

from src.core.context import PlatformContext
from src.core.workflow_engine import WorkflowEngine


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
    document = Document(path)
    texts = []

    for paragraph in document.paragraphs:
        text = paragraph.text.strip()

        if text:
            texts.append(text)

    return "\n".join(texts)


def load_news_list():
    folder = Path(NEWS_INPUT_DIR)

    if not folder.exists():
        raise FileNotFoundError(
            f"找不到新聞資料夾：{NEWS_INPUT_DIR}"
        )

    files = sorted([
        path
        for path in folder.iterdir()
        if path.is_file()
        and not path.name.startswith("~$")
        and path.suffix.lower() == ".docx"
    ])

    if not files:
        raise FileNotFoundError(
            f"新聞資料夾內沒有 .docx 檔案：{NEWS_INPUT_DIR}"
        )

    news_list = []

    for file in files:
        content = read_docx(file)

        if not content.strip():
            print(
                f"略過空白 Word 檔：{file.name}"
            )
            continue

        news_list.append({
            "filename": file.name,
            "content": content
        })

    if not news_list:
        raise ValueError(
            "所有新聞 Word 檔均為空白，無法執行晨報。"
        )

    return news_list


def build_source_signature(news_list):
    serialized = json.dumps(
        news_list,
        ensure_ascii=False,
        sort_keys=True
    )

    return hashlib.sha256(
        serialized.encode("utf-8")
    ).hexdigest()


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

    news_list = load_news_list()

    source_signature = build_source_signature(
        news_list
    )

    context = PlatformContext()

    context.set(
        "input",
        "news_list",
        news_list
    )

    context.set(
        "metadata",
        "source_signature",
        source_signature
    )

    context.set(
        "metadata",
        "news_count",
        len(news_list)
    )

    txt_path = os.path.join(
        OUTPUT_DIR,
        "final_morning_brief_yaml.txt"
    )

    docx_path = os.path.join(
        OUTPUT_DIR,
        "final_morning_brief_yaml.docx"
    )

    checkpoint_path = os.path.join(
        OUTPUT_DIR,
        "morning_checkpoint.json"
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

    print(
        f"共讀取 {len(news_list)} 份新聞 Word 檔。"
    )

    engine = WorkflowEngine(
        "workflows/morning.yaml"
    )

    result = engine.run(
        context=context,
        checkpoint_path=checkpoint_path,
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
    print("Morning Workflow 完成")
    print("==============================")
    print(f"新聞篇數   ：{len(news_list)}")
    print(f"輸入資料夾 ：{NEWS_INPUT_DIR}")
    print(f"輸出資料夾 ：{OUTPUT_DIR}")
    print(f"Checkpoint：{checkpoint_path}")
    print(f"TXT       ：{final_txt_path}")
    print(f"DOCX      ：{result.get('output', 'docx_path')}")


if __name__ == "__main__":
    main()
