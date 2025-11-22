#!/usr/bin/env python3
"""
Анализ оставшихся Unknown рынков для выявления паттернов
"""

import os
import sys
import logging
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from dotenv import load_dotenv
from db import PolymarketDB

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def analyze_unknown_markets(db_path='polymarket_notifier.db'):
    """Анализировать Unknown рынки из wallet_category_stats"""
    db = PolymarketDB(db_path)
    
    with db.get_connection() as conn:
        cursor = conn.cursor()
        
        # Получаем все Unknown рынки с их данными
        cursor.execute("""
            SELECT DISTINCT wallet_address, category
            FROM wallet_category_stats
            WHERE category = 'other/Unknown'
            LIMIT 1000
        """)
        
        unknown_wallets = cursor.fetchall()
        logger.info(f"Найдено {len(unknown_wallets)} кошельков с Unknown категориями")
        
        # Получаем примеры Unknown рынков из закрытых позиций
        # Нужно получить condition_id из закрытых позиций этих кошельков
        condition_ids = set()
        wallet_addresses = [w[0] for w in unknown_wallets[:100]]  # Ограничиваем для анализа
        
        logger.info(f"Анализируем кошельки: {len(wallet_addresses)}")
        
        # Получаем condition_id из rolling_buys (если есть)
        for wallet in wallet_addresses[:50]:  # Ограничиваем для производительности
            try:
                cursor.execute("""
                    SELECT data FROM rolling_buys
                    WHERE k LIKE ?
                    LIMIT 10
                """, (f"%{wallet}%",))
                
                results = cursor.fetchall()
                for row in results:
                    try:
                        import json
                        data = json.loads(row[0])
                        events = data.get("events", [])
                        for event in events:
                            cond_id = event.get("conditionId") or event.get("condition_id")
                            if cond_id:
                                condition_ids.add(cond_id)
                    except:
                        pass
            except Exception as e:
                logger.debug(f"Ошибка при получении данных для {wallet[:12]}...: {e}")
        
        logger.info(f"Собрано {len(condition_ids)} уникальных condition_id для анализа")
        
        # Теперь попробуем получить данные о рынках через API
        from gamma_client import get_event_by_condition_id
        
        market_data = []
        analyzed = 0
        
        for condition_id in list(condition_ids)[:100]:  # Ограничиваем для производительности
            try:
                event = get_event_by_condition_id(condition_id)
                if event:
                    markets = event.get("markets", [])
                    for market in markets:
                        market_condition_id = market.get("conditionId") or market.get("condition_id")
                        if market_condition_id and market_condition_id.lower() == condition_id.lower():
                            slug = market.get("slug") or market.get("marketSlug") or ""
                            question = market.get("question") or market.get("title") or ""
                            description = market.get("description") or ""
                            
                            market_data.append({
                                "condition_id": condition_id,
                                "slug": slug,
                                "question": question,
                                "description": description,
                                "full_text": f"{slug} {question} {description}".lower()
                            })
                            break
                    
                    # Если не нашли в markets, используем event данные
                    if not any(m.get("condition_id") == condition_id for m in market_data):
                        slug = event.get("slug") or event.get("eventSlug") or ""
                        question = event.get("question") or event.get("title") or ""
                        description = event.get("description") or ""
                        
                        market_data.append({
                            "condition_id": condition_id,
                            "slug": slug,
                            "question": question,
                            "description": description,
                            "full_text": f"{slug} {question} {description}".lower()
                        })
                
                analyzed += 1
                if analyzed % 10 == 0:
                    logger.info(f"Проанализировано {analyzed}/{len(condition_ids)} рынков...")
            except Exception as e:
                logger.debug(f"Ошибка при анализе {condition_id[:20]}...: {e}")
        
        logger.info(f"Собрано данных о {len(market_data)} рынках")
        
        # Анализ паттернов
        print("\n" + "=" * 80)
        print("📊 АНАЛИЗ ПАТТЕРНОВ UNKNOWN РЫНКОВ")
        print("=" * 80)
        
        # Извлекаем ключевые слова
        keywords = Counter()
        common_words = Counter()
        
        for market in market_data:
            text = market["full_text"]
            words = text.split()
            
            # Игнорируем стоп-слова
            stop_words = {
                "will", "the", "be", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for",
                "of", "with", "by", "from", "as", "is", "are", "was", "were", "been", "being",
                "have", "has", "had", "do", "does", "did", "this", "that", "these", "those",
                "what", "which", "who", "when", "where", "why", "how", "if", "than", "then"
            }
            
            for word in words:
                word_clean = word.strip(".,!?;:()[]{}'\"").lower()
                if len(word_clean) > 3 and word_clean not in stop_words:
                    keywords[word_clean] += 1
                    common_words[word_clean] += 1
        
        print("\n🔤 Топ-30 ключевых слов в Unknown рынках:")
        for word, count in keywords.most_common(30):
            print(f"   {word:<20} {count:>4}")
        
        # Анализ по типам паттернов
        patterns = {
            "dates": [],
            "numbers": [],
            "questions": [],
            "short_text": [],
            "empty_data": []
        }
        
        for market in market_data:
            text = market["full_text"]
            question = market["question"]
            slug = market["slug"]
            
            # Паттерны с датами
            import re
            if re.search(r'\d{4}-\d{2}-\d{2}|\d{1,2}/\d{1,2}/\d{4}|january|february|march|april|may|june|july|august|september|october|november|december', text, re.IGNORECASE):
                patterns["dates"].append(market)
            
            # Паттерны с числами (цены, проценты)
            if re.search(r'\$[\d,]+|\d+%|\d+\.\d+%', text):
                patterns["numbers"].append(market)
            
            # Вопросы
            if question and '?' in question:
                patterns["questions"].append(market)
            
            # Короткий текст
            if len(text) < 20:
                patterns["short_text"].append(market)
            
            # Пустые данные
            if not text or text.strip() == "":
                patterns["empty_data"].append(market)
        
        print("\n📋 Статистика по паттернам:")
        print(f"   Рынки с датами: {len(patterns['dates'])}")
        print(f"   Рынки с числами/ценами: {len(patterns['numbers'])}")
        print(f"   Рынки-вопросы: {len(patterns['questions'])}")
        print(f"   Короткий текст (<20 символов): {len(patterns['short_text'])}")
        print(f"   Пустые данные: {len(patterns['empty_data'])}")
        
        # Примеры для каждого паттерна
        print("\n📝 Примеры Unknown рынков:")
        print("\n1. Рынки с датами:")
        for market in patterns["dates"][:5]:
            print(f"   • {market['question'][:80] or market['slug'][:80]}")
        
        print("\n2. Рынки с числами/ценами:")
        for market in patterns["numbers"][:5]:
            print(f"   • {market['question'][:80] or market['slug'][:80]}")
        
        print("\n3. Короткий текст:")
        for market in patterns["short_text"][:5]:
            print(f"   • {market['question'][:80] or market['slug'][:80]}")
        
        print("\n4. Пустые данные:")
        for market in patterns["empty_data"][:5]:
            print(f"   • condition_id: {market['condition_id'][:40]}...")
        
        # Рекомендации
        print("\n" + "=" * 80)
        print("💡 РЕКОМЕНДАЦИИ ПО УЛУЧШЕНИЮ КЛАССИФИКАЦИИ:")
        print("=" * 80)
        
        recommendations = []
        
        if len(patterns["empty_data"]) > len(market_data) * 0.3:
            recommendations.append("⚠️  Много рынков с пустыми данными - улучшить получение данных через GraphQL/web scraping")
        
        if len(patterns["short_text"]) > len(market_data) * 0.2:
            recommendations.append("⚠️  Много рынков с коротким текстом - использовать description из API")
        
        if len(patterns["dates"]) > 0:
            recommendations.append("✅ Добавить паттерны для классификации по датам (события, дедлайны)")
        
        if len(patterns["numbers"]) > 0:
            recommendations.append("✅ Добавить паттерны для классификации по ценам/процентам (макро, крипто)")
        
        # Анализ ключевых слов для новых категорий
        top_keywords = [w for w, c in keywords.most_common(50) if c >= 2]
        
        # Проверяем, какие ключевые слова не покрыты текущими категориями
        from market_utils import (
            NFL_TEAMS, NBA_TEAMS, NHL_TEAMS, MLB_TEAMS,
            CRYPTO_KEYWORDS, POLITICS_KEYWORDS, MACRO_KEYWORDS,
            STOCKS_KEYWORDS, ENTERTAINMENT_KEYWORDS, TECH_KEYWORDS
        )
        
        all_known_keywords = set()
        for kw_list in [NFL_TEAMS, NBA_TEAMS, NHL_TEAMS, MLB_TEAMS,
                        CRYPTO_KEYWORDS, POLITICS_KEYWORDS, MACRO_KEYWORDS,
                        STOCKS_KEYWORDS, ENTERTAINMENT_KEYWORDS, TECH_KEYWORDS]:
            all_known_keywords.update([k.lower() for k in kw_list])
        
        unknown_keywords = [kw for kw in top_keywords if kw not in all_known_keywords]
        
        if unknown_keywords:
            recommendations.append(f"📝 Новые ключевые слова для добавления: {', '.join(unknown_keywords[:20])}")
        
        for rec in recommendations:
            print(f"   {rec}")
        
        print("\n" + "=" * 80)
        
        return {
            "total_analyzed": len(market_data),
            "patterns": patterns,
            "top_keywords": dict(keywords.most_common(30)),
            "unknown_keywords": unknown_keywords[:20],
            "recommendations": recommendations
        }

if __name__ == "__main__":
    db_path = os.getenv('DB_PATH', 'polymarket_notifier.db')
    if not os.path.isabs(db_path):
        db_path = os.path.abspath(db_path)
    
    results = analyze_unknown_markets(db_path)
    
    print(f"\n✅ Анализ завершён. Проанализировано {results['total_analyzed']} рынков.")
