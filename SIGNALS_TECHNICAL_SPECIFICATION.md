# Poly Eye - Техническая Спецификация Сигналов и Функций

## 🔔 Часть 1: Типы Сигналов - Детальная Спецификация

---

## 1. Consensus Alpha Signals (Основной Сигнал)

### Описание

Обнаруживает консенсус между несколькими успешными трейдерами, когда они покупают один и тот же исход рынка в короткий временной интервал.

### Как Работает

1. **Мониторинг кошельков**: Отслеживает 200+ кошельков каждые 7 секунд
2. **Временное окно**: Поддерживает скользящее окно 15 минут для каждого рынка/исхода
3. **Фильтрация**: Проверяет качество кошельков (win rate ≥70%, объем ≥$25K, ≥12 рынков)
4. **Валидация**: Проверяет статус рынка (активен, не разрешен)
5. **Проверка цен**: Валидирует расхождение цен входа (≤25% для $0.05-$0.5, ≤10% для ≥$0.5)

### Источники Данных

#### 1. Polymarket Data API - Торговые Данные

```python
# Endpoint для получения сделок кошелька
GET https://data-api.polymarket.com/trades
Parameters:
  - user: wallet_address (обязательный)
  - side: BUY или SELL
  - limit: количество сделок (по умолчанию 10)
  - market: condition_id (опционально)

# Пример запроса
import requests

def get_wallet_trades(wallet_address: str, side: str = "BUY", limit: int = 10):
    url = "https://data-api.polymarket.com/trades"
    params = {
        "user": wallet_address,
        "side": side,
        "limit": limit
    }
    response = requests.get(url, params=params)
    return response.json()
```

#### 2. База Данных Кошельков (SQLite)

```python
# Таблица wallets содержит информацию о кошельках
SELECT address, win_rate, traded_total, realized_pnl_total, daily_trading_frequency
FROM wallets
WHERE is_tracked = 1
  AND win_rate >= 0.70
  AND traded_total >= 12
  AND realized_pnl_total >= 25000
```

#### 3. Polymarket CLOB API - Статус Рынка

```python
# Проверка статуса рынка
GET https://clob.polymarket.com/markets/{condition_id}

# Проверка цены
GET https://clob.polymarket.com/price
Headers:
  X-API-KEY: your_key
  X-API-SECRET: your_secret
  X-API-PASSPHRASE: your_passphrase
Parameters:
  - token_id: condition_id:outcome_index
  - side: BUY или SELL
```

### Техническая Реализация

```python
class ConsensusDetector:
    def __init__(self, db, window_minutes=15, min_consensus=3):
        self.db = db
        self.window_minutes = window_minutes
        self.min_consensus = min_consensus
        self.rolling_windows = {}  # condition_id:outcome_index -> {wallets: [], timestamps: []}
    
    def process_trade(self, wallet_address: str, condition_id: str, 
                     outcome_index: int, side: str, price: float, timestamp: datetime):
        """Обработать новую сделку и проверить консенсус"""
        key = f"{condition_id}:{outcome_index}:{side}"
        
        # Получить или создать окно
        if key not in self.rolling_windows:
            self.rolling_windows[key] = {
                "wallets": [],
                "timestamps": [],
                "prices": []
            }
        
        window = self.rolling_windows[key]
        
        # Очистить старые сделки (старше window_minutes)
        cutoff_time = timestamp - timedelta(minutes=self.window_minutes)
        valid_indices = [
            i for i, ts in enumerate(window["timestamps"]) 
            if ts >= cutoff_time
        ]
        
        window["wallets"] = [window["wallets"][i] for i in valid_indices]
        window["timestamps"] = [window["timestamps"][i] for i in valid_indices]
        window["prices"] = [window["prices"][i] for i in valid_indices]
        
        # Добавить новую сделку
        if wallet_address not in window["wallets"]:
            window["wallets"].append(wallet_address)
            window["timestamps"].append(timestamp)
            window["prices"].append(price)
        
        # Проверить консенсус
        unique_wallets = len(set(window["wallets"]))
        if unique_wallets >= self.min_consensus:
            # Валидация расхождения цен
            if self._validate_price_divergence(window["prices"]):
                # Проверка статуса рынка
                if self._is_market_active(condition_id):
                    return self._create_consensus_signal(
                        condition_id, outcome_index, side,
                        window["wallets"], window["prices"], timestamp
                    )
        
        return None
    
    def _validate_price_divergence(self, prices: List[float]) -> bool:
        """Проверить расхождение цен"""
        if len(prices) < 3:
            return True
        
        avg_price = sum(prices) / len(prices)
        
        # Правила расхождения
        if avg_price < 0.05:
            # Для низких цен расхождение не ограничено
            return True
        elif 0.05 <= avg_price < 0.5:
            # Расхождение ≤ 25%
            max_divergence = 0.25
        else:
            # Расхождение ≤ 10%
            max_divergence = 0.10
        
        for price in prices:
            divergence = abs(price - avg_price) / avg_price
            if divergence > max_divergence:
                return False
        
        return True
    
    def _is_market_active(self, condition_id: str) -> bool:
        """Проверить, активен ли рынок"""
        # Получить статус рынка через CLOB API
        url = f"https://clob.polymarket.com/markets/{condition_id}"
        response = requests.get(url)
        
        if response.status_code == 200:
            market_data = response.json()
            status = market_data.get("status", "")
            
            # Рынок закрыт если статус: closed, resolved, finished
            if status in ["closed", "resolved", "finished"]:
                return False
            
            # Проверить цену (если цена >= 0.999 или <= 0.001, рынок разрешен)
            # Это проверяется отдельно при получении цены
        
        return True
```

### Сила Сигнала

- **Слабый**: 3 кошелька, <$5K общая позиция
- **Умеренный**: 4-5 кошельков, $5K-$10K общая позиция
- **Сильный**: 6+ кошельков, >$10K общая позиция
- **Очень сильный**: Включает A-list трейдеров

---

## 2. A-List Trader Consensus (Премиум Сигнал)

### Описание

Обнаруживает консенсус между A-list трейдерами (топ 1% по объему/прибыли) в определенной категории рынков.

### Как Работает

1. **Идентификация A-list**: Определяет A-list трейдеров из weekly/monthly лидербордов
2. **Категоризация**: Отслеживает производительность по категориям (Politics, Sports, Crypto и т.д.)
3. **Консенсус**: Требует 2+ A-list трейдеров для сигнала
4. **Роутинг**: Направляет в премиум Telegram топик

### Источники Данных

#### 1. Polymarket Leaderboards API

```python
# Weekly leaderboard
GET https://polymarket.com/leaderboard/overall/weekly/profit

# Monthly leaderboard  
GET https://polymarket.com/leaderboard/overall/monthly/profit

# Использование Playwright для скрапинга (так как это SPA)
from playwright.sync_api import sync_playwright

def scrape_leaderboard(url: str, max_pages: int = 20):
    """Скрапить лидерборд для получения A-list трейдеров"""
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(url)
        
        wallets = []
        for page_num in range(max_pages):
            # Дождаться загрузки данных
            page.wait_for_selector('.leaderboard-row')
            
            # Извлечь адреса кошельков
            rows = page.query_selector_all('.leaderboard-row')
            for row in rows:
                wallet_link = row.query_selector('a[href*="/profile/"]')
                if wallet_link:
                    href = wallet_link.get_attribute('href')
                    wallet_address = href.split('/')[-1]
                    wallets.append(wallet_address)
            
            # Перейти на следующую страницу
            next_button = page.query_selector('button[aria-label="Next"]')
            if next_button and next_button.is_enabled():
                next_button.click()
                page.wait_for_timeout(2000)  # Подождать загрузки
            else:
                break
        
        browser.close()
        return wallets
```

#### 2. Polymarket Analytics API

```python
# Получить данные о производительности трейдера по категориям
GET https://polymarketanalytics.com/api/traders-tag-performance

# Параметры могут включать:
# - wallet_address
# - category (Politics, Sports, Crypto, etc.)
# - time_period (weekly, monthly, all-time)
```

#### 3. База Данных - A-List Кошельки

