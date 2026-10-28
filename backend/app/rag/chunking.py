"""Document parsing, normalisation and heading-aware chunking."""
import re
import unicodedata
from dataclasses import dataclass

MAX_CHARS = 900


@dataclass
class Chunk:
    ordinal: int
    heading: str
    content: str


def parse_front_matter(text: str) -> tuple[dict[str, str], str]:
    """Minimal `---` front matter: `key: value` lines only (no YAML execution)."""
    if not text.startswith("---\n"):
        return {}, text
    end = text.find("\n---", 4)
    if end == -1:
        return {}, text
    meta = {}
    for line in text[4:end].splitlines():
        if ":" in line:
            key, value = line.split(":", 1)
            meta[key.strip().lower()] = value.strip()
    return meta, text[end + 4:].lstrip("\n")


def normalise(text: str) -> str:
    text = unicodedata.normalize("NFKC", text).replace("\r\n", "\n").replace("\t", " ")
    text = re.sub(r"[  ]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def chunk_markdown(text: str, max_chars: int = MAX_CHARS) -> list[Chunk]:
    """Split on headings, then pack paragraphs up to ``max_chars``. Each chunk
    keeps its heading path so retrieval results carry their context."""
    sections: list[tuple[str, list[str]]] = []
    path: list[str] = []
    current: list[str] = []
    for line in normalise(text).split("\n"):
        match = re.match(r"^(#{1,4})\s+(.*)$", line)
        if match:
            if current:
                sections.append((" > ".join(path), current))
            level = len(match.group(1))
            path = path[: level - 1] + [match.group(2).strip()]
            current = []
        else:
            current.append(line)
    if current:
        sections.append((" > ".join(path), current))

    chunks: list[Chunk] = []
    for heading, lines in sections:
        paragraphs = [p.strip() for p in "\n".join(lines).split("\n\n") if p.strip()]
        buffer = ""
        for paragraph in paragraphs:
            while len(paragraph) > max_chars:  # hard-split very long paragraphs on sentence boundaries
                cut = paragraph.rfind(". ", 0, max_chars)
                cut = cut + 1 if cut > max_chars // 2 else max_chars
                if buffer:
                    chunks.append(Chunk(len(chunks), heading, buffer))
                    buffer = ""
                chunks.append(Chunk(len(chunks), heading, paragraph[:cut].strip()))
                paragraph = paragraph[cut:].strip()
            if buffer and len(buffer) + len(paragraph) + 2 > max_chars:
                chunks.append(Chunk(len(chunks), heading, buffer))
                buffer = ""
            buffer = f"{buffer}\n\n{paragraph}" if buffer else paragraph
        if buffer:
            chunks.append(Chunk(len(chunks), heading, buffer))
    return chunks
