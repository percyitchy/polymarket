# Poly Eye - Техническая Спецификация Дополнительных Функций

## 🚀 Часть 2: Дополнительные Функции - Детальная Спецификация

---

## 1. Real-Time Dashboard

### Описание
Веб-интерфейс для отображения сигналов в реальном времени с фильтрацией, метриками производительности кошельков и heatmap активности консенсуса.

### Функциональность

#### Основные Компоненты:
1. **Live Signal Feed**: Поток сигналов в реальном времени
2. **Wallet Performance Metrics**: Метрики производительности кошельков
3. **Market Heatmap**: Heatmap активности консенсуса
4. **Historical Signal Performance**: Отслеживание исторической производительности сигналов
5. **Win Rate Statistics**: Статистика win rate по типам сигналов

### Технический Стек

#### Frontend:
- **Framework**: React/Next.js
- **Real-time**: WebSocket для обновлений в реальном времени
- **Charts**: Chart.js или Recharts для визуализации
- **UI Library**: Tailwind CSS или Material-UI

#### Backend:
- **API**: FastAPI (Python) или Express.js (Node.js)
- **WebSocket**: Socket.io или native WebSocket
- **Database**: PostgreSQL для production, SQLite для development

### Источники Данных

#### 1. WebSocket для Real-Time Updates
```python
# Backend: FastAPI WebSocket endpoint
from fastapi import FastAPI, WebSocket
import json

app = FastAPI()

@app.websocket("/ws/signals")
async def websocket_signals(websocket: WebSocket):
    await websocket.accept()
    
    # Подписаться на обновления сигналов
    signal_queue = asyncio.Queue()
    
    async def send_signals():
        while True:
            signal = await signal_queue.get()
            await websocket.send_json(signal)
    
    # Запустить задачу отправки
    task = asyncio.create_task(send_signals())
    
    try:
        while True:
            # Получить сообщение от клиента (фильтры, подписки)
            data = await websocket.receive_json()
            # Обработать подписки/фильтры
            await handle_client_subscription(websocket, data)
    except WebSocketDisconnect:
        task.cancel()

# Frontend: React WebSocket hook
import { useEffect, useState } from 'react';

function useSignalFeed(filters) {
    const [signals, setSignals] = useState([]);
    const [ws, setWs] = useState(null);
    
    useEffect(() => {
        const websocket = new WebSocket('wss://api.polyeye.com/ws/signals');
        
        websocket.onopen = () => {
            // Отправить фильтры
            websocket.send(JSON.stringify({ filters }));
        };
        
        websocket.onmessage = (event) => {
            const signal = JSON.parse(event.data);
            setSignals(prev => [signal, ...prev].slice(0, 100)); // Хранить последние 100
        };
        
        setWs(websocket);
        
        return () => websocket.close();
    }, [filters]);
    
    return signals;
}
```

#### 2. REST API для Исторических Данных
```python
# Endpoint для получения сигналов
@app.get("/api/v1/signals")
async def get_signals(
    limit: int = 50,
    offset: int = 0,
    signal_type: Optional[str] = None,
    category: Optional[str] = None,
    min_consensus: Optional[int] = None
):
    """Получить исторические сигналы с фильтрацией"""
    query = """
        SELECT * FROM signals
        WHERE 1=1
    """
    params = []
    
    if signal_type:
        query += " AND signal_type = ?"
        params.append(signal_type)
    
    if category:
        query += " AND category = ?"
        params.append(category)
    
    if min_consensus:
        query += " AND wallet_count >= ?"
        params.append(min_consensus)
    
    query += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
    params.extend([limit, offset])
    
    # Выполнить запрос и вернуть результаты
    return execute_query(query, params)
```

