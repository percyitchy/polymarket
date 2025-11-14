"""
Многоступенчатый fallback для получения актуальной цены рынка Polymarket
"""

import os
import logging
import requests
from typing import Optional, Dict, Any
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

# Попытка импортировать gamma_client
try:
    from gamma_client import get_event_by_slug, get_event_by_condition_id
    GAMMA_CLIENT_AVAILABLE = True
except ImportError:
    GAMMA_CLIENT_AVAILABLE = False
    logger.debug("[PRICE_FETCH] gamma_client module not available")

# Конфигурация таймаутов
REQUEST_TIMEOUT = 5  # секунды
MAX_RETRIES = 2  # количество попыток для каждого источника


def condition_id_to_token_id(condition_id: str, outcome_index: int) -> str:
    """
    Конвертировать condition_id и outcome_index в token_id
    
    В Polymarket token_id обычно формируется как: condition_id:outcome_index
    или просто используется condition_id с указанием outcome_index отдельно
    
    Args:
        condition_id: ID условия рынка (hex string)
        outcome_index: Индекс исхода (0, 1, 2, ...)
        
    Returns:
        str: token_id в формате "{condition_id}:{outcome_index}"
    """
    return f"{condition_id}:{outcome_index}"


def get_price_from_polymarket_clob(token_id: str) -> Optional[float]:
    """
    Получить цену через Polymarket CLOB API /price endpoint
    
    Поддерживает два формата авторизации:
    1. Builder API Key (только PM_API_KEY) - простая авторизация через X-API-KEY
    2. Полная авторизация (PM_API_KEY + PM_API_SECRET + PM_API_PASSPHRASE) - для обратной совместимости
    
    Args:
        token_id: ID токена-маркета Polymarket
        
    Returns:
        float: цена токена или None при ошибке
    """
    api_key = os.getenv("PM_API_KEY")
    api_secret = os.getenv("PM_API_SECRET")
    api_passphrase = os.getenv("PM_API_PASSPHRASE")
    
    # Проверяем наличие хотя бы PM_API_KEY
    if not api_key:
        logger.warning(f"[PRICE_FETCH] [CLOB] API key not configured (PM_API_KEY missing) — skipping CLOB price step")
        return None
    
    # Определяем формат авторизации
    use_builder_key = bool(api_key) and not (api_secret and api_passphrase)
    use_full_auth = bool(api_key and api_secret and api_passphrase)
    
    if use_builder_key:
        logger.debug(f"[PRICE_FETCH] [CLOB] Using Builder API Key format (PM_API_KEY only)")
    elif use_full_auth:
        logger.debug(f"[PRICE_FETCH] [CLOB] Using full authentication (PM_API_KEY + SECRET + PASSPHRASE)")
    else:
        logger.warning(f"[PRICE_FETCH] [CLOB] Partial configuration detected — using Builder API Key format")
    
    try:
        url = "https://clob.polymarket.com/price"
        
        # Формируем заголовки в зависимости от формата авторизации
        if use_full_auth:
            # Полная авторизация (для обратной совместимости)
            headers = {
                "X-API-KEY": api_key,
                "X-API-SECRET": api_secret,
                "X-API-PASSPHRASE": api_passphrase,
                "Content-Type": "application/json"
            }
        else:
            # Builder API Key (только ключ)
            headers = {
                "X-API-KEY": api_key,
                "Content-Type": "application/json"
            }
        
        params = {
            "token_id": token_id,
            "side": "BUY"
        }
        
        logger.info(f"[PRICE_FETCH] Step 1/6: CLOB /price")
        logger.info(f"[PRICE_FETCH] [1/6] Requesting Polymarket CLOB API /price: token_id={token_id[:30]}...")
        response = requests.get(url, headers=headers, params=params, timeout=REQUEST_TIMEOUT)
        
        logger.info(f"[PRICE_FETCH] [1/6] Response status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            logger.debug(f"[PRICE_FETCH] [1/6] Response data keys: {list(data.keys()) if isinstance(data, dict) else 'not a dict'}")
            price = data.get("price") or data.get("last_price")
            if price is not None:
                try:
                    price_float = float(price)
                    logger.info(f"[PRICE_FETCH] ✅ Got price=0.{str(price_float).split('.')[1][:6]} from Polymarket CLOB API")
                    return price_float
                except (ValueError, TypeError) as e:
                    logger.warning(f"[PRICE_FETCH] ❌ Failed at CLOB API (parse error): price={price}, error={e}")
            else:
                logger.warning(f"[PRICE_FETCH] ❌ Failed at CLOB API (missing price field): Response: {str(data)[:200]}")
        elif response.status_code == 401:
            logger.warning(f"[PRICE_FETCH] [CLOB] Unauthorized (401): {response.text[:200]}")
        elif response.status_code == 403:
            logger.warning(f"[PRICE_FETCH] [CLOB] Forbidden (403): {response.text[:200]}")
        elif response.status_code >= 500:
            logger.warning(f"[PRICE_FETCH] [CLOB] Error {response.status_code}: {response.text[:200]}")
        else:
            logger.warning(f"[PRICE_FETCH] [CLOB] Error {response.status_code}: {response.text[:200]}")
            
    except requests.exceptions.Timeout:
        logger.warning(f"[PRICE_FETCH] ❌ Failed at CLOB API (timeout {REQUEST_TIMEOUT}s)")
    except requests.exceptions.RequestException as e:
        logger.warning(f"[PRICE_FETCH] ❌ Failed at CLOB API (request error): {type(e).__name__}: {e}")
    except Exception as e:
        logger.warning(f"[PRICE_FETCH] ❌ Failed at CLOB API (unexpected error): {type(e).__name__}: {e}")
    
    return None


def get_price_from_hashdive(token_id: str) -> Optional[float]:
    """
    Получить цену через HashiDive API
    
    Args:
        token_id: ID токена (asset_id в HashiDive)
        
    Returns:
        float: цена токена или None при ошибке
    """
    api_key = os.getenv("HASHDIVE_API_KEY") or os.getenv("HASHIDIVE_API_KEY")
    
    if not api_key:
        logger.warning(f"[PRICE_FETCH] [HashiDive] API key not configured (HASHDIVE_API_KEY or HASHIDIVE_API_KEY)")
        return None
    
    try:
        url = "https://hashdive.com/api/get_last_price"
        headers = {
            "x-api-key": api_key,
            "Content-Type": "application/json"
        }
        params = {
            "asset_id": token_id
        }
        
        logger.info(f"[PRICE_FETCH] Step 2/5: HashiDive API")
        logger.info(f"[PRICE_FETCH] [2/5] Requesting HashiDive API: asset_id={token_id[:30]}...")
        response = requests.get(url, headers=headers, params=params, timeout=REQUEST_TIMEOUT)
        
        logger.info(f"[PRICE_FETCH] [2/5] Response status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            logger.debug(f"[PRICE_FETCH] [2/5] Response data keys: {list(data.keys()) if isinstance(data, dict) else 'not a dict'}")
            price = data.get("last_price") or data.get("price")
            if price is not None:
                try:
                    price_float = float(price)
                    logger.info(f"[PRICE_FETCH] ✅ Got price=0.{str(price_float).split('.')[1][:6]} from HashiDive")
                    return price_float
                except (ValueError, TypeError) as e:
                    logger.warning(f"[PRICE_FETCH] ❌ Failed at HashiDive (parse error): price={price}, error={e}")
            else:
                logger.warning(f"[PRICE_FETCH] ❌ Failed at HashiDive (missing price field): Response: {str(data)[:200]}")
        elif response.status_code == 401:
            logger.warning(f"[PRICE_FETCH] ❌ Failed at HashiDive (401 authentication failed): {response.text[:200]}")
        elif response.status_code == 403:
            logger.warning(f"[PRICE_FETCH] ❌ Failed at HashiDive (403 forbidden): {response.text[:200]}")
        elif response.status_code == 429:
            logger.warning(f"[PRICE_FETCH] ❌ Failed at HashiDive (429 rate limit exceeded): {response.text[:200]}")
        elif response.status_code >= 500:
            logger.warning(f"[PRICE_FETCH] ❌ Failed at HashiDive (5xx server error {response.status_code}): {response.text[:200]}")
        else:
            logger.warning(f"[PRICE_FETCH] ❌ Failed at HashiDive (status {response.status_code}): {response.text[:200]}")
            
    except requests.exceptions.Timeout:
        logger.warning(f"[PRICE_FETCH] ❌ Failed at HashiDive (timeout {REQUEST_TIMEOUT}s)")
    except requests.exceptions.RequestException as e:
        logger.warning(f"[PRICE_FETCH] ❌ Failed at HashiDive (request error): {type(e).__name__}: {e}")
    except Exception as e:
        logger.warning(f"[PRICE_FETCH] ❌ Failed at HashiDive (unexpected error): {type(e).__name__}: {e}")
    
    return None


def get_price_from_trades_history(token_id: str, condition_id: Optional[str] = None, max_trades: int = 10) -> Optional[float]:
    """
    Получить цену из истории сделок (среднее значение последних N сделок)
    
    Args:
        token_id: ID токена
        condition_id: ID условия рынка (опционально, для фильтрации)
        max_trades: Максимальное количество сделок для усреднения
        
    Returns:
        float: средняя цена из последних сделок или None при ошибке
    """
    try:
        # Попробуем Polymarket Data API для получения сделок
        url = "https://data-api.polymarket.com/trades"
        params = {
            "token_id": token_id,
            "limit": max_trades
        }
        
        if condition_id:
            params["market"] = condition_id
        
        logger.info(f"[PRICE_FETCH] Step 3/5: Trades History")
        logger.debug(f"[PRICE_FETCH] [3/5] Trying trades history for token_id={token_id[:20]}...")
        response = requests.get(url, params=params, timeout=REQUEST_TIMEOUT)
        
        if response.status_code == 200:
            data = response.json()
            # API может вернуть список напрямую или объект с полем trades/data
            if isinstance(data, list):
                trades = data
            else:
                trades = data.get("trades") or data.get("data") or []
            
            if trades:
                prices = []
                import time
                current_time = time.time()
                max_age_seconds = 3600  # Фильтруем сделки старше 1 часа
                
                for trade in trades[:max_trades]:
                    # trade может быть dict или уже содержать цену напрямую
                    if isinstance(trade, dict):
                        price = trade.get("price") or trade.get("last_price")
                        # Проверяем возраст сделки (если есть timestamp)
                        trade_timestamp = trade.get("timestamp") or trade.get("created_at") or trade.get("time")
                        if trade_timestamp:
                            try:
                                # Если timestamp в миллисекундах
                                if isinstance(trade_timestamp, (int, float)) and trade_timestamp > 1e10:
                                    trade_timestamp = trade_timestamp / 1000
                                trade_age = current_time - float(trade_timestamp)
                                if trade_age > max_age_seconds:
                                    logger.debug(f"[PRICE_FETCH] Skipping old trade (age: {trade_age/60:.1f} min, price: {price})")
                                    continue
                            except (ValueError, TypeError):
                                pass  # Если не можем определить возраст, используем сделку
                    elif isinstance(trade, (int, float)):
                        price = trade
                    else:
                        continue
                    
                    if price is not None:
                        try:
                            price_float = float(price)
                            # Фильтруем нереалистичные цены (слишком высокие или низкие для активного рынка)
                            if 0.001 <= price_float <= 0.999:
                                prices.append(price_float)
                            else:
                                logger.debug(f"[PRICE_FETCH] Skipping trade with extreme price: {price_float}")
                        except (ValueError, TypeError):
                            continue
                
                if prices:
                    avg_price = sum(prices) / len(prices)
                    logger.info(f"[PRICE_FETCH] ✅ Got price=0.{str(avg_price).split('.')[1][:6]} from trades history (avg of {len(prices)} trades, filtered from {len(trades)} total)")
                    # Предупреждение, если цена сильно отличается от ожидаемой (может быть устаревшей)
                    if avg_price > 0.5:
                        logger.warning(f"[PRICE_FETCH] ⚠️  Price from trades history ({avg_price:.3f}) seems high - trades may be outdated or incorrect")
                    return avg_price
                else:
                    logger.debug(f"[PRICE_FETCH] [3/5] No valid prices found in trades")
            else:
                logger.debug(f"[PRICE_FETCH] [3/5] No trades found for token_id={token_id[:20]}...")
        else:
            logger.debug(f"[PRICE_FETCH] [3/5] Trades API returned status {response.status_code}")
            
    except requests.exceptions.Timeout:
        logger.warning(f"[PRICE_FETCH] ❌ Failed at Trades History (timeout {REQUEST_TIMEOUT}s)")
    except requests.exceptions.RequestException as e:
        logger.warning(f"[PRICE_FETCH] ❌ Failed at Trades History (request error): {type(e).__name__}: {e}")
    except Exception as e:
        logger.warning(f"[PRICE_FETCH] ❌ Failed at Trades History (unexpected error): {type(e).__name__}: {e}")
    
    # Fallback: попробуем CLOB API /data/trades
    try:
        url = "https://clob.polymarket.com/data/trades"
        params = {
            "token_id": token_id,
            "limit": max_trades
        }
        
        logger.debug(f"[Price] Trying CLOB /data/trades for token_id={token_id[:20]}...")
        response = requests.get(url, params=params, timeout=REQUEST_TIMEOUT)
        
        if response.status_code == 200:
            data = response.json()
            # API может вернуть список напрямую или объект с полем trades/data
            if isinstance(data, list):
                trades = data
            else:
                trades = data.get("trades") or data.get("data") or []
            
            if trades:
                prices = []
                for trade in trades[:max_trades]:
                    # trade может быть dict или уже содержать цену напрямую
                    if isinstance(trade, dict):
                        price = trade.get("price") or trade.get("last_price")
                    elif isinstance(trade, (int, float)):
                        price = trade
                    else:
                        continue
                    
                    if price is not None:
                        try:
                            prices.append(float(price))
                        except (ValueError, TypeError):
                            continue
                
                if prices:
                    avg_price = sum(prices) / len(prices)
                    logger.info(f"[Price] ✅ Got price from CLOB trades (avg of {len(prices)} trades): {avg_price:.6f}")
                    return avg_price
                    
    except Exception as e:
        logger.debug(f"[Price] CLOB trades API error: {type(e).__name__}: {e}")
    
    return None


def get_price_from_finfeed(token_id: str) -> Optional[float]:
    """
    Получить цену через FinFeed API
    
    Args:
        token_id: ID токена/рынка
        
    Returns:
        float: цена токена или None при ошибке
    """
    api_key = os.getenv("FINFEED_API_KEY")
    
    if not api_key:
        logger.debug("[Price] FinFeed API key not configured")
        return None
    
    try:
        # Уточнить реальный endpoint по документации FinFeed
        url = "https://api.finfeedapi.com/v1/prediction-markets/last-price"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        params = {
            "market": token_id
        }
        
        logger.info(f"[PRICE_FETCH] Step 4/5: FinFeed API")
        logger.debug(f"[PRICE_FETCH] [4/5] Trying FinFeed API for token_id={token_id[:20]}...")
        response = requests.get(url, headers=headers, params=params, timeout=REQUEST_TIMEOUT)
        
        if response.status_code == 200:
            data = response.json()
            price = data.get("last_price") or data.get("price") or data.get("value")
            if price is not None:
                try:
                    price_float = float(price)
                    logger.info(f"[PRICE_FETCH] ✅ Got price=0.{str(price_float).split('.')[1][:6]} from FinFeed")
                    return price_float
                except (ValueError, TypeError) as e:
                    logger.warning(f"[PRICE_FETCH] ❌ Failed at FinFeed (parse error): {e}")
            else:
                logger.warning(f"[PRICE_FETCH] ❌ Failed at FinFeed (missing price field): {data}")
        elif response.status_code == 401:
            logger.warning(f"[PRICE_FETCH] ❌ Failed at FinFeed (401 authentication failed): {response.text[:200]}")
        elif response.status_code == 403:
            logger.warning(f"[PRICE_FETCH] ❌ Failed at FinFeed (403 forbidden): {response.text[:200]}")
        elif response.status_code == 429:
            logger.warning(f"[PRICE_FETCH] ❌ Failed at FinFeed (429 rate limit exceeded): {response.text[:200]}")
        elif response.status_code >= 500:
            logger.warning(f"[PRICE_FETCH] ❌ Failed at FinFeed (5xx server error {response.status_code}): {response.text[:200]}")
        else:
            logger.warning(f"[PRICE_FETCH] ❌ Failed at FinFeed (status {response.status_code}): {response.text[:200]}")
            
    except requests.exceptions.Timeout:
        logger.warning(f"[PRICE_FETCH] ❌ Failed at FinFeed (timeout {REQUEST_TIMEOUT}s)")
    except requests.exceptions.RequestException as e:
        logger.warning(f"[PRICE_FETCH] ❌ Failed at FinFeed (request error): {type(e).__name__}: {e}")
    except Exception as e:
        logger.warning(f"[PRICE_FETCH] ❌ Failed at FinFeed (unexpected error): {type(e).__name__}: {e}")
    
    return None


def _get_price_from_gamma(condition_id: str,
                          outcome_index: int,
                          slug: Optional[str] = None) -> Optional[float]:
    """
    Пытается получить цену из Gamma API.
    
    Структура Gamma API:
    - /events возвращает список событий
    - Каждое событие имеет поле "markets" (массив)
    - Каждый market имеет "conditionId", "slug" и "outcomePrices" (строка JSON)
    - outcomePrices: "[\"0.123\", \"0.877\"]" - нужно парсить через json.loads()
    
    1) Если есть slug → поиск через /events по slug в markets
    2) Иначе поиск события по condition_id через /events по conditionId в markets
    
    Берёт поле outcomePrices из первого market, первый элемент = Yes (0), второй = No (1).
    Возвращает цену для outcome_index (0 или 1).
    
    Args:
        condition_id: ID условия рынка
        outcome_index: Индекс исхода (0 = Yes, 1 = No)
        slug: Slug рынка (опционально, для более быстрого запроса)
        
    Returns:
        float: Цена исхода или None при ошибке
    """
    if not GAMMA_CLIENT_AVAILABLE:
        logger.debug(f"[PRICE_FETCH] [GAMMA] gamma_client not available, skipping")
        return None
    
    logger.info(f"[PRICE_FETCH] [GAMMA] Trying Gamma API for condition_id={condition_id[:20]}..., outcome_index={outcome_index}")
    
    event = None
    
    # Приоритет 1: Если есть slug, используем его
    if slug:
        logger.debug(f"[PRICE_FETCH] [GAMMA] Trying to get event by slug: {slug[:50]}...")
        event = get_event_by_slug(slug)
        if event:
            logger.debug(f"[PRICE_FETCH] [GAMMA] ✅ Got event by slug")
    
    # Приоритет 2: Если не получилось по slug, пробуем по condition_id
    if not event:
        logger.debug(f"[PRICE_FETCH] [GAMMA] Trying to get event by condition_id: {condition_id[:20]}...")
        event = get_event_by_condition_id(condition_id)
        if event:
            logger.debug(f"[PRICE_FETCH] [GAMMA] ✅ Got event by condition_id")
    
    if not event:
        logger.warning(f"[PRICE_FETCH] [GAMMA] ❌ Failed to get price from Gamma: event not found (slug={slug[:50] if slug else 'N/A'}, condition_id={condition_id[:20]}...)")
        return None
    
    # Извлекаем markets из события
    markets = event.get("markets", [])
    if not markets:
        logger.warning(f"[PRICE_FETCH] [GAMMA] ❌ Failed to get price from Gamma: no markets in event")
        return None
    
    # Берём первый market (или ищем по condition_id/slug если их несколько)
    market = None
    for m in markets:
        market_condition_id = m.get("conditionId") or m.get("condition_id", "")
        market_slug = m.get("slug", "")
        if condition_id and market_condition_id.lower() == condition_id.lower():
            market = m
            break
        elif slug and (market_slug == slug or slug in market_slug):
            market = m
            break
    
    # Если не нашли по condition_id/slug, берём первый
    if not market:
        market = markets[0]
        logger.debug(f"[PRICE_FETCH] [GAMMA] Using first market from event (found {len(markets)} markets)")
    
    # Извлекаем outcomePrices из market
    outcome_prices_str = market.get("outcomePrices") or market.get("outcome_prices")
    
    if not outcome_prices_str:
        logger.warning(f"[PRICE_FETCH] [GAMMA] ❌ Failed to get price from Gamma: outcomePrices field missing in market")
        return None
    
    # Парсим outcomePrices (это строка JSON)
    import json
    outcome_prices = None
    
    if isinstance(outcome_prices_str, str):
        try:
            outcome_prices = json.loads(outcome_prices_str)
        except json.JSONDecodeError as e:
            logger.warning(f"[PRICE_FETCH] [GAMMA] ❌ Failed to parse outcomePrices JSON: {e}, raw value: {outcome_prices_str[:100]}")
            return None
    elif isinstance(outcome_prices_str, list):
        outcome_prices = outcome_prices_str
    else:
        logger.warning(f"[PRICE_FETCH] [GAMMA] ❌ Failed to get price from Gamma: outcomePrices is not a string or list, got {type(outcome_prices_str)}")
        return None
    
    if not isinstance(outcome_prices, list):
        logger.warning(f"[PRICE_FETCH] [GAMMA] ❌ Failed to get price from Gamma: outcomePrices is not a list after parsing")
        return None
    
    if len(outcome_prices) <= outcome_index:
        logger.warning(
            f"[PRICE_FETCH] [GAMMA] ❌ Failed to get price from Gamma: "
            f"outcomePrices array too short (length={len(outcome_prices)}, need index={outcome_index})"
        )
        return None
    
    # Получаем цену для нужного исхода
    price_value = outcome_prices[outcome_index]
    
    if price_value is None:
        logger.warning(f"[PRICE_FETCH] [GAMMA] ❌ Failed to get price from Gamma: outcomePrices[{outcome_index}] is None")
        return None
    
    try:
        price = float(price_value)
        logger.info(f"[PRICE_FETCH] [GAMMA] ✅ Got price={price:.6f} from Gamma (slug={slug[:50] if slug else 'N/A'}, condition_id={condition_id[:20]}..., outcome_index={outcome_index})")
        return price
    except (ValueError, TypeError) as e:
        logger.warning(f"[PRICE_FETCH] [GAMMA] ❌ Failed to get price from Gamma: cannot convert outcomePrices[{outcome_index}]={price_value} to float: {e}")
        return None


def get_current_price(token_id: Optional[str] = None, 
                      condition_id: Optional[str] = None, 
                      outcome_index: Optional[int] = None,
                      wallet_prices: Optional[Dict[str, float]] = None,
                      slug: Optional[str] = None,
                      debug: bool = False) -> tuple[Optional[float], Optional[str]]:
    """
    Получить актуальную цену токена с многоступенчатым fallback
    
    Логика fail-open: даже если один из источников недоступен, продолжаем попытки.
    Порядок попыток:
    1. Polymarket CLOB API /price (с авторизацией)
    2. Gamma API (/slug или /events)
    3. История сделок (среднее значение)
    4. HashiDive API
    5. FinFeed API
    6. Средняя цена из wallet_prices (если предоставлена)
    
    Args:
        token_id: ID токена-маркета Polymarket (если известен напрямую)
        condition_id: ID условия рынка (если известен condition_id, но не token_id)
        outcome_index: Индекс исхода (если известен condition_id)
        wallet_prices: Словарь wallet -> price для fallback (опционально)
        slug: Slug рынка для Gamma API (опционально, ускоряет запрос)
        
    Returns:
        float: актуальная цена токена или None при полной неудаче
        
    Example:
        >>> # Вариант 1: с token_id напрямую
        >>> price = get_current_price(token_id="7132104567...123")
        >>> 
        >>> # Вариант 2: с condition_id и outcome_index
        >>> price = get_current_price(condition_id="0x123...", outcome_index=0)
        >>> 
        >>> # Вариант 3: с wallet_prices fallback
        >>> price = get_current_price(condition_id="0x123...", outcome_index=0, 
        ...                          wallet_prices={"0xabc...": 0.75, "0xdef...": 0.76})
        >>> 
        >>> if price is None:
        ...     print("Не удалось получить цену")
        ... else:
        ...     print(f"Актуальная цена: {price:.3f}")
    """
    # Определяем token_id из параметров
    if not token_id:
        if condition_id and outcome_index is not None:
            token_id = condition_id_to_token_id(condition_id, outcome_index)
            logger.info(f"[Price] Converted condition_id={condition_id[:20]}... outcome={outcome_index} to token_id={token_id[:30]}...")
        else:
            logger.warning(f"[Price] Missing required parameters: need either token_id or (condition_id + outcome_index)")
            return None, None
    
    logger.info(f"[PRICE_FETCH] 🔍 Starting price lookup for token_id={token_id[:30]}... condition_id={condition_id[:20] if condition_id else 'N/A'}... outcome={outcome_index}")
    
    # Шаг 1: Polymarket CLOB API /price
    logger.info(f"[PRICE_FETCH] Step 1/6: CLOB /price")
    price = get_price_from_polymarket_clob(token_id)
    if price is not None:
        source = "CLOB"
        if debug:
            logger.info(f"[PRICE_FETCH] [DEBUG] Source: {source}")
        return price, source
    
    # Шаг 2: Gamma API
    logger.info(f"[PRICE_FETCH] Step 2/6: Gamma API")
    if condition_id and outcome_index is not None:
        price = _get_price_from_gamma(condition_id, outcome_index, slug=slug)
        if price is not None:
            source = "gamma"
            if debug:
                logger.info(f"[PRICE_FETCH] [DEBUG] Source: {source}")
            return price, source
    else:
        logger.debug(f"[PRICE_FETCH] [GAMMA] Skipped: condition_id or outcome_index not provided")
    
    # Шаг 3: История сделок
    logger.info(f"[PRICE_FETCH] Step 3/6: Trades History")
    price = get_price_from_trades_history(token_id, condition_id=condition_id)
    if price is not None:
        source = "trades"
        if debug:
            logger.info(f"[PRICE_FETCH] [DEBUG] Source: {source}")
        return price, source
    
    # Шаг 4: HashiDive API
    logger.info(f"[PRICE_FETCH] Step 4/6: HashiDive API")
    price = get_price_from_hashdive(token_id)
    if price is not None:
        source = "HashiDive"
        if debug:
            logger.info(f"[PRICE_FETCH] [DEBUG] Source: {source}")
        return price, source
    
    # Шаг 5: FinFeed API
    logger.info(f"[PRICE_FETCH] Step 5/6: FinFeed API")
    price = get_price_from_finfeed(token_id)
    if price is not None:
        source = "FinFeed"
        if debug:
            logger.info(f"[PRICE_FETCH] [DEBUG] Source: {source}")
        return price, source
    
    # Шаг 6: Средняя цена из wallet_prices (если предоставлена) - fail-open
    logger.info(f"[PRICE_FETCH] Step 6/6: wallet_prices fallback")
    if wallet_prices:
        logger.info(f"[WALLET_FALLBACK] Trying wallet_prices fallback (provided {len(wallet_prices)} wallet prices)...")
        logger.info(f"[WALLET_FALLBACK] wallet_prices content: {wallet_prices}")
        try:
            prices = [p for p in wallet_prices.values() if isinstance(p, (int, float)) and p > 0]
            logger.info(f"[WALLET_FALLBACK] Valid prices extracted: {prices} (from {len(wallet_prices)} total)")
            if prices:
                avg_price = sum(prices) / len(prices)
                logger.info(f"[WALLET_FALLBACK] Using average price {avg_price:.6f} from {prices}")
                logger.info(f"[PRICE_FETCH] ✅ Got price=0.{str(avg_price).split('.')[1][:6]} from wallet_prices fallback")
                source = "wallet_fallback"
                if debug:
                    logger.info(f"[PRICE_FETCH] [DEBUG] Source: {source}")
                return avg_price, source
            else:
                logger.warning(f"[WALLET_FALLBACK] Skipped: wallet_prices provided ({len(wallet_prices)} entries) but no valid prices found after filtering")
                logger.warning(f"[WALLET_FALLBACK] wallet_prices values: {list(wallet_prices.values())}")
        except Exception as e:
            logger.error(f"[WALLET_FALLBACK] ❌ Failed to calculate average from wallet_prices: {type(e).__name__}: {e}")
            import traceback
            logger.error(f"[WALLET_FALLBACK] Traceback: {traceback.format_exc()}")
    else:
        logger.warning(f"[WALLET_FALLBACK] Skipped: wallet_prices empty or invalid")
    
    # Все источники исчерпаны
    logger.warning(f"[PRICE_FETCH] ❗ All sources failed — returning None for token_id={token_id[:30]}... condition_id={condition_id[:20] if condition_id else 'N/A'}... outcome={outcome_index}")
    return None, None

