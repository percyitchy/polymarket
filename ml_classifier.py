"""
ML-based market classifier as fallback for rule-based classification
Uses TF-IDF and Logistic Regression for text classification
Requires scikit-learn: pip install scikit-learn
"""

import logging
import pickle
import os
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

# Try to import sklearn, make it optional
try:
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.linear_model import LogisticRegression
    from sklearn.pipeline import Pipeline
    import numpy as np
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False
    logger.warning("[ML] scikit-learn not available. ML classification will be disabled. Install with: pip install scikit-learn")

# Training data based on known patterns from real Polymarket data
TRAINING_DATA = [
    # Sports/NFL (expanded with real examples)
    ("buccaneers vs seahawks", "sports/NFL"),
    ("bears vs commanders", "sports/NFL"),
    ("jaguars vs 49ers", "sports/NFL"),
    ("cowboys vs bears", "sports/NFL"),
    ("dolphins vs panthers", "sports/NFL"),
    ("bears vs raiders", "sports/NFL"),
    ("texans vs jaguars", "sports/NFL"),
    ("seahawks vs cardinals", "sports/NFL"),
    ("spread patriots", "sports/NFL"),
    ("spread eagles", "sports/NFL"),
    ("spread packers", "sports/NFL"),
    ("spread broncos", "sports/NFL"),
    ("cowboys vs jets", "sports/NFL"),
    ("broncos vs chargers", "sports/NFL"),
    ("raiders vs commanders", "sports/NFL"),
    ("rams vs eagles", "sports/NFL"),
    ("colts vs titans", "sports/NFL"),
    ("nfl game", "sports/NFL"),
    ("super bowl", "sports/NFL"),
    ("nfl-tb-sea", "sports/NFL"),
    ("nfl-chi-was", "sports/NFL"),
    ("nfl-jax-sf", "sports/NFL"),
    
    # Sports/NBA
    ("lakers vs warriors", "sports/NBA"),
    ("celtics vs 76ers", "sports/NBA"),
    ("bucks vs hornets", "sports/NBA"),
    ("bulls vs pistons", "sports/NBA"),
    ("raptors vs pacers", "sports/NBA"),
    ("nba game", "sports/NBA"),
    ("nba-chi-det", "sports/NBA"),
    ("nba-tor-ind", "sports/NBA"),
    
    # Sports/NHL
    ("bruins vs rangers", "sports/NHL"),
    ("nhl game", "sports/NHL"),
    
    # Sports/Other
    ("atp tennis", "sports/Other"),
    ("masters golf", "sports/Other"),
    ("rolex masters", "sports/Other"),
    ("lol t1 vs kt", "sports/Other"),
    ("lol t1 vs kt rolster", "sports/Other"),
    ("cs2 game", "sports/Other"),
    ("uef", "sports/Other"),
    ("epl", "sports/Other"),
    ("ucl", "sports/Other"),
    ("psg paris", "sports/Other"),
    
    # Crypto/BTC
    ("bitcoin price", "crypto/BTC"),
    ("bitcoin above", "crypto/BTC"),
    ("bitcoin below", "crypto/BTC"),
    ("bitcoin up or down", "crypto/BTC"),
    ("btc price", "crypto/BTC"),
    ("btc updown", "crypto/BTC"),
    ("bitcoin above 104000", "crypto/BTC"),
    
    # Crypto/Altcoins
    ("ethereum up or down", "crypto/Altcoins"),
    ("ethereum price", "crypto/Altcoins"),
    ("eth updown", "crypto/Altcoins"),
    ("eth up or down", "crypto/Altcoins"),
    ("megaeth", "crypto/Altcoins"),
    
    # Politics/US
    ("biden election", "politics/US"),
    ("trump election", "politics/US"),
    ("presidential election", "politics/US"),
    ("republican nomination", "politics/US"),
    
    # Politics/Global
    ("chilean presidential election", "politics/Global"),
    ("will johannes kaiser win", "politics/Global"),
    ("election winner", "politics/Global"),
    
    # Macro/Fed
    ("fed interest rates", "macro/Fed"),
    ("fed decreases interest rates", "macro/Fed"),
    ("federal reserve", "macro/Fed"),
    ("government shutdown", "macro/Fed"),
    
    # Macro/Events (NEW - for date-based events)
    ("will happen on", "macro/Events"),
    ("deadline", "macro/Events"),
    ("by end of", "macro/Events"),
    ("by december", "macro/Events"),
    ("by november", "macro/Events"),
    ("by january", "macro/Events"),
    ("on 2025", "macro/Events"),
    ("on 2024", "macro/Events"),
    ("event on", "macro/Events"),
    ("announcement on", "macro/Events"),
    ("release on", "macro/Events"),
    ("launch on", "macro/Events"),
    
    # Stocks/Companies (NEW CATEGORY)
    ("tesla up or down", "stocks/Companies"),
    ("tsla up or down", "stocks/Companies"),
    ("palantir pltr up or down", "stocks/Companies"),
    ("apple aapl up or down", "stocks/Companies"),
    ("nvidia nvda up or down", "stocks/Companies"),
    ("will palantir pltr close above", "stocks/Companies"),
    ("will tesla close above", "stocks/Companies"),
    ("will apple close above", "stocks/Companies"),
    ("nvidia nvda up or down on november", "stocks/Companies"),
    ("palantir pltr up or down on november", "stocks/Companies"),
    ("apple aapl up or down on november", "stocks/Companies"),
    ("over 10m committed to the zklsol raise on metadao", "stocks/Companies"),
    ("over 100m committed to the avici raise on metadao", "stocks/Companies"),
    
    # Entertainment/Gaming
    ("lol worlds 2025", "entertainment/Gaming"),
    ("will t1 win lol worlds 2025", "entertainment/Gaming"),
    ("kt rolster vs gen.g", "entertainment/Gaming"),
    ("lol gen.g vs kt rolster bo5", "entertainment/Gaming"),
    ("cs2 game", "entertainment/Gaming"),
    ("valorant tournament", "entertainment/Gaming"),
    
    # Entertainment/Movies
    ("top global netflix movie", "entertainment/Movies"),
    ("box office", "entertainment/Movies"),
    ("oscar winner", "entertainment/Movies"),
    ("emmy award", "entertainment/Movies"),
    
    # Entertainment/Music
    ("grammy winner", "entertainment/Music"),
    ("billboard number one", "entertainment/Music"),
    ("spotify top chart", "entertainment/Music"),
    
    # Tech/Releases
    ("will gemini 3.0 be released", "tech/Releases"),
    ("chatgpt app store", "tech/Releases"),
    ("sora app store", "tech/Releases"),
    ("will polymarket us go live", "tech/Releases"),
    ("openai release", "tech/Releases"),
    
    # Additional examples from real Unknown markets analysis
    # Crypto with dates/times
    ("bitcoin up or down november", "crypto/BTC"),
    ("bitcoin up or down october", "crypto/BTC"),
    ("ethereum up or down november", "crypto/Altcoins"),
    ("ethereum up or down october", "crypto/Altcoins"),
    ("bitcoin price above", "crypto/BTC"),
    ("bitcoin price below", "crypto/BTC"),
    
    # Sports with dates
    ("nfl game october", "sports/NFL"),
    ("nfl game november", "sports/NFL"),
    ("nba game october", "sports/NBA"),
    ("nba game november", "sports/NBA"),
    
    # Generic patterns that should be classified
    ("will happen", "macro/Events"),
    ("will be", "macro/Events"),
    ("will close", "macro/Fed"),
    ("will exceed", "macro/Fed"),
    ("will reach", "macro/Fed"),
    ("will hit", "macro/Fed"),
    
    # Price patterns
    ("price above", "crypto/BTC"),
    ("price below", "crypto/BTC"),
    ("close above", "crypto/BTC"),
    ("close below", "crypto/BTC"),
    
    # Election patterns
    ("will win election", "politics/US"),
    ("election winner", "politics/US"),
    ("presidential", "politics/US"),
    
    # More specific crypto patterns
    ("btc updown", "crypto/BTC"),
    ("eth updown", "crypto/Altcoins"),
    ("sol updown", "crypto/Altcoins"),
    
    # More sports patterns
    ("vs", "sports/Other"),
    ("versus", "sports/Other"),
    ("game winner", "sports/Other"),
    ("championship", "sports/Other"),
    
    # Real examples from Unknown markets analysis
    # Crypto with dates (very common pattern)
    ("bitcoin up or down november", "crypto/BTC"),
    ("bitcoin up or down october", "crypto/BTC"),
    ("bitcoin up or down december", "crypto/BTC"),
    ("ethereum up or down november", "crypto/Altcoins"),
    ("ethereum up or down october", "crypto/Altcoins"),
    ("solana up or down november", "crypto/Altcoins"),
    ("bitcoin up or down 2025", "crypto/BTC"),
    ("ethereum up or down 2025", "crypto/Altcoins"),
    
    # Crypto price patterns
    ("bitcoin price above", "crypto/BTC"),
    ("bitcoin price below", "crypto/BTC"),
    ("price of bitcoin", "crypto/BTC"),
    ("price of ethereum", "crypto/Altcoins"),
    ("bitcoin above 110000", "crypto/BTC"),
    ("bitcoin above 118000", "crypto/BTC"),
    
    # Sports with dates
    ("ravens vs dolphins", "sports/NFL"),
    ("panthers vs falcons", "sports/NFL"),
    ("49ers vs cardinals", "sports/NFL"),
    ("eagles vs packers", "sports/NFL"),
    ("jaguars vs texans", "sports/NFL"),
    ("nfl november", "sports/NFL"),
    ("nfl october", "sports/NFL"),
    
    # LoL/Gaming
    ("lol t1 vs kt rolster", "entertainment/Gaming"),
    ("lol t1 vs kt", "entertainment/Gaming"),
    ("lol game winner", "entertainment/Gaming"),
    ("lol bo5", "entertainment/Gaming"),
    
    # Politics
    ("netherlands parliamentary election", "politics/Global"),
    ("d66 vs vvd", "politics/Global"),
    ("trump election", "politics/US"),
    ("presidential election", "politics/US"),
    
    # Generic date patterns
    ("november 13", "macro/Events"),
    ("november 11", "macro/Events"),
    ("november 10", "macro/Events"),
    ("october 29", "macro/Events"),
    ("october 25", "macro/Events"),
    ("2025", "macro/Events"),
    ("2026", "macro/Events"),
    
    # Short patterns
    ("updown", "crypto/BTC"),
    ("up-down", "crypto/BTC"),
    ("spread", "sports/NFL"),
    ("o/u", "sports/NFL"),
]

