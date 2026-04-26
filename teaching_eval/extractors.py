import io
import os
import zipfile
import subprocess
import tempfile
import xml.etree.ElementTree as ET
from typing import Iterable


def allowed_file(filename: str, allowed_extensions: Iterable[str]) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in allowed_extensions


def extract_text_from_docx(file_bytes: bytes) -> str:
    try:
        with zipfile.ZipFile(io.BytesIO(file_bytes)) as zf:
            xml_content = zf.read("word/document.xml")
        tree = ET.fromstring(xml_content)
        texts = []
        namespace = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
        for para in tree.iter(f"{namespace}p"):
            para_texts = []
            for node in para.iter(f"{namespace}t"):
                if node.text:
                    para_texts.append(node.text)
            if para_texts:
                texts.append("".join(para_texts))
        return "\n".join(texts)
    except Exception as exc:
        return f"[DOCX解析失败: {exc}]"


def extract_text_from_pdf(file_bytes: bytes) -> str:
    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as handle:
            handle.write(file_bytes)
            tmp_path = handle.name
        result = subprocess.run(
            ["pdftotext", tmp_path, "-"],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            return f"[PDF解析失败: {result.stderr.strip()}]"
        return result.stdout.strip()
    except Exception as exc:
        return f"[PDF解析失败: {exc}]"
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)


def normalize_text(raw_text: str, max_length: int) -> str:
    text = raw_text.strip()
    if len(text) > max_length:
        text = text[:max_length] + "\n\n[内容过长，系统已自动截断]"
    return text