```python
# Создать таблицу для A-list трейдеров
CREATE TABLE a_list_wallets (
    address TEXT PRIMARY KEY,
    category TEXT,
    weekly_rank INTEGER,
    monthly_rank INTEGER,
    total_volume REAL,
    total_profit REAL,
    added_at TEXT,
    updated_at TEXT
);

# Критерии для A-list:
# - Топ 1% по объему или прибыли в категории
# - Или топ 50 в общем лидерборде
```

### Техническая Реализация

```python
class AListConsensusDetector:
    def __init__(self, db, min_a_list_traders=2):
        self.db = db
        self.min_a_list_traders = min_a_list_traders
        self.a_list_wallets = self._load_a_list_wallets()
    
    def _load_a_list_wallets(self) -> Dict[str, Dict]:
        """Загрузить A-list кошельки из БД"""
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT address, category, weekly_rank, monthly_rank
                FROM a_list_wallets
            """)
            rows = cursor.fetchall()
            
            a_list = {}
            for row in rows:
                address, category, weekly_rank, monthly_rank = row
                a_list[address] = {
                    "category": category,
                    "weekly_rank": weekly_rank,
                    "monthly_rank": monthly_rank
                }
            return a_list
    
    def check_a_list_consensus(self, wallets: List[str], 
                              condition_id: str, category: str) -> bool:
        """Проверить, есть ли консенсус A-list трейдеров"""
        a_list_count = 0
        a_list_wallets = []
        
        for wallet in wallets:
            if wallet.lower() in self.a_list_wallets:
                wallet_info = self.a_list_wallets[wallet.lower()]
                # Проверить категорию (если указана)
                if not category or wallet_info["category"] == category:
                    a_list_count += 1
                    a_list_wallets.append(wallet)
        
        return a_list_count >= self.min_a_list_traders, a_list_wallets
    
    def update_a_list_wallets(self):
        """Обновить список A-list кошельков из лидербордов"""
        # Скрапить weekly и monthly лидерборды
        weekly_wallets = scrape_leaderboard(
            "https://polymarket.com/leaderboard/overall/weekly/profit"
        )
        monthly_wallets = scrape_leaderboard(
            "https://polymarket.com/leaderboard/overall/monthly/profit"
        )
        
        # Объединить и получить топ 50
        all_wallets = list(set(weekly_wallets + monthly_wallets))
        
        # Получить данные о производительности для каждого
        for wallet in all_wallets[:50]:  # Топ 50
            # Получить категории и производительность
            performance = get_trader_performance(wallet)
            
            # Сохранить в БД
            self._save_a_list_wallet(wallet, performance)
```

---

## 3. Whale Position Alerts

### Описание

Обнаруживает крупные позиции (>$10K) от отслеживаемых кошельков, различая входы и выходы.

### Как Работает

1. **Мониторинг позиций**: Отслеживает изменения размера позиций в реальном времени
2. **Расчет USD**: Вычисляет USD стоимость позиций
3. **Различение**: Различает вход (entry) и выход (exit) сигналы
4. **Паттерны**: Отслеживает поведенческие паттерны китов

### Источники Данных

#### 1. Polymarket Data API - Закрытые Позиции

```python
# Получить закрытые позиции кошелька
GET https://data-api.polymarket.com/closed-positions
Parameters:
  - user: wallet_address
  - limit: количество позиций
  - market: condition_id (опционально)

def get_closed_positions(wallet_address: str, limit: int = 100):
    url = "https://data-api.polymarket.com/closed-positions"
    params = {
        "user": wallet_address,
        "limit": limit
    }
    response = requests.get(url, params=params)
    return response.json()
```

#### 2. Polymarket Data API - Активные Позиции

```python
# Получить активные позиции кошелька
GET https://data-api.polymarket.com/positions
Parameters:
  - user: wallet_address
  - market: condition_id (опционально)

def get_active_positions(wallet_address: str):
    url = "https://data-api.polymarket.com/positions"
    params = {"user": wallet_address}
    response = requests.get(url, params=params)
    return response.json()
```

#### 3. База Данных - История Позиций

```python
# Таблица для отслеживания позиций
CREATE TABLE wallet_positions (
    wallet_address TEXT,
    condition_id TEXT,
    outcome_index INTEGER,
    position_size REAL,
    position_type TEXT,  -- 'long' или 'short'
    usd_value REAL,
    first_seen_at TEXT,
    last_updated_at TEXT,
    PRIMARY KEY (wallet_address, condition_id, outcome_index)
);
```

### Техническая Реализация

```python
class WhalePositionDetector:
    def __init__(self, db, min_whale_size_usd=10000):
        self.db = db
        self.min_whale_size_usd = min_whale_size_usd
        self.previous_positions = {}  # wallet -> {condition_id:outcome -> size}
    
    def monitor_positions(self, wallet_address: str):
        """Мониторить позиции кошелька и обнаружить изменения"""
        # Получить текущие активные позиции
        current_positions = self._get_current_positions(wallet_address)
        
        # Получить предыдущие позиции
        previous = self.previous_positions.get(wallet_address, {})
        
        # Обнаружить изменения
        for key, current_size in current_positions.items():
            previous_size = previous.get(key, 0)
            
            if current_size > previous_size:
                # Увеличение позиции (entry)
                change = current_size - previous_size
                usd_value = self._calculate_usd_value(key, change)
                
                if usd_value >= self.min_whale_size_usd:
                    self._create_whale_entry_alert(
                        wallet_address, key, change, usd_value
                    )
            
            elif current_size < previous_size:
                # Уменьшение позиции (exit)
                change = previous_size - current_size
                usd_value = self._calculate_usd_value(key, change)
                
                if usd_value >= self.min_whale_size_usd:
                    self._create_whale_exit_alert(
                        wallet_address, key, change, usd_value
                    )
        
        # Обновить предыдущие позиции
        self.previous_positions[wallet_address] = current_positions
    
    def _get_current_positions(self, wallet_address: str) -> Dict[str, float]:
        """Получить текущие позиции кошелька"""
        positions_data = get_active_positions(wallet_address)
        
        positions = {}
        for pos in positions_data:
            condition_id = pos.get("condition_id")
            outcome_index = pos.get("outcome_index")
            size = float(pos.get("size", 0))
            
            if size > 0:
                key = f"{condition_id}:{outcome_index}"
                positions[key] = size
        
        return positions
    
    def _calculate_usd_value(self, position_key: str, size: float) -> float:
        """Вычислить USD стоимость позиции"""
        condition_id, outcome_index = position_key.split(":")
        
        # Получить цену токена
        token_id = f"{condition_id}:{outcome_index}"
        price = get_token_price(token_id)
        
        # USD стоимость = размер * цена
        usd_value = size * price
        return usd_value
    
    def _create_whale_entry_alert(self, wallet: str, position_key: str, 
                                  size: float, usd_value: float):
        """Создать алерт о входе кита"""
        condition_id, outcome_index = position_key.split(":")
        
        # Получить информацию о рынке
        market_info = get_market_info(condition_id)
        
        alert = {
            "type": "whale_entry",
            "wallet": wallet,
            "condition_id": condition_id,
            "outcome_index": int(outcome_index),
            "position_size": size,
            "usd_value": usd_value,
            "market_title": market_info.get("title"),
            "market_slug": market_info.get("slug"),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
        # Отправить алерт
        send_whale_alert(alert)
```

---

## 4. Open Interest (OI) Spike Detection

### Описание

Обнаруживает внезапные увеличения открытого интереса (>50% спайк), указывающие на сильное убеждение рынка.

### Как Работает

1. **Мониторинг OI**: Отслеживает изменения открытого интереса по всем рынкам
2. **Расчет изменений**: Вычисляет процентное изменение за временные окна
3. **Корреляция**: Коррелирует с консенсусными сигналами для подтверждения
4. **Фильтрация**: Фильтрует ложные срабатывания (малые рынки, низкая ликвидность)

### Источники Данных

#### 1. Polymarket CLOB API - Market Data

