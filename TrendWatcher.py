"""TrendWatcher news workspace. Run: python -m streamlit run TrendWatcher.py"""
from __future__ import annotations
import copy
import html
import json
import os
from pathlib import Path
import pandas as pd
import streamlit as st
from trendwatcher.catalog import SOURCES
from trendwatcher.core import FACTOR_NAMES, WEIGHTS, import_articles, safe_url
from trendwatcher.seed import starter_articles, apply_prepared_analysis
from trendwatcher.services import collect_sources, run_pipeline, DEFAULT_MODEL
from trendwatcher.storage import Store
from trendwatcher.visuals import score_ring, factor_bars, signal_art
from trendwatcher.presentation import (SECTORS, FACTOR_HELP, average_score, sectors_for,
    select_news, saved_cards, radar_svg, factor_distribution_html, export_news)

PAGES = ["Новости", "Избранное", "Аналитика", "Источники"]
PERIODS = ["Все даты", "Сегодня", "7 дней", "30 дней"]

def esc(value):
    return html.escape(str(value or ""), quote=True)


def secret(name):
    value = os.environ.get(name, "")
    if value:
        return value
    try:
        return str(st.secrets.get(name, ""))
    except (FileNotFoundError, st.errors.StreamlitSecretNotFoundError):
        return ""


def go_page(page):
    st.session_state.page = page


def reset_workspace(user=None):
    for key in list(st.session_state):
        if key not in {"page"} and not key.startswith("$$"):
            del st.session_state[key]
    st.session_state.user = user
    st.session_state.page = "Новости"


def initialize(store):
    defaults = {"user": None, "results": None, "articles": [], "annotations": {}, "memory_cache": {},
                "session_runs": [], "source_logs": [], "selected_sources": list(SOURCES)[:6],
                "profile": "Продуктовая команда банка", "use_llm": False, "model": DEFAULT_MODEL,
                "page": "Новости", "data_label": "Сохранённые публикации", "selected_id": None}
    for key,value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = copy.deepcopy(value)
    if not st.session_state.get("initialized"):
        user = st.session_state.user
        if user:
            st.session_state.annotations = store.annotations(user["id"])
            runs = store.runs(user["id"])
            if runs:
                st.session_state.results = runs[0]
                st.session_state.data_label = runs[0].get("data_label", "Сохранённый анализ")
        if st.session_state.results is None:
            st.session_state.articles = starter_articles()
            st.session_state.results = run_pipeline(st.session_state.articles, limit=60)
        apply_prepared_analysis(st.session_state.results['cards'])
        for note in st.session_state.annotations.values():
            if isinstance(note.get('card'), dict):
                apply_prepared_analysis([note['card']])
        # Migrate previous digest selections to favorites without losing notes.
        by_id = {c["id"]:c for c in st.session_state.results["cards"]}
        for key, note in st.session_state.annotations.items():
            note.setdefault("favorite", note.get("digest", False))
            if key in by_id:
                note.setdefault("card", by_id[key])
        st.session_state.initialized = True


def annotate(store, card_id, **values):
    data = {**st.session_state.annotations.get(card_id, {}), **values}
    user = st.session_state.user
    if user:
        store.annotate(user["id"],card_id,data)
    st.session_state.annotations[card_id] = data


def active_api_key():
    return st.session_state.get('api_key_input', '').strip() or secret('OPENROUTER_API_KEY')