#### 3. Database Schema
```sql
-- Таблица сигналов
CREATE TABLE signals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    signal_type TEXT NOT NULL,
    condition_id TEXT NOT NULL,
    outcome_index INTEGER NOT NULL,
    side TEXT NOT NULL,
    wallet_count INTEGER NOT NULL,
    total_position_usd REAL,
    category TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    market_title TEXT,
    market_slug TEXT
);

-- Таблица производительности сигналов
CREATE TABLE signal_performance (
    signal_id INTEGER PRIMARY KEY,
    condition_id TEXT NOT NULL,
    outcome_index INTEGER NOT NULL,
    entry_price REAL,
    exit_price REAL,
    pnl REAL,
    win_rate REAL,
    resolved_at TIMESTAMP,
    FOREIGN KEY (signal_id) REFERENCES signals(id)
);

-- Индексы для быстрого поиска
CREATE INDEX idx_signals_created_at ON signals(created_at);
CREATE INDEX idx_signals_type ON signals(signal_type);
CREATE INDEX idx_signals_category ON signals(category);
```

### Реализация Компонентов

#### Signal Feed Component
```typescript
// React компонент для отображения сигналов
import React from 'react';
import { useSignalFeed } from '../hooks/useSignalFeed';

interface Signal {
    id: string;
    signal_type: string;
    market_title: string;
    wallet_count: number;
    total_position_usd: number;
    created_at: string;
}

function SignalFeed({ filters }) {
    const signals = useSignalFeed(filters);
    
    return (
        <div className="signal-feed">
            {signals.map(signal => (
                <SignalCard key={signal.id} signal={signal} />
            ))}
        </div>
    );
}

function SignalCard({ signal }: { signal: Signal }) {
    return (
        <div className="signal-card">
            <h3>{signal.market_title}</h3>
            <p>Type: {signal.signal_type}</p>
            <p>Wallets: {signal.wallet_count}</p>
            <p>Position: ${signal.total_position_usd.toLocaleString()}</p>
            <p>Time: {new Date(signal.created_at).toLocaleString()}</p>
        </div>
    );
}
```

---

## 2. Signal Performance Analytics

### Описание
Отслеживает точность сигналов с течением времени, вычисляет win rate по типам сигналов, ROI и анализирует ложные срабатывания.

### Функциональность

#### Метрики:
1. **Signal Accuracy**: Точность сигналов по типам
2. **Win Rate**: Процент выигрышных сигналов
3. **ROI Calculation**: Расчет ROI для сигналов
4. **False Positive Analysis**: Анализ ложных срабатываний
5. **Signal Quality Scoring**: Оценка качества сигналов

### Источники Данных

#### 1. Polymarket Data API - Resolved Markets
```python
# Получить информацию о разрешенных рынках
GET https://data-api.polymarket.com/markets/{condition_id}

def get_market_resolution(condition_id: str):
    """Получить информацию о разрешении рынка"""
    url = f"https://data-api.polymarket.com/markets/{condition_id}"
    response = requests.get(url)
    
    if response.status_code == 200:
        data = response.json()
        return {
            "resolved": data.get("resolved", False),
            "resolved_outcome": data.get("resolvedOutcome"),
            "resolved_at": data.get("resolvedAt")
        }
    return None
```

#### 2. База Данных - Исторические Сигналы
```python
# Таблица для отслеживания производительности
CREATE TABLE signal_performance_tracking (
    signal_id INTEGER PRIMARY KEY,
    condition_id TEXT NOT NULL,
    outcome_index INTEGER NOT NULL,
    signal_type TEXT NOT NULL,
    entry_price REAL,
    entry_time TIMESTAMP,
    resolved_outcome INTEGER,
    resolved_price REAL,
    resolved_time TIMESTAMP,
    is_win INTEGER,  -- 1 если выигрыш, 0 если проигрыш
    pnl REAL,
    roi REAL,
    FOREIGN KEY (signal_id) REFERENCES signals(id)
);
```

### Техническая Реализация