```python
# Получить данные рынка включая открытый интерес
GET https://clob.polymarket.com/markets/{condition_id}

# Ответ включает:
# - openInterest: открытый интерес
# - volume24h: объем за 24 часа
# - liquidity: ликвидность

def get_market_oi(condition_id: str):
    url = f"https://clob.polymarket.com/markets/{condition_id}"
    response = requests.get(url)
    
    if response.status_code == 200:
        data = response.json()
        return {
            "open_interest": float(data.get("openInterest", 0)),
            "volume_24h": float(data.get("volume24h", 0)),
            "liquidity": float(data.get("liquidity", 0))
        }
    return None
```

#### 2. База Данных - История OI

```python
# Таблица для отслеживания истории OI
CREATE TABLE oi_history (
    condition_id TEXT,
    outcome_index INTEGER,
    open_interest REAL,
    timestamp TEXT,
    PRIMARY KEY (condition_id, outcome_index, timestamp)
);

# Индексировать для быстрого поиска
CREATE INDEX idx_oi_timestamp ON oi_history(timestamp);
```

### Техническая Реализация

```python
class OISpikeDetector:
    def __init__(self, db, spike_threshold=0.5, min_liquidity=1000):
        self.db = db
        self.spike_threshold = spike_threshold  # 50% увеличение
        self.min_liquidity = min_liquidity  # Минимальная ликвидность
    
    def check_oi_spike(self, condition_id: str, outcome_index: int):
        """Проверить спайк открытого интереса"""
        # Получить текущий OI
        current_oi_data = get_market_oi(condition_id)
        if not current_oi_data:
            return None
        
        current_oi = current_oi_data["open_interest"]
        liquidity = current_oi_data["liquidity"]
        
        # Фильтр: минимальная ликвидность
        if liquidity < self.min_liquidity:
            return None
        
        # Получить исторический OI (последние 1 час)
        historical_oi = self._get_historical_oi(
            condition_id, outcome_index, hours=1
        )
        
        if not historical_oi or len(historical_oi) < 2:
            # Сохранить текущий OI для будущих сравнений
            self._save_oi_snapshot(condition_id, outcome_index, current_oi)
            return None
        
        # Вычислить средний OI за последний час
        avg_oi = sum(historical_oi) / len(historical_oi)
        
        # Вычислить процентное изменение
        if avg_oi > 0:
            spike_percent = (current_oi - avg_oi) / avg_oi
        else:
            spike_percent = 0
        
        # Проверить порог спайка
        if spike_percent >= self.spike_threshold:
            return self._create_oi_spike_alert(
                condition_id, outcome_index,
                old_oi=avg_oi,
                new_oi=current_oi,
                spike_percent=spike_percent
            )
        
        # Сохранить текущий OI
        self._save_oi_snapshot(condition_id, outcome_index, current_oi)
        return None
    
    def _get_historical_oi(self, condition_id: str, outcome_index: int, 
                          hours: int) -> List[float]:
        """Получить исторический OI из БД"""
        cutoff_time = datetime.now(timezone.utc) - timedelta(hours=hours)
        
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT open_interest
                FROM oi_history
                WHERE condition_id = ? AND outcome_index = ?
                  AND timestamp >= ?
                ORDER BY timestamp DESC
            """, (condition_id, outcome_index, cutoff_time.isoformat()))
            
            rows = cursor.fetchall()
            return [row[0] for row in rows]
    
    def _save_oi_snapshot(self, condition_id: str, outcome_index: int, oi: float):
        """Сохранить снимок OI в БД"""
        timestamp = datetime.now(timezone.utc).isoformat()
        
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO oi_history 
                (condition_id, outcome_index, open_interest, timestamp)
                VALUES (?, ?, ?, ?)
            """, (condition_id, outcome_index, oi, timestamp))
            conn.commit()
```

---

## 5. Order Flow Analysis

### Описание

Анализирует давление покупки/продажи и динамику order book для предсказания движений цены.

### Как Работает

1. **Мониторинг Order Book**: Отслеживает глубину order book через CLOB API
2. **Расчет дисбаланса**: Вычисляет дисбаланс bid/ask
3. **Отслеживание крупных ордеров**: Идентифицирует размещение крупных ордеров
4. **Паттерны**: Идентифицирует паттерны потока ордеров

### Источники Данных

#### 1. Polymarket CLOB API - Order Book

```python
# Получить order book для токена
GET https://clob.polymarket.com/book
Parameters:
  - token_id: condition_id:outcome_index

def get_order_book(token_id: str):
    url = "https://clob.polymarket.com/book"
    params = {"token_id": token_id}
    response = requests.get(url, params=params)
    
    if response.status_code == 200:
        data = response.json()
        return {
            "bids": data.get("bids", []),  # Список ордеров на покупку
            "asks": data.get("asks", [])   # Список ордеров на продажу
        }
    return None
```

#### 2. Polymarket CLOB API - Trades Stream

```python
# Получить последние сделки
GET https://clob.polymarket.com/data/trades
Parameters:
  - token_id: condition_id:outcome_index
  - limit: количество сделок

def get_recent_trades(token_id: str, limit: int = 50):
    url = "https://clob.polymarket.com/data/trades"
    params = {
        "token_id": token_id,
        "limit": limit
    }
    response = requests.get(url, params=params)
    return response.json()
```

### Техническая Реализация

```python
class OrderFlowAnalyzer:
    def __init__(self, db):
        self.db = db
    
    def analyze_order_flow(self, condition_id: str, outcome_index: int):
        """Анализировать поток ордеров для рынка"""
        token_id = f"{condition_id}:{outcome_index}"
        
        # Получить order book
        order_book = get_order_book(token_id)
        if not order_book:
            return None
        
        # Вычислить дисбаланс bid/ask
        bid_volume = sum([bid["size"] for bid in order_book["bids"]])
        ask_volume = sum([ask["size"] for ask in order_book["asks"]])
        
        total_volume = bid_volume + ask_volume
        if total_volume == 0:
            return None
        
        bid_ratio = bid_volume / total_volume
        ask_ratio = ask_volume / total_volume
        
        # Определить давление
        pressure = "buy" if bid_ratio > 0.6 else "sell" if ask_ratio > 0.6 else "neutral"
        
        # Получить последние сделки для подтверждения
        recent_trades = get_recent_trades(token_id, limit=20)
        buy_trades = [t for t in recent_trades if t.get("side") == "BUY"]
        sell_trades = [t for t in recent_trades if t.get("side") == "SELL"]
        
        buy_volume = sum([t.get("size", 0) for t in buy_trades])
        sell_volume = sum([t.get("size", 0) for t in sell_trades])
        
        # Вычислить силу давления
        if buy_volume + sell_volume > 0:
            trade_pressure_ratio = buy_volume / (buy_volume + sell_volume)
        else:
            trade_pressure_ratio = 0.5
        
        # Определить подтверждение
        confirmed = False
        if pressure == "buy" and trade_pressure_ratio > 0.6:
            confirmed = True
        elif pressure == "sell" and trade_pressure_ratio < 0.4:
            confirmed = True
        
        return {
            "pressure": pressure,
            "bid_volume": bid_volume,
            "ask_volume": ask_volume,
            "bid_ratio": bid_ratio,
            "ask_ratio": ask_ratio,
            "trade_pressure_ratio": trade_pressure_ratio,
            "confirmed": confirmed
        }
```

---

## 6. Insider Pattern Detection

### Описание

Идентифицирует подозрительные торговые паттерны, которые могут указывать на инсайдерскую информацию.

### Как Работает

1. **Новые кошельки**: Обнаруживает новые кошельки с крупными позициями (>$5K)
2. **Высокий win rate**: Идентифицирует высокий win rate на первых сделках (>80%)
3. **Концентрированная торговля**: Находит необычную концентрацию на конкретных рынках
4. **Временные паттерны**: Отслеживает необычное время (перед крупными событиями)

### Источники Данных

#### 1. Polymarket Data API - История Сделок

```python
# Получить все сделки кошелька
GET https://data-api.polymarket.com/trades
Parameters:
  - user: wallet_address
  - limit: максимальное количество (до 500)

def get_all_wallet_trades(wallet_address: str):
    """Получить все сделки кошелька"""
    all_trades = []
    limit = 500
    offset = 0
    
    while True:
        url = "https://data-api.polymarket.com/trades"
        params = {
            "user": wallet_address,
            "limit": limit,
            "offset": offset
        }
        response = requests.get(url, params=params)
        trades = response.json()
        
        if not trades or len(trades) == 0:
            break
        
        all_trades.extend(trades)
        offset += limit
        
        if len(trades) < limit:
            break
    
    return all_trades
```