def analyze(store, force_ai=False):
    use_llm = force_ai or st.session_state.use_llm
    if use_llm and not active_api_key():
        st.error('Введите API-ключ OpenRouter для ИИ-анализа.')
        return False
    bar = st.progress(0., text="Подготовка публикаций")
    user = st.session_state.user
    cache = st.session_state.memory_cache
    get = (lambda key: store.cache_get(user["id"],key)) if user else cache.get
    put = (lambda key,value:store.cache_put(user["id"],key,value)) if user else (lambda key,value:cache.__setitem__(key,value))
    try:
        result = run_pipeline(st.session_state.articles, use_llm=use_llm,
            api_key=active_api_key() if use_llm else "",
            model=st.session_state.model, profile=st.session_state.profile, cache_get=get, cache_put=put,
            limit=st.session_state.get("analysis_limit",60), progress=lambda p,t:bar.progress(p,text=t))
        apply_prepared_analysis(result['cards'])
        result["data_label"] = st.session_state.data_label
        result["source_logs"] = st.session_state.source_logs
        st.session_state.results = result
        if user:
            store.save_run(user["id"],result)
        else:
            st.session_state.session_runs.insert(0,copy.deepcopy(result))
            st.session_state.session_runs = st.session_state.session_runs[:20]
        st.session_state.selected_id = None
        if use_llm:
            st.info(f'ИИ-анализ: {result["stats"]["llm_cards"]} из {len(result["cards"])} новостей. '
                    f'Из кэша: {result["stats"]["cards_from_cache"]}.')
            for warning in result['warnings']:st.warning(warning)
        return True
    finally:
        bar.empty()


def page_heading(title, subtitle="", eyebrow="FINTECH INTELLIGENCE"):
    st.markdown(f'<div class="tw-eyebrow">{esc(eyebrow)}</div>', unsafe_allow_html=True)
    st.title(title)
    if subtitle:
        st.markdown(f'<p class="tw-subtitle">{esc(subtitle)}</p>', unsafe_allow_html=True)


def empty(title, text):
    st.markdown(f'<div class="tw-empty"><strong>{esc(title)}</strong><p>{esc(text)}</p></div>',unsafe_allow_html=True)


def navigate():
    st.session_state.selected_id = None


def open_card(card_id, origin):
    st.session_state.selected_id = card_id
    st.session_state.detail_origin = origin


def favorite_button(card, store, prefix):
    selected = st.session_state.annotations.get(card['id'],{}).get('favorite',False)
    if st.button("В избранном" if selected else "В избранное",icon=":material/bookmark:" if selected else ":material/bookmark_border:",
                 key=f"fav_{prefix}_{card['id']}",use_container_width=True):
        annotate(store,card['id'],favorite=not selected,card=card)
        st.rerun()


def factors_html(card):
    factors=''.join(f'<div class="tw-factor"><div class="tw-factor-label">{esc(label)}</div>'
        f'<div class="tw-factor-value">{card["breakdown"][key]:g}<span> / 5</span></div>'
        f'<div class="tw-track"><span style="width:{card["breakdown"][key]*20}%"></span></div></div>'
        for key,label in FACTOR_NAMES.items())
    return '<div class="tw-factors">'+factors+'</div>'


def signal_row(card, store, prefix):
    with st.container(border=True,key=f"card_{prefix}_{card['id']}"):
        sectors=sectors_for(card)
        note=st.session_state.annotations.get(card['id'],{}).get('note','')
        st.markdown(f'<article class="tw-news">{signal_art(card)}<div class="tw-news-top"><div class="tw-kicker">{esc(sectors[0])}</div></div>'
            f'<h2 class="tw-news-title">{esc(card["headline"])}</h2>'
            f'<div class="tw-meta">{esc(card["source"])}<span>·</span>{esc(card.get("date") or "Без даты")}</div>'
            f'<p class="tw-summary">{esc(card["summary"])}</p><div class="tw-evaluation"><div class="tw-ring-block">'
            f'<span>FinSignal Score</span>{score_ring(card)}</div>{factor_bars(card)}</div>'
            f'<div class="tw-average">Средняя оценка: {average_score(card):.2f} / 5</div></article>',unsafe_allow_html=True)
        if note:
            st.markdown(f'<div class="tw-note-preview"><b>Заметка</b> {esc(note[:180])}</div>',unsafe_allow_html=True)
        a,b=st.columns(2)
        a.button("Подробнее",icon=":material/arrow_outward:",key=f"open_{prefix}_{card['id']}",
            on_click=open_card,args=(card['id'],st.session_state.page),use_container_width=True)
        with b:favorite_button(card,store,prefix)