```python
class SignalPerformanceAnalyzer:
    def __init__(self, db):
        self.db = db
    
    def track_signal_performance(self, signal_id: int, condition_id: str, 
                                outcome_index: int, entry_price: float):
        """Начать отслеживание производительности сигнала"""
        # Сохранить начальную информацию
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO signal_performance_tracking
                (signal_id, condition_id, outcome_index, entry_price, entry_time)
                VALUES (?, ?, ?, ?, ?)
            """, (signal_id, condition_id, outcome_index, entry_price, 
                  datetime.now(timezone.utc).isoformat()))
            conn.commit()
    
    def update_signal_resolution(self, condition_id: str):
        """Обновить разрешение для всех сигналов по рынку"""
        # Получить информацию о разрешении
        resolution = get_market_resolution(condition_id)
        
        if not resolution or not resolution["resolved"]:
            return
        
        resolved_outcome = resolution["resolved_outcome"]
        resolved_price = 1.0 if resolved_outcome == 0 else 0.0  # Упрощенно
        
        # Обновить все сигналы по этому рынку
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE signal_performance_tracking
                SET resolved_outcome = ?,
                    resolved_price = ?,
                    resolved_time = ?,
                    is_win = CASE 
                        WHEN outcome_index = ? THEN 1 
                        ELSE 0 
                    END,
                    pnl = CASE 
                        WHEN outcome_index = ? THEN (1.0 - entry_price) * 100
                        ELSE (0.0 - entry_price) * 100
                    END,
                    roi = CASE 
                        WHEN outcome_index = ? THEN (1.0 - entry_price) / entry_price
                        ELSE (0.0 - entry_price) / entry_price
                    END
                WHERE condition_id = ? AND resolved_time IS NULL
            """, (resolved_outcome, resolved_price, 
                  datetime.now(timezone.utc).isoformat(),
                  resolved_outcome, resolved_outcome, resolved_outcome,
                  condition_id))
            conn.commit()
    
    def get_signal_statistics(self, signal_type: str = None, 
                              days: int = 30) -> dict:
        """Получить статистику производительности сигналов"""
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)
        
        query = """
            SELECT 
                signal_type,
                COUNT(*) as total_signals,
                SUM(is_win) as wins,
                AVG(roi) as avg_roi,
                AVG(pnl) as avg_pnl
            FROM signal_performance_tracking
            WHERE resolved_time >= ?
        """
        params = [cutoff_date.isoformat()]
        
        if signal_type:
            query += " AND signal_type = ?"
            params.append(signal_type)
        
        query += " GROUP BY signal_type"
        
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            rows = cursor.fetchall()
            
            stats = {}
            for row in rows:
                sig_type, total, wins, avg_roi, avg_pnl = row
                stats[sig_type] = {
                    "total": total,
                    "wins": wins,
                    "win_rate": wins / total if total > 0 else 0,
                    "avg_roi": avg_roi,
                    "avg_pnl": avg_pnl
                }
            
            return stats
```

---

## 3. User Feed & Social Features

### Описание
Персонализированная лента сигналов на основе предпочтений пользователя, возможность подписки на конкретные кошельки или трейдеров, комментарии и обсуждения сигналов.

### Функциональность

#### Основные Возможности:
1. **Personalized Feed**: Лента на основе предпочтений пользователя
2. **Follow Wallets**: Подписка на конкретные кошельки
3. **Comments & Discussions**: Комментарии и обсуждения сигналов
4. **Share Signals**: Поделиться сигналами с сообществом
5. **Reputation System**: Система репутации для качества сигналов

### Технический Стек

#### Backend:
- **User Management**: JWT authentication
- **Social Features**: GraphQL или REST API
- **Real-time**: WebSocket для комментариев

#### Database Schema
```sql
-- Таблица пользователей
CREATE TABLE users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT UNIQUE NOT NULL,
    username TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Таблица подписок на кошельки
CREATE TABLE user_wallet_follows (
    user_id INTEGER,
    wallet_address TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (user_id, wallet_address),
    FOREIGN KEY (user_id) REFERENCES users(id)
);

-- Таблица комментариев
CREATE TABLE signal_comments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    signal_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    content TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (signal_id) REFERENCES signals(id),
    FOREIGN KEY (user_id) REFERENCES users(id)
);

-- Таблица репутации сигналов
CREATE TABLE signal_reputation (
    signal_id INTEGER,
    user_id INTEGER,
    rating INTEGER CHECK(rating IN (1, 2, 3, 4, 5)),
    PRIMARY KEY (signal_id, user_id),
    FOREIGN KEY (signal_id) REFERENCES signals(id),
    FOREIGN KEY (user_id) REFERENCES users(id)
);
```