#### 2. База Данных - Новые Кошельки

```python
# Таблица для отслеживания новых кошельков
CREATE TABLE new_wallets (
    address TEXT PRIMARY KEY,
    first_seen_at TEXT,
    first_trade_at TEXT,
    first_trade_size REAL,
    total_trades INTEGER DEFAULT 0,
    win_rate REAL,
    is_insider_candidate INTEGER DEFAULT 0
);
```

### Техническая Реализация

```python
class InsiderDetector:
    def __init__(self, db, min_position_size=5000, min_win_rate=0.80):
        self.db = db
        self.min_position_size = min_position_size
        self.min_win_rate = min_win_rate
    
    def detect_insider_patterns(self, wallet_address: str):
        """Обнаружить инсайдерские паттерны для кошелька"""
        # Проверить, новый ли это кошелек
        if not self._is_new_wallet(wallet_address):
            return None
        
        # Получить первые сделки
        trades = get_all_wallet_trades(wallet_address)
        if len(trades) < 3:
            return None
        
        # Сортировать по времени
        trades.sort(key=lambda x: x.get("timestamp", ""))
        first_trades = trades[:10]  # Первые 10 сделок
        
        # Проверить паттерны
        patterns = []
        
        # Паттерн 1: Крупная первая позиция
        first_trade_size = float(first_trades[0].get("size", 0))
        first_trade_price = float(first_trades[0].get("price", 0))
        first_position_usd = first_trade_size * first_trade_price
        
        if first_position_usd >= self.min_position_size:
            patterns.append({
                "type": "new_wallet_large_position",
                "size": first_position_usd,
                "description": f"New wallet opened large position: ${first_position_usd:,.0f}"
            })
        
        # Паттерн 2: Высокий win rate на первых сделках
        closed_positions = get_closed_positions(wallet_address, limit=10)
        if len(closed_positions) >= 3:
            wins = sum([1 for p in closed_positions if float(p.get("realizedPnl", 0)) > 0])
            win_rate = wins / len(closed_positions)
            
            if win_rate >= self.min_win_rate:
                patterns.append({
                    "type": "high_winrate_new_wallet",
                    "win_rate": win_rate,
                    "trades": len(closed_positions),
                    "description": f"New wallet with {win_rate:.1%} win rate on first {len(closed_positions)} trades"
                })
        
        # Паттерн 3: Концентрированная торговля
        markets_traded = set()
        for trade in first_trades:
            condition_id = trade.get("condition_id")
            if condition_id:
                markets_traded.add(condition_id)
        
        if len(markets_traded) == 1 and len(first_trades) >= 5:
            patterns.append({
                "type": "concentrated_trading",
                "market": list(markets_traded)[0],
                "trades": len(first_trades),
                "description": f"New wallet trading only one market: {len(first_trades)} trades"
            })
        
        if patterns:
            return {
                "wallet": wallet_address,
                "patterns": patterns,
                "risk_level": "high" if len(patterns) >= 2 else "medium"
            }
        
        return None
```

---

## 7. Category-Specific Consensus

### Описание

Обнаруживает консенсус в рамках конкретных категорий рынков (Politics, Sports, Crypto и т.д.).

### Как Работает

1. **Классификация**: Классифицирует рынки по категориям с помощью ML классификатора
2. **Отслеживание производительности**: Отслеживает производительность трейдеров по категориям
3. **Консенсус**: Идентифицирует консенсус среди экспертов категории
4. **Роутинг**: Направляет сигналы в категорийные каналы

### Источники Данных

#### 1. Gamma API - Market Metadata

```python
# Получить информацию о рынке включая категорию
GET https://gamma-api.polymarket.com/events
Parameters:
  - conditionId: condition_id

def get_market_category(condition_id: str):
    url = "https://gamma-api.polymarket.com/events"
    params = {"conditionId": condition_id}
    response = requests.get(url, params=params)
    
    if response.status_code == 200:
        data = response.json()
        # Категория может быть в разных полях
        category = (data.get("category") or 
                   data.get("group") or 
                   data.get("tags", [{}])[0].get("name") if data.get("tags") else None)
        return category
    return None
```

#### 2. ML Классификатор (из проекта)

```python
# Использовать существующий классификатор из ml_classifier.py
from ml_classifier import classify_market

def classify_market_category(event_data: dict, slug: str = None, question: str = None):
    """Классифицировать рынок по категории"""
    category = classify_market(event_data, slug, question)
    return category
```

#### 3. База Данных - Категории Трейдеров

```python
# Таблица для отслеживания производительности по категориям
CREATE TABLE trader_category_performance (
    wallet_address TEXT,
    category TEXT,
    markets_traded INTEGER,
    win_rate REAL,
    total_volume REAL,
    total_profit REAL,
    PRIMARY KEY (wallet_address, category)
);
```

### Техническая Реализация

```python
class CategoryConsensusDetector:
    def __init__(self, db, ml_classifier):
        self.db = db
        self.ml_classifier = ml_classifier
    
    def detect_category_consensus(self, condition_id: str, outcome_index: int, 
                                 wallets: List[str]):
        """Обнаружить консенсус в категории"""
        # Классифицировать рынок
        event_data = get_event_data(condition_id)
        category = self.ml_classifier.classify_market(
            event_data, 
            slug=event_data.get("slug"),
            question=event_data.get("question")
        )
        
        if not category:
            return None
        
        # Получить экспертов категории (трейдеры с лучшей производительностью в категории)
        category_experts = self._get_category_experts(category, min_markets=5)
        
        # Проверить, сколько экспертов в консенсусе
        expert_wallets = [w for w in wallets if w in category_experts]
        
        if len(expert_wallets) >= 2:
            return {
                "category": category,
                "expert_count": len(expert_wallets),
                "expert_wallets": expert_wallets,
                "total_consensus": len(wallets),
                "strength": "strong" if len(expert_wallets) >= 3 else "moderate"
            }
        
        return None
    
    def _get_category_experts(self, category: str, min_markets: int = 5) -> List[str]:
        """Получить экспертов категории"""
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT wallet_address
                FROM trader_category_performance
                WHERE category = ?
                  AND markets_traded >= ?
                  AND win_rate >= 0.70
                ORDER BY total_profit DESC
                LIMIT 50
            """, (category, min_markets))
            
            rows = cursor.fetchall()
            return [row[0] for row in rows]
```

---

## 8. Size-Based Signal Routing

### Описание

Направляет сигналы на основе общего размера позиции для разных сегментов пользователей. Разделяет сигналы на категории по уровню убеждения трейдеров.

### Как Работает

1. **Расчет размера**: Вычисляет общий USD размер позиции всех трейдеров в консенсусе
2. **Роутинг**: Направляет в разные Telegram топики:
   - Low Size (<$10K): Стандартные сигналы для обычных пользователей
   - High Size (≥$10K): Премиум сигналы для серьезных трейдеров
3. **Фильтрация**: Позволяет пользователям фильтровать по силе сигнала
4. **Категоризация**: Дополнительные категории для очень крупных позиций

### Источники Данных

#### 1. Polymarket Data API - Активные Позиции

```python
# Получить активные позиции кошелька
GET https://data-api.polymarket.com/positions
Parameters:
  - user: wallet_address
  - market: condition_id (опционально)

def get_wallet_position_size(wallet_address: str, condition_id: str, 
                             outcome_index: int) -> float:
    """Получить размер позиции кошелька для конкретного рынка"""
    url = "https://data-api.polymarket.com/positions"
    params = {
        "user": wallet_address,
        "market": condition_id
    }
    response = requests.get(url, params=params)
    
    if response.status_code == 200:
        positions = response.json()
        for pos in positions:
            if (pos.get("condition_id") == condition_id and 
                pos.get("outcome_index") == outcome_index):
                return float(pos.get("size", 0))
    return 0.0
```

#### 2. Polymarket Data API - История Сделок