def detail(card,store):
    st.button("К новостям" if st.session_state.get('detail_origin')!='Избранное' else "К избранному",
              icon=":material/arrow_back:",on_click=navigate)
    page_heading(card['headline'],f'{card["source"]} · {card.get("date") or "Без даты"}'," / ".join(sectors_for(card)))
    right,left,actions=st.columns([1,1.35,1.15],gap="large")
    with left:
        with st.container(border=True,key='summary_panel'):
            st.subheader("Short Summary")
            st.write(card['summary'])
        body=card.get('text','')
        remainder=body[len(card['summary']):].strip() if body.startswith(card['summary']) else body
        if remainder and remainder!=card['summary']:
            with st.expander('Подробности публикации'):st.write(remainder)
        if safe_url(card.get('url')):
            st.link_button("Читать в источнике",card['url'],icon=":material/open_in_new:",type="primary")
        else:
            st.caption("Источник без ссылки")
        with st.container(border=True,key='why_panel'):
            st.subheader("Why Now")
            st.caption("Почему это важно сейчас")
            st.write(card.get('why_now') or 'Запустите ИИ-анализ в разделе «Источники», чтобы оценить актуальность новости.')
    with actions:
        st.subheader("Recommended Actions")
        st.caption("Рекомендуемые действия для команды")
        for index, action in enumerate(card.get('recommended_actions', []), 1):
            st.markdown(f'<div class="tw-action"><span>{index}</span><p>{esc(action)}</p></div>',unsafe_allow_html=True)
        if not card.get('recommended_actions'):
            st.write('Запустите ИИ-анализ в разделе «Источники», чтобы получить рекомендации.')
        for ref in card.get('related_sources',[]):
            if safe_url(ref.get('url')):st.link_button(ref['source'],ref['url'])
        st.divider()
        favorite_button(card,store,"detail")
        note=st.session_state.annotations.get(card['id'],{}).get('note','')
        with st.form('note_'+card['id']):
            st.text_area("Заметка к новости",value=note,max_chars=3000,height=130,
                         placeholder="Что стоит учесть или обсудить с командой",key='note_text_'+card['id'])
            if st.form_submit_button("Сохранить заметку",type="primary"):
                annotate(store,card['id'],note=st.session_state['note_text_'+card['id']],card=card)
                st.success("Заметка сохранена")
    with right:
        with st.container(border=True,key="rating_detail"):
            st.subheader('FinSignal Score')
            st.markdown('<div class="tw-score-hero">'+score_ring(card)+
                        '<p>Взвешенная значимость<br><small>для продуктовой команды</small></p></div>',unsafe_allow_html=True)
            st.markdown('<div class="tw-panel-label">Оценка по пяти факторам</div>'+factor_bars(card),unsafe_allow_html=True)
            st.caption(f'Средняя оценка: {average_score(card):.2f} / 5')
        with st.expander('Радар пяти факторов'):
            st.markdown(radar_svg(card['breakdown']),unsafe_allow_html=True)
        with st.expander("Как читать оценку"):
            st.write("Средняя оценка — сумма пяти критериев, делённая на пять. Каждый критерий: от 1 до 5.")
            for key,label in FACTOR_NAMES.items():st.write(f"**{label}.** {FACTOR_HELP[key]}")
            st.caption("Метод: ИИ-анализ" if card.get('generation_method')=='llm' else
                       "Метод: подготовленный разбор; оценки по правилам категории" if card.get('analysis_origin')=='prepared' else
                       "Метод: оценка по правилам категории")
            st.caption(f'FinSignal с весами 30/25/20/15/10%: {card["finsignal_score"]:.2f} / 5.')


