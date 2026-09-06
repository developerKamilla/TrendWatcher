from pathlib import Path
from streamlit.testing.v1 import AppTest
from trendwatcher.presentation import average_score, sectors_for, select_news, saved_cards, export_news
from trendwatcher.seed import starter_articles
from trendwatcher.services import run_pipeline


def button(at,label):
    return next(b for b in at.button if b.label==label)


def nav(at,page):
    next(r for r in at.radio if r.label=='Навигация').set_value(page).run()
    assert not at.exception


def test_news_favorite_note_and_filters(monkeypatch,tmp_path):
    monkeypatch.setenv('TRENDWATCHER_DB',str(tmp_path/'app.sqlite3'))
    at=AppTest.from_file(str(Path(__file__).parents[1]/'TrendWatcher.py'),default_timeout=30).run()
    assert not at.exception
    assert at.title[0].value=='Финтех в фокусе.'
    assert len(at.sidebar)==0
    cards=at.session_state.results['cards']
    assert len(cards)==6 and all(c['url'] and not c['is_demo'] for c in cards)
    button(at,'В избранное').click().run()
    nav(at,'Избранное')
    assert len([b for b in at.button if b.label=='Подробнее'])==1
    button(at,'Подробнее').click().run()
    assert len(at.get('plotly_chart'))==1 and not at.exception
    at.text_area[0].set_value('Обсудить влияние на платёжный продукт')
    button(at,'Сохранить заметку').click().run()
    assert at.success and not at.exception
    button(at,'К избранному').click().run()
    assert any('Обсудить влияние' in m.value for m in at.markdown)
    nav(at,'Новости')
    next(m for m in at.multiselect if m.label=='Сфера').set_value(['Кредитование и BNPL']).run()
    filtered_count=len([b for b in at.button if b.label=='Подробнее'])
    assert filtered_count==1
    button(at,'Подробнее').click().run()
    button(at,'К новостям').click().run()
    assert next(m for m in at.multiselect if m.label=='Сфера').value==['Кредитование и BNPL']
    button(at,'Сбросить фильтры').click().run()
    assert len([b for b in at.button if b.label=='Подробнее'])==6
    nav(at,'Аналитика')
    assert len(at.get('plotly_chart'))==2
    nav(at,'Источники')
    assert any(b.label=='Обновить новости' for b in at.button)
    next(t for t in at.text_area if t.label=='Темы и задачи команды').set_value('Платежи для бизнеса').run()
    nav(at,'Новости');nav(at,'Источники')
    assert next(t for t in at.text_area if t.label=='Темы и задачи команды').value=='Платежи для бизнеса'
    saved_id=next(key for key,note in at.session_state.annotations.items() if note.get('favorite'))
    replacement=next(a for a in starter_articles() if a['id']!=saved_id)
    monkeypatch.setattr('trendwatcher.services.collect_sources',lambda *args:([replacement],[]))
    button(at,'Обновить новости').click().run()
    assert not at.exception and len(at.session_state.results['cards'])==1
    nav(at,'Избранное')
    assert len([b for b in at.button if b.label=='Подробнее'])==1
    nav(at,'Источники')
    button(at,'Открыть').click().run()
    assert not at.exception and at.title[0].value=='Финтех в фокусе.'


def test_average_filter_and_saved_news_outlive_refresh():
    cards=run_pipeline(starter_articles())['cards']
    c=cards[0]
    c['breakdown']={k:v for k,v in zip(c['breakdown'],[5,4,3,2,1])}
    assert average_score(c)==3.0  # Distinct from the legacy weighted FinSignal.
    assert c not in select_news(cards,minimum=3.5)
    bnpl=select_news(cards,sectors=['Кредитование и BNPL'])
    assert len(bnpl)==1 and 'рассроч' in bnpl[0]['headline']
    annotations={c['id']:{'favorite':True,'note':'Сохранённый вывод','card':c}}
    assert saved_cards([],annotations)==[c]
    exported=export_news(saved_cards([],annotations),annotations)
    assert c['url'] in exported and 'Сохранённый вывод' in exported
    annotations[c['id']]['favorite']=False
    assert saved_cards([],annotations)==[]


def test_header_login_restores_persistent_favorite(monkeypatch,tmp_path):
    from trendwatcher.storage import Store
    db=tmp_path/'auth.sqlite3'
    monkeypatch.setenv('TRENDWATCHER_DB',str(db))
    store=Store(db)
    user=store.register('reader','only-local-test-password')
    c=run_pipeline(starter_articles())['cards'][0]
    store.annotate(user['id'],c['id'],{'favorite':True,'note':'Сохранено ранее','card':c})
    at=AppTest.from_file(str(Path(__file__).parents[1]/'TrendWatcher.py'),default_timeout=30).run()
    next(t for t in at.text_input if t.label=='Логин').set_value('reader')
    next(t for t in at.text_input if t.label=='Пароль').set_value('only-local-test-password')
    button(at,'Войти').click().run()
    assert not at.exception and at.session_state.user['id']==user['id']
    nav(at,'Избранное')
    assert len([b for b in at.button if b.label=='Подробнее'])==1
    button(at,'Выйти').click().run()
    assert not at.exception and at.session_state.user is None
    assert at.session_state.annotations=={}
