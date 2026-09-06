"""Каталог и правила исходного проекта Alpha Girls; сохранены при доработке."""

JUNK_MARKERS = [
    "sorry, you have been blocked",
    "access denied",
    "enable javascript and cookies",
    "checking your browser",
    "cloudflare",
    "just a moment",
    "ddos-guard",
    "please wait",
    "verifying you are human",
    "robot or human",
]

FETCH_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0 Safari/537.36"
    ),
    "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.8",
}

RELEVANCE_PATTERNS = [
    r"банк", r"финтех", r"fintech", r"сбп", r"payment", r"bnpl",
    r"рассрочк", r"эквайр", r"биометри", r"цифровой\s+рубл",
    r"\bai\b", r"\bии\b", r"gpt", r"llm", r"нейросет", r"искусственн",
    r"регулятор", r"цб\s+рф", r"крипто", r"blockchain", r"crypto",
    r"стартап", r"startup", r"venture", r"инвест", r"invest",
    r"stripe", r"visa", r"mastercard", r"paypal", r"klarna",
    r"open\s*banking", r"embedded\s*finance", r"neobank",
    r"мобильн.*банк", r"цифров.*банк", r"онлайн.*банк",
    r"кредит", r"ипотек", r"займ", r"loan", r"mortgage",
    r"fraud", r"мошенни", r"кибербезопасн", r"security",
]

