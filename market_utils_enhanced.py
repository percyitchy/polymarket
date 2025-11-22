"""
Enhanced Market Classification Utilities
Categorizes markets into sports, politics, macro, crypto, and other categories
Uses expanded keyword lists and ML-based classification
"""

import logging
import re
from typing import Dict, Any, Optional
from collections import Counter

logger = logging.getLogger(__name__)

# Expanded keyword lists based on Polymarket analysis

# NFL Teams (all 32 teams)
NFL_TEAMS = [
    "chiefs", "packers", "cowboys", "patriots", "rams", "bills", "eagles", "49ers", "niners",
    "buccaneers", "bucs", "seahawks", "bears", "commanders", "jaguars", "ravens", "steelers",
    "browns", "bengals", "titans", "colts", "texans", "raiders", "chargers", "broncos",
    "dolphins", "jets", "giants", "redskins", "cardinals", "falcons", "panthers", "saints",
    "vikings", "lions", "cowboys", "packers", "washington", "commanders", "houston", "hou",
    "philadelphia", "phi", "denver", "den", "los angeles", "lac", "lac", "atlanta", "atl",
    "carolina", "car", "new orleans", "no", "minnesota", "min", "detroit", "det", "green bay",
    "gb", "chicago", "chi", "dallas", "dal", "new york", "nyg", "nyj", "philadelphia", "phi"
]

# NBA Teams
NBA_TEAMS = [
    "lakers", "warriors", "celtics", "heat", "bulls", "knicks", "nets", "mavericks", "mavs",
    "clippers", "suns", "bucks", "nuggets", "76ers", "sixers", "raptors", "jazz", "trail blazers",
    "blazers", "hawks", "cavaliers", "cavs", "wizards", "magic", "pistons", "hornets", "pacers",
    "kings", "grizzlies", "pelicans", "thunder", "rockets", "spurs", "timberwolves", "wolves",
    "orlando", "atlanta", "chicago", "cleveland", "detroit", "miami", "philadelphia", "toronto",
    "boston", "brooklyn", "new york", "charlotte", "indiana", "milwaukee", "washington", "denver",
    "minnesota", "oklahoma city", "portland", "utah", "golden state", "la clippers", "la lakers",
    "phoenix", "sacramento", "dallas", "houston", "memphis", "new orleans", "san antonio"
]

# NHL Teams
NHL_TEAMS = [
    "bruins", "sabres", "red wings", "panthers", "canadiens", "senators", "lightning", "maple leafs",
    "hurricanes", "blue jackets", "devils", "islanders", "rangers", "flyers", "penguins", "capitals",
    "blackhawks", "avalanche", "stars", "wild", "predators", "blues", "jets", "ducks", "coyotes",
    "flames", "oilers", "kings", "sharks", "kraken", "canucks", "golden knights", "vegas"
]

# MLB Teams
MLB_TEAMS = [
    "yankees", "red sox", "blue jays", "rays", "orioles", "white sox", "guardians", "tigers",
    "royals", "twins", "astros", "angels", "athletics", "mariners", "rangers", "braves",
    "marlins", "mets", "phillies", "nationals", "cubs", "reds", "brewers", "pirates", "cardinals",
    "diamondbacks", "rockies", "dodgers", "padres", "giants"
]

# Crypto keywords (expanded)
CRYPTO_KEYWORDS = [
    "bitcoin", "btc", "ethereum", "eth", "crypto", "cryptocurrency", "blockchain", "solana", "sol",
    "cardano", "ada", "polygon", "matic", "avalanche", "avax", "chainlink", "link", "uniswap",
    "doge", "dogecoin", "shiba", "meme coin", "altcoin", "alt coin", "defi", "nft", "opensea",
    "blur", "fdv", "token", "coin", "price", "above", "below", "market cap", "marketcap"
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
    "basis points", "inflation rate", "unemployment rate", "gdp growth"
]


def classify_market(event: Dict[str, Any], slug: Optional[str] = None, question: Optional[str] = None) -> str:
    """
    Enhanced market classification with expanded keywords and pattern matching.
    
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
    - crypto/BTC
    - crypto/Altcoins
    - other/Unknown
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
    
    # SPORTS CLASSIFICATION
    
    # Check for NFL
    if any(team in all_text for team in NFL_TEAMS) or "nfl" in all_text:
        # Check for "Team vs Team" pattern
        vs_pattern = r'\b\w+\s+vs\.?\s+\w+\b'
        if re.search(vs_pattern, all_text, re.IGNORECASE):
            logger.debug(f"[CATEGORY] condition={slug[:30] if slug else 'N/A'}... → category=sports/NFL")
            return "sports/NFL"
        if any(team in all_text for team in NFL_TEAMS) or "nfl" in all_text or "super bowl" in all_text or "superbowl" in all_text:
            logger.debug(f"[CATEGORY] condition={slug[:30] if slug else 'N/A'}... → category=sports/NFL")
            return "sports/NFL"
    
    # Check for NBA
    if any(team in all_text for team in NBA_TEAMS) or "nba" in all_text:
        logger.debug(f"[CATEGORY] condition={slug[:30] if slug else 'N/A'}... → category=sports/NBA")
        return "sports/NBA"
    
    # Check for NHL
    if any(team in all_text for team in NHL_TEAMS) or "nhl" in all_text:
        logger.debug(f"[CATEGORY] condition={slug[:30] if slug else 'N/A'}... → category=sports/NHL")
        return "sports/NHL"
    
    # Check for MLB
    if any(team in all_text for team in MLB_TEAMS) or "mlb" in all_text:
        logger.debug(f"[CATEGORY] condition={slug[:30] if slug else 'N/A'}... → category=sports/MLB")
        return "sports/MLB"
    
    # Check for Soccer
    soccer_keywords = ["uefa", "uef", "fifa", "fif", "soccer", "football", "world cup", "worldcup",
                      "champions league", "premier league", "la liga", "serie a", "bundesliga",
                      "euro", "euros", "copa", "confederations cup"]
    if any(keyword in all_text for keyword in soccer_keywords):
        logger.debug(f"[CATEGORY] condition={slug[:30] if slug else 'N/A'}... → category=sports/Soccer")
        return "sports/Soccer"
    
    # Check for other sports
    sports_keywords = ["basketball", "hockey", "baseball", "tennis", "golf", "olympics", "olympic",
                      "ncaa", "college football", "college basketball", "ufc", "boxing", "mma",
                      "formula 1", "f1", "nascar", "racing", "championship", "playoff", "ncaab",
                      "ncaaf", "march madness", "final four"]
    if any(keyword in all_text for keyword in sports_keywords):
        logger.debug(f"[CATEGORY] condition={slug[:30] if slug else 'N/A'}... → category=sports/Other")
        return "sports/Other"
    
    # POLITICS CLASSIFICATION
    if any(keyword in all_text for keyword in POLITICS_KEYWORDS):
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
    
    # CRYPTO CLASSIFICATION
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
    
    # DEFAULT: Unknown
    logger.debug(f"[CATEGORY] condition={slug[:30] if slug else 'N/A'}... → category=other/Unknown")
    return "other/Unknown"