### Реализация

```python
class UserFeedService:
    def __init__(self, db):
        self.db = db
    
    def get_personalized_feed(self, user_id: int, limit: int = 50) -> List[dict]:
        """Получить персонализированную ленту для пользователя"""
        # Получить предпочтения пользователя
        preferences = self._get_user_preferences(user_id)
        
        # Получить подписки на кошельки
        followed_wallets = self._get_followed_wallets(user_id)
        
        # Построить запрос с учетом предпочтений
        query = """
            SELECT s.*
            FROM signals s
            WHERE 1=1
        """
        params = []
        
        # Фильтр по категориям
        if preferences.get("categories"):
            query += " AND s.category IN ({})".format(
                ",".join(["?" for _ in preferences["categories"]])
            )
            params.extend(preferences["categories"])
        
        # Приоритет для подписанных кошельков
        if followed_wallets:
            query += """
                ORDER BY 
                    CASE WHEN EXISTS (
                        SELECT 1 FROM signal_wallets sw 
                        WHERE sw.signal_id = s.id 
                        AND sw.wallet_address IN ({})
                    ) THEN 0 ELSE 1 END,
                    s.created_at DESC
            """.format(",".join(["?" for _ in followed_wallets]))
            params.extend(followed_wallets)
        else:
            query += " ORDER BY s.created_at DESC"
        
        query += " LIMIT ?"
        params.append(limit)
        
        # Выполнить запрос
        return self._execute_query(query, params)
    
    def follow_wallet(self, user_id: int, wallet_address: str):
        """Подписаться на кошелек"""
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR IGNORE INTO user_wallet_follows (user_id, wallet_address)
                VALUES (?, ?)
            """, (user_id, wallet_address))
            conn.commit()
```

---

## 4. SDK & API Access

### Описание
RESTful API для программного доступа, Python SDK для легкой интеграции, WebSocket API для сигналов в реальном времени, поддержка webhooks.

### API Endpoints

#### 1. Signals API
```python
# GET /api/v1/signals - Получить сигналы
@app.get("/api/v1/signals")
async def get_signals(
    limit: int = 50,
    offset: int = 0,
    signal_type: Optional[str] = None,
    category: Optional[str] = None
):
    """Получить список сигналов"""
    pass

# GET /api/v1/signals/{signal_id} - Получить конкретный сигнал
@app.get("/api/v1/signals/{signal_id}")
async def get_signal(signal_id: int):
    """Получить детали сигнала"""
    pass
```

#### 2. Wallets API
```python
# GET /api/v1/wallets - Получить список кошельков
@app.get("/api/v1/wallets")
async def get_wallets(
    min_win_rate: Optional[float] = None,
    min_volume: Optional[float] = None
):
    """Получить список отслеживаемых кошельков"""
    pass

# GET /api/v1/wallets/{address} - Получить информацию о кошельке
@app.get("/api/v1/wallets/{address}")
async def get_wallet(address: str):
    """Получить детальную информацию о кошельке"""
    pass
```

#### 3. Markets API
```python
# GET /api/v1/markets/{condition_id} - Получить информацию о рынке
@app.get("/api/v1/markets/{condition_id}")
async def get_market(condition_id: str):
    """Получить информацию о рынке"""
    pass
```

#### 4. WebSocket API
```python
# WebSocket endpoint для real-time сигналов
@app.websocket("/ws/signals")
async def websocket_signals(websocket: WebSocket):
    """WebSocket для получения сигналов в реальном времени"""
    await websocket.accept()
    
    # Подписка на фильтры
    filters = await websocket.receive_json()
    
    # Отправка сигналов в реальном времени
    async for signal in signal_stream(filters):
        await websocket.send_json(signal)
```

### Python SDK

