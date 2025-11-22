"""
Enhanced Market Classification Utilities
Categorizes markets into sports, politics, macro, crypto, and other categories
Uses expanded keyword lists based on Polymarket analysis
"""

import logging
import re
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

# Expanded keyword lists based on Polymarket analysis

# NFL Teams (all 32 teams + abbreviations + common variations)
NFL_TEAMS = [
    # Team names
    "chiefs", "packers", "cowboys", "patriots", "rams", "bills", "eagles", "49ers", "niners",
    "buccaneers", "bucs", "seahawks", "bears", "commanders", "jaguars", "ravens", "steelers",
    "browns", "bengals", "titans", "colts", "texans", "raiders", "chargers", "broncos",
    "dolphins", "jets", "giants", "redskins", "cardinals", "falcons", "panthers", "saints",
    "vikings", "lions",
    # City names
    "washington", "houston", "philadelphia", "denver", "atlanta", "carolina", "new orleans",
    "minnesota", "detroit", "green bay", "chicago", "dallas", "new york", "los angeles",
    "kansas city", "tampa bay", "san francisco", "seattle", "baltimore", "pittsburgh",
    "cleveland", "cincinnati", "indianapolis", "jacksonville", "las vegas", "san diego",
    "miami", "buffalo", "arizona", "new england", "tennessee",
    # Abbreviations
    "hou", "phi", "den", "atl", "car", "no", "min", "det", "gb", "chi", "dal", "nyg", "nyj",
    "lac", "lar", "kc", "tb", "sf", "sea", "bal", "pit", "cle", "cin", "ind", "jax", "lv",
    "sd", "mia", "buf", "ari", "ne", "ten", "was", "wsh"
]

# NBA Teams (expanded)
NBA_TEAMS = [
    # Team names
    "lakers", "warriors", "celtics", "heat", "bulls", "knicks", "nets", "mavericks", "mavs",
    "clippers", "suns", "bucks", "nuggets", "76ers", "sixers", "raptors", "jazz", "trail blazers",
    "blazers", "hawks", "cavaliers", "cavs", "wizards", "magic", "pistons", "hornets", "pacers",
    "kings", "grizzlies", "pelicans", "thunder", "rockets", "spurs", "timberwolves", "wolves",
    # City names
    "orlando", "atlanta", "chicago", "cleveland", "detroit", "miami", "philadelphia", "toronto",
    "boston", "brooklyn", "new york", "charlotte", "indiana", "milwaukee", "washington", "denver",
    "minnesota", "oklahoma city", "portland", "utah", "golden state", "la clippers", "la lakers",
    "phoenix", "sacramento", "dallas", "houston", "memphis", "new orleans", "san antonio",
    # Abbreviations
    "lal", "gsw", "bos", "mia", "chi", "nyk", "bkn", "dal", "lac", "phx", "mil", "den", "phi",
    "tor", "uta", "por", "atl", "cha", "ind", "was", "min", "okc", "sac", "hou", "mem", "nop",
    "sa", "det", "orl", "cle"
]

# NHL Teams (expanded)
NHL_TEAMS = [
    # Team names
    "bruins", "sabres", "red wings", "panthers", "canadiens", "senators", "lightning", "maple leafs",
    "hurricanes", "blue jackets", "devils", "islanders", "rangers", "flyers", "penguins", "capitals",
    "blackhawks", "avalanche", "stars", "wild", "predators", "blues", "jets", "ducks", "coyotes",
    "flames", "oilers", "kings", "sharks", "kraken", "canucks", "golden knights", "vegas",
    # Abbreviations
    "bos", "buf", "det", "fla", "mtl", "ott", "tb", "tor", "car", "cbj", "nj", "nyi", "nyr", "phi",
    "pit", "wsh", "chi", "col", "dal", "min", "nsh", "stl", "wpg", "ana", "ari", "cgy", "edm",
    "la", "sj", "sea", "van", "vgk"
]

# MLB Teams (expanded)
MLB_TEAMS = [
    # Team names
    "yankees", "red sox", "blue jays", "rays", "orioles", "white sox", "guardians", "tigers",
    "royals", "twins", "astros", "angels", "athletics", "mariners", "rangers", "braves",
    "marlins", "mets", "phillies", "nationals", "cubs", "reds", "brewers", "pirates", "cardinals",
    "diamondbacks", "rockies", "dodgers", "padres", "giants",
    # Abbreviations
    "nyy", "bos", "tor", "tb", "bal", "cws", "cle", "det", "kc", "min", "hou", "laa", "oak",
    "sea", "tex", "atl", "mia", "nym", "phi", "was", "chc", "cin", "mil", "pit", "stl", "ari",
    "col", "lad", "sd", "sf"
]

# Crypto keywords (expanded)
CRYPTO_KEYWORDS = [
    "bitcoin", "btc", "ethereum", "eth", "crypto", "cryptocurrency", "blockchain", "solana", "sol",
    "cardano", "ada", "polygon", "matic", "avalanche", "avax", "chainlink", "link", "uniswap",
    "doge", "dogecoin", "shiba", "meme coin", "altcoin", "alt coin", "defi", "nft", "opensea",
    "blur", "fdv", "token", "coin", "price", "above", "below", "market cap", "marketcap",
    "up or down", "updown", "megaeth"
]

# Politics keywords (expanded)
POLITICS_KEYWORDS = [
    "election", "president", "senate", "governor", "congress", "house", "senator", "representative",
    "mayor", "vote", "voting", "ballot", "democrat", "republican", "primary", "caucus",
    "impeachment", "presidential", "nomination", "nominee", "candidate", "campaign", "poll",
    "biden", "trump", "harris", "pence", "youngkin", "desantis", "haley", "newsom"
]

# Macro keywords (expanded)
MACRO_KEYWORDS = [
    "fed", "federal reserve", "interest rate", "rates", "cpi", "inflation", "unemployment",
    "fomc", "federal open market committee", "gdp", "economic", "economy", "recession",
    "employment", "jobs report", "non-farm payroll", "nfp", "consumer price index", "bps",
    "basis points", "inflation rate", "unemployment rate", "gdp growth", "earnings",
    "quarterly earnings", "beat earnings", "eps", "gaap", "nongaap", "revenue", "profit",
    "loss", "shutdown", "government shutdown"
]