SOURCES = {
    # ── РОССИЙСКИЕ ─────────────────────────────────────────────
    "cbr.ru": {
        "url": "https://cbr.ru/press/",
        "rss": "https://cbr.ru/rss/",
        "authority": 5,
        "category": "regulation",
        "language": "ru",
    },
    "banki.ru": {
        "url": "https://www.banki.ru/news/lenta/",
        "rss": "https://www.banki.ru/xml/news.rss",
        "authority": 4,
        "category": "banking",
        "language": "ru",
    },
    "frank.media": {
        "url": "https://frankrg.com/",
        "rss": "https://frankrg.com/feed",
        "authority": 4,
        "category": "banking",
        "language": "ru",
    },
    "vc.ru/fintech": {
        "url": "https://vc.ru/fintech",
        "rss": "https://vc.ru/rss/fintech",
        "authority": 3,
        "category": "fintech",
        "language": "ru",
    },
    "rbc.ru": {
        "url": "https://www.rbc.ru/finances/",
        "rss": "https://rssexport.rbc.ru/rbcnews/news/30/full.rss",
        "authority": 4,
        "category": "markets",
        "language": "ru",
    },
    "plusworld.ru": {
        "url": "https://plusworld.ru/",
        "rss": "https://plusworld.ru/feed/",
        "authority": 3,
        "category": "payments",
        "language": "ru",
    },
    "fintech.ru": {
        "url": "https://fintech.ru/",
        "rss": "https://fintech.ru/feed/",
        "authority": 3,
        "category": "fintech",
        "language": "ru",
    },
    "habr.com/fintech": {
        "url": "https://habr.com/ru/hub/fintech/",
        "rss": "https://habr.com/ru/rss/hub/fintech/all/",
        "authority": 3,
        "category": "fintech",
        "language": "ru",
    },
    "tass.ru/ekonomika": {
        "url": "https://tass.ru/ekonomika",
        "rss": "https://tass.ru/rss/v2.xml",
        "authority": 4,
        "category": "markets",
        "language": "ru",
    },
    "kommersant.ru": {
        "url": "https://www.kommersant.ru/finance",
        "rss": "https://www.kommersant.ru/RSS/news.xml",
        "authority": 4,
        "category": "markets",
        "language": "ru",
    },
    "rusbase.com": {
        "url": "https://rb.ru/",
        "rss": "https://rb.ru/feeds/news/",
        "authority": 3,
        "category": "startups",
        "language": "ru",
    },
    # ── МЕЖДУНАРОДНЫЕ ФИНТЕХ ───────────────────────────────────
    "TechCrunch Fintech": {
        "url": "https://techcrunch.com/category/fintech/",
        "rss": "https://techcrunch.com/category/fintech/feed/",
        "authority": 5,
        "category": "fintech",
        "language": "en",
    },
    "Finextra": {
        "url": "https://www.finextra.com/",
        "rss": "https://www.finextra.com/rss/headlines.aspx",
        "authority": 5,
        "category": "banking",
        "language": "en",
    },
    "PYMNTS": {
        "url": "https://www.pymnts.com/",
        "rss": "https://www.pymnts.com/feed/",
        "authority": 4,
        "category": "payments",
        "language": "en",
    },
    "Fintech Futures": {
        "url": "https://www.fintechfutures.com/",
        "rss": "https://www.fintechfutures.com/feed/",
        "authority": 4,
        "category": "fintech",
        "language": "en",
    },
    "Payments Dive": {
        "url": "https://www.paymentsdive.com/",
        "rss": "https://www.paymentsdive.com/feeds/news/",
        "authority": 4,
        "category": "payments",
        "language": "en",
    },
    "American Banker": {
        "url": "https://www.americanbanker.com/",
        "rss": "https://www.americanbanker.com/feed",
        "authority": 5,
        "category": "banking",
        "language": "en",
    },
    "The Paypers": {
        "url": "https://thepaypers.com/",
        "rss": "https://thepaypers.com/feed",
        "authority": 4,
        "category": "payments",
        "language": "en",
    },
    # ── AI / BIG TECH ─────────────────────────────────────────
    "OpenAI Blog": {
        "url": "https://openai.com/blog/",
        "rss": "https://openai.com/blog/rss.xml",
        "authority": 5,
        "category": "ai",
        "language": "en",
    },
    "Google AI": {
        "url": "https://blog.google/technology/ai/",
        "rss": "https://blog.google/technology/ai/rss/",
        "authority": 5,
        "category": "ai",
        "language": "en",
    },
    "Anthropic News": {
        "url": "https://www.anthropic.com/news/",
        "rss": "https://www.anthropic.com/news/rss.xml",
        "authority": 5,
        "category": "ai",
        "language": "en",
    },
    "Microsoft AI": {
        "url": "https://blogs.microsoft.com/ai/",
        "rss": "https://blogs.microsoft.com/ai/feed/",
        "authority": 5,
        "category": "ai",
        "language": "en",
    },
    # ── VC / STARTUPS ─────────────────────────────────────────
    "a16z": {
        "url": "https://a16z.com/",
        "rss": "https://a16z.com/feed/",
        "authority": 5,
        "category": "venture",
        "language": "en",
    },
    "Crunchbase News": {
        "url": "https://news.crunchbase.com/",
        "rss": "https://news.crunchbase.com/feed/",
        "authority": 4,
        "category": "venture",
        "language": "en",
    },
    # ── REGULATION ────────────────────────────────────────────
    "Federal Reserve": {
        "url": "https://www.federalreserve.gov/",
        "rss": "https://www.federalreserve.gov/feeds/press_all.xml",
        "authority": 5,
        "category": "regulation",
        "language": "en",
    },
    "ECB": {
        "url": "https://www.ecb.europa.eu/",
        "rss": "https://www.ecb.europa.eu/rss/press.html",
        "authority": 5,
        "category": "regulation",
        "language": "en",
    },
    # ── CRYPTO ───────────────────────────────────────────────
    "CoinDesk": {
        "url": "https://www.coindesk.com/",
        "rss": "https://www.coindesk.com/arc/outboundfeeds/rss/",
        "authority": 4,
        "category": "crypto",
        "language": "en",
    },
    "Cointelegraph": {
        "url": "https://cointelegraph.com/",
        "rss": "https://cointelegraph.com/rss",
        "authority": 3,
        "category": "crypto",
        "language": "en",
    },
    # ── PRODUCT / PAYMENTS ────────────────────────────────────
    "Stripe Blog": {
        "url": "https://stripe.com/blog/",
        "rss": "https://stripe.com/blog/feed.rss",
        "authority": 5,
        "category": "payments",
        "language": "en",
    },
    # ── MARKETS ───────────────────────────────────────────────
    "Reuters Business": {
        "url": "https://www.reuters.com/business/",
        "rss": "https://feeds.reuters.com/reuters/businessNews",
        "authority": 5,
        "category": "markets",
        "language": "en",
    },
    "CNBC Finance": {
        "url": "https://www.cnbc.com/finance/",
        "rss": "https://www.cnbc.com/id/10001147/device/rss/rss.html",
        "authority": 4,
        "category": "markets",
        "language": "en",
    },
    # ── SECURITY ─────────────────────────────────────────────
    "Krebs on Security": {
        "url": "https://krebsonsecurity.com/",
        "rss": "https://krebsonsecurity.com/feed/",
        "authority": 5,
        "category": "security",
        "language": "en",
    },
    # ── GENERAL TECH ─────────────────────────────────────────
    "Wired": {
        "url": "https://www.wired.com/",
        "rss": "https://www.wired.com/feed/rss",
        "authority": 4,
        "category": "technology",
        "language": "en",
    },
    "The Verge": {
        "url": "https://www.theverge.com/",
        "rss": "https://www.theverge.com/rss/index.xml",
        "authority": 4,
        "category": "technology",
        "language": "en",
    },
}