```python
# polyeye_sdk.py
import requests
from typing import List, Dict, Optional

class PolyEyeClient:
    def __init__(self, api_key: str, base_url: str = "https://api.polyeye.com"):
        self.api_key = api_key
        self.base_url = base_url
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
    
    def get_signals(self, limit: int = 50, signal_type: Optional[str] = None) -> List[Dict]:
        """Получить сигналы"""
        url = f"{self.base_url}/api/v1/signals"
        params = {"limit": limit}
        if signal_type:
            params["signal_type"] = signal_type
        
        response = requests.get(url, headers=self.headers, params=params)
        response.raise_for_status()
        return response.json()
    
    def get_wallet(self, address: str) -> Dict:
        """Получить информацию о кошельке"""
        url = f"{self.base_url}/api/v1/wallets/{address}"
        response = requests.get(url, headers=self.headers)
        response.raise_for_status()
        return response.json()
    
    def subscribe_to_signals(self, callback, filters: Optional[Dict] = None):
        """Подписаться на сигналы через WebSocket"""
        import websocket
        import json
        
        ws_url = f"wss://api.polyeye.com/ws/signals"
        
        def on_message(ws, message):
            signal = json.loads(message)
            callback(signal)
        
        ws = websocket.WebSocketApp(
            ws_url,
            on_message=on_message,
            header=[f"Authorization: Bearer {self.api_key}"]
        )
        
        ws.run_forever()
```

---

## 5. Gasless Trading Integration

### Описание
Интеграция с Polymarket Builder Relayer для gasless транзакций, развертывание Safe Wallets для пользователей, выполнение ордеров одним кликом из сигналов.

### Техническая Реализация

#### Использование Builder Relayer Client
```python
from polymarket_builder_relayer_client import RelayClient
from polymarket_builder_signing_sdk import BuilderConfig, BuilderApiKeyCreds
from ethers import Wallet, providers

class GaslessTradingService:
    def __init__(self, builder_creds: BuilderApiKeyCreds):
        self.relayer_url = "https://relayer-v2.polymarket.com/"
        self.chain_id = 137  # Polygon mainnet
        self.builder_config = BuilderConfig(localBuilderCreds=builder_creds)
    
    def deploy_safe_wallet(self, user_private_key: str):
        """Развернуть Safe Wallet для пользователя"""
        provider = providers.JsonRpcProvider(os.getenv("RPC_URL"))
        wallet = Wallet.from_key(user_private_key, provider)
        
        client = RelayClient(
            self.relayer_url,
            self.chain_id,
            wallet,
            self.builder_config
        )
        
        response = await client.deploySafe()
        result = await response.wait()
        
        if result:
            return {
                "safe_address": result.proxyAddress,
                "transaction_hash": result.transactionHash
            }
        return None
    
    def execute_trade_from_signal(self, signal: dict, user_safe_address: str, 
                                 position_size: float):
        """Выполнить торговлю из сигнала"""
        # Создать ордер на основе сигнала
        order = self._create_order_from_signal(signal, position_size)
        
        # Выполнить через relayer
        # (детали зависят от конкретной реализации)
        pass
```

---

## 6. Portfolio Tracking

### Описание
Отслеживание позиций, открытых из сигналов, расчет P&L, метрики производительности, история сделок, экспорт в CSV/Excel.

### Database Schema
```sql
-- Таблица портфелей пользователей
CREATE TABLE user_portfolios (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    condition_id TEXT NOT NULL,
    outcome_index INTEGER NOT NULL,
    entry_price REAL NOT NULL,
    position_size REAL NOT NULL,
    entry_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    exit_price REAL,
    exit_time TIMESTAMP,
    pnl REAL,
    roi REAL,
    FOREIGN KEY (user_id) REFERENCES users(id)
);
```

