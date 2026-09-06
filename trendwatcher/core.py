"""Pure, testable filtering, scoring and digest logic.

The source catalog and keyword classification are retained from Alpha Girls.
Scores are prioritization heuristics, not forecasts or probabilities.
"""
from __future__ import annotations

import copy
import csv
import hashlib
import io
import json
import math
import re
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode

from bs4 import BeautifulSoup
from .catalog import RELEVANCE_PATTERNS, NEWS_PATTERNS, BREAKDOWN_PROFILES

WEIGHTS = {"business_impact": .30, "time_sensitivity": .25, "competitive_threat": .20,
           "regulatory_risk": .15, "feasibility": .10}
FACTOR_NAMES = dict(zip(WEIGHTS, ["Влияние на бизнес", "Срочность", "Конкуренция", "Регуляторный риск", "Реализуемость"]))
CATEGORIES = {"regulation": "Регулирование", "competitor": "Конкуренты", "ai_tech": "ИИ и технологии",
              "partnership": "Партнёрства", "payments": "Платежи", "crypto": "Цифровые активы",
              "security": "Безопасность", "market": "Рынок"}
STATUSES = ["Новый", "Проверить", "В работе", "Применён", "Неактуален"]
VERSION = "1.2-actions-v1"


def clean_text(value, limit=6000):
    if not isinstance(value, str):
        return ""
    return re.sub(r"\s+", " ", BeautifulSoup(value, "html.parser").get_text(" ", strip=True)).strip()[:limit]


def safe_url(value):
    """Only navigable HTTP(S) links; imports are never fetched automatically."""
    if not isinstance(value, str) or re.search(r'[\s<>"\x00-\x1f]', value):
        return ""
    try:
        p = urlsplit(value)
        if p.scheme.lower() not in {"https", "http"} or not p.hostname or p.username or p.password:
            return ""
        return value
    except ValueError:
        return ""


def canonical_url(value):
    value = safe_url(value)
    if not value:
        return ""
    p = urlsplit(value)
    query = [(k, v) for k, v in parse_qsl(p.query) if not k.lower().startswith("utm_") and k.lower() not in {"fbclid", "gclid"}]
    return urlunsplit((p.scheme.lower(), p.netloc.lower(), p.path.rstrip("/"), urlencode(sorted(query)), ""))


def parse_date(value):
    """Unknown date stays unknown. Date-only feeds retain day precision."""
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        dt = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        try:
            dt = parsedate_to_datetime(value)
        except (ValueError, TypeError, OverflowError):
            return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def normalize_article(raw):
    if not isinstance(raw, dict):
        raise ValueError("Каждая публикация должна быть объектом JSON.")
    title = clean_text(raw.get("title"), 300)
    if len(title) < 10:
        raise ValueError("Заголовок публикации должен содержать минимум 10 символов.")
    text = clean_text(raw.get("text") or raw.get("summary") or title)
    if any(marker in (title + " " + text).casefold() for marker in
           ("sorry, you have been blocked", "enable javascript and cookies", "verifying you are human")):
        raise ValueError("Вместо публикации получена страница проверки доступа.")
    dt = parse_date(raw.get("published_at") or raw.get("date"))
    url = safe_url(raw.get("url", ""))
    precision = "day" if len(str(raw.get("date", ""))) == 10 and not raw.get("published_at") else "time"
    key = canonical_url(url) or title.casefold()
    return {"id": hashlib.sha256(key.encode()).hexdigest()[:20], "title": title, "text": text,
            "url": url, "source": clean_text(raw.get("source") or "Импорт", 100),
            "published_at": dt.isoformat() if dt else None, "date": dt.date().isoformat() if dt else None,
            "date_precision": raw.get("date_precision", precision) if dt else "unknown",
            "authority": raw.get("authority", 3), "is_demo": str(raw.get("is_demo", False)).casefold() in {"true", "1", "yes"},
            "source_kind": raw.get("source_kind", "Публикация; первоисточник не подтверждён"),
            "text_kind": raw.get("text_kind", "Фрагмент публикации")}


def is_relevant(title, text):
    return any(re.search(p, (title + " " + text).lower()) for p in RELEVANCE_PATTERNS)