NEWS_PATTERNS = {
    "regulation": [
        r"цб\b", r"банк\s+росси", r"регулятор", r"указани",
        r"обязал", r"штраф", r"закон", r"нормати",
        r"regulation", r"compliance", r"cfpb", r"sec\b", r"policy",
    ],
    "competitor": [
        r"т-банк", r"тинькофф", r"сбер\b", r"втб\b",
        r"запустил", r"анонсировал", r"выпустил", r"klarna",
        r"revolut", r"wise\b", r"monzo", r"chime",
    ],
    "ai_tech": [
        r"\bai\b", r"\bии\b", r"искусственн.*интеллект",
        r"нейросет", r"llm", r"gpt", r"чат.?бот",
        r"agent", r"copilot", r"openai", r"anthropic",
    ],
    "partnership": [
        r"партнёр", r"партнер", r"совместн", r"интеграци",
        r"partnership", r"joint", r"collaboration",
    ],
    "payments": [
        r"\bсбп\b", r"bnpl", r"рассрочк", r"сплит",
        r"цифровой\s+рубл", r"эквайр",
        r"payment", r"visa\b", r"mastercard", r"stripe",
        r"checkout", r"transaction",
    ],
    "crypto": [
        r"крипт", r"bitcoin", r"ethereum", r"blockchain",
        r"defi", r"web3", r"nft", r"токен",
    ],
    "security": [
        r"fraud", r"мошенни", r"кибербезопасн",
        r"breach", r"hack", r"vulnerability",
    ],
    "market": [
        r"рынок", r"тренд", r"рост\s+на", r"млрд", r"млн",
        r"market", r"economy", r"inflation", r"ipo", r"funding",
    ],
}

BREAKDOWN_PROFILES = {
    "regulation": {"business_impact": 4, "time_sensitivity": 5, "competitive_threat": 2, "regulatory_risk": 5,
                   "feasibility": 3},
    "competitor": {"business_impact": 5, "time_sensitivity": 4, "competitive_threat": 5, "regulatory_risk": 1,
                   "feasibility": 4},
    "ai_tech": {"business_impact": 4, "time_sensitivity": 3, "competitive_threat": 4, "regulatory_risk": 1,
                "feasibility": 5},
    "partnership": {"business_impact": 4, "time_sensitivity": 3, "competitive_threat": 4, "regulatory_risk": 1,
                    "feasibility": 3},
    "payments": {"business_impact": 5, "time_sensitivity": 4, "competitive_threat": 4, "regulatory_risk": 3,
                 "feasibility": 4},
    "crypto": {"business_impact": 3, "time_sensitivity": 3, "competitive_threat": 3, "regulatory_risk": 4,
               "feasibility": 3},
    "security": {"business_impact": 4, "time_sensitivity": 5, "competitive_threat": 2, "regulatory_risk": 4,
                 "feasibility": 3},
    "market": {"business_impact": 3, "time_sensitivity": 2, "competitive_threat": 2, "regulatory_risk": 1,
               "feasibility": 4},
}

CATEGORY_DISPLAY_NAMES = {
    "regulation": "регулирование",
    "competitor": "конкурент",
    "ai_tech": "AI/технологии",
    "partnership": "партнёрство",
    "payments": "платёжный сервис",
    "crypto": "крипто/блокчейн",
    "security": "кибербезопасность",
    "market": "рынок",
}