### Реализация
```python
class PortfolioTracker:
    def __init__(self, db):
        self.db = db
    
    def add_position(self, user_id: int, condition_id: str, 
                    outcome_index: int, entry_price: float, position_size: float):
        """Добавить позицию в портфель"""
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO user_portfolios
                (user_id, condition_id, outcome_index, entry_price, position_size)
                VALUES (?, ?, ?, ?, ?)
            """, (user_id, condition_id, outcome_index, entry_price, position_size))
            conn.commit()
    
    def get_portfolio(self, user_id: int) -> dict:
        """Получить портфель пользователя"""
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT 
                    COUNT(*) as total_positions,
                    SUM(CASE WHEN exit_time IS NULL THEN 1 ELSE 0 END) as open_positions,
                    SUM(pnl) as total_pnl,
                    AVG(roi) as avg_roi
                FROM user_portfolios
                WHERE user_id = ?
            """, (user_id,))
            
            row = cursor.fetchone()
            return {
                "total_positions": row[0],
                "open_positions": row[1],
                "total_pnl": row[2] or 0,
                "avg_roi": row[3] or 0
            }
```

---

## 7. Alert Customization

### Описание
Пользовательские правила алертов (минимальный консенсус, фильтры кошельков), множественные каналы уведомлений, контроль частоты алертов, фильтрация по категориям.

### Database Schema
```sql
-- Таблица настроек алертов пользователя
CREATE TABLE user_alert_settings (
    user_id INTEGER PRIMARY KEY,
    min_consensus INTEGER DEFAULT 3,
    min_position_size REAL,
    categories TEXT,  -- JSON array
    signal_types TEXT,  -- JSON array
    notification_channels TEXT,  -- JSON array: ['telegram', 'email', 'sms']
    alert_frequency TEXT DEFAULT 'realtime',  -- 'realtime', 'hourly', 'daily'
    FOREIGN KEY (user_id) REFERENCES users(id)
);
```

---

## 8. Mobile App

### Описание
Нативные iOS и Android приложения с push-уведомлениями для сигналов, быстрым выполнением сделок, отслеживанием портфеля.

### Технологии
- **Framework**: React Native или Flutter
- **Push Notifications**: Firebase Cloud Messaging (FCM) или Apple Push Notification Service (APNs)
- **Backend Integration**: REST API и WebSocket

---

## 9. Backtesting & Strategy Builder

### Описание
Backtesting сигнальных стратегий, историческая производительность сигналов, оптимизация стратегий, режим paper trading, инструменты управления рисками.

### Реализация
```python
class BacktestingEngine:
    def __init__(self, db):
        self.db = db
    
    def backtest_strategy(self, strategy_config: dict, start_date: datetime, 
                         end_date: datetime) -> dict:
        """Backtest стратегию на исторических данных"""
        # Получить исторические сигналы
        signals = self._get_historical_signals(start_date, end_date)
        
        # Применить фильтры стратегии
        filtered_signals = self._apply_strategy_filters(signals, strategy_config)
        
        # Симулировать торговлю
        results = self._simulate_trading(filtered_signals, strategy_config)
        
        return {
            "total_signals": len(filtered_signals),
            "total_trades": results["total_trades"],
            "wins": results["wins"],
            "losses": results["losses"],
            "win_rate": results["win_rate"],
            "total_pnl": results["total_pnl"],
            "roi": results["roi"]
        }
```

---

## 10. Integration Marketplace

### Описание
Интеграции с торговыми ботами, Discord бот интеграция, TradingView алерты, Zapier/IFTTT подключения, кастомные webhook интеграции.

### Примеры Интеграций

#### Discord Bot
```python
import discord
from polyeye_sdk import PolyEyeClient

class PolyEyeDiscordBot(discord.Client):
    def __init__(self):
        super().__init__()
        self.polyeye = PolyEyeClient(os.getenv("POLYEYE_API_KEY"))
    
    async def on_ready(self):
        print(f'Logged in as {self.user}')
        # Подписаться на сигналы
        self.polyeye.subscribe_to_signals(self.on_signal)
    
    def on_signal(self, signal):
        """Обработать новый сигнал"""
        channel = self.get_channel(int(os.getenv("DISCORD_CHANNEL_ID")))
        
        embed = discord.Embed(
            title=f"🔮 {signal['signal_type']} Signal",
            description=signal['market_title'],
            color=0x00ff00
        )
        embed.add_field(name="Wallets", value=signal['wallet_count'])
        embed.add_field(name="Position", value=f"${signal['total_position_usd']:,.0f}")
        
        await channel.send(embed=embed)
```

---

**Конец документации**

