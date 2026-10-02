def document(text, *, heading=None):
    item = {"item_id": "#/texts/0", "text": text, "original_text": text,
            "heading_path": [] if heading is None else [
                {"item_id": "#/texts/1", "text": heading, "depth": 1}]}
    items = [item]
    if heading:
        items.insert(0, {"item_id": "#/texts/1", "text": heading,
                         "original_text": heading, "heading_path": []})
    ids = [i["item_id"] for i in items]
    return {"schema_version": 1, "status": "completed", "source_sha256": "a" * 64,
            "source_reading_order": ids,
            "chunks": [{"chunk_id": "chunk-000001", "item_ids": ids,
                        "items": items, "content": text}]}
