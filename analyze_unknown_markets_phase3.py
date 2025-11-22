#!/usr/bin/env python3
"""
Analyze remaining Unknown markets to identify patterns and improve classification
"""

import os
import sys
import requests
from collections import Counter
from typing import List, Dict, Any
from dotenv import load_dotenv
from db import PolymarketDB

load_dotenv()

def get_unknown_markets_sample(db: PolymarketDB, limit: int = 1000) -> List[Dict[str, Any]]:
    """Get sample of wallets with Unknown categories"""
    with db.get_connection() as conn:
        cursor = conn.cursor()
        
        # Get wallets with Unknown categories
        cursor.execute('''
            SELECT DISTINCT wallet_address, SUM(markets) as unknown_markets
            FROM wallet_category_stats
            WHERE category = "other/Unknown"
            GROUP BY wallet_address
            ORDER BY unknown_markets DESC
            LIMIT ?
        ''', (limit,))
        
        return cursor.fetchall()

def fetch_closed_positions(address: str, limit: int = 50) -> List[Dict[str, Any]]:
    """Fetch closed positions for a wallet"""
    try:
        url = "https://data-api.polymarket.com/closed-positions"
        params = {"user": address, "limit": limit}
        response = requests.get(url, params=params, timeout=10)
        
        if response.status_code == 200:
            return response.json() if isinstance(response.json(), list) else []
        return []
    except Exception as e:
        print(f"Error fetching positions for {address[:20]}...: {e}")
        return []

def get_market_data_from_clob(condition_id: str) -> Dict[str, Any]:
    """Get market data from CLOB API"""
    try:
        url = f"https://clob.polymarket.com/markets/{condition_id}"
        response = requests.get(url, timeout=10)
        
        if response.status_code == 200:
            return response.json()
        return {}
    except Exception as e:
        return {}