```python
# Получить последние сделки для расчета цены входа
GET https://data-api.polymarket.com/trades
Parameters:
  - user: wallet_address
  - market: condition_id
  - side: BUY или SELL
  - limit: количество сделок

def get_wallet_entry_price(wallet_address: str, condition_id: str, 
                           outcome_index: int, side: str = "BUY") -> float:
    """Получить среднюю цену входа кошелька"""
    url = "https://data-api.polymarket.com/trades"
    params = {
        "user": wallet_address,
        "market": condition_id,
        "side": side,
        "limit": 10
    }
    response = requests.get(url, params=params)
    
    if response.status_code == 200:
        trades = response.json()
        if trades:
            prices = [float(t.get("price", 0)) for t in trades]
            return sum(prices) / len(prices) if prices else 0.0
    return 0.0
```

#### 3. База Данных - История Позиций

```python
# Таблица для отслеживания размеров позиций
CREATE TABLE signal_position_sizes (
    signal_id INTEGER,
    wallet_address TEXT,
    condition_id TEXT,
    outcome_index INTEGER,
    position_size REAL,
    entry_price REAL,
    usd_value REAL,
    PRIMARY KEY (signal_id, wallet_address),
    FOREIGN KEY (signal_id) REFERENCES signals(id)
);
```

### Техническая Реализация

```python
class SizeBasedRouter:
    def __init__(self, db, size_threshold_usd=10000, 
                 very_high_size_threshold=50000):
        self.db = db
        self.size_threshold_usd = size_threshold_usd
        self.very_high_size_threshold = very_high_size_threshold
    
    def calculate_total_position_size(self, wallets: List[str], 
                                     wallet_prices: Dict[str, float],
                                     condition_id: str, 
                                     outcome_index: int) -> float:
        """Вычислить общий размер позиции в USD"""
        total_usd = 0.0
        
        for wallet in wallets:
            # Получить размер позиции кошелька
            position_size = get_wallet_position_size(
                wallet, condition_id, outcome_index
            )
            
            # Получить цену входа (из параметра или из API)
            entry_price = wallet_prices.get(wallet, 0.0)
            
            # Если цена не предоставлена, получить из API
            if entry_price == 0.0:
                entry_price = get_wallet_entry_price(
                    wallet, condition_id, outcome_index
                )
            
            # USD стоимость = размер * цена
            if entry_price > 0 and position_size > 0:
                usd_value = position_size * entry_price
                total_usd += usd_value
        
        return total_usd
    
    def route_signal(self, total_usd: float, wallets: List[str],
                    condition_id: str, outcome_index: int,
                    signal_id: int = None) -> dict:
        """Направить сигнал в соответствующий топик и категорию"""
        # Определить категорию размера
        if total_usd >= self.very_high_size_threshold:
            size_category = "very_high"
            topic_id = "very_high_size"  # Очень крупные позиции
            priority = "highest"
        elif total_usd >= self.size_threshold_usd:
            size_category = "high"
            topic_id = "high_size"  # Премиум топик
            priority = "high"
        else:
            size_category = "low"
            topic_id = "low_size"  # Стандартный топик
            priority = "normal"
        
        # Сохранить информацию о размерах позиций в БД
        if signal_id:
            self._save_position_sizes(
                signal_id, wallets, condition_id, outcome_index,
                wallet_prices={}, total_usd=total_usd
            )
        
        return {
            "size_category": size_category,
            "total_usd": total_usd,
            "topic_id": topic_id,
            "priority": priority,
            "wallet_count": len(wallets),
            "avg_position_size": total_usd / len(wallets) if wallets else 0
        }
    
    def _save_position_sizes(self, signal_id: int, wallets: List[str],
                             condition_id: str, outcome_index: int,
                             wallet_prices: Dict[str, float],
                             total_usd: float):
        """Сохранить размеры позиций в БД"""
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            
            for wallet in wallets:
                position_size = get_wallet_position_size(
                    wallet, condition_id, outcome_index
                )
                entry_price = wallet_prices.get(wallet, 0.0)
                
                if entry_price == 0.0:
                    entry_price = get_wallet_entry_price(
                        wallet, condition_id, outcome_index
                    )
                
                usd_value = position_size * entry_price if entry_price > 0 else 0
                
                cursor.execute("""
                    INSERT OR REPLACE INTO signal_position_sizes
                    (signal_id, wallet_address, condition_id, outcome_index,
                     position_size, entry_price, usd_value)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (signal_id, wallet, condition_id, outcome_index,
                      position_size, entry_price, usd_value))
            
            conn.commit()
    
    def get_size_statistics(self, days: int = 7) -> dict:
        """Получить статистику по размерам позиций"""
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)
        
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT 
                    COUNT(*) as total_signals,
                    SUM(CASE WHEN usd_value < ? THEN 1 ELSE 0 END) as low_size,
                    SUM(CASE WHEN usd_value >= ? AND usd_value < ? THEN 1 ELSE 0 END) as high_size,
                    SUM(CASE WHEN usd_value >= ? THEN 1 ELSE 0 END) as very_high_size,
                    AVG(usd_value) as avg_size,
                    MAX(usd_value) as max_size
                FROM signal_position_sizes
                WHERE signal_id IN (
                    SELECT id FROM signals WHERE created_at >= ?
                )
            """, (self.size_threshold_usd, self.size_threshold_usd,
                  self.very_high_size_threshold, self.very_high_size_threshold,
                  cutoff_date.isoformat()))
            
            row = cursor.fetchone()
            return {
                "total_signals": row[0],
                "low_size_count": row[1],
                "high_size_count": row[2],
                "very_high_size_count": row[3],
                "avg_size": row[4] or 0,
                "max_size": row[5] or 0
            }
```

---

## 9. Multi-Timeframe Consensus

### Описание

Обнаруживает консенсусные паттерны на разных временных окнах (5мин, 15мин, 1ч) для подтверждения сигналов и повышения надежности.

### Как Работает

1. **Множественные окна**: Поддерживает несколько скользящих окон на рынок одновременно
2. **Идентификация паттернов**: Идентифицирует консенсусные паттерны на разных таймфреймах
3. **Уверенность**: Предоставляет уверенность сигнала на основе согласованности таймфреймов
4. **Фильтрация**: Фильтрует конфликтующие сигналы между таймфреймами
5. **Валидация**: Требует подтверждения на минимум 2 таймфреймах

### Источники Данных

#### 1. База Данных - Множественные Окна

```python
# Таблица для хранения консенсусов по таймфреймам
CREATE TABLE timeframe_consensus (
    condition_id TEXT,
    outcome_index INTEGER,
    side TEXT,
    timeframe_minutes INTEGER,
    wallet_count INTEGER,
    consensus_detected_at TEXT,
    PRIMARY KEY (condition_id, outcome_index, side, timeframe_minutes, consensus_detected_at)
);

# Индекс для быстрого поиска
CREATE INDEX idx_timeframe_consensus ON timeframe_consensus(
    condition_id, outcome_index, side, timeframe_minutes, consensus_detected_at
);
```

#### 2. Использование ConsensusDetector для каждого таймфрейма

```python
# Каждый таймфрейм использует свой экземпляр ConsensusDetector
# с соответствующим window_minutes
```

### Техническая Реализация

