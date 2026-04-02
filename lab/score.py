import re


def canonical(gold):
    if isinstance(gold, int) and not isinstance(gold, bool):
        return str(gold)
    return str(gold)


def extract_answer(text):
    if text is None:
        return ""
    raw = str(text).strip()
    marker_at = -1
    marker_len = 0
    upper = raw.upper()
    for marker in ("ANSWER:", "ОТВЕТ:"):
        at = upper.rfind(marker)
        if at >= marker_at:
            marker_at = at
            marker_len = len(marker)
    if marker_at >= 0:
        raw = raw[marker_at + marker_len :]
    raw = raw.strip().strip("`").strip()
    if raw.endswith("."):
        raw = raw[:-1].strip()
    if len(raw) >= 2 and raw[0] == raw[-1] and raw[0] in "\"'«»":
        raw = raw[1:-1].strip()
    return raw


def match_answer(pred, gold):
    text = extract_answer(pred)
    if isinstance(gold, int) and not isinstance(gold, bool):
        compact = text.replace(" ", "").replace("\u00a0", "")
        found = re.fullmatch(
            r"(-?\d+)(?:руб(?:лей|ля|\.)?|usd|долларов|доллара|eur|евро|cny|юаней)?",
            compact,
            re.I,
        )
        return bool(found) and int(found.group(1)) == gold
    gold_text = " ".join(str(gold).casefold().replace("ё", "е").split())
    pred_text = " ".join(text.casefold().replace("ё", "е").split())
    return pred_text == gold_text