def filters(cards, prefix):
    keys={name:f'{prefix}_{name}' for name in ['query','sectors','period','minimum','order']}
    # Keep filters when navigating into a story: widget cleanup otherwise discards them.
    saved=st.session_state.setdefault('filter_values',{})
    for name,key in keys.items():
        if key not in st.session_state:st.session_state[key]=saved.get(key,{'query':'','sectors':[],'period':'Все даты','minimum':1.,'order':'По оценке'}[name])
    with st.container(key='filters_'+prefix):
        a,b,c=st.columns([2,1.65,1])
        query=a.text_input("Поиск новостей",placeholder="Тема, компания или источник",key=keys['query'])
        sectors=b.multiselect("Сфера",SECTORS,placeholder="Все сферы",key=keys['sectors'])
        period=c.selectbox("Период",PERIODS,key=keys['period'])
        a,b,c=st.columns([1,1,2.65])
        minimum=a.selectbox("Средняя оценка от",[1.,2.,3.,4.,4.5],key=keys['minimum'],format_func=lambda x:f'{x:g} / 5')
        order=b.selectbox("Порядок",["По оценке","Сначала новые"],key=keys['order'])
        with c:
            st.markdown('<div class="tw-filter-reset">',unsafe_allow_html=True)
            def clear():
                for name,key in keys.items():
                    st.session_state[key]={'query':'','sectors':[],'period':'Все даты','minimum':1.,'order':'По оценке'}[name]
            st.button("Сбросить фильтры",key='reset_'+prefix,on_click=clear,type="tertiary")
            st.markdown('</div>',unsafe_allow_html=True)
    for key in keys.values():saved[key]=st.session_state[key]
    return select_news(cards,query,sectors,minimum,period,order)