```python
class MultiTimeframeConsensus:
    def __init__(self, db, timeframes: List[int] = [5, 15, 60], min_consensus=3):
        """
        Инициализировать детектор мульти-таймфрейм консенсуса
        
        Args:
            db: База данных
            timeframes: Список таймфреймов в минутах [5, 15, 60]
            min_consensus: Минимальное количество кошельков для консенсуса
        """
        self.db = db
        self.timeframes = timeframes
        self.min_consensus = min_consensus
        
        # Создать детектор консенсуса для каждого таймфрейма
        self.consensus_detectors = {}
        for tf in timeframes:
            self.consensus_detectors[tf] = ConsensusDetector(
                db=db,
                window_minutes=tf,
                min_consensus=min_consensus
            )
    
    def process_trade(self, wallet_address: str, condition_id: str,
                     outcome_index: int, side: str, price: float,
                     timestamp: datetime):
        """Обработать сделку для всех таймфреймов"""
        results = {}
        
        # Обработать сделку для каждого таймфрейма
        for timeframe, detector in self.consensus_detectors.items():
            result = detector.process_trade(
                wallet_address, condition_id, outcome_index,
                side, price, timestamp
            )
            results[timeframe] = result
        
        # Проверить мульти-таймфрейм консенсус
        return self._check_multi_timeframe_consensus(
            condition_id, outcome_index, side, results
        )
    
    def _check_multi_timeframe_consensus(self, condition_id: str,
                                        outcome_index: int, side: str,
                                        timeframe_results: Dict[int, any]) -> dict:
        """Проверить консенсус на нескольких таймфреймах"""
        confirmed_timeframes = []
        timeframe_details = {}
        
        for timeframe, result in timeframe_results.items():
            if result:  # Если консенсус обнаружен на этом таймфрейме
                confirmed_timeframes.append(timeframe)
                timeframe_details[timeframe] = {
                    "wallet_count": result.get("wallet_count", 0),
                    "total_position_usd": result.get("total_position_usd", 0),
                    "detected_at": result.get("timestamp")
                }
        
        # Требуется минимум 2 таймфрейма для подтверждения
        if len(confirmed_timeframes) >= 2:
            # Определить уровень уверенности
            confidence = self._calculate_confidence(
                confirmed_timeframes, timeframe_details
            )
            
            # Сохранить в БД
            self._save_multi_timeframe_consensus(
                condition_id, outcome_index, side,
                confirmed_timeframes, timeframe_details, confidence
            )
            
            return {
                "confirmed": True,
                "timeframes": confirmed_timeframes,
                "timeframe_details": timeframe_details,
                "confidence": confidence,
                "consensus_strength": self._calculate_strength(timeframe_details)
            }
        
        return None
    
    def _calculate_confidence(self, confirmed_timeframes: List[int],
                             timeframe_details: Dict[int, dict]) -> str:
        """Вычислить уровень уверенности на основе таймфреймов"""
        # Если все таймфреймы подтверждены - очень высокая уверенность
        if len(confirmed_timeframes) == len(self.timeframes):
            return "very_high"
        
        # Если подтверждены долгосрочные таймфреймы (15мин, 60мин) - высокая
        if 15 in confirmed_timeframes and 60 in confirmed_timeframes:
            return "high"
        
        # Если подтверждены средние таймфреймы (5мин, 15мин) - средняя
        if 5 in confirmed_timeframes and 15 in confirmed_timeframes:
            return "medium"
        
        # Иначе - низкая
        return "low"
    
    def _calculate_strength(self, timeframe_details: Dict[int, dict]) -> str:
        """Вычислить силу консенсуса"""
        total_wallets = sum([d["wallet_count"] for d in timeframe_details.values()])
        total_position = sum([d["total_position_usd"] for d in timeframe_details.values()])
        
        if total_wallets >= 6 and total_position >= 20000:
            return "very_strong"
        elif total_wallets >= 4 and total_position >= 10000:
            return "strong"
        elif total_wallets >= 3:
            return "moderate"
        else:
            return "weak"
    
    def _save_multi_timeframe_consensus(self, condition_id: str,
                                       outcome_index: int, side: str,
                                       confirmed_timeframes: List[int],
                                       timeframe_details: Dict[int, dict],
                                       confidence: str):
        """Сохранить мульти-таймфрейм консенсус в БД"""
        timestamp = datetime.now(timezone.utc).isoformat()
        
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            
            for timeframe in confirmed_timeframes:
                details = timeframe_details[timeframe]
                cursor.execute("""
                    INSERT INTO timeframe_consensus
                    (condition_id, outcome_index, side, timeframe_minutes,
                     wallet_count, consensus_detected_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (condition_id, outcome_index, side, timeframe,
                      details["wallet_count"], timestamp))
            
            conn.commit()
    
    def get_multi_timeframe_statistics(self, days: int = 7) -> dict:
        """Получить статистику мульти-таймфрейм консенсусов"""
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)
        
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT 
                    COUNT(DISTINCT condition_id || ':' || outcome_index || ':' || side) as total_signals,
                    AVG(wallet_count) as avg_wallet_count,
                    COUNT(CASE WHEN timeframe_minutes = 5 THEN 1 END) as tf_5min_count,
                    COUNT(CASE WHEN timeframe_minutes = 15 THEN 1 END) as tf_15min_count,
                    COUNT(CASE WHEN timeframe_minutes = 60 THEN 1 END) as tf_60min_count
                FROM timeframe_consensus
                WHERE consensus_detected_at >= ?
            """, (cutoff_date.isoformat(),))
            
            row = cursor.fetchone()
            return {
                "total_signals": row[0] or 0,
                "avg_wallet_count": row[1] or 0,
                "tf_5min_signals": row[2] or 0,
                "tf_15min_signals": row[3] or 0,
                "tf_60min_signals": row[4] or 0
            }
    
    def detect_multi_timeframe_consensus(self, condition_id: str,
                                        outcome_index: int, side: str) -> dict:
        """Обнаружить консенсус на нескольких таймфреймах (синхронная проверка)"""
        timeframe_results = {}
        
        # Получить все сделки по этому рынку за последний час
        all_trades = self._get_recent_trades(condition_id, outcome_index, side, hours=1)
        
        # Проверить консенсус для каждого таймфрейма
        for timeframe, detector in self.consensus_detectors.items():
            # Очистить окно детектора
            detector.rolling_windows.clear()
            
            # Обработать все сделки для этого таймфрейма
            for trade in all_trades:
                result = detector.process_trade(
                    trade["wallet"],
                    condition_id,
                    outcome_index,
                    side,
                    trade["price"],
                    trade["timestamp"]
                )
            
            # Проверить текущий консенсус
            key = f"{condition_id}:{outcome_index}:{side}"
            window = detector.rolling_windows.get(key, {})
            wallet_count = len(set(window.get("wallets", [])))
            
            timeframe_results[timeframe] = {
                "has_consensus": wallet_count >= self.min_consensus,
                "wallet_count": wallet_count,
                "wallets": list(set(window.get("wallets", [])))
            }
        
        # Определить согласованность
        consensus_count = sum([
            1 for r in timeframe_results.values() 
            if r["has_consensus"]
        ])
        
        if consensus_count >= 2:
            confirmed_timeframes = [
                tf for tf, r in timeframe_results.items()
                if r["has_consensus"]
            ]
            
            return {
                "confirmed": True,
                "timeframes": confirmed_timeframes,
                "timeframe_details": {
                    tf: {
                        "wallet_count": timeframe_results[tf]["wallet_count"],
                        "wallets": timeframe_results[tf]["wallets"]
                    }
                    for tf in confirmed_timeframes
                },
                "confidence": "high" if consensus_count == 3 else "medium"
            }
        
        return None
    
    def _get_recent_trades(self, condition_id: str, outcome_index: int,
                          side: str, hours: int = 1) -> List[dict]:
        """Получить недавние сделки по рынку"""
        # Получить все отслеживаемые кошельки
        tracked_wallets = self.db.get_tracked_wallets()
        
        all_trades = []
        cutoff_time = datetime.now(timezone.utc) - timedelta(hours=hours)
        
        for wallet in tracked_wallets:
            trades = get_wallet_trades(wallet, side=side, limit=100)
            for trade in trades:
                if (trade.get("condition_id") == condition_id and
                    trade.get("outcome_index") == outcome_index):
                    trade_time = datetime.fromisoformat(
                        trade.get("timestamp", "").replace("Z", "+00:00")
                    )
                    if trade_time >= cutoff_time:
                        all_trades.append({
                            "wallet": wallet,
                            "price": float(trade.get("price", 0)),
                            "timestamp": trade_time
                        })
        
        # Сортировать по времени
        all_trades.sort(key=lambda x: x["timestamp"])
        return all_trades
```

---

## 10. News Correlation Signals

### Описание

Коррелирует торговые сигналы с новостными событиями и активностью в социальных сетях для понимания контекста и подтверждения сигналов.

### Как Работает

1. **Интеграция новостей**: Интегрируется с новостными API (Alpha Vantage, NewsAPI, custom sources)
2. **Мониторинг соцсетей**: Отслеживает упоминания в социальных сетях (Twitter/X, Reddit)
3. **Корреляция**: Коррелирует новостные события с торговой активностью
4. **Контекст**: Предоставляет контекст для консенсусных сигналов
5. **Временной анализ**: Анализирует активность до и после новостей
6. **Sentiment анализ**: Определяет тональность новостей и социальных упоминаний

