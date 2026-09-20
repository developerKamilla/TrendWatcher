"""View models for the news feed. Keep arithmetic average distinct from FinSignal."""
import re
import html
import math
from datetime import timedelta, datetime, timezone
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


def radar_svg(breakdown):
    bd=validate_breakdown(breakdown)
    labels=["Влияние на бизнес","Срочность","Конкуренция","Регуляторный риск","Реализуемость"]
    values=list(bd.values())
    cx,cy,radius=230,205,125
    angles=[-math.pi/2+i*2*math.pi/5 for i in range(5)]
    def points(scale):
        return ' '.join(f'{cx+math.cos(a)*radius*scale:.1f},{cy+math.sin(a)*radius*scale:.1f}' for a in angles)
    data=' '.join(f'{cx+math.cos(a)*radius*(v/5):.1f},{cy+math.sin(a)*radius*(v/5):.1f}' for a,v in zip(angles,values))
    grids=''.join(f'<polygon points="{points(level/5)}" fill="none" stroke="#3d3538" stroke-width="1"/>' for level in range(1,6))
    axes=''.join(f'<line x1="{cx}" y1="{cy}" x2="{cx+math.cos(a)*radius:.1f}" y2="{cy+math.sin(a)*radius:.1f}" stroke="#3d3538"/>' for a in angles)
    dots=''.join(f'<circle cx="{cx+math.cos(a)*radius*(v/5):.1f}" cy="{cy+math.sin(a)*radius*(v/5):.1f}" r="4" fill="#ef443c"><title>{html.escape(label)}: {v:g} / 5</title></circle>' for a,v,label in zip(angles,values,labels))
    label_positions=[(230,42,'middle'),(405,164,'start'),(340,354,'middle'),(120,354,'middle'),(55,164,'end')]
    texts=''.join(f'<text x="{x}" y="{y}" text-anchor="{anchor}" fill="#ddd7d8" font-size="13">{html.escape(label)}</text>' for (x,y,anchor),label in zip(label_positions,labels))
    return (f'<div class="tw-radar"><svg viewBox="0 0 460 380" role="img" aria-label="Радарная диаграмма пяти факторов">'
            f'{grids}{axes}<polygon points="{data}" fill="rgba(239,68,60,.22)" stroke="#ef443c" stroke-width="3"/>{dots}{texts}'
            '</svg></div>')


def factor_distribution_html(cards):
    colors=['#ef443c','#c92f2a','#f4786d','#bdaeb1','#83757a']
    rows=[]
    for (key,label),color in zip(FACTOR_NAMES.items(),colors):
        counts=[0]*5
        for card in cards:
            score=max(1,min(5,int(float(card['breakdown'][key])+.5)))
            counts[score-1]+=1
        peak=max(counts) or 1
        bars=''.join(
            f'<div class="tw-hist-bin"><span style="height:{max(6,count/peak*118):.0f}px;background:{color}" title="{count} новостей"></span><b>{score}</b><small>{count}</small></div>'
            for score,count in enumerate(counts,1))
        rows.append(f'<div class="tw-hist-row"><strong>{html.escape(label)}</strong><div class="tw-hist-bars">{bars}</div></div>')
    return '<div class="tw-histogram">'+''.join(rows)+'</div>'


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
