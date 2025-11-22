#!/usr/bin/env python3
"""
Фильтрация кошельков по новым критериям:
- Win rate рассчитывается по рынкам (не по сделкам)
- Учитываются только рынки за последние 3 месяца или последние 100
- Минимальный порог: ≥6 рынков, торговый объём ≥5000 USDC, win rate ≥70%
"""

import os
import sys
import time
import logging
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any, Optional, Tuple
from collections import defaultdict
import requests
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Конфигурация
DATA_API = "https://data-api.polymarket.com"
CLOSED_POSITIONS_ENDPOINT = f"{DATA_API}/closed-positions"
REQUEST_TIMEOUT = 10
MAX_POSITIONS_TO_FETCH = 500  # Получаем больше, чтобы после фильтрации осталось достаточно (для 250 рынков)

# Критерии фильтрации (новые строгие критерии)
MIN_MARKETS = int(os.getenv("MINIMUM_MARKETS", "12"))  # Минимальное количество закрытых рынков (≥12)
MIN_VOLUME_USD = float(os.getenv("MINIMUM_VOLUME", "25000.0"))  # Минимальный торговый объём в USDC ($25,000)
MIN_WIN_RATE = float(os.getenv("WIN_RATE_THRESHOLD", "0.70"))  # Минимальный win rate (70%)
MIN_ROI = float(os.getenv("MINIMUM_ROI", "0.0025"))  # Минимальный ROI (0.25%)
MIN_AVG_PNL = float(os.getenv("MINIMUM_AVG_PNL", "50.0"))  # Минимальная средняя прибыль на рынок ($50)
MIN_AVG_STAKE = float(os.getenv("MINIMUM_AVG_STAKE", "100.0"))  # Минимальный средний размер ставки ($100)
LOOKBACK_MONTHS = 3  # Период анализа (последние 3 месяца)
MAX_MARKETS_TO_ANALYZE = int(os.getenv("MAX_CLOSED_POSITIONS", "250"))  # Максимум рынков для анализа (250 или 3 месяца, что больше)


def get_closed_positions(address: str, max_positions: int = MAX_POSITIONS_TO_FETCH) -> List[Dict[str, Any]]:
    """
    Получить закрытые позиции для кошелька из Data API.
    
    Returns:
        List[Dict]: Список закрытых позиций
    """
    positions = []
    offset = 0
    page_limit = 500
    
    try:
        while len(positions) < max_positions:
            limit = min(page_limit, max_positions - len(positions))
            params = {"user": address, "limit": limit, "offset": offset}
            
            response = requests.get(
                CLOSED_POSITIONS_ENDPOINT,
                params=params,
                timeout=REQUEST_TIMEOUT,
                headers={"User-Agent": "PolymarketNotifier/1.0"}
            )
            
            if response.status_code != 200:
                logger.warning(f"API error for {address}: status {response.status_code}")
                break
            
            data = response.json()
            batch = data if isinstance(data, list) else (data.get("positions", []) if isinstance(data, dict) else [])
            
            if not batch:
                break
            
            positions.extend(batch)
            offset += len(batch)
            
            if len(batch) < limit:
                break
                
    except Exception as e:
        logger.error(f"Error fetching closed positions for {address}: {e}")
        return []
    
    return positions


