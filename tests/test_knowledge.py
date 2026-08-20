from voiceos_api.knowledge import chunk_text, extract_bytes


def test_chunk_text_respects_overlap_and_boundaries() -> None:
    chunks = chunk_text("um dois três quatro cinco seis sete oito", 20, 5)
    assert len(chunks) > 1
    assert all(len(chunk) <= 20 for chunk in chunks)
    assert chunk_text("   ", 100, 10) == []


def test_extract_html_upload() -> None:
    assert "Prazo de sete dias" in extract_bytes(b"<p>Prazo de sete dias</p>", "text/html", "faq.html")