# Stocks/Companies keywords (NEW CATEGORY)
STOCKS_KEYWORDS = [
    # Stock tickers
    "tsla", "tesla", "nvda", "nvidia", "aapl", "apple", "msft", "microsoft", "googl", "google",
    "amzn", "amazon", "meta", "facebook", "pltr", "palantir", "gme", "gamestop", "amc",
    "nflx", "netflix", "dis", "disney", "twtr", "twitter", "x", "snap", "snapchat",
    # Stock-related terms
    "stock", "stocks", "share", "shares", "equity", "equities", "s&p", "sp500", "dow", "nasdaq",
    "ticker", "trading", "close above", "close below", "price target", "earnings report",
    "quarterly", "q1", "q2", "q3", "q4", "revenue", "eps", "beat", "miss", "guidance",
    "app store", "apple app store", "most searched", "top searched"
]

# Entertainment keywords (NEW CATEGORY)
ENTERTAINMENT_KEYWORDS = [
    # Movies/TV
    "movie", "film", "series", "tv show", "box office", "oscar", "emmy", "golden globe",
    "netflix", "top global netflix", "streaming", "cinema", "theater", "premiere",
    # Music
    "album", "song", "artist", "grammy", "billboard", "spotify", "chart", "top chart",
    "music", "single", "release", "hit", "number one", "#1",
    # Gaming/Esports
    "game", "gaming", "esports", "lol", "league of legends", "worlds", "worlds 2025",
    "cs2", "counter-strike", "valorant", "dota", "steam", "playstation", "xbox", "nintendo",
    "console", "console sales", "game release", "bo1", "bo5", "best of", "rolster", "gen.g",
    "ctbc", "flying oyster", "hanwha life esports", "t1", "kt rolster"
]

# Tech/Releases keywords (NEW CATEGORY)
TECH_KEYWORDS = [
    "release", "launch", "update", "version", "beta", "alpha", "app", "api",
    "ios", "android", "chatgpt", "openai", "sora", "gemini", "gpt", "ai",
    "artificial intelligence", "model", "be released", "will be released",
    "go live", "polymarket us", "us go live"
]