def filter_positions_by_time(positions: List[Dict[str, Any]], lookback_months: int = LOOKBACK_MONTHS, max_markets: int = MAX_MARKETS_TO_ANALYZE) -> List[Dict[str, Any]]:
    """
    Фильтровать позиции по времени: только последние N месяцев или последние MAX_MARKETS_TO_ANALYZE (что больше).
    
    Returns:
        List[Dict]: Отфильтрованные позиции, отсортированные по времени закрытия (новые первыми)
    """
    if not positions:
        return []
    
    # Вычисляем временную границу (последние 3 месяца)
    cutoff_time = datetime.now(timezone.utc) - timedelta(days=lookback_months * 30)
    cutoff_timestamp = cutoff_time.timestamp()
    
    # Извлекаем timestamp из каждой позиции
    def get_timestamp(pos: Dict[str, Any]) -> float:
        """Извлечь timestamp закрытия позиции"""
        timestamp = (
            pos.get("closed_at") or 
            pos.get("closedAt") or 
            pos.get("timestamp") or 
            pos.get("created_at") or 
            pos.get("createdAt") or
            0
        )
        
        # Обработка строковых timestamp
        if isinstance(timestamp, str):
            try:
                dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
                return dt.timestamp()
            except Exception:
                return 0.0
        
        # Обработка числовых timestamp (может быть в миллисекундах)
        if isinstance(timestamp, (int, float)):
            if timestamp > 1e10:
                return timestamp / 1000.0
            return float(timestamp)
        
        return 0.0
    
    # Фильтруем и сортируем
    filtered = []
    for pos in positions:
        ts = get_timestamp(pos)
        if ts > cutoff_timestamp:
            filtered.append(pos)
    
    # Сортируем по timestamp (новые первыми)
    filtered.sort(key=get_timestamp, reverse=True)
    
    # Ограничиваем максимумом (250 рынков или 3 месяца, что больше)
    # Если у нас больше позиций за последние 3 месяца, чем max_markets, берём последние max_markets
    if len(filtered) > max_markets:
        filtered = filtered[:max_markets]
    
    return filtered