# Initialize classifier
_classifier = None
_vectorizer = None

def _train_classifier():
    """Train ML classifier on training data"""
    global _classifier, _vectorizer
    
    if not SKLEARN_AVAILABLE:
        return None, None
    
    if _classifier is not None:
        return _classifier, _vectorizer
    
    try:
        # Prepare training data
        texts = [text for text, _ in TRAINING_DATA]
        labels = [label for _, label in TRAINING_DATA]
        
        # Create pipeline
        _classifier = Pipeline([
            ('tfidf', TfidfVectorizer(max_features=1000, ngram_range=(1, 2))),
            ('clf', LogisticRegression(max_iter=1000, random_state=42))
        ])
        
        # Train
        _classifier.fit(texts, labels)
        
        logger.info(f"[ML] Trained classifier on {len(TRAINING_DATA)} examples")
        return _classifier, _classifier.named_steps['tfidf']
    except Exception as e:
        logger.warning(f"[ML] Failed to train classifier: {e}")
        return None, None

def classify_with_ml(text: str) -> Optional[str]:
    """
    Classify text using ML classifier
    
    Args:
        text: Text to classify
        
    Returns:
        Category string or None if classification fails
    """
    if not SKLEARN_AVAILABLE:
        return None
    
    if not text or len(text.strip()) < 3:
        return None
    
    try:
        classifier, vectorizer = _train_classifier()
        if classifier is None:
            return None
        
        # Predict
        prediction = classifier.predict([text.lower()])[0]
        probabilities = classifier.predict_proba([text.lower()])[0]
        max_prob = max(probabilities)
        
        # Very aggressive classification to reduce Unknown % to 20%
        # Accept predictions with very low confidence
        threshold = 0.01  # Very low threshold for aggressive classification (reduced from 0.05)
        
        if max_prob > threshold and prediction != "other/Unknown":
            logger.debug(f"[ML] Classified '{text[:50]}...' as '{prediction}' (confidence: {max_prob:.2f})")
            return prediction
        
        # Even more aggressive: accept any non-Unknown prediction with > 0.5% confidence
        if max_prob > 0.005 and prediction != "other/Unknown":
            logger.debug(f"[ML] Very low-confidence classification '{text[:50]}...' as '{prediction}' (confidence: {max_prob:.2f})")
            return prediction
        
        return None
    except Exception as e:
        logger.debug(f"[ML] Classification error: {e}")
        return None

def save_classifier(path: str = "market_classifier.pkl"):
    """Save trained classifier to file"""
    try:
        classifier, _ = _train_classifier()
        if classifier is not None:
            with open(path, 'wb') as f:
                pickle.dump(classifier, f)
            logger.info(f"[ML] Saved classifier to {path}")
    except Exception as e:
        logger.warning(f"[ML] Failed to save classifier: {e}")

def load_classifier(path: str = "market_classifier.pkl"):
    """Load trained classifier from file"""
    global _classifier
    try:
        if os.path.exists(path):
            with open(path, 'rb') as f:
                _classifier = pickle.load(f)
            logger.info(f"[ML] Loaded classifier from {path}")
            return True
    except Exception as e:
        logger.warning(f"[ML] Failed to load classifier: {e}")
    return False

