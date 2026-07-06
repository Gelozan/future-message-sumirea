def _escape_html(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _entity_tags(e: dict) -> tuple[str, str]:
    etype = e["type"]
    if etype == "bold":
        return "<b>", "</b>"
    if etype == "italic":
        return "<i>", "</i>"
    if etype == "underline":
        return "<u>", "</u>"
    if etype == "strikethrough":
        return "<s>", "</s>"
    if etype == "code":
        return "<code>", "</code>"
    if etype == "pre":
        lang = e.get("language", "")
        return (f'<pre><code class="language-{lang}">', "</code></pre>") if lang else ("<pre>", "</pre>")
    if etype == "spoiler":
        return '<span class="tg-spoiler">', "</span>"
    if etype == "text_link":
        url = e.get("url", "")
        return f'<a href="{url}">', "</a>"
    return "", ""


def entities_to_html(text: str, entities: list[dict]) -> str:
    if not entities:
        return _escape_html(text)

    opens: dict[int, list[str]] = {}
    closes: dict[int, list[str]] = {}

    for e in entities:
        offset = e["offset"]
        end = offset + e["length"]
        tag_open, tag_close = _entity_tags(e)
        if tag_open:
            opens.setdefault(offset, []).append(tag_open)
            closes.setdefault(end, []).insert(0, tag_close)

    result = []
    for i, char in enumerate(text):
        for tag in closes.get(i, []):
            result.append(tag)
        for tag in opens.get(i, []):
            result.append(tag)
        result.append(_escape_html(char))

    for tag in closes.get(len(text), []):
        result.append(tag)

    return "".join(result)