def classify_market(event: Dict[str, Any], slug: Optional[str] = None, question: Optional[str] = None) -> str:
    """
    Classify a market into a category based on event data, slug, and question text.
    
    Categories:
    - sports/NFL
    - sports/NBA
    - sports/NHL
    - sports/MLB
    - sports/Soccer
    - sports/Other
    - politics/US
    - politics/Global
    - macro/Fed
    - macro/Events
    - crypto/BTC
    - crypto/Altcoins
    - stocks/Companies
    - entertainment/Movies
    - entertainment/Music
    - entertainment/Gaming
    - tech/Releases
    - other/Unknown
    
    Args:
        event: Event dictionary from Gamma API (may contain category, groupType, tags)
        slug: Market slug (e.g., "will-trump-win-2024-election")
        question: Market question text
        
    Returns:
        str: Category string (e.g., "sports/NFL", "politics/US")
    """
    # Normalize inputs
    slug_lower = (slug or "").lower()
    question_lower = (question or "").lower()
    
    # Get event fields
    event_category = (event.get("category") or "").lower()
    event_group_type = (event.get("groupType") or "").lower()
    event_tags = event.get("tags", [])
    if isinstance(event_tags, str):
        event_tags = [event_tags]
    event_tags_lower = [str(tag).lower() for tag in event_tags if tag]
    
    # Combine all text for analysis
    all_text = f"{slug_lower} {question_lower} {event_category} {event_group_type} {' '.join(event_tags_lower)}"
    
    # Check categories in order of specificity
    # IMPORTANT: Tech and Entertainment BEFORE Politics to avoid false positives (e.g., "US Apple App Store" -> tech, not politics)
    
    # STOCKS CLASSIFICATION - MetaDAO/raise patterns FIRST (before tech/crypto, as they might contain crypto-like tokens)
    # Improved patterns: "over $Xm committed to the Y raise on metadao", "raise on metadao", "committed to raise"
    metadao_patterns = [
        r'\braise\s+on\s+metadao',
        r'\bcommitted\s+to\s+.*\s+raise\s+on\s+metadao',
        r'\bover\s+\$?\d+[km]?\s+committed\s+to\s+.*\s+raise\s+on\s+metadao',
        r'\bmetadao.*raise',
        r'\braise.*metadao'
    ]
    if "metadao" in all_text or any(re.search(pattern, all_text, re.IGNORECASE) for pattern in metadao_patterns):
        logger.debug(f"[CATEGORY] condition={slug[:30] if slug else 'N/A'}... → category=stocks/Companies")
        return "stocks/Companies"
    
    # Also check for "committed to raise" pattern (MetaDAO raises) - but exclude crypto
    if ("committed" in all_text and "raise" in all_text) or ("raise on" in all_text and "committed" in all_text):
        # Check if it's about MetaDAO or companies (not crypto)
        if not any(crypto in all_text for crypto in ["bitcoin", "btc", "ethereum", "eth", "solana", "sol", "crypto"]):
            logger.debug(f"[CATEGORY] condition={slug[:30] if slug else 'N/A'}... → category=stocks/Companies")
            return "stocks/Companies"
    
    # TECH CLASSIFICATION (check AFTER stocks to avoid conflicts with MetaDAO)
    if any(keyword in all_text for keyword in TECH_KEYWORDS):
        # Check for specific tech products
        if any(keyword in all_text for keyword in ["chatgpt", "openai", "sora", "gemini", "gpt", "ai", "artificial intelligence"]):
            logger.debug(f"[CATEGORY] condition={slug[:30] if slug else 'N/A'}... → category=tech/Releases")
            return "tech/Releases"
        # Check for app store / releases
        if any(keyword in all_text for keyword in ["app store", "apple app store", "be released", "will be released", "go live"]):
            logger.debug(f"[CATEGORY] condition={slug[:30] if slug else 'N/A'}... → category=tech/Releases")
            return "tech/Releases"
        # Generic tech release
        if re.search(r'\b(release|launch|update|version|beta|alpha)\b', all_text, re.IGNORECASE):
            logger.debug(f"[CATEGORY] condition={slug[:30] if slug else 'N/A'}... → category=tech/Releases")
            return "tech/Releases"
    
    # ENTERTAINMENT CLASSIFICATION (check BEFORE politics and BEFORE sports to avoid conflicts)
    # Movies/TV - check FIRST before sports to avoid false positives
    if any(keyword in all_text for keyword in ["netflix", "box office", "oscar", "emmy", "golden globe", "movie", "film", "series", "tv show"]):
        # Exclude if it's clearly about sports (e.g., "Los Angeles Dodgers" is MLB, not entertainment)
        # But use word boundaries to avoid false positives (e.g., "global" containing "bal" from MLB_TEAMS)
        # Check for explicit sports context first
        if "world series" in all_text or "super bowl" in all_text or "champions league" in all_text:
            # This is clearly sports, skip entertainment
            pass
        else:
            # Check for sports teams using word boundaries to avoid partial matches
            sports_team_patterns = [
                r'\bdodgers\b', r'\byankees\b', r'\bred sox\b', r'\bblue jays\b', r'\bworld series\b',
                r'\blakers\b', r'\bwarriors\b', r'\bceltics\b', r'\bheat\b', r'\bbulls\b',
                r'\bbruins\b', r'\bblackhawks\b', r'\bcapitals\b', r'\bstars\b',
                r'\bchiefs\b', r'\bpackers\b', r'\bcowboys\b', r'\bpatriots\b'
            ]
            has_sports_team = any(re.search(pattern, all_text, re.IGNORECASE) for pattern in sports_team_patterns)
            if not has_sports_team:
                logger.debug(f"[CATEGORY] condition={slug[:30] if slug else 'N/A'}... → category=entertainment/Movies")
                return "entertainment/Movies"
    
    # Music
    if any(keyword in all_text for keyword in ["grammy", "billboard", "spotify", "album", "song", "artist", "chart", "top chart", "music", "single"]):
        logger.debug(f"[CATEGORY] condition={slug[:30] if slug else 'N/A'}... → category=entertainment/Music")
        return "entertainment/Music"
    
    # STOCKS - Additional patterns (App Store rankings, searches) - BEFORE politics
    # Check for "searched person" or "most searched" patterns (these are about Google searches, not tech releases)
    if any(keyword in all_text for keyword in ["most searched", "top searched", "#1 searched", "searched person"]):
        logger.debug(f"[CATEGORY] condition={slug[:30] if slug else 'N/A'}... → category=stocks/Companies")
        return "stocks/Companies"
    
    # Check for App Store rankings
    if any(keyword in all_text for keyword in ["app store", "apple app store", "#1 free app"]):
        if any(keyword in all_text for keyword in ["chatgpt", "sora", "openai"]):
            logger.debug(f"[CATEGORY] condition={slug[:30] if slug else 'N/A'}... → category=tech/Releases")
            return "tech/Releases"
        logger.debug(f"[CATEGORY] condition={slug[:30] if slug else 'N/A'}... → category=stocks/Companies")
        return "stocks/Companies"
    
    # POLITICS CLASSIFICATION (check after tech/entertainment to avoid false positives)
    # BUT exclude if it's a sports match (has "vs" and sports teams)
    # Also exclude if it's entertainment (movies, music, etc.)
    vs_pattern = r'\b\w+\s+vs\.?\s+\w+\b'
    is_sports_match = re.search(vs_pattern, all_text, re.IGNORECASE)
    
    # Check for politics keywords, but exclude common false positives
    # "house" alone is not enough - need "house of representatives" or political context
    politics_matches = []
    for keyword in POLITICS_KEYWORDS:
        if keyword in all_text:
            # Special handling for "house" - only match if it's in political context
            if keyword == "house":
                # Check if it's "house of representatives" or "house of commons" or similar
                if re.search(r'\bhouse\s+of\s+(representatives|commons|lords)', all_text, re.IGNORECASE):
                    politics_matches.append(keyword)
                # Or if it's clearly political context (e.g., "house vote", "house passes")
                elif re.search(r'\bhouse\s+(vote|passes|approves|rejects|bill|act)', all_text, re.IGNORECASE):
                    politics_matches.append(keyword)
                # Skip if it's just "house" in a movie title or similar
            else:
                politics_matches.append(keyword)
    
    if politics_matches:
        # Exclude if it's entertainment (movies, music, etc.)
        if any(keyword in all_text for keyword in ["netflix", "movie", "film", "series", "tv show", "box office", "oscar", "emmy", "grammy", "billboard", "spotify", "album", "song", "artist"]):
            # Skip politics classification if it's clearly entertainment
            pass
        # Exclude if it's a sports match (e.g., "bruins vs. senators" is NHL, not politics)
        elif is_sports_match:
            # Check if it contains sports teams
            all_sports_teams = NFL_TEAMS + NBA_TEAMS + NHL_TEAMS + MLB_TEAMS
            if any(team in all_text for team in all_sports_teams):
                # This is likely a sports match, not politics
                pass  # Continue to sports classification
            else:
                # Check if US-specific
                us_keywords = ["us", "usa", "united states", "america", "american", "biden", "trump",
                              "harris", "pence", "congress", "senate", "house of representatives",
                              "electoral college", "electoral", "presidential election", "republican",
                              "democrat", "youngkin", "desantis", "haley"]
                if any(keyword in all_text for keyword in us_keywords):
                    logger.debug(f"[CATEGORY] condition={slug[:30] if slug else 'N/A'}... → category=politics/US")
                    return "politics/US"
                else:
                    logger.debug(f"[CATEGORY] condition={slug[:30] if slug else 'N/A'}... → category=politics/Global")
                    return "politics/Global"
        else:
            # Check if US-specific
            us_keywords = ["us", "usa", "united states", "america", "american", "biden", "trump",
                          "harris", "pence", "congress", "senate", "house of representatives",
                          "electoral college", "electoral", "presidential election", "republican",
                          "democrat", "youngkin", "desantis", "haley"]
            if any(keyword in all_text for keyword in us_keywords):
                logger.debug(f"[CATEGORY] condition={slug[:30] if slug else 'N/A'}... → category=politics/US")
                return "politics/US"
            else:
                logger.debug(f"[CATEGORY] condition={slug[:30] if slug else 'N/A'}... → category=politics/Global")
                return "politics/Global"
    
    # MACRO CLASSIFICATION
    if any(keyword in all_text for keyword in MACRO_KEYWORDS):
        logger.debug(f"[CATEGORY] condition={slug[:30] if slug else 'N/A'}... → category=macro/Fed")
        return "macro/Fed"
    
    
    # CRYPTO CLASSIFICATION (check before other stocks to avoid conflicts)
    # First check for "up or down" patterns (most common crypto pattern)
    # IMPROVED: Allow for dates/times after "up or down" (including "- october 10, 2:30pm" format)
    # Pattern matches: "bitcoin up or down", "bitcoin up or down on november 5", "bitcoin up or down - october 10"
    crypto_updown_pattern = r'\b(bitcoin|ethereum|solana|btc|eth|sol|xrp|cardano|ada|polygon|matic|avalanche|avax|chainlink|link|uniswap|doge|dogecoin|shiba)\s+up\s+or\s+down'
    if re.search(crypto_updown_pattern, all_text, re.IGNORECASE):
        # Check if BTC
        if re.search(r'\b(bitcoin|btc)\s+up\s+or\s+down', all_text, re.IGNORECASE):
            logger.debug(f"[CATEGORY] condition={slug[:30] if slug else 'N/A'}... → category=crypto/BTC")
            return "crypto/BTC"
        # Otherwise altcoins
        logger.debug(f"[CATEGORY] condition={slug[:30] if slug else 'N/A'}... → category=crypto/Altcoins")
        return "crypto/Altcoins"
    
    # Also check for crypto keywords with "up or down" pattern that might have been missed
    # This catches cases like "bitcoin" + "up or down" separated by other words
    if any(keyword in all_text for keyword in ["bitcoin", "btc", "ethereum", "eth", "solana", "sol", "xrp"]):
        if re.search(r'\bup\s+or\s+down', all_text, re.IGNORECASE):
            if re.search(r'\b(bitcoin|btc)\b', all_text, re.IGNORECASE):
                logger.debug(f"[CATEGORY] condition={slug[:30] if slug else 'N/A'}... → category=crypto/BTC")
                return "crypto/BTC"
            logger.debug(f"[CATEGORY] condition={slug[:30] if slug else 'N/A'}... → category=crypto/Altcoins")
            return "crypto/Altcoins"
    
    # Also check for "updown" (no spaces) pattern
    crypto_updown_compact = r'\b(bitcoin|ethereum|solana|btc|eth|sol|xrp|cardano|ada|polygon|matic|avalanche|avax|chainlink|link|uniswap|doge|dogecoin|shiba)\s+updown'
    if re.search(crypto_updown_compact, all_text, re.IGNORECASE):
        if re.search(r'\b(bitcoin|btc)\s+updown', all_text, re.IGNORECASE):
            logger.debug(f"[CATEGORY] condition={slug[:30] if slug else 'N/A'}... → category=crypto/BTC")
            return "crypto/BTC"
        logger.debug(f"[CATEGORY] condition={slug[:30] if slug else 'N/A'}... → category=crypto/Altcoins")
        return "crypto/Altcoins"
    
    # Check for crypto keywords (including "updown" standalone)
    if "updown" in all_text:
        # Check if it's about crypto (has crypto keywords nearby)
        crypto_context = r'\b(bitcoin|ethereum|solana|btc|eth|sol|xrp|cardano|ada|polygon|matic|avalanche|avax|chainlink|link|uniswap|doge|dogecoin|shiba)\b'
        if re.search(crypto_context, all_text, re.IGNORECASE):
            if re.search(r'\b(bitcoin|btc)\b', all_text, re.IGNORECASE):
                logger.debug(f"[CATEGORY] condition={slug[:30] if slug else 'N/A'}... → category=crypto/BTC")
                return "crypto/BTC"
            logger.debug(f"[CATEGORY] condition={slug[:30] if slug else 'N/A'}... → category=crypto/Altcoins")
            return "crypto/Altcoins"
    
    if any(keyword in all_text for keyword in CRYPTO_KEYWORDS):
        # Check for BTC specifically
        btc_keywords = ["bitcoin", "btc"]
        if any(keyword in all_text for keyword in btc_keywords):
            # Check if it's specifically about BTC (not altcoins)
            altcoin_keywords = ["ethereum", "eth", "solana", "sol", "cardano", "ada", "polygon",
                               "matic", "avalanche", "avax", "chainlink", "link", "uniswap",
                               "doge", "dogecoin", "shiba", "meme coin", "opensea", "blur", "fdv"]
            if not any(keyword in all_text for keyword in altcoin_keywords):
                logger.debug(f"[CATEGORY] condition={slug[:30] if slug else 'N/A'}... → category=crypto/BTC")
                return "crypto/BTC"
        
        # Altcoins
        altcoin_keywords = ["ethereum", "eth", "solana", "sol", "cardano", "ada", "polygon",
                           "matic", "avalanche", "avax", "chainlink", "link", "uniswap",
                           "doge", "dogecoin", "shiba", "meme coin", "altcoin", "alt coin",
                           "opensea", "blur", "fdv", "token"]
        if any(keyword in all_text for keyword in altcoin_keywords):
            logger.debug(f"[CATEGORY] condition={slug[:30] if slug else 'N/A'}... → category=crypto/Altcoins")
            return "crypto/Altcoins"
        
        # Generic crypto (fallback)
        logger.debug(f"[CATEGORY] condition={slug[:30] if slug else 'N/A'}... → category=crypto/Altcoins")
        return "crypto/Altcoins"
    
    # STOCKS CLASSIFICATION (check after crypto to avoid conflicts)
    # Check for stock tickers and "up or down" pattern
    stocks_updown_pattern = r'\b(tsla|tesla|nvda|nvidia|aapl|apple|msft|microsoft|googl|google|amzn|amazon|meta|facebook|pltr|palantir|gme|gamestop|amc)\s+up\s+or\s+down'
    if re.search(stocks_updown_pattern, all_text, re.IGNORECASE):
        logger.debug(f"[CATEGORY] condition={slug[:30] if slug else 'N/A'}... → category=stocks/Companies")
        return "stocks/Companies"
    
    # Check for stock keywords
    if any(keyword in all_text for keyword in STOCKS_KEYWORDS):
        # Check for "up or down" pattern with stock names (but not crypto)
        if re.search(r'\b(up\s+or\s+down|close\s+above|close\s+below)', all_text, re.IGNORECASE):
            # Make sure it's not crypto
            crypto_keywords_in_text = ["bitcoin", "btc", "ethereum", "eth", "solana", "sol", "crypto", "cryptocurrency"]
            if not any(ckw in all_text for ckw in crypto_keywords_in_text):
                logger.debug(f"[CATEGORY] condition={slug[:30] if slug else 'N/A'}... → category=stocks/Companies")
                return "stocks/Companies"
        # Check for stock ticker patterns like "(PLTR)", "(AAPL)", etc.
        if re.search(r'\([A-Z]{1,5}\)', all_text):
            logger.debug(f"[CATEGORY] condition={slug[:30] if slug else 'N/A'}... → category=stocks/Companies")
            return "stocks/Companies"
    
    # DATE-BASED CLASSIFICATION (check BEFORE sports to avoid false positives)
    # Check for deadline/event patterns FIRST
    deadline_patterns = [
        r'\b(deadline|event|happen|release|launch|announcement)\s+(on|by|before)\s+',
        r'\bby\s+(end\s+of\s+)?(january|february|march|april|may|june|july|august|september|october|november|december)\b',
        r'\b(deadline|event|happen|release|launch|announcement)\s+(on|by|before)\s+\d{4}',
    ]
    has_deadline_pattern = any(re.search(pattern, all_text, re.IGNORECASE) for pattern in deadline_patterns)
    
    date_patterns = [
        r'\d{4}-\d{2}-\d{2}',  # YYYY-MM-DD
        r'\d{1,2}/\d{1,2}/\d{4}',  # MM/DD/YYYY
        r'\b(january|february|march|april|may|june|july|august|september|october|november|december)\s+\d{1,2}\b',  # Month Day (word boundaries)
        r'\b\d{1,2}\s+(january|february|march|april|may|june|july|august|september|october|november|december)\b',  # Day Month (word boundaries)
    ]
    has_date_pattern = any(re.search(pattern, all_text, re.IGNORECASE) for pattern in date_patterns)
    
    if has_deadline_pattern or has_date_pattern:
        # Check if it's a sports date (has team names or sports keywords)
        # Use word boundaries to avoid false positives (e.g., "December" containing "ember")
        all_sports_teams = NFL_TEAMS + NBA_TEAMS + NHL_TEAMS + MLB_TEAMS
        has_sports_team = any(re.search(r'\b' + re.escape(team) + r'\b', all_text, re.IGNORECASE) for team in all_sports_teams)
        has_sports_keyword = any(keyword in all_text for keyword in ["game", "match", "vs", "versus", "championship", "playoff", "nfl", "nba", "nhl", "mlb"])
        
        if has_sports_team or has_sports_keyword:
            # Continue to sports classification below
            pass
        else:
            # It's likely a macro event or deadline
            logger.debug(f"[CATEGORY] Date pattern detected → macro/Events")
            return "macro/Events"
    
    # SPORTS CLASSIFICATION
    
    # Check for specific sports keywords first (to avoid false positives)
    # Tennis
    if "atp" in all_text or "wta" in all_text:
        logger.debug(f"[CATEGORY] condition={slug[:30] if slug else 'N/A'}... → category=sports/Other")
        return "sports/Other"
    
    # Golf
    if "masters" in all_text or "rolex" in all_text:
        logger.debug(f"[CATEGORY] condition={slug[:30] if slug else 'N/A'}... → category=sports/Other")
        return "sports/Other"
    
    # Esports/Gaming (check before general sports)
    esports_keywords = ["lol", "league of legends", "worlds", "worlds 2025", "cs2", "counter-strike",
                       "esports", "valorant", "dota", "rolster", "gen.g", "ctbc", "flying oyster",
                       "hanwha life esports", "t1", "kt rolster", "bo1", "bo5", "best of"]
    if any(keyword in all_text for keyword in esports_keywords):
        logger.debug(f"[CATEGORY] condition={slug[:30] if slug else 'N/A'}... → category=entertainment/Gaming")
        return "entertainment/Gaming"
    
    # Check for Soccer
    # First check for "will [team] win" pattern (common soccer pattern)
    # Improved: also check for dates in format "2025-11-01" or "on 2025-11-01"
    soccer_win_pattern = r'will\s+\w+\s+(win|fc|club|atlético|atletico)'
    soccer_date_pattern = r'\b(202[4-9]|20[3-9][0-9])-\d{2}-\d{2}\b'  # Matches dates like "2025-11-01"
    
    if re.search(soccer_win_pattern, all_text, re.IGNORECASE) or re.search(soccer_date_pattern, all_text):
        # Check for soccer teams
        soccer_teams = ["brighton", "arsenal", "barcelona", "madrid", "atlético", "atletico", "chelsea",
                       "liverpool", "manchester", "city", "united", "tottenham", "spurs", "newcastle",
                       "west ham", "aston villa", "crystal palace", "fulham", "wolves", "everton",
                       "burnley", "sheffield", "luton", "nottingham", "forest", "bournemouth", "brentford"]
        if any(team in all_text for team in soccer_teams) or "fc" in all_text or "club" in all_text:
            logger.debug(f"[CATEGORY] condition={slug[:30] if slug else 'N/A'}... → category=sports/Soccer")
            return "sports/Soccer"
    
    soccer_keywords = ["uefa", "uef", "fifa", "fif", "soccer", "world cup", "worldcup",
                      "champions league", "premier league", "la liga", "serie a", "bundesliga",
                      "euro", "euros", "copa", "confederations cup", "epl", "ucl", "psg", "paris",
                      "brighton", "arsenal", "barcelona", "madrid", "atlético", "atletico"]
    if any(keyword in all_text for keyword in soccer_keywords):
        logger.debug(f"[CATEGORY] condition={slug[:30] if slug else 'N/A'}... → category=sports/Soccer")
        return "sports/Soccer"
    
    # Check for explicit league indicators FIRST (before team checks)
    if "nfl" in all_text:
        logger.debug(f"[CATEGORY] condition={slug[:30] if slug else 'N/A'}... → category=sports/NFL")
        return "sports/NFL"
    if "nba" in all_text:
        logger.debug(f"[CATEGORY] condition={slug[:30] if slug else 'N/A'}... → category=sports/NBA")
        return "sports/NBA"
    if "nhl" in all_text:
        logger.debug(f"[CATEGORY] condition={slug[:30] if slug else 'N/A'}... → category=sports/NHL")
        return "sports/NHL"
    if "mlb" in all_text:
        logger.debug(f"[CATEGORY] condition={slug[:30] if slug else 'N/A'}... → category=sports/MLB")
        return "sports/MLB"
    
    # Check for Tennis tournaments FIRST (before NBA/NHL to avoid false positives)
    tennis_keywords = ["djokovic", "pegula", "rybakina", "paolini", "musetti", "djere", "spizzirri", 
                      "hellenic", "wta finals", "atp finals"]
    if any(keyword in all_text for keyword in tennis_keywords):
        # Check if it's a tennis match (has "vs" and tennis keywords)
        if "vs" in all_text or "versus" in all_text or "championship" in all_text or "finals" in all_text:
            logger.debug(f"[CATEGORY] condition={slug[:30] if slug else 'N/A'}... → category=sports/Other")
            return "sports/Other"
    
    # Check for Tennis BEFORE NBA/NHL checks (to catch "hellenic championship")
    if "hellenic" in all_text and ("vs" in all_text or "championship" in all_text):
        logger.debug(f"[CATEGORY] condition={slug[:30] if slug else 'N/A'}... → category=sports/Other")
        return "sports/Other"
    
    # Check for NHL FIRST in "vs" matches (to avoid false positives with NBA)
    # Check for specific NHL teams first (to avoid false positives with "senators" = politics)
    nhl_specific_teams = ["bruins", "blackhawks", "capitals", "stars", "jets", "senators", "lightning", 
                         "maple leafs", "hurricanes", "blue jackets", "devils", "islanders", "rangers", 
                         "flyers", "penguins", "avalanche", "wild", "predators", "blues", "ducks", 
                         "coyotes", "flames", "oilers", "sharks", "kraken", "canucks", 
                         "golden knights", "vegas", "sabres", "red wings", "panthers", "canadiens"]
    # Note: "kings" removed from nhl_specific_teams as it exists in both NBA and NHL
    # NBA-specific teams (not in NHL)
    nba_specific_teams = ["bulls", "heat", "lakers", "76ers", "sixers", "wizards", "raptors", "spurs", 
                         "pacers", "trail blazers", "blazers", "pelicans", "timberwolves", "wolves",
                         "grizzlies", "hornets", "magic", "pistons", "cavaliers", "cavs", "kings"]
    # Note: "kings" added to nba_specific_teams as it's more commonly NBA (Sacramento Kings)
    
    if is_sports_match:
        # If it's "Team vs Team" format, check both teams
        # Check for explicit league indicators first
        if "nfl" in all_text:
            logger.debug(f"[CATEGORY] condition={slug[:30] if slug else 'N/A'}... → category=sports/NFL")
            return "sports/NFL"
        if "nba" in all_text:
            logger.debug(f"[CATEGORY] condition={slug[:30] if slug else 'N/A'}... → category=sports/NBA")
            return "sports/NBA"
        if "nhl" in all_text:
            logger.debug(f"[CATEGORY] condition={slug[:30] if slug else 'N/A'}... → category=sports/NHL")
            return "sports/NHL"
        
        # Check teams (NHL before NFL to avoid false positives)
        has_nfl_team = any(team in all_text for team in NFL_TEAMS)
        has_nba_specific = any(team in all_text for team in nba_specific_teams)
        has_nhl_specific = any(team in all_text for team in nhl_specific_teams)
        
        if has_nhl_specific:
            logger.debug(f"[CATEGORY] condition={slug[:30] if slug else 'N/A'}... → category=sports/NHL")
            return "sports/NHL"
        elif has_nba_specific and not has_nfl_team:
            logger.debug(f"[CATEGORY] condition={slug[:30] if slug else 'N/A'}... → category=sports/NBA")
            return "sports/NBA"
        elif has_nfl_team:
            logger.debug(f"[CATEGORY] condition={slug[:30] if slug else 'N/A'}... → category=sports/NFL")
            return "sports/NFL"
    
    # Check for MLB FIRST (before NBA/NHL to avoid conflicts with city names)
    if any(team in all_text for team in MLB_TEAMS) or "mlb" in all_text or "world series" in all_text:
        logger.debug(f"[CATEGORY] condition={slug[:30] if slug else 'N/A'}... → category=sports/MLB")
        return "sports/MLB"
    
    # Check for NBA (after MLB check)
    if any(team in all_text for team in NBA_TEAMS) or "nba" in all_text:
        logger.debug(f"[CATEGORY] condition={slug[:30] if slug else 'N/A'}... → category=sports/NBA")
        return "sports/NBA"
    
    # Check for NHL (general check)
    if any(team in all_text for team in NHL_TEAMS) or "nhl" in all_text:
        logger.debug(f"[CATEGORY] condition={slug[:30] if slug else 'N/A'}... → category=sports/NHL")
        return "sports/NHL"
    
    # Check for NFL - improved pattern matching
    # Check for "Team vs Team" pattern first (most common)
    vs_pattern = r'\b\w+\s+vs\.?\s+\w+\b'
    if re.search(vs_pattern, all_text, re.IGNORECASE):
        # Check if it contains NFL team names
        if any(team in all_text for team in NFL_TEAMS):
            logger.debug(f"[CATEGORY] condition={slug[:30] if slug else 'N/A'}... → category=sports/NFL")
            return "sports/NFL"
        # Check for NBA teams
        if any(team in all_text for team in NBA_TEAMS):
            logger.debug(f"[CATEGORY] condition={slug[:30] if slug else 'N/A'}... → category=sports/NBA")
            return "sports/NBA"
        # Check for NHL teams
        if any(team in all_text for team in NHL_TEAMS):
            logger.debug(f"[CATEGORY] condition={slug[:30] if slug else 'N/A'}... → category=sports/NHL")
            return "sports/NHL"
        # Check for MLB teams
        if any(team in all_text for team in MLB_TEAMS):
            logger.debug(f"[CATEGORY] condition={slug[:30] if slug else 'N/A'}... → category=sports/MLB")
            return "sports/MLB"
    
    # Check for "spread:" pattern (common in NFL betting)
    if "spread:" in all_text or ("spread" in all_text and any(team in all_text for team in NFL_TEAMS)):
        logger.debug(f"[CATEGORY] condition={slug[:30] if slug else 'N/A'}... → category=sports/NFL")
        return "sports/NFL"
    
    # General NFL check
    if any(team in all_text for team in NFL_TEAMS) or "nfl" in all_text or "super bowl" in all_text or "superbowl" in all_text:
        logger.debug(f"[CATEGORY] condition={slug[:30] if slug else 'N/A'}... → category=sports/NFL")
        return "sports/NFL"
    
    
    # Check for other sports (general keywords)
    sports_keywords = ["basketball", "hockey", "baseball", "tennis", "golf", "olympics", "olympic",
                      "ncaa", "college football", "college basketball", "ufc", "boxing", "mma",
                      "formula 1", "f1", "nascar", "racing", "championship", "playoff", "ncaab",
                      "ncaaf", "march madness", "final four", "game winner"]
    if any(keyword in all_text for keyword in sports_keywords):
        logger.debug(f"[CATEGORY] condition={slug[:30] if slug else 'N/A'}... → category=sports/Other")
        return "sports/Other"
    
    # Gaming (already checked above in sports section, but double-check here)
    if any(keyword in all_text for keyword in ENTERTAINMENT_KEYWORDS):
        if any(keyword in all_text for keyword in ["game", "gaming", "steam", "playstation", "xbox", "nintendo", "console"]):
            logger.debug(f"[CATEGORY] condition={slug[:30] if slug else 'N/A'}... → category=entertainment/Gaming")
            return "entertainment/Gaming"
    
    # AGGRESSIVE FALLBACK CLASSIFICATION (to reduce Unknown %)
    
    # 1. Check event.category from API if available
    if event_category and event_category not in ["", "other", "unknown"]:
        # Map common API categories to our categories
        category_map = {
            "sports": "sports/Other",
            "politics": "politics/US",
            "crypto": "crypto/BTC",
            "macro": "macro/Fed",
            "entertainment": "entertainment/Movies",
            "tech": "tech/Releases"
        }
        mapped_category = category_map.get(event_category)
        if mapped_category:
            logger.debug(f"[CATEGORY] Using event.category={event_category} → {mapped_category}")
            return mapped_category
    
    # 2. Number/price-based classification
    price_patterns = [
        r'\$[\d,]+',  # $100,000
        r'\d+\.\d+%',  # 5.5%
        r'\d+%',  # 5%
        r'\d+[km]',  # 100k, 5m
    ]
    if any(re.search(pattern, all_text) for pattern in price_patterns):
        # Check context
        if any(keyword in all_text for keyword in ["bitcoin", "btc", "ethereum", "eth", "crypto", "cryptocurrency"]):
            logger.debug(f"[CATEGORY] Price + crypto context → crypto/BTC")
            return "crypto/BTC"
        elif any(keyword in all_text for keyword in ["stock", "share", "nasdaq", "sp500", "dow", "tsla", "aapl", "nvda"]):
            logger.debug(f"[CATEGORY] Price + stock context → stocks/Companies")
            return "stocks/Companies"
        elif any(keyword in all_text for keyword in ["fed", "federal reserve", "interest rate", "inflation", "gdp"]):
            logger.debug(f"[CATEGORY] Price + macro context → macro/Fed")
            return "macro/Fed"
        else:
            # Generic price → likely macro or crypto
            logger.debug(f"[CATEGORY] Price pattern detected → macro/Fed")
            return "macro/Fed"
    
    # 4. Very short text classification (use ML more aggressively)
    combined_text = f"{question_lower} {slug_lower}".strip()
    if combined_text and len(combined_text) < 30:
        try:
            from ml_classifier import classify_with_ml
            ml_category = classify_with_ml(combined_text)
            if ml_category and ml_category != "other/Unknown":
                logger.debug(f"[CATEGORY] ML (short text) classified '{combined_text[:50]}...' as '{ml_category}'")
                return ml_category
        except Exception as e:
            logger.debug(f"[CATEGORY] ML classification failed: {e}")
    
    # 5. Try ML classifier as fallback (standard)
    if combined_text:
        try:
            from ml_classifier import classify_with_ml
            ml_category = classify_with_ml(combined_text)
            if ml_category and ml_category != "other/Unknown":
                logger.debug(f"[CATEGORY] ML classified '{combined_text[:50]}...' as '{ml_category}'")
                return ml_category
        except Exception as e:
            logger.debug(f"[CATEGORY] ML classification failed: {e}")
    
    # 6. Very aggressive ML fallback (even lower threshold)
    if combined_text:
        try:
            from ml_classifier import classify_with_ml
            # Try to get prediction even with very low confidence
            import sys
            import os
            sys.path.insert(0, os.path.dirname(__file__))
            from ml_classifier import SKLEARN_AVAILABLE
            if SKLEARN_AVAILABLE:
                from sklearn.feature_extraction.text import TfidfVectorizer
                from sklearn.linear_model import LogisticRegression
                from sklearn.pipeline import Pipeline
                from ml_classifier import TRAINING_DATA
                
                # Quick ML prediction with very low threshold
                texts = [text for text, _ in TRAINING_DATA]
                labels = [label for _, label in TRAINING_DATA]
                
                pipeline = Pipeline([
                    ('tfidf', TfidfVectorizer(max_features=500, ngram_range=(1, 2))),
                    ('clf', LogisticRegression(max_iter=1000, random_state=42))
                ])
                pipeline.fit(texts, labels)
                
                prediction = pipeline.predict([combined_text.lower()])[0]
                probabilities = pipeline.predict_proba([combined_text.lower()])[0]
                max_prob = max(probabilities)
                
                # Very aggressive: accept even 1% confidence (reduced from 5%)
                if max_prob > 0.01 and prediction != "other/Unknown":
                    logger.debug(f"[CATEGORY] Aggressive ML classified '{combined_text[:50]}...' as '{prediction}' (confidence: {max_prob:.2f})")
                    return prediction
        except Exception as e:
            logger.debug(f"[CATEGORY] Aggressive ML failed: {e}")
    
    # 7. Slug/condition_id pattern classification (before context heuristics)
    # Many Unknown markets have patterns in slug/condition_id
    slug_text = slug_lower or ""
    condition_id_text = ""  # Can extract from condition_id if available
    
    # Check slug patterns
    if slug_text:
        # NFL patterns in slug
        if re.search(r'nfl-|nfl_|nfl\s', slug_text) or any(team in slug_text for team in ["bal-", "mia-", "car-", "atl-", "sf-", "ari-", "phi-", "gb-", "jax-", "hou-"]):
            logger.debug(f"[CATEGORY] Slug pattern: NFL → sports/NFL")
            return "sports/NFL"
        
        # NBA patterns
        if re.search(r'nba-|nba_|nba\s', slug_text):
            logger.debug(f"[CATEGORY] Slug pattern: NBA → sports/NBA")
            return "sports/NBA"
        
        # Crypto patterns
        if re.search(r'bitcoin|btc-|btc_|btc\s', slug_text, re.IGNORECASE):
            logger.debug(f"[CATEGORY] Slug pattern: Bitcoin → crypto/BTC")
            return "crypto/BTC"
        
        if re.search(r'ethereum|eth-|eth_|eth\s|solana|sol-|sol_', slug_text, re.IGNORECASE):
            logger.debug(f"[CATEGORY] Slug pattern: Altcoin → crypto/Altcoins")
            return "crypto/Altcoins"
        
        # Up or down patterns in slug
        if re.search(r'up-or-down|updown|up-down', slug_text, re.IGNORECASE):
            if "bitcoin" in slug_text or "btc" in slug_text:
                return "crypto/BTC"
            elif "ethereum" in slug_text or "eth" in slug_text:
                return "crypto/Altcoins"
            else:
                return "crypto/BTC"  # Default to BTC for up/down
        
        # LoL/Gaming patterns
        if re.search(r'lol-|lol_|lol\s|cs2-|cs2_|counter-strike', slug_text, re.IGNORECASE):
            logger.debug(f"[CATEGORY] Slug pattern: Gaming → entertainment/Gaming")
            return "entertainment/Gaming"
        
        # ATP/Tennis patterns
        if re.search(r'atp-|atp_|atp\s|tennis', slug_text, re.IGNORECASE):
            logger.debug(f"[CATEGORY] Slug pattern: Tennis → sports/Other")
            return "sports/Other"
        
        # Date patterns in slug (YYYY-MM-DD)
        if re.search(r'\d{4}-\d{2}-\d{2}', slug_text):
            # If it's a sports slug with date, classify as sports
            if any(sport in slug_text for sport in ["nfl", "nba", "nhl", "mlb", "lol", "cs2", "atp"]):
                if "nfl" in slug_text:
                    return "sports/NFL"
                elif "nba" in slug_text:
                    return "sports/NBA"
                elif "lol" in slug_text or "cs2" in slug_text:
                    return "entertainment/Gaming"
                else:
                    return "sports/Other"
            # Otherwise, it's likely a macro event
            logger.debug(f"[CATEGORY] Slug pattern: Date → macro/Events")
            return "macro/Events"
    
    # 8. Context-based heuristics (last resort)
    # If we have ANY text, try to infer category from minimal clues
    if combined_text:
        # Check for common patterns even in short/partial text
        
        # Election patterns (check FIRST before up/down to avoid false positives)
        if re.search(r'\b(win|winner|election|vote|president|senate|house|parliamentary)\b', combined_text, re.IGNORECASE):
            if any(kw in combined_text for kw in ["us", "usa", "united states", "biden", "trump", "harris"]):
                logger.debug(f"[CATEGORY] Heuristic: US election pattern → politics/US")
                return "politics/US"
            else:
                logger.debug(f"[CATEGORY] Heuristic: election pattern → politics/Global")
                return "politics/Global"
        
        # Spread/O/U patterns (NFL betting)
        if re.search(r'\bspread\b|o/u|over/under', combined_text, re.IGNORECASE):
            logger.debug(f"[CATEGORY] Heuristic: spread/o/u pattern → sports/NFL")
            return "sports/NFL"
        
        # Up or down patterns (very common in Unknown)
        if re.search(r'\bup\s+or\s+down\b|\bupdown\b|\bup-down\b', combined_text, re.IGNORECASE):
            if any(kw in combined_text for kw in ["bitcoin", "btc"]):
                logger.debug(f"[CATEGORY] Heuristic: up/down + bitcoin → crypto/BTC")
                return "crypto/BTC"
            elif any(kw in combined_text for kw in ["ethereum", "eth", "solana", "sol"]):
                logger.debug(f"[CATEGORY] Heuristic: up/down + altcoin → crypto/Altcoins")
                return "crypto/Altcoins"
            else:
                # Generic up/down → likely crypto
                logger.debug(f"[CATEGORY] Heuristic: up/down pattern → crypto/BTC")
                return "crypto/BTC"
        
        # Spread/O/U patterns (NFL betting)
        if re.search(r'\bspread\b|o/u|over/under', combined_text, re.IGNORECASE):
            logger.debug(f"[CATEGORY] Heuristic: spread/o/u pattern → sports/NFL")
            return "sports/NFL"
        
        # Election patterns
        if re.search(r'\b(win|winner|election|vote|president|senate|house|parliamentary)\b', combined_text, re.IGNORECASE):
            if any(kw in combined_text for kw in ["us", "usa", "united states", "biden", "trump", "harris"]):
                logger.debug(f"[CATEGORY] Heuristic: US election pattern → politics/US")
                return "politics/US"
            else:
                logger.debug(f"[CATEGORY] Heuristic: election pattern → politics/Global")
                return "politics/Global"
        
        # Price patterns
        elif re.search(r'\b(price|above|below|close|reach|hit)\b', combined_text, re.IGNORECASE):
            # Generic price movement → likely crypto or macro
            if any(kw in combined_text for kw in ["bitcoin", "btc", "crypto"]):
                logger.debug(f"[CATEGORY] Heuristic: price + crypto → crypto/BTC")
                return "crypto/BTC"
            elif any(kw in combined_text for kw in ["ethereum", "eth", "solana", "sol"]):
                logger.debug(f"[CATEGORY] Heuristic: price + altcoin → crypto/Altcoins")
                return "crypto/Altcoins"
            else:
                logger.debug(f"[CATEGORY] Heuristic: price pattern → macro/Fed")
                return "macro/Fed"
        
        # Game/match patterns
        elif re.search(r'\b(game|match|vs|versus|team|player|winner)\b', combined_text, re.IGNORECASE):
            # Check for specific sports
            if any(kw in combined_text for kw in ["nfl", "football", "super bowl"]):
                logger.debug(f"[CATEGORY] Heuristic: game + NFL → sports/NFL")
                return "sports/NFL"
            elif any(kw in combined_text for kw in ["nba", "basketball"]):
                logger.debug(f"[CATEGORY] Heuristic: game + NBA → sports/NBA")
                return "sports/NBA"
            elif any(kw in combined_text for kw in ["lol", "league of legends", "cs2", "counter-strike"]):
                logger.debug(f"[CATEGORY] Heuristic: game + esports → entertainment/Gaming")
                return "entertainment/Gaming"
            else:
                logger.debug(f"[CATEGORY] Heuristic: game/match pattern → sports/Other")
                return "sports/Other"
        
        # Month/year patterns (dates)
        elif re.search(r'\b(november|october|december|january|february|march|april|may|june|july|august|september)\s+\d+|\b(202[4-9]|20[3-9][0-9])\b', combined_text, re.IGNORECASE):
            # If it's clearly crypto with date
            if any(kw in combined_text for kw in ["bitcoin", "btc", "ethereum", "eth", "up or down", "updown"]):
                if "bitcoin" in combined_text or "btc" in combined_text:
                    return "crypto/BTC"
                else:
                    return "crypto/Altcoins"
            # If it's clearly sports with date
            elif any(kw in combined_text for kw in ["nfl", "nba", "vs", "versus", "game"]):
                if "nfl" in combined_text:
                    return "sports/NFL"
                elif "nba" in combined_text:
                    return "sports/NBA"
                else:
                    return "sports/Other"
            # Otherwise, generic date → macro/Events
            else:
                logger.debug(f"[CATEGORY] Heuristic: date pattern → macro/Events")
                return "macro/Events"
    
    # DEFAULT: Unknown (only if absolutely no data or patterns)
    logger.debug(f"[CATEGORY] condition={slug[:30] if slug else 'N/A'}... → category=other/Unknown")
    return "other/Unknown"