def news_page(cards,store,favorites=False):
    if favorites:
        cards=saved_cards(cards,st.session_state.annotations)
    selected=next((c for c in cards if c['id']==st.session_state.selected_id),None)
    # Removing a favorite in detail must not close the story or discard an edited note.
    if not selected and st.session_state.selected_id:
        selected=st.session_state.annotations.get(st.session_state.selected_id,{}).get('card')
    if selected:
        detail(selected,store);return
    page_heading("Избранное" if favorites else "Финтех в фокусе.",
                 "Сохранённые новости и ваши заметки." if favorites else "Новости, которые имеют значение для банка.")
    if not favorites:
        high=sum(c['finsignal_score']>=4 for c in cards)
        saved=len(saved_cards(cards,st.session_state.annotations))
        st.markdown(f'<section class="tw-overview"><div><span class="tw-mini-mark">↗</span><b>Ваша финтех-подборка</b>'
                    f'<p>От новостей — к решениям.</p></div><div><strong>{len(cards)}</strong><span>Публикаций</span></div>'
                    f'<div><strong>{high}</strong><span>FinSignal ≥ 4</span></div><div><strong>{saved}</strong><span>В избранном</span></div></section>',unsafe_allow_html=True)
    if favorites and not cards:
        empty("Здесь будет важное","Сохраняйте новости кнопкой «В избранное».");return
    subset=filters(cards,'favorites' if favorites else 'news')
    a,b=st.columns([3,1])
    a.markdown(f'<div class="tw-result-count">{len(subset)} публикаций <span> / {len(cards)} в подборке</span></div>',unsafe_allow_html=True)
    if favorites and subset:
        with b,st.popover("Скачать подборку",use_container_width=True):
            st.download_button("Markdown",export_news(subset,st.session_state.annotations),"TrendWatcher_Favorites.md","text/markdown")
            payload={'cards':subset,'annotations':{c['id']:{k:v for k,v in st.session_state.annotations.get(c['id'],{}).items() if k!='card'} for c in subset}}
            st.download_button("JSON",json.dumps(payload,ensure_ascii=False,indent=2),"TrendWatcher_Favorites.json","application/json")
    if not subset:
        empty("Новостей не найдено","Попробуйте другую сферу или расширьте период.");return
    pages=max(1,(len(subset)+7)//8)
    page=st.selectbox("Страница",range(1,pages+1),key='pagination_'+str(favorites)) if pages>1 else 1
    visible=subset[(page-1)*8:page*8]
    for i in range(0,len(visible),2):
        columns=st.columns(2,gap='large')
        for col,card in zip(columns,visible[i:i+2]):
            with col:signal_row(card,store,'favorites' if favorites else 'news')


def analytics(cards):
    page_heading("Аналитика","Профиль новостей по пяти критериям.")
    subset=filters(cards,'analytics')
    if not subset:empty("Нет данных для графиков","Расширьте фильтры.");return
    a,b,c=st.columns(3)
    a.metric("Публикаций",len(subset))
    b.metric("Средняя оценка",f'{sum(average_score(c) for c in subset)/len(subset):.2f} / 5')
    c.metric("Оценка от 4",sum(average_score(c)>=4 for c in subset))
    left,right=st.columns([1,1.4],gap="large")
    with left:
        st.subheader("Средний профиль")
        means={key:sum(c['breakdown'][key] for c in subset)/len(subset) for key in FACTOR_NAMES}
        st.markdown(radar_svg(means),unsafe_allow_html=True)
    with right:
        st.subheader("Распределение пяти факторов")
        st.markdown(factor_distribution_html(subset),unsafe_allow_html=True)
        st.caption("Дробные оценки сгруппированы по ближайшему целому баллу.")


def sources(store):
    page_heading("Источники","Соберите новости и запустите анализ.")
    with st.container(border=True):
        st.subheader('AI-анализ')
        st.text_input('API-ключ OpenRouter',type='password',key='api_key_input',
                      placeholder='Вставьте ключ OpenRouter',help='Хранится только в текущей сессии; не записывается в историю и файлы.')
        configured=bool(active_api_key())
        st.caption('Ключ указан. Соединение проверяется при запуске.' if configured else
                   'Без ключа доступна подготовленная подборка с Why Now и Recommended Actions.')
        st.caption('При запуске тексты новостей и контекст команды отправляются OpenRouter и выбранной модели. Возможны расходы по тарифу провайдера.')
        a,b=st.columns(2)
        if a.button('Запустить AI-анализ подборки',type='primary',disabled=not configured or not st.session_state.results['cards']):
            st.session_state.articles=copy.deepcopy(st.session_state.results['cards'])
            analyze(store,force_ai=True)
        if b.button('Открыть подготовленную подборку'):
            st.session_state.articles=starter_articles()
            result=run_pipeline(st.session_state.articles)
            apply_prepared_analysis(result['cards'])
            st.session_state.results=result
            st.session_state.data_label='Сохранённые публикации'
            st.session_state.source_logs=[]
            st.session_state.selected_id=None
            st.success('Подборка готова. Откройте «Новости» → «Подробнее». Избранное и заметки сохранены.')
        def clear_key():
            st.session_state.api_key_input=''
            st.session_state.use_llm=False
        st.button('Очистить введённый ключ',on_click=clear_key,type='tertiary',disabled=not st.session_state.get('api_key_input'))
        if secret('OPENROUTER_API_KEY'):st.caption('Также настроен серверный ключ: при пустом поле используется он.')
    st.multiselect("Источники мониторинга",list(SOURCES),key='selected_sources')
    with st.expander("Настройки анализа"):
        st.text_area("Темы и задачи команды",key='profile',max_chars=800)
        st.number_input("Лимит публикаций",1,120,60,key='analysis_limit')
        st.checkbox("Дополнять RSS заголовками с сайтов",key='html_fallback')
        st.checkbox("ИИ-анализ",key='use_llm',disabled=not configured)
        st.caption('Применять ИИ при обновлении источников и импорте файла.')
        st.text_input("Модель",key='model',max_chars=100)
        if configured:st.caption("ИИ-анализ отправляет тексты и контекст провайдеру и использует его оплачиваемый API.")
    if st.button("Обновить новости",icon=":material/refresh:",type='primary',disabled=not st.session_state.selected_sources):
        with st.spinner("Собираем публикации…"):
            articles,logs=collect_sources(st.session_state.selected_sources,st.session_state.get('html_fallback',False))
        st.session_state.source_logs=logs
        if articles:
            st.session_state.articles=articles
            st.session_state.data_label='Публикации из источников'
            analyze(store)
            st.success(f'Готово: {len(st.session_state.results["cards"])} новостей')
            st.button("К новостям",on_click=go_page,args=('Новости',))
        else:st.error("Не удалось загрузить новости. Предыдущая подборка сохранена.")
    with st.expander("Загрузить JSON или CSV"):
        st.caption("Поля: title, text, source, url, date. UTF-8, до 2 МБ.")
        upload=st.file_uploader("Файл публикаций",type=['json','csv'])
        if st.button("Загрузить и проанализировать",disabled=upload is None):
            try:
                st.session_state.articles=import_articles(upload.getvalue(),upload.name)
                st.session_state.data_label=upload.name
                st.session_state.source_logs=[]
                analyze(store)
                st.success("Новости добавлены")
            except (ValueError,UnicodeError) as error:st.error(str(error))
    with st.expander("История подборок"):
        user=st.session_state.user
        runs=store.runs(user['id']) if user else st.session_state.session_runs
        if not runs:st.caption("Здесь появятся результаты обновлений.")
        for i,result in enumerate(runs):
            st.write(f'{result["stats"]["run_time"]} · {len(result["cards"])} новостей')
            def restore(result=result):
                st.session_state.results=copy.deepcopy(result)
                st.session_state.selected_id=None
                st.session_state.page='Новости'
            st.button("Открыть",key=f'restore_{i}',on_click=restore)
    if st.session_state.source_logs or st.session_state.results.get('warnings'):
        with st.expander("Результаты загрузки"):
            for warning in st.session_state.results.get('warnings',[]):st.warning(warning)
            if st.session_state.source_logs:
                st.dataframe(pd.DataFrame(st.session_state.source_logs).rename(columns={'source':'Источник','status':'Результат','count':'Публикации','method':'Метод'}),hide_index=True,use_container_width=True)


def account(store):
    user=st.session_state.user
    with st.popover(user['username'] if user else 'Войти',icon=":material/person_outline:",use_container_width=True):
        if user:
            st.caption("Избранное и заметки сохраняются в аккаунте")
            st.button("Выйти",on_click=reset_workspace)
            return
        st.caption("Войдите, чтобы сохранять избранное между сессиями.")
        mode=st.radio('Доступ',['Вход','Регистрация'],horizontal=True,label_visibility='collapsed',key='auth_mode')
        def authenticate():
            try:
                name=st.session_state.auth_username
                password=st.session_state.auth_password
                user=store.login(name,password) if st.session_state.auth_mode=='Вход' else store.register(name,password)
                if user:
                    reset_workspace(user)
                else:
                    st.session_state.auth_error='Неверный логин или пароль'
            except ValueError as error:
                st.session_state.auth_error=str(error)
        with st.form('account_form'):
            st.text_input('Логин',max_chars=32,key='auth_username')
            st.text_input('Пароль',type='password',max_chars=256,key='auth_password')
            if mode=='Регистрация':st.caption('Логин — латиницей, пароль — от 10 символов.')
            st.form_submit_button('Войти' if mode=='Вход' else 'Создать аккаунт',type='primary',on_click=authenticate)
        if st.session_state.get('auth_error'):st.error(st.session_state.auth_error)


def main():
    st.set_page_config(page_title='TrendWatcher',page_icon='🔴',layout='wide',initial_sidebar_state='collapsed')
    st.markdown('<style>'+Path(__file__).with_name('trendwatcher').joinpath('theme.css').read_text()+'</style>',unsafe_allow_html=True)
    try:
        store=Store();initialize(store)
    except Exception:
        st.error('Не удалось открыть хранилище. Проверьте доступ к каталогу данных.');return
    if st.session_state.page not in PAGES:st.session_state.page='Новости'
    # Streamlit cleans up hidden widgets; preserve model settings across navigation.
    for key in ['selected_sources','profile','use_llm','model','analysis_limit','html_fallback','api_key_input']:
        if key in st.session_state:st.session_state[key]=st.session_state[key]
    with st.container(key='header'):
        logo,nav,profile=st.columns([1.7,3.6,1],vertical_alignment='center')
        with logo:st.markdown('<div class="tw-brand"><span class="tw-logo-mark">↗</span>TrendWatcher</div>',unsafe_allow_html=True)
        with nav:st.radio('Навигация',PAGES,key='page',horizontal=True,label_visibility='collapsed',on_change=navigate)
        with profile:account(store)
    cards=st.session_state.results['cards']
    try:
        page=st.session_state.page
        if page=='Новости':news_page(cards,store)
        elif page=='Избранное':news_page(cards,store,True)
        elif page=='Аналитика':analytics(cards)
        else:sources(store)
    except OSError:st.error('Не удалось сохранить изменения. Повторите действие.')
    st.markdown('<footer class="tw-footer"><b>TrendWatcher</b><span>Fintech intelligence</span></footer>',unsafe_allow_html=True)


if __name__=='__main__':
    main()
