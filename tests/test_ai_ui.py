from pathlib import Path
from streamlit.testing.v1 import AppTest
from trendwatcher.seed import starter_articles, apply_prepared_analysis
from trendwatcher.services import run_pipeline
from trendwatcher.presentation import export_news
from test_app import button, nav


def test_prepared_analysis_and_export():
    cards = apply_prepared_analysis(run_pipeline(starter_articles())['cards'])
    assert len({c['why_now'] for c in cards}) == 6
    assert all(len(c['recommended_actions']) == 3 for c in cards)
    assert all(c['analysis_origin'] == 'prepared' for c in cards)
    assert '### Why Now' in export_news(cards, {})
    assert '### Recommended Actions' in export_news(cards, {})
    cards[0].update(generation_method='llm', why_now='Авторский ответ ИИ')
    apply_prepared_analysis(cards)
    assert cards[0]['why_now'] == 'Авторский ответ ИИ'


def test_key_analysis_clear_and_offline_restore(monkeypatch, tmp_path):
    monkeypatch.setenv('TRENDWATCHER_DB', str(tmp_path/'ai.sqlite3'))
    monkeypatch.delenv('OPENROUTER_API_KEY', raising=False)
    calls = []

    def fake_batch(articles, api_key, model, profile):
        calls.append((api_key, model, profile))
        return [dict(article_id=a['id'], headline=a['title'], summary=a['text'][:200],
                     why_now='Конкретный повод для внимания команды.',
                     recommended_actions=['Сравнить продуктовые сценарии.', 'Проверить гипотезу на данных.'],
                     breakdown={k:3 for k in ['business_impact','time_sensitivity','competitive_threat','regulatory_risk','feasibility']},
                     evidence=[a['text'][:80]]) for a in articles], {}, ''

    monkeypatch.setattr('trendwatcher.services.analyze_batch', fake_batch)
    at = AppTest.from_file(str(Path(__file__).parents[1]/'TrendWatcher.py'), default_timeout=30).run()
    button(at, 'Подробнее').click().run()
    assert {'Why Now','Recommended Actions'} <= {x.value for x in at.subheader}
    nav(at, 'Источники')
    assert button(at, 'Запустить AI-анализ подборки').disabled
    next(t for t in at.text_input if t.label=='API-ключ OpenRouter').set_value('test-session-key').run()
    assert not button(at, 'Запустить AI-анализ подборки').disabled
    nav(at, 'Новости'); nav(at, 'Источники')
    assert next(t for t in at.text_input if t.label=='API-ключ OpenRouter').value == 'test-session-key'
    button(at, 'Запустить AI-анализ подборки').click().run()
    assert not at.exception and calls[0][0] == 'test-session-key'
    assert at.session_state.results['stats']['llm_cards'] == 6
    assert 'test-session-key' not in str(at.session_state.results)
    assert 'test-session-key' not in str(at.session_state.session_runs)
    button(at, 'Очистить введённый ключ').click().run()
    assert at.session_state.api_key_input == ''
    assert button(at, 'Запустить AI-анализ подборки').disabled
    count = len(calls)
    button(at, 'Открыть подготовленную подборку').click().run()
    assert len(calls) == count and not at.exception
    assert all(c.get('analysis_origin')=='prepared' for c in at.session_state.results['cards'])


def test_api_failure_is_visible(monkeypatch, tmp_path):
    monkeypatch.setenv('TRENDWATCHER_DB', str(tmp_path/'failed.sqlite3'))
    monkeypatch.setattr('trendwatcher.services.analyze_batch', lambda *a: ([], {}, 'LLM недоступна: проверьте ключ, доступ и баланс.'))
    at = AppTest.from_file(str(Path(__file__).parents[1]/'TrendWatcher.py'), default_timeout=30).run()
    nav(at, 'Источники')
    next(t for t in at.text_input if t.label=='API-ключ OpenRouter').set_value('invalid-test-key').run()
    button(at, 'Запустить AI-анализ подборки').click().run()
    assert not at.exception and at.warning
    assert at.session_state.results['stats']['llm_cards'] == 0
    assert all(c.get('analysis_origin')=='prepared' for c in at.session_state.results['cards'])