def analyze_unknown_markets():
    """Analyze Unknown markets to find patterns"""
    db_path = os.getenv('DB_PATH', 'polymarket_notifier.db')
    if not os.path.isabs(db_path):
        db_path = os.path.abspath(db_path)
    
    db = PolymarketDB(db_path)
    
    print("=" * 100)
    print("АНАЛИЗ UNKNOWN РЫНКОВ (ФАЗА 3)")
    print("=" * 100)
    print()
    
    # Get sample wallets
    print("📋 Получение кошельков с Unknown категориями...")
    wallets = get_unknown_markets_sample(db, limit=100)
    print(f"✅ Найдено {len(wallets)} кошельков с Unknown категориями")
    print()
    
    all_titles = []
    all_slugs = []
    all_keywords = []
    markets_with_data = 0
    markets_without_data = 0
    
    print("🔍 Анализ рынков...")
    print()
    
    for i, (wallet_addr, unknown_count) in enumerate(wallets[:50], 1):  # Analyze first 50 wallets
        print(f"[{i}/{min(50, len(wallets))}] Кошелёк: {wallet_addr[:20]}... ({unknown_count} Unknown рынков)")
        
        positions = fetch_closed_positions(wallet_addr, limit=50)
        
        for pos in positions[:20]:  # Analyze first 20 positions per wallet
            condition_id = pos.get("conditionId") or pos.get("condition_id")
            if not condition_id:
                continue
            
            # Get data from position
            title = pos.get("title")
            slug = pos.get("slug") or pos.get("eventSlug")
            
            # If no data, try CLOB API
            if not title and not slug:
                clob_data = get_market_data_from_clob(condition_id)
                title = clob_data.get("question") or clob_data.get("title")
                slug = clob_data.get("slug") or clob_data.get("market_slug")
            
            if title or slug:
                markets_with_data += 1
                if title:
                    all_titles.append(title.lower())
                    # Extract words
                    words = title.lower().replace('-', ' ').replace('_', ' ').replace('?', '').replace('!', '').split()
                    all_keywords.extend([w for w in words if len(w) > 2])
                
                if slug:
                    all_slugs.append(slug.lower())
                    words = slug.lower().replace('-', ' ').replace('_', ' ').split()
                    all_keywords.extend([w for w in words if len(w) > 2])
            else:
                markets_without_data += 1
        
        if i % 10 == 0:
            print(f"   Обработано {i} кошельков...")
    
    print()
    print("=" * 100)
    print("РЕЗУЛЬТАТЫ АНАЛИЗА")
    print("=" * 100)
    print()
    
    print(f"📊 Статистика:")
    print(f"   • Рынков с данными: {markets_with_data}")
    print(f"   • Рынков без данных: {markets_without_data}")
    print(f"   • Всего проанализировано: {markets_with_data + markets_without_data}")
    print()
    
    if markets_without_data > 0:
        pct_no_data = markets_without_data / (markets_with_data + markets_without_data) * 100
        print(f"⚠️  {pct_no_data:.1f}% рынков не имеют данных (title/slug)")
        print()
    
    if all_titles:
        print(f"📝 Примеры Unknown рынков (первые 20):")
        for i, title in enumerate(all_titles[:20], 1):
            print(f"   {i}. {title[:80]}")
        print()
    
    if all_keywords:
        print(f"🔑 Топ-50 ключевых слов из Unknown рынков:")
        keyword_counts = Counter(all_keywords)
        
        # Filter out common stop words
        stop_words = {'will', 'the', 'and', 'for', 'are', 'but', 'not', 'you', 'all', 'can', 'her', 'was', 'one', 'our', 'out', 'day', 'get', 'has', 'him', 'his', 'how', 'its', 'may', 'new', 'now', 'old', 'see', 'two', 'way', 'who', 'boy', 'did', 'its', 'let', 'put', 'say', 'she', 'too', 'use'}
        
        filtered_keywords = Counter({k: v for k, v in keyword_counts.items() if k not in stop_words and len(k) > 2})
        
        for keyword, count in filtered_keywords.most_common(50):
            print(f"   • {keyword:<20} ({count} раз)")
        print()
    
    # Analyze patterns
    print("🔍 Анализ паттернов:")
    print()
    
    # Check for common patterns
    patterns = {
        'dates': sum(1 for t in all_titles if any(month in t for month in ['january', 'february', 'march', 'april', 'may', 'june', 'july', 'august', 'september', 'october', 'november', 'december'])),
        'numbers': sum(1 for t in all_titles if any(char.isdigit() for char in t)),
        'questions': sum(1 for t in all_titles if '?' in t),
        'crypto_mentions': sum(1 for t in all_titles if any(crypto in t for crypto in ['bitcoin', 'ethereum', 'crypto', 'btc', 'eth'])),
        'sports_mentions': sum(1 for t in all_titles if any(sport in t for sport in ['nfl', 'nba', 'nhl', 'mlb', 'soccer', 'football', 'basketball'])),
        'politics_mentions': sum(1 for t in all_titles if any(pol in t for pol in ['election', 'president', 'trump', 'biden', 'vote'])),
    }
    
    for pattern, count in patterns.items():
        if count > 0:
            pct = count / len(all_titles) * 100 if all_titles else 0
            print(f"   • {pattern}: {count} ({pct:.1f}%)")
    
    print()
    print("=" * 100)
    print("РЕКОМЕНДАЦИИ")
    print("=" * 100)
    print()
    
    if markets_without_data > markets_with_data:
        print("1. ⚠️  Основная проблема: отсутствие данных в API")
        print("   → Необходимо улучшить источники данных (GraphQL API, парсинг веб-страниц)")
        print()
    
    if all_keywords:
        print("2. 📝 Расширить ключевые слова на основе топ-50 найденных слов")
        print()
    
    if patterns.get('dates', 0) > len(all_titles) * 0.3:
        print("3. 📅 Много рынков с датами - возможно, нужна категория 'events/Dates'")
        print()
    
    print("=" * 100)

if __name__ == "__main__":
    analyze_unknown_markets()