def classify_news(title, text):
    combined = (title + " " + text).lower()
    scores = {t: sum(bool(re.search(p, combined)) for p in patterns) for t, patterns in NEWS_PATTERNS.items()}
    best = max(scores, key=scores.get)
    return best if scores[best] else "market"


def cosine_sim(a, b):
    stop = {"этот", "также", "которые", "который", "после", "среди", "будет", "были", "того", "with", "from", "that", "this", "have"}
    x, y = [set(w for w in re.findall(r"[\w]+", s.casefold()) if len(w) > 3 and w not in stop) for s in (a, b)]
    return len(x & y) / math.sqrt(len(x) * len(y)) if x and y else 0.


def deduplicate(articles, threshold=.72):
    """Lexical similarity, with retained alternative links. No semantic claim."""
    unique, duplicates = [], []
    for article in articles:
        art = copy.deepcopy(article)
        content = art["title"] + " " + art["text"]
        match = None
        for kept in unique:
            same_url = bool(art["url"] and canonical_url(art["url"]) == canonical_url(kept["url"]))
            same_title = art["title"].casefold() == kept["title"].casefold()
            d1, d2 = parse_date(art["published_at"]), parse_date(kept["published_at"])
            close_dates = not d1 or not d2 or abs((d1-d2).total_seconds()) <= 7*86400
            similar = close_dates and cosine_sim(content[:1800], (kept["title"]+" "+kept["text"])[:1800]) >= threshold
            if same_url or same_title or similar:
                match = kept
                reason = "Одинаковая ссылка" if same_url else "Совпадение текста / слов"
                break
        if match:
            ref = {"source": art["source"], "url": art["url"], "title": art["title"]}
            if ref not in match["related_sources"]:
                match["related_sources"].append(ref)
            duplicates.append({**art, "duplicate_of": match["id"], "reason": reason})
        else:
            art["related_sources"] = []
            unique.append(art)
    return unique, duplicates


def validate_breakdown(bd):
    if not isinstance(bd, dict) or set(WEIGHTS) - set(bd):
        raise ValueError("В оценке отсутствуют факторы.")
    result = {}
    for key in WEIGHTS:
        value = bd[key]
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not 1 <= value <= 5:
            raise ValueError("Все факторы должны быть числами от 1 до 5.")
        result[key] = float(value)
    return result


def compute_score(bd):
    bd = validate_breakdown(bd)
    return round(sum(bd[k] * w for k, w in WEIGHTS.items()), 2)


def local_card(article, reason="Локальная оценка по ключевым словам"):
    category = classify_news(article["title"], article["text"])
    bd = copy.deepcopy(BREAKDOWN_PROFILES.get(category, BREAKDOWN_PROFILES["market"]))
    return {**article, "headline": article["title"], "category": CATEGORIES[category],
            "breakdown": bd, "finsignal_score": compute_score(bd),
            "summary": article["text"][:800],
            "why_now": "Предварительный сигнал для продуктовой команды. Сроки, масштаб влияния и применимость к вашему банку требуют проверки по первоисточнику.",
            "recommended_actions": [f"Открыть публикацию «{article['title'][:100]}» и проверить факты и дату.",
                                    "Сопоставить сигнал с текущими задачами команды; записать вывод и ответственного."],
            "generation_method": "local", "confidence": "Требует проверки", "confidence_note": reason,
            "evidence": [], "analysis_version": VERSION}


def parse_json_safe(raw):
    if not isinstance(raw, str):
        return None
    decoder = json.JSONDecoder()
    for i, ch in enumerate(raw):
        if ch in "{[":
            try:
                return decoder.raw_decode(raw[i:])[0]
            except ValueError:
                continue
    return None