### Источники Данных

#### 1. Alpha Vantage News API

```python
# Получить новости по ключевым словам
GET https://www.alphavantage.co/query
Parameters:
  - function: NEWS_SENTIMENT
  - apikey: your_api_key
  - topics: topic_keywords (comma-separated)
  - time_from: start_time (YYYYMMDDTHHMM format)
  - time_to: end_time (YYYYMMDDTHHMM format)
  - limit: количество новостей (default: 50)

def get_news_for_market(market_keywords: List[str], hours: int = 24, limit: int = 50):
    """Получить новости для рынка"""
    url = "https://www.alphavantage.co/query"
    params = {
        "function": "NEWS_SENTIMENT",
        "apikey": os.getenv("ALPHA_VANTAGE_API_KEY"),
        "topics": ",".join(market_keywords),
        "time_from": (datetime.now(timezone.utc) - timedelta(hours=hours)).strftime("%Y%m%dT%H%M"),
        "time_to": datetime.now(timezone.utc).strftime("%Y%m%dT%H%M"),
        "limit": limit
    }
    response = requests.get(url, params=params, timeout=10)
    
    if response.status_code == 200:
        data = response.json()
        return data.get("feed", [])
    return []
```

#### 2. NewsAPI (Альтернативный источник)

```python
# Получить новости из NewsAPI
GET https://newsapi.org/v2/everything
Parameters:
  - q: search query
  - apiKey: your_api_key
  - from: start_date (ISO 8601)
  - to: end_date (ISO 8601)
  - sortBy: relevance, popularity, publishedAt
  - language: en

def get_newsapi_news(query: str, hours: int = 24):
    """Получить новости из NewsAPI"""
    url = "https://newsapi.org/v2/everything"
    params = {
        "q": query,
        "apiKey": os.getenv("NEWSAPI_KEY"),
        "from": (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat(),
        "to": datetime.now(timezone.utc).isoformat(),
        "sortBy": "relevance",
        "language": "en"
    }
    response = requests.get(url, params=params, timeout=10)
    
    if response.status_code == 200:
        data = response.json()
        return data.get("articles", [])
    return []
```

#### 3. Twitter/X API v2

```python
# Поиск твитов через Twitter API v2
GET https://api.twitter.com/2/tweets/search/recent
Headers:
  Authorization: Bearer {bearer_token}
Parameters:
  - query: search query
  - max_results: количество результатов (10-100)
  - start_time: start time (ISO 8601)
  - end_time: end time (ISO 8601)

def search_tweets(query: str, count: int = 100, hours: int = 24):
    """Поиск твитов по запросу"""
    url = "https://api.twitter.com/2/tweets/search/recent"
    headers = {
        "Authorization": f"Bearer {os.getenv('TWITTER_BEARER_TOKEN')}"
    }
    params = {
        "query": query,
        "max_results": min(count, 100),
        "start_time": (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat(),
        "tweet.fields": "created_at,public_metrics,author_id",
        "expansions": "author_id"
    }
    
    response = requests.get(url, headers=headers, params=params, timeout=10)
    
    if response.status_code == 200:
        data = response.json()
        return data.get("data", [])
    return []
```

#### 4. Reddit API (через PRAW или Reddit API)

```python
# Поиск постов в Reddit
import praw

def search_reddit_posts(query: str, subreddit: str = None, limit: int = 50):
    """Поиск постов в Reddit"""
    reddit = praw.Reddit(
        client_id=os.getenv("REDDIT_CLIENT_ID"),
        client_secret=os.getenv("REDDIT_CLIENT_SECRET"),
        user_agent="PolyEye/1.0"
    )
    
    if subreddit:
        sub = reddit.subreddit(subreddit)
        posts = sub.search(query, limit=limit, sort="relevance", time_filter="day")
    else:
        posts = reddit.subreddit("all").search(query, limit=limit, sort="relevance", time_filter="day")
    
    return [{
        "title": post.title,
        "score": post.score,
        "created_utc": datetime.fromtimestamp(post.created_utc, tz=timezone.utc),
        "url": post.url,
        "subreddit": post.subreddit.display_name
    } for post in posts]
```

#### 5. База Данных - История Новостей

```python
# Таблица для хранения новостей и корреляций
CREATE TABLE news_correlations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    signal_id INTEGER,
    condition_id TEXT,
    news_source TEXT,
    news_title TEXT,
    news_url TEXT,
    news_published_at TEXT,
    sentiment_score REAL,
    correlation_type TEXT,  -- 'before', 'after', 'during'
    social_mentions_count INTEGER,
    created_at TEXT,
    FOREIGN KEY (signal_id) REFERENCES signals(id)
);

CREATE INDEX idx_news_condition ON news_correlations(condition_id, news_published_at);
```

### Техническая Реализация