def group_positions_by_market(positions: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    """
    Сгруппировать позиции по conditionId (рынку).
    
    Returns:
        Dict[str, List[Dict]]: Словарь {condition_id: [позиции]}
    """
    grouped = defaultdict(list)
    
    for pos in positions:
        condition_id = pos.get("conditionId") or pos.get("condition_id")
        if condition_id:
            grouped[condition_id].append(pos)
    
    return dict(grouped)


def calculate_market_pnl(positions: List[Dict[str, Any]]) -> float:
    """
    Рассчитать итоговый PnL для рынка (сумма всех realizedPnl по позициям этого рынка).
    
    Returns:
        float: Суммарный PnL для рынка
    """
    total_pnl = 0.0
    
    for pos in positions:
        pnl = pos.get("realizedPnl") or pos.get("realized_pnl") or 0
        try:
            total_pnl += float(pnl)
        except (ValueError, TypeError):
            continue
    
    return total_pnl


def calculate_market_volume(positions: List[Dict[str, Any]]) -> float:
    """
    Рассчитать торговый объём для рынка (сумма totalBought или аналогичных полей).
    
    Returns:
        float: Суммарный объём в USDC
    """
    total_volume = 0.0
    
    for pos in positions:
        # Пробуем разные поля для объёма
        volume = (
            pos.get("totalBought") or 
            pos.get("total_bought") or 
            pos.get("volume") or 
            pos.get("usdVolume") or
            0
        )
        try:
            total_volume += float(volume)
        except (ValueError, TypeError):
            continue
    
    return total_volume


def calculate_market_stake(positions: List[Dict[str, Any]]) -> float:
    """
    Рассчитать размер ставки для рынка (totalBought * avgPrice).
    
    Ставка по рынку = totalBought * avgPrice (в долларах).
    
    Returns:
        float: Размер ставки в USDC
    """
    total_stake = 0.0
    
    for pos in positions:
        # Получаем totalBought (количество токенов)
        total_bought = pos.get("totalBought") or pos.get("total_bought") or 0
        # Получаем avgPrice (средняя цена в долларах)
        avg_price = pos.get("avgPrice") or pos.get("avg_price") or pos.get("price") or 0
        
        try:
            total_bought_val = float(total_bought)
            avg_price_val = float(avg_price)
            # Ставка = количество токенов * средняя цена
            stake = total_bought_val * avg_price_val
            total_stake += stake
        except (ValueError, TypeError):
            # Если нет данных, пробуем использовать totalBought как объём (если он уже в долларах)
            try:
                volume = pos.get("totalBought") or pos.get("total_bought") or pos.get("volume") or 0
                total_stake += float(volume)
            except (ValueError, TypeError):
                continue
    
    return total_stake


def analyze_wallet(address: str) -> Optional[Dict[str, Any]]:
    """
    Проанализировать кошелёк по новым критериям.
    
    Returns:
        Dict с метриками или None, если не прошёл фильтры
    """
    try:
        # Шаг 1: Получить закрытые позиции
        all_positions = get_closed_positions(address)
        if not all_positions:
            logger.debug(f"{address}: No closed positions found")
            return None
        
        # Шаг 2: Фильтровать по времени (последние 3 месяца или последние 250, что больше)
        recent_positions = filter_positions_by_time(all_positions, lookback_months=LOOKBACK_MONTHS, max_markets=MAX_MARKETS_TO_ANALYZE)
        if not recent_positions:
            logger.debug(f"{address}: No recent positions (last {LOOKBACK_MONTHS} months or {MAX_MARKETS_TO_ANALYZE} markets)")
            return None
        
        # Шаг 3: Группировать по рынкам (conditionId)
        markets = group_positions_by_market(recent_positions)
        
        if len(markets) < MIN_MARKETS:
            logger.debug(f"{address}: Only {len(markets)} markets (< {MIN_MARKETS})")
            return None
        
        # Шаг 4: Рассчитать метрики по каждому рынку
        market_results = []
        total_volume = 0.0
        total_pnl = 0.0
        total_stakes = 0.0  # Сумма всех ставок для расчёта средней ставки
        
        for condition_id, market_positions in markets.items():
            market_pnl = calculate_market_pnl(market_positions)
            market_volume = calculate_market_volume(market_positions)
            market_stake = calculate_market_stake(market_positions)
            
            market_results.append({
                "condition_id": condition_id,
                "pnl": market_pnl,
                "volume": market_volume,
                "stake": market_stake,
                "positions_count": len(market_positions),
                "won": market_pnl > 0
            })
            
            total_volume += market_volume
            total_pnl += market_pnl
            total_stakes += market_stake
        
        # Шаг 5: Проверить минимальное количество рынков
        total_markets = len(market_results)
        if total_markets < MIN_MARKETS:
            logger.debug(f"{address}: Only {total_markets} markets (< {MIN_MARKETS})")
            return None
        
        # Шаг 6: Проверить минимальный объём
        if total_volume < MIN_VOLUME_USD:
            logger.debug(f"{address}: Total volume ${total_volume:.2f} < ${MIN_VOLUME_USD}")
            return None
        
        # Шаг 7: Рассчитать win rate по рынкам
        won_markets = sum(1 for m in market_results if m["won"])
        win_rate = won_markets / total_markets if total_markets > 0 else 0.0
        
        # Шаг 8: Проверить минимальный win rate
        if win_rate < MIN_WIN_RATE:
            logger.debug(f"{address}: Win rate {win_rate:.2%} < {MIN_WIN_RATE:.0%}")
            return None
        
        # Шаг 9: Рассчитать ROI (Total PnL / Total Volume)
        roi = total_pnl / total_volume if total_volume > 0 else 0.0
        
        # Шаг 10: Проверить минимальный ROI
        if roi < MIN_ROI:
            logger.debug(f"{address}: ROI {roi:.4%} < {MIN_ROI:.4%}")
            return None
        
        # Шаг 11: Рассчитать среднюю прибыль на рынок
        avg_pnl_per_market = total_pnl / total_markets if total_markets > 0 else 0.0
        
        # Шаг 12: Проверить минимальную среднюю прибыль на рынок
        if avg_pnl_per_market < MIN_AVG_PNL:
            logger.debug(f"{address}: Avg PnL per market ${avg_pnl_per_market:.2f} < ${MIN_AVG_PNL}")
            return None
        
        # Шаг 13: Рассчитать средний размер ставки
        avg_stake = total_stakes / total_markets if total_markets > 0 else 0.0
        
        # Шаг 14: Проверить минимальный средний размер ставки
        if avg_stake < MIN_AVG_STAKE:
            logger.debug(f"{address}: Avg stake ${avg_stake:.2f} < ${MIN_AVG_STAKE}")
            return None
        
        # Шаг 15: Дополнительные метрики
        # Profit factor: сумма положительных PnL / сумма абсолютных отрицательных PnL
        positive_pnl = sum(m["pnl"] for m in market_results if m["pnl"] > 0)
        negative_pnl_abs = abs(sum(m["pnl"] for m in market_results if m["pnl"] < 0))
        profit_factor = positive_pnl / negative_pnl_abs if negative_pnl_abs > 0 else float('inf')
        
        # Шаг 16: Результат
        result = {
            "address": address,
            "total_markets": total_markets,
            "won_markets": won_markets,
            "lost_markets": total_markets - won_markets,
            "win_rate": win_rate,
            "roi": roi,
            "total_volume_usd": total_volume,
            "total_pnl": total_pnl,
            "avg_pnl_per_market": avg_pnl_per_market,
            "avg_stake": avg_stake,
            "profit_factor": profit_factor,
            "recent_positions_count": len(recent_positions),
            "all_positions_count": len(all_positions)
        }
        
        logger.info(
            f"✅ {address}: {total_markets} markets, "
            f"{win_rate:.1%} win rate, "
            f"{roi:.2%} ROI, "
            f"${total_volume:.0f} volume, "
            f"${total_pnl:.0f} PnL, "
            f"${avg_pnl_per_market:.0f} avg PnL/market, "
            f"${avg_stake:.0f} avg stake"
        )
        
        return result
        
    except Exception as e:
        logger.error(f"Error analyzing {address}: {e}", exc_info=True)
        return None


def main():
    """Основная функция"""
    # Читаем список кошельков из файла
    input_file = "tracked_wallets_20251114_230313.txt"
    
    if not os.path.exists(input_file):
        logger.error(f"File not found: {input_file}")
        sys.exit(1)
    
    logger.info(f"Reading wallets from {input_file}")
    
    wallets = []
    with open(input_file, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line and line.startswith('0x') and len(line) == 42:
                wallets.append(line.lower())
    
    logger.info(f"Loaded {len(wallets)} wallets from file")
    logger.info("=" * 80)
    logger.info("Starting analysis with NEW STRICT criteria:")
    logger.info(f"  • Min markets: {MIN_MARKETS}")
    logger.info(f"  • Min volume: ${MIN_VOLUME_USD:,.0f} USDC")
    logger.info(f"  • Min win rate: {MIN_WIN_RATE:.0%}")
    logger.info(f"  • Min ROI: {MIN_ROI:.2%}")
    logger.info(f"  • Min avg PnL per market: ${MIN_AVG_PNL:.2f}")
    logger.info(f"  • Min avg stake: ${MIN_AVG_STAKE:.2f}")
    logger.info(f"  • Lookback period: {LOOKBACK_MONTHS} months or {MAX_MARKETS_TO_ANALYZE} markets (whichever is greater)")
    logger.info("=" * 80)
    
    # Анализируем каждый кошелёк
    passed_wallets = []
    failed_wallets = []
    
    for i, address in enumerate(wallets, 1):
        if i % 100 == 0:
            logger.info(f"Progress: {i}/{len(wallets)} ({i*100/len(wallets):.1f}%)")
        
        result = analyze_wallet(address)
        
        if result:
            passed_wallets.append(result)
        else:
            failed_wallets.append(address)
        
        # Небольшая задержка, чтобы не перегружать API
        time.sleep(0.1)
    
    # Сортируем прошедшие кошельки по win rate и объёму
    passed_wallets.sort(key=lambda x: (x["win_rate"], x["total_volume_usd"]), reverse=True)
    
    # Создаём файл с результатами
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = f"filtered_wallets_new_criteria_{timestamp}.txt"
    
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write("=" * 80 + "\n")
        f.write("Фильтрация кошельков по новым критериям\n")
        f.write("=" * 80 + "\n")
        f.write(f"Дата анализа: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"Всего проанализировано: {len(wallets)}\n")
        f.write(f"Прошли фильтры: {len(passed_wallets)}\n")
        f.write(f"Не прошли фильтры: {len(failed_wallets)}\n")
        f.write("\n")
        f.write("Критерии фильтрации (НОВЫЕ СТРОГИЕ):\n")
        f.write(f"  • Минимум рынков: {MIN_MARKETS}\n")
        f.write(f"  • Минимум объёма: ${MIN_VOLUME_USD:,.0f} USDC\n")
        f.write(f"  • Минимум win rate: {MIN_WIN_RATE:.0%}\n")
        f.write(f"  • Минимум ROI: {MIN_ROI:.2%}\n")
        f.write(f"  • Минимум средняя прибыль на рынок: ${MIN_AVG_PNL:.2f}\n")
        f.write(f"  • Минимум средний размер ставки: ${MIN_AVG_STAKE:.2f}\n")
        f.write(f"  • Период анализа: последние {LOOKBACK_MONTHS} месяца или последние {MAX_MARKETS_TO_ANALYZE} рынков (что больше)\n")
        f.write("=" * 80 + "\n\n")
        
        f.write("=" * 80 + "\n")
        f.write("КОШЕЛЬКИ, ПРОШЕДШИЕ ФИЛЬТРЫ\n")
        f.write("=" * 80 + "\n\n")
        
        for i, wallet in enumerate(passed_wallets, 1):
            f.write(f"{i}. {wallet['address']}\n")
            f.write(f"   Markets: {wallet['total_markets']} (won: {wallet['won_markets']}, lost: {wallet['lost_markets']})\n")
            f.write(f"   Win Rate: {wallet['win_rate']:.2%}\n")
            f.write(f"   ROI: {wallet['roi']:.2%}\n")
            f.write(f"   Total Volume: ${wallet['total_volume_usd']:,.2f} USDC\n")
            f.write(f"   Total PnL: ${wallet['total_pnl']:,.2f}\n")
            f.write(f"   Avg PnL per Market: ${wallet['avg_pnl_per_market']:,.2f}\n")
            f.write(f"   Avg Stake: ${wallet['avg_stake']:,.2f}\n")
            f.write(f"   Profit Factor: {wallet['profit_factor']:.2f}\n")
            f.write(f"   Recent Positions: {wallet['recent_positions_count']} (from {wallet['all_positions_count']} total)\n")
            f.write("\n")
    
    # Также создаём файл только с адресами
    addresses_file = f"filtered_wallets_addresses_{timestamp}.txt"
    with open(addresses_file, 'w', encoding='utf-8') as f:
        for wallet in passed_wallets:
            f.write(f"{wallet['address']}\n")
    
    # Выводим статистику
    print("\n" + "=" * 80)
    print("✅ Анализ завершён")
    print("=" * 80)
    print(f"Всего проанализировано: {len(wallets)}")
    print(f"Прошли фильтры: {len(passed_wallets)}")
    print(f"Не прошли фильтры: {len(failed_wallets)}")
    print("=" * 80)
    print(f"\nФайлы созданы:")
    print(f"  • Детальный отчёт: {output_file}")
    print(f"  • Только адреса: {addresses_file}")
    
    if passed_wallets:
        avg_win_rate = sum(w["win_rate"] for w in passed_wallets) / len(passed_wallets)
        avg_roi = sum(w["roi"] for w in passed_wallets) / len(passed_wallets)
        avg_volume = sum(w["total_volume_usd"] for w in passed_wallets) / len(passed_wallets)
        avg_pnl = sum(w["avg_pnl_per_market"] for w in passed_wallets) / len(passed_wallets)
        avg_stake = sum(w["avg_stake"] for w in passed_wallets) / len(passed_wallets)
        print(f"\nСредние показатели прошедших кошельков:")
        print(f"  • Средний win rate: {avg_win_rate:.2%}")
        print(f"  • Средний ROI: {avg_roi:.2%}")
        print(f"  • Средний объём: ${avg_volume:,.0f} USDC")
        print(f"  • Средняя прибыль на рынок: ${avg_pnl:,.2f}")
        print(f"  • Средний размер ставки: ${avg_stake:,.2f}")
        print(f"  • Среднее количество рынков: {sum(w['total_markets'] for w in passed_wallets) / len(passed_wallets):.1f}")


if __name__ == "__main__":
    main()

