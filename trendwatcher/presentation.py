"""View models for the news feed. Keep arithmetic average distinct from FinSignal."""
import re
from datetime import timedelta, datetime, timezone
import plotly.graph_objects as go
from .core import FACTOR_NAMES, validate_breakdown, filter_cards, parse_date, safe_url

SECTOR_PATTERNS = {
    "Платежи и переводы": r"плат[её]ж|перевод|эквайр|\bсбп\b|payment|acquir",
    "Кредитование и BNPL": r"кредит|рассроч|\bbnpl\b|lending|loan",
    "ИИ и данные": r"\bии\b|\bai\b|нейросет|искусственн|машинн.{0,12}обуч|данных|data|llm",
    "Кибербезопасность": r"мошеннич|антифрод|кибератак|компьютерн.{0,8}атак|fraud|cyber",
    "Цифровые активы": r"цифров.{0,12}(рубл|актив)|крипто|\bцфа\b|crypto|blockchain|token",
    "Идентификация и биометрия": r"биометр|идентификац|\bkyc\b|identity|biometric",
    "Инвестиции": r"инвест|брокер|ценн.{0,8}бумаг|invest|wealth",
    "Страхование": r"страхов|insur",
}
SECTORS = [*SECTOR_PATTERNS, "Банковские сервисы"]
FACTOR_HELP = {
    "business_impact": "Влияние события на продукты, выручку и издержки банка.",
    "time_sensitivity": "Насколько быстро событие требует внимания команды.",
    "competitive_threat": "Насколько событие меняет конкурентную позицию банка.",
    "regulatory_risk": "Значимость регуляторных требований и последствий.",
    "feasibility": "Насколько реалистично применить подход в банке.",
}


def average_score(card):
    values = validate_breakdown(card["breakdown"])
    return round(sum(values.values()) / len(values), 2)


def sectors_for(card):
    text = (card.get("headline",card.get("title","")) + " " + card.get("text",card.get("summary",""))).casefold()
    return [label for label,pattern in SECTOR_PATTERNS.items() if re.search(pattern,text)] or ["Банковские сервисы"]


def select_news(cards, query="", sectors=None, minimum=1., period="Все даты", order="По оценке", now=None):
    now = now or datetime.now(timezone.utc)
    subset = filter_cards(cards, query=query, period="Все даты" if period=="30 дней" else period, now=now)
    if period=="30 дней":
        subset=[c for c in subset if (d:=parse_date(c.get("published_at"))) and now-timedelta(days=30)<=d<=now]
    subset = [c for c in subset if average_score(c)>=minimum and (not sectors or set(sectors)&set(sectors_for(c)))]
    return sorted(subset,key=(lambda c:c.get("published_at") or "") if order=="Сначала новые" else (lambda c:(average_score(c),c.get("published_at") or "")),reverse=True)


def saved_cards(cards, annotations):
    merged={c["id"]:c for c in cards}
    for key,note in annotations.items():
        if key not in merged and isinstance(note.get("card"),dict):
            merged[key]=note["card"]
    return [c for key,c in merged.items() if annotations.get(key,{}).get("favorite",annotations.get(key,{}).get("digest",False))]


def radar_figure(breakdown):
    bd=validate_breakdown(breakdown)
    labels=["Влияние<br>на бизнес","Срочность","Конкуренция","Регуляторный<br>риск","Реализуемость"]
    values=list(bd.values())
    fig=go.Figure(go.Scatterpolar(r=values+[values[0]],theta=labels+[labels[0]],fill="toself",
        line=dict(color="#ef443c",width=2.5),fillcolor="rgba(225,46,40,.20)",
        marker=dict(size=7,color="#ef443c"),hovertemplate="%{theta}: %{r:.1f} / 5<extra></extra>"))
    fig.update_layout(height=380,margin=dict(l=72,r=72,t=40,b=40),paper_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Aptos, Segoe UI, sans-serif",color="#ddd7d8",size=12),showlegend=False,
        polar=dict(bgcolor="rgba(0,0,0,0)",radialaxis=dict(range=[0,5],tickvals=[1,2,3,4,5],
            gridcolor="#3d3538",linecolor="#3d3538",tickfont=dict(size=10,color="#a59c9f")),
            angularaxis=dict(gridcolor="#3d3538",linecolor="#3d3538",rotation=0,direction="counterclockwise")))
    return fig


def export_news(cards, annotations):
    lines=["# TrendWatcher · избранное",f"Публикаций: {len(cards)}",""]
    for c in cards:
        lines += [f"## {c['headline']}",f"{c.get('date') or 'Без даты'} · {c['source']}",
                  f"Средняя оценка: {average_score(c):.2f}/5",c['summary'], ""]
        lines += [f"- {FACTOR_NAMES[k]}: {v:g}/5" for k,v in c['breakdown'].items()]
        if c.get('why_now'):lines += ['', '### Why Now', c['why_now']]
        if c.get('recommended_actions'):
            lines += ['', '### Recommended Actions'] + [f'{i}. {a}' for i,a in enumerate(c['recommended_actions'],1)]
        if safe_url(c.get('url')):lines += ["", f"Источник: {c['url']}"]
        if annotations.get(c['id'],{}).get('note'):lines += ["", "Заметка: " + annotations[c['id']]['note']]
        lines += ["", "---", ""]
    return '\n'.join(lines)