def validate_llm_card(raw, article):
    if not isinstance(raw, dict) or raw.get("article_id") != article["id"]:
        raise ValueError("Ответ не соответствует исходной публикации.")
    bd = validate_breakdown(raw.get("breakdown"))
    for key in ["headline", "summary", "why_now"]:
        if not isinstance(raw.get(key), str) or not raw[key].strip():
            raise ValueError("Неполная карточка.")
    actions = raw.get("recommended_actions")
    if not isinstance(actions, list) or not 1 <= len(actions) <= 4 or not all(isinstance(a, str) and a.strip() for a in actions):
        raise ValueError("Некорректный список действий.")
    evidence = raw.get("evidence", [])
    source_text = clean_text(article["title"] + " " + article["text"]).casefold()
    if not isinstance(evidence, list):
        raise ValueError("Некорректные выдержки.")
    verified = [clean_text(e, 350) for e in evidence if isinstance(e, str) and len(clean_text(e)) >= 12 and clean_text(e).casefold() in source_text]
    if not verified:
        raise ValueError("Нет проверяемой выдержки из публикации.")
    category = raw.get("category")
    if category not in CATEGORIES.values():
        category = CATEGORIES[classify_news(article["title"], article["text"])]
    return {**article, "headline": clean_text(raw["headline"], 250), "summary": clean_text(raw["summary"], 1400),
            "why_now": clean_text(raw["why_now"], 800), "breakdown": bd, "finsignal_score": compute_score(bd),
            "category": category, "recommended_actions": [clean_text(a, 600) for a in actions],
            "evidence": verified[:3], "generation_method": "llm", "confidence": "Черновик ИИ",
            "confidence_note": "Выдержки сверены с входным текстом. Факты и выводы ещё требуют проверки человеком.", "analysis_version": VERSION}


def cache_key(article, method, model, profile):
    payload = {k: article.get(k) for k in ["title", "text", "url", "published_at", "source", "is_demo"]}
    payload.update(version=VERSION, method=method, model=model, profile=profile)
    return hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def filter_cards(cards, query="", categories=None, min_score=1., period="Все даты", now=None):
    now = now or datetime.now(timezone.utc)
    result = []
    for c in cards:
        if c["finsignal_score"] < min_score or (categories and c["category"] not in categories):
            continue
        if query.casefold() not in (c["headline"]+" "+c["summary"]+" "+c["source"]).casefold():
            continue
        dt = parse_date(c.get("published_at"))
        if period != "Все даты":
            if not dt or dt > now:
                continue
            if period == "Сегодня" and dt.date() != now.date():
                continue
            if period == "7 дней" and dt < now - timedelta(days=7):
                continue
        result.append(c)
    return result


def import_articles(content: bytes, filename):
    if len(content) > 2_000_000:
        raise ValueError("Файл больше 2 МБ.")
    text = content.decode("utf-8-sig")
    data = json.loads(text) if filename.lower().endswith(".json") else list(csv.DictReader(io.StringIO(text)))
    if isinstance(data, dict):
        data = data.get("articles")
    if not isinstance(data, list) or not data or len(data) > 500:
        raise ValueError("Нужен список от 1 до 500 публикаций.")
    # Import raw articles only; do not trust precomputed model results.
    return [normalize_article(a) for a in data]


def to_markdown(cards, stats, annotations=None):
    annotations = annotations or {}
    lines = ["# TrendWatcher · дайджест", f"Сформирован: {stats.get('run_time', '—')}", f"В экспорт включено сигналов: {len(cards)}", ""]
    if any(c.get("is_demo") for c in cards):
        lines += ["**ДЕМОНСТРАЦИЯ: учебные сценарии, не реальные новости.**", ""]
    for c in cards:
        lines += [f"## {c['headline']}", f"FinSignal: {c['finsignal_score']:.2f}/5 · {c['category']}",
                  f"Метод: {c['generation_method']} · {c['confidence']}", f"Дата: {c.get('date') or 'не указана'}", c["summary"],
                  "", "### Почему важно", c["why_now"], "", "### Следующий шаг", *[f"- {a}" for a in c["recommended_actions"]]]
        if safe_url(c.get("url")):
            lines += ["", f"Источник: {c['source']} — {c['url']}"]
        for ref in c.get("related_sources", []):
            if safe_url(ref.get("url")):
                lines.append(f"Связанный материал: {ref['source']} — {ref['url']}")
        lines += [f"Ограничение: {c['confidence_note']}"]
        if annotations.get(c["id"], {}).get("note"):
            lines += ["Заметка аналитика: " + annotations[c["id"]]["note"]]
        lines += ["", "---", ""]
    return "\n".join(lines)
