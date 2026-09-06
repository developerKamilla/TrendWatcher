import copy
import json
from datetime import datetime, timezone

import pytest

from trendwatcher.core import (normalize_article,parse_date,compute_score,local_card,filter_cards,
    import_articles,validate_llm_card,deduplicate,safe_url,cache_key,to_markdown)
from trendwatcher.demo import demo_articles
from trendwatcher.services import run_pipeline,parse_feed
from trendwatcher.storage import Store


def article(**kw):
    return normalize_article({"title":"Банк запускает новый платёжный сервис", "text":"Банк запускает новый платёжный сервис для предпринимателей.",
                              "source":"Источник","url":"https://example.org/news/1","date":"2026-09-04", **kw})


def valid_response(a):
    return {"article_id":a["id"],"headline":a["title"],"summary":a["text"],"why_now":"Гипотеза: упростит работу предпринимателей.",
            "category":"Платежи","breakdown":{k:3 for k in local_card(a)["breakdown"]},
            "recommended_actions":["Проверить условия сервиса."],"evidence":[a["text"]]}


def test_demo_funnel_and_cache():
    cache={}
    first=run_pipeline(demo_articles(),cache_get=cache.get,cache_put=cache.__setitem__)
    second=run_pipeline(demo_articles(),cache_get=cache.get,cache_put=cache.__setitem__)
    s=first["stats"]
    assert (s["total_input"],s["noise_removed"],s["duplicates_removed"],s["cards_generated"],s["cards_from_cache"])==(10,1,1,8,0)
    assert second["stats"]["cards_from_cache"]==8
    assert all(c["is_demo"] and not c["url"] for c in first["cards"])
    assert s["total_input"]==s["invalid_removed"]+s["noise_removed"]+s["duplicates_removed"]+s["limit_skipped"]+s["cards_generated"]


def test_empty_relevance_does_not_bypass_filter():
    result=run_pipeline([{"title":"Сегодня открылась выставка живописи", "text":"Художники показали пейзажи."}])
    assert result["cards"]==[]
    assert result["stats"]["noise_removed"]==1


def test_unknown_dates_and_future_are_not_fresh():
    assert parse_date("nonsense") is None
    assert parse_date("") is None
    assert parse_date("Fri, 04 Sep 2026 23:00:00 -0300").day==5
    cards=[local_card(article(date=d)) for d in ["2026-09-05","", "2026-09-06","2026-09-01"]]
    assert len(filter_cards(cards,period="Сегодня",now=datetime(2026,9,5,12,tzinfo=timezone.utc)))==1
    assert len(filter_cards(cards,period="7 дней",now=datetime(2026,9,5,12,tzinfo=timezone.utc)))==2


@pytest.mark.parametrize('value',[None,'5',float('nan'),float('inf'),0,6,True])
def test_invalid_breakdown(value):
    bd=local_card(article())["breakdown"]
    bd["business_impact"]=value
    with pytest.raises(ValueError):compute_score(bd)


def test_score_deterministic_and_no_invented_fallback_numbers():
    a=article()
    assert local_card(a)==local_card(a)
    assert not any(ch.isdigit() for ch in local_card(a)["why_now"])
    assert compute_score({k:5 for k in local_card(a)["breakdown"]})==5


def test_dedup_retains_sources_and_protects_distant_events():
    a=article();b=article(url="https://example.org/news/1?utm_source=email",source="Другой источник")
    unique,dupes=deduplicate([a,b])
    assert len(unique)==1 and len(dupes)==1
    assert unique[0]["related_sources"][0]["source"]=="Другой источник"
    c=article(title="Банк запускает другой платёжный сервис",url="https://example.org/news/2",date="2025-01-01")
    assert len(deduplicate([a,c])[0])==2


def test_llm_out_of_order_mapped_by_id(monkeypatch):
    a=article();b=article(title="ЦБ обсуждает правила банковской биометрии",text="ЦБ обсуждает правила банковской биометрии для новых счетов.",url="https://example.org/2")
    monkeypatch.setattr("trendwatcher.services.analyze_batch",lambda *args:([valid_response(b),valid_response(a)],{"prompt_tokens":100,"completion_tokens":80},""))
    result=run_pipeline([a,b],use_llm=True,api_key="test-only",threshold=.95)
    assert {c["id"]:c["headline"] for c in result["cards"]}=={a["id"]:a["title"],b["id"]:b["title"]}
    assert result["stats"]["llm_cards"]==2


def test_invalid_llm_evidence_falls_back_without_poisoning_cache(monkeypatch):
    a=article();row=valid_response(a);row["evidence"]=["This quotation was never in the supplied article."]
    monkeypatch.setattr("trendwatcher.services.analyze_batch",lambda *args:([row],{},""))
    cache={}
    result=run_pipeline([a],use_llm=True,api_key="test-only",cache_put=cache.__setitem__)
    assert result["stats"]["local_cards"]==1 and cache=={} and result["warnings"]
    assert cache_key(a,"local","","x")!=cache_key(a,"llm","model","x")


def test_untrusted_import_and_export():
    assert not safe_url('javascript:alert(1)')
    assert not safe_url('https://example.org/"onload=1')
    raw=[{"title":"<script>bad()</script>Банк обновляет платежи", "text":"Текст публикации", "url":"javascript:alert(1)"}]
    data=import_articles(json.dumps(raw).encode(),'data.json')
    assert not data[0]["url"] and '<script>' not in data[0]["title"]
    with pytest.raises(ValueError):import_articles(b'{}','a.json')
    cards=run_pipeline(demo_articles())["cards"][:2]
    markdown=to_markdown(cards,{"run_time":"test"})
    assert "В экспорт включено сигналов: 2" in markdown and "ДЕМОНСТРАЦИЯ" in markdown


def test_rss_atom_and_missing_dates():
    rss=b'<rss version="2.0"><channel><item><title>Bank launches payment service</title><link>https://example.org/a</link><description>A new payment service for businesses</description></item></channel></rss>'
    atom=b'<feed xmlns="http://www.w3.org/2005/Atom"><entry><title>Bank launches payment service</title><link href="/b"/><updated>2026-09-04T12:00:00Z</updated><summary>Payment service</summary></entry></feed>'
    cfg={"url":"https://example.org/"}
    assert parse_feed(rss,"test",cfg)[0]["date"] is None
    row=parse_feed(atom,"test",cfg)[0]
    assert row["url"]=="https://example.org/b" and row["date"]=="2026-09-04"


def test_persistence_account_isolation_and_throttle(tmp_path):
    store=Store(tmp_path/'store.sqlite3')
    alice=store.register("alice","a-long-password")
    bob=store.register("bob","b-long-password")
    result=run_pipeline(demo_articles())
    store.save_run(alice["id"],result)
    store.annotate(alice["id"],"article",{"note":"private"})
    store.cache_put(alice["id"],"key",{"a":1})
    reopened=Store(store.path)
    assert reopened.login("alice","a-long-password")==alice
    assert len(reopened.runs(alice["id"]))==1
    assert reopened.runs(bob["id"])==[] and reopened.annotations(bob["id"])=={}
    assert reopened.cache_get(bob["id"],"key") is None
    for _ in range(5):assert reopened.login("alice","incorrect") is None
    with pytest.raises(ValueError):reopened.login("alice","incorrect")