```python
class NewsCorrelationAnalyzer:
    def __init__(self, db):
        self.db = db
        self.news_sources = ["alphavantage", "newsapi"]  # Доступные источники
        self.social_sources = ["twitter", "reddit"]  # Доступные социальные источники
    
    def correlate_with_news(self, condition_id: str, consensus_signal: dict,
                           signal_id: int = None) -> dict:
        """Коррелировать сигнал с новостями и социальными медиа"""
        # Получить информацию о рынке
        market_info = get_market_info(condition_id)
        if not market_info:
            return None
        
        # Извлечь ключевые слова из рынка
        keywords = self._extract_keywords(market_info)
        
        # Получить новости из всех источников
        all_news = []
        for source in self.news_sources:
            if source == "alphavantage":
                news = get_news_for_market(keywords, hours=24)
                all_news.extend(news)
            elif source == "newsapi":
                query = " ".join(keywords)
                news = get_newsapi_news(query, hours=24)
                all_news.extend(news)
        
        # Получить социальные упоминания
        social_data = {}
        query = " ".join(keywords)
        
        if "twitter" in self.social_sources:
            tweets = search_tweets(query, count=100, hours=24)
            social_data["twitter"] = {
                "count": len(tweets),
                "tweets": tweets[:10]  # Топ 10 твитов
            }
        
        if "reddit" in self.social_sources:
            reddit_posts = search_reddit_posts(query, limit=50)
            social_data["reddit"] = {
                "count": len(reddit_posts),
                "posts": reddit_posts[:10]  # Топ 10 постов
            }
        
        # Анализировать временную корреляцию
        signal_time = datetime.fromisoformat(
            consensus_signal.get("timestamp", datetime.now(timezone.utc).isoformat())
            .replace("Z", "+00:00")
        )
        
        temporal_analysis = self._analyze_temporal_correlation(
            signal_time, all_news, social_data
        )
        
        # Вычислить sentiment
        sentiment_analysis = self._analyze_sentiment(all_news, social_data)
        
        # Вычислить общий correlation score
        correlation_score = self._calculate_correlation_score(
            consensus_signal, all_news, social_data, temporal_analysis, sentiment_analysis
        )
        
        # Сохранить в БД
        if signal_id:
            self._save_news_correlation(
                signal_id, condition_id, all_news, social_data,
                correlation_score, temporal_analysis
            )
        
        return {
            "correlation_score": correlation_score,
            "news_count": len(all_news),
            "social_mentions": {
                "twitter": social_data.get("twitter", {}).get("count", 0),
                "reddit": social_data.get("reddit", {}).get("count", 0)
            },
            "temporal_analysis": temporal_analysis,
            "sentiment_analysis": sentiment_analysis,
            "recent_news": sorted(all_news, key=lambda x: x.get("published_at", ""), reverse=True)[:5],
            "top_social": {
                "twitter": social_data.get("twitter", {}).get("tweets", [])[:3],
                "reddit": social_data.get("reddit", {}).get("posts", [])[:3]
            }
        }
    
    def _extract_keywords(self, market_info: dict) -> List[str]:
        """Извлечь ключевые слова из информации о рынке"""
        keywords = []
        
        # Из названия рынка
        title = market_info.get("title", "")
        if title:
            # Удалить стоп-слова и извлечь ключевые слова
            stop_words = {"will", "be", "the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for", "of", "with"}
            words = title.lower().split()
            keywords.extend([w for w in words if w not in stop_words and len(w) > 2])
        
        # Из вопроса рынка
        question = market_info.get("question", "")
        if question:
            words = question.lower().split()
            keywords.extend([w for w in words if w not in stop_words and len(w) > 2])
        
        # Из категории
        category = market_info.get("category", "")
        if category:
            keywords.append(category.lower())
        
        # Удалить дубликаты и вернуть
        return list(set(keywords))[:10]  # Максимум 10 ключевых слов
    
    def _analyze_temporal_correlation(self, signal_time: datetime,
                                     news: List[dict], social_data: dict) -> dict:
        """Анализировать временную корреляцию между сигналом и новостями"""
        before_count = 0
        after_count = 0
        during_count = 0
        
        # Анализ новостей
        for article in news:
            published_at = self._parse_news_time(article)
            if not published_at:
                continue
            
            time_diff = (signal_time - published_at).total_seconds() / 3600  # В часах
            
            if time_diff < -1:  # Новость после сигнала
                after_count += 1
            elif time_diff > 1:  # Новость до сигнала
                before_count += 1
            else:  # Новость во время сигнала (±1 час)
                during_count += 1
        
        # Анализ социальных медиа
        for source, data in social_data.items():
            items = data.get("tweets", []) or data.get("posts", [])
            for item in items:
                created_at = self._parse_social_time(item, source)
                if not created_at:
                    continue
                
                time_diff = (signal_time - created_at).total_seconds() / 3600
                
                if time_diff < -1:
                    after_count += 1
                elif time_diff > 1:
                    before_count += 1
                else:
                    during_count += 1
        
        return {
            "before_signal": before_count,
            "during_signal": during_count,
            "after_signal": after_count,
            "total": before_count + during_count + after_count,
            "correlation_type": self._determine_correlation_type(
                before_count, during_count, after_count
            )
        }
    
    def _determine_correlation_type(self, before: int, during: int, after: int) -> str:
        """Определить тип корреляции"""
        if before > during and before > after:
            return "pre_news_activity"  # Активность перед новостями
        elif during > before and during > after:
            return "news_driven"  # Движимо новостями
        elif after > before and after > during:
            return "post_news_confirmation"  # Подтверждение после новостей
        else:
            return "mixed"  # Смешанная корреляция
    
    def _analyze_sentiment(self, news: List[dict], social_data: dict) -> dict:
        """Анализировать sentiment новостей и социальных медиа"""
        # Простой sentiment анализ (можно улучшить с помощью NLP библиотек)
        positive_keywords = ["up", "rise", "gain", "bullish", "positive", "good", "strong", "win"]
        negative_keywords = ["down", "fall", "drop", "bearish", "negative", "bad", "weak", "lose"]
        
        positive_count = 0
        negative_count = 0
        neutral_count = 0
        
        # Анализ новостей
        for article in news:
            text = (article.get("title", "") + " " + article.get("summary", "")).lower()
            pos_score = sum([1 for kw in positive_keywords if kw in text])
            neg_score = sum([1 for kw in negative_keywords if kw in text])
            
            if pos_score > neg_score:
                positive_count += 1
            elif neg_score > pos_score:
                negative_count += 1
            else:
                neutral_count += 1
        
        # Анализ социальных медиа
        for source, data in social_data.items():
            items = data.get("tweets", []) or data.get("posts", [])
            for item in items:
                text = (item.get("text", "") or item.get("title", "")).lower()
                pos_score = sum([1 for kw in positive_keywords if kw in text])
                neg_score = sum([1 for kw in negative_keywords if kw in text])
                
                if pos_score > neg_score:
                    positive_count += 1
                elif neg_score > pos_score:
                    negative_count += 1
                else:
                    neutral_count += 1
        
        total = positive_count + negative_count + neutral_count
        if total == 0:
            return {"sentiment": "neutral", "score": 0.0}
        
        sentiment_score = (positive_count - negative_count) / total
        
        return {
            "sentiment": "positive" if sentiment_score > 0.2 else "negative" if sentiment_score < -0.2 else "neutral",
            "score": sentiment_score,
            "positive": positive_count,
            "negative": negative_count,
            "neutral": neutral_count
        }
    
    def _calculate_correlation_score(self, consensus_signal: dict,
                                     news: List[dict], social_data: dict,
                                     temporal_analysis: dict,
                                     sentiment_analysis: dict) -> float:
        """Вычислить общий correlation score (0.0 - 1.0)"""
        score = 0.0
        
        # Фактор 1: Количество новостей (максимум 0.3)
        news_factor = min(len(news) / 20.0, 1.0) * 0.3
        score += news_factor
        
        # Фактор 2: Социальные упоминания (максимум 0.2)
        social_count = sum([
            social_data.get("twitter", {}).get("count", 0),
            social_data.get("reddit", {}).get("count", 0)
        ])
        social_factor = min(social_count / 100.0, 1.0) * 0.2
        score += social_factor
        
        # Фактор 3: Временная корреляция (максимум 0.3)
        total_temporal = temporal_analysis["total"]
        if total_temporal > 0:
            temporal_factor = min(total_temporal / 30.0, 1.0) * 0.3
            score += temporal_factor
        
        # Фактор 4: Sentiment согласованность (максимум 0.2)
        # Если sentiment положительный и сигнал BUY, или negative и сигнал SELL
        signal_side = consensus_signal.get("side", "BUY")
        sentiment = sentiment_analysis.get("sentiment", "neutral")
        
        if (signal_side == "BUY" and sentiment == "positive") or \
           (signal_side == "SELL" and sentiment == "negative"):
            sentiment_factor = abs(sentiment_analysis.get("score", 0)) * 0.2
            score += sentiment_factor
        
        return min(score, 1.0)  # Ограничить максимум 1.0
    
    def _parse_news_time(self, article: dict) -> Optional[datetime]:
        """Парсить время публикации новости"""
        # Разные форматы времени в разных источниках
        time_str = article.get("published_at") or article.get("time_published") or article.get("publishedAt")
        if not time_str:
            return None
        
        try:
            # Попробовать разные форматы
            formats = [
                "%Y-%m-%dT%H:%M:%S%z",
                "%Y-%m-%dT%H:%M:%SZ",
                "%Y%m%dT%H%M",
                "%Y-%m-%d %H:%M:%S"
            ]
            
            for fmt in formats:
                try:
                    return datetime.strptime(time_str, fmt).replace(tzinfo=timezone.utc)
                except ValueError:
                    continue
            
            # Если ничего не подошло, попробовать ISO формат
            return datetime.fromisoformat(time_str.replace("Z", "+00:00"))
        except Exception:
            return None
    
    def _parse_social_time(self, item: dict, source: str) -> Optional[datetime]:
        """Парсить время создания социального поста"""
        if source == "twitter":
            time_str = item.get("created_at")
        elif source == "reddit":
            return datetime.fromtimestamp(item.get("created_utc", 0), tz=timezone.utc)
        else:
            return None
        
        if not time_str:
            return None
        
        try:
            return datetime.fromisoformat(time_str.replace("Z", "+00:00"))
        except Exception:
            return None
    
    def _save_news_correlation(self, signal_id: int, condition_id: str,
                               news: List[dict], social_data: dict,
                               correlation_score: float,
                               temporal_analysis: dict):
        """Сохранить корреляцию с новостями в БД"""
        timestamp = datetime.now(timezone.utc).isoformat()
        
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            
            # Сохранить каждую новость
            for article in news:
                published_at = self._parse_news_time(article)
                cursor.execute("""
                    INSERT INTO news_correlations
                    (signal_id, condition_id, news_source, news_title, news_url,
                     news_published_at, correlation_type, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    signal_id,
                    condition_id,
                    article.get("source", "unknown"),
                    article.get("title", "")[:500],  # Ограничить длину
                    article.get("url", ""),
                    published_at.isoformat() if published_at else None,
                    temporal_analysis.get("correlation_type", "mixed"),
                    timestamp
                ))
            
            conn.commit()
```

---

**Продолжение следует в следующем файле с описанием дополнительных функций...**
