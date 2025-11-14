#!/usr/bin/env python3
"""
Анализ кошельков из CSV файла и добавление подходящих в БД
Фильтры:
- Winrate > 65%
- Сделок в день <= 40 (за последнюю неделю)
"""

import csv
import os
import sys
import time
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Tuple
import requests
from dotenv import load_dotenv

from db import PolymarketDB
from hashdive_client import HashDiveClient

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Загрузка переменных окружения
load_dotenv()

# Константы
HASHDIVE_API_KEY = "2fcbbb010f3ff15f84dc47ebb0d92917d6fee90771407f56174423b9b28e5c3c"
POLYMARKET_CLOSED_POSITIONS_URL = "https://data-api.polymarket.com/closed-positions"
POLYMARKET_TRADES_URL = "https://data-api.polymarket.com/traded"

# Фильтры
MIN_WINRATE = 0.65  # 65%
MAX_DAILY_TRADES = 40.0
WEEKS_LOOKBACK = 1  # Последняя неделя


class WalletAnalyzer:
    """Анализатор кошельков для CSV импорта"""
    
    def __init__(self):
        self.db = PolymarketDB()
        self.hashdive_client = HashDiveClient(HASHDIVE_API_KEY)
        self.stats = {
            'total': 0,
            'processed': 0,
            'passed': 0,
            'failed': 0,
            'api_errors': 0,
            'no_data': 0
        }
    
    def get_week_timestamp_range(self) -> Tuple[str, str]:
        """Получить диапазон времени за последнюю неделю"""
        now = datetime.now(timezone.utc)
        week_ago = now - timedelta(weeks=WEEKS_LOOKBACK)
        return week_ago.isoformat(), now.isoformat()
    
    def get_closed_positions_polymarket(self, address: str, timestamp_gte: Optional[str] = None) -> List[Dict]:
        """Получить закрытые позиции из Polymarket API"""
        try:
            params = {"user": address}
            if timestamp_gte:
                params["timestamp_gte"] = timestamp_gte
            
            response = requests.get(POLYMARKET_CLOSED_POSITIONS_URL, params=params, timeout=20)
            if response.status_code == 200:
                data = response.json()
                if isinstance(data, list):
                    return data
                elif isinstance(data, dict) and "data" in data:
                    return data["data"]
            return []
        except Exception as e:
            logger.warning(f"Error getting closed positions from Polymarket for {address}: {e}")
            return []
    
    def get_trades_polymarket(self, address: str, timestamp_gte: Optional[str] = None) -> List[Dict]:
        """Получить сделки из Polymarket API"""
        try:
            params = {"user": address, "limit": 1000}
            if timestamp_gte:
                params["timestamp_gte"] = timestamp_gte
            
            response = requests.get(POLYMARKET_TRADES_URL, params=params, timeout=20)
            if response.status_code == 200:
                data = response.json()
                if isinstance(data, list):
                    return data
                elif isinstance(data, dict) and "data" in data:
                    return data["data"]
            return []
        except Exception as e:
            logger.warning(f"Error getting trades from Polymarket for {address}: {e}")
            return []
    
    def get_closed_positions_hashdive(self, address: str, timestamp_gte: Optional[str] = None) -> List[Dict]:
        """Получить закрытые позиции из HashDive API"""
        try:
            # HashDive использует get_positions, но нам нужны закрытые
            # Попробуем через get_trades и фильтруем
            data = self.hashdive_client.get_trades(
                user_address=address,
                timestamp_gte=timestamp_gte,
                page_size=1000
            )
            if isinstance(data, dict):
                return data.get("results", [])
            return []
        except Exception as e:
            logger.debug(f"HashDive API error for {address}: {e}")
            return []
    
    def calculate_winrate(self, closed_positions: List[Dict]) -> float:
        """Рассчитать winrate из закрытых позиций"""
        if not closed_positions:
            return 0.0
        
        wins = 0
        for position in closed_positions:
            pnl = float(position.get("realizedPnl", 0) or position.get("realized_pnl", 0) or 0)
            if pnl > 0:
                wins += 1
        
        return wins / len(closed_positions) if closed_positions else 0.0
    
    def calculate_daily_trades(self, trades: List[Dict], timestamp_gte: str) -> float:
        """Рассчитать среднее количество сделок в день за последнюю неделю"""
        if not trades:
            return 0.0
        
        # Фильтруем сделки за последнюю неделю
        week_ago = datetime.fromisoformat(timestamp_gte.replace('Z', '+00:00'))
        now = datetime.now(timezone.utc)
        
        week_trades = []
        for trade in trades:
            trade_time = trade.get("timestamp") or trade.get("time") or trade.get("created_at")
            if not trade_time:
                continue
            
            try:
                if isinstance(trade_time, str):
                    trade_dt = datetime.fromisoformat(trade_time.replace('Z', '+00:00'))
                else:
                    trade_dt = datetime.fromtimestamp(trade_time, tz=timezone.utc)
                
                if week_ago <= trade_dt <= now:
                    week_trades.append(trade)
            except Exception:
                continue
        
        if not week_trades:
            return 0.0
        
        # Вычисляем количество дней
        if len(week_trades) == 1:
            days = 1.0
        else:
            timestamps = []
            for trade in week_trades:
                trade_time = trade.get("timestamp") or trade.get("time") or trade.get("created_at")
                try:
                    if isinstance(trade_time, str):
                        trade_dt = datetime.fromisoformat(trade_time.replace('Z', '+00:00'))
                    else:
                        trade_dt = datetime.fromtimestamp(trade_time, tz=timezone.utc)
                    timestamps.append(trade_dt)
                except Exception:
                    continue
            
            if len(timestamps) < 2:
                days = 1.0
            else:
                time_span = (max(timestamps) - min(timestamps)).total_seconds() / (24 * 3600)
                days = max(1.0, time_span)
        
        return len(week_trades) / days
    
    def analyze_wallet(self, address: str) -> Optional[Dict]:
        """Проанализировать один кошелек"""
        address = address.lower().strip()
        if not address.startswith("0x") or len(address) != 42:
            logger.warning(f"Invalid address format: {address}")
            return None
        
        timestamp_gte, timestamp_lte = self.get_week_timestamp_range()
        
        # Пробуем получить данные из HashDive (приоритет)
        closed_positions = []
        trades = []
        
        try:
            closed_positions = self.get_closed_positions_hashdive(address, timestamp_gte)
            if closed_positions:
                logger.debug(f"Got {len(closed_positions)} closed positions from HashDive for {address}")
        except Exception as e:
            logger.debug(f"HashDive failed for {address}: {e}")
        
        # Fallback на Polymarket API
        if not closed_positions:
            closed_positions = self.get_closed_positions_polymarket(address, timestamp_gte)
            if closed_positions:
                logger.debug(f"Got {len(closed_positions)} closed positions from Polymarket for {address}")
        
        # Получаем сделки
        try:
            hashdive_trades = self.hashdive_client.get_trades(
                user_address=address,
                timestamp_gte=timestamp_gte,
                timestamp_lte=timestamp_lte,
                page_size=1000
            )
            if isinstance(hashdive_trades, dict):
                trades = hashdive_trades.get("results", [])
        except Exception:
            pass
        
        if not trades:
            trades = self.get_trades_polymarket(address, timestamp_gte)
        
        # Рассчитываем метрики
        winrate = self.calculate_winrate(closed_positions)
        daily_trades = self.calculate_daily_trades(trades, timestamp_gte)
        
        # Проверяем фильтры
        passed = winrate > MIN_WINRATE and daily_trades <= MAX_DAILY_TRADES
        
        result = {
            "address": address,
            "winrate": winrate,
            "daily_trades": daily_trades,
            "closed_positions_count": len(closed_positions),
            "trades_count": len(trades),
            "passed": passed
        }
        
        return result
    
    def process_csv(self, csv_path: str, resume: bool = False) -> List[Dict]:
        """Обработать CSV файл и вернуть список подходящих кошельков"""
        logger.info(f"Reading CSV file: {csv_path}")
        
        wallets_to_add = []
        
        # Если resume, получаем список уже обработанных адресов
        processed_addresses = set()
        if resume:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT address FROM wallets WHERE source = 'csv_filtered_import'")
                processed_addresses = {row[0].lower() for row in cursor.fetchall()}
            logger.info(f"Resume mode: найдено {len(processed_addresses)} уже обработанных кошельков")
        
        with open(csv_path, 'r', encoding='utf-8') as f:
            # Пропускаем пустую первую строку если есть
            first_line = f.readline()
            if not first_line.strip():
                # Первая строка пустая, DictReader прочитает следующую как заголовки
                pass
            else:
                # Возвращаемся в начало
                f.seek(0)
            
            reader = csv.DictReader(f)
            
            # Проверяем заголовки
            if not reader.fieldnames:
                logger.error("CSV file has no headers")
                return []
            
            logger.info(f"CSV columns: {reader.fieldnames}")
            
            for row in reader:
                self.stats['total'] += 1
                # Пробуем разные варианты названия колонки
                address = (row.get('TRADER_ADDRESS', '') or 
                          row.get('trader_address', '') or 
                          row.get('address', '') or 
                          row.get('Address', '')).strip()
                
                if not address:
                    logger.warning(f"Row {self.stats['total']}: No address found")
                    continue
                
                # Пропускаем уже обработанные в режиме resume
                if resume and address.lower() in processed_addresses:
                    logger.debug(f"Skipping {address[:10]}... (already processed)")
                    continue
                
                logger.info(f"[{self.stats['processed'] + 1}/{self.stats['total']}] Analyzing {address[:10]}...")
                
                try:
                    result = self.analyze_wallet(address)
                    self.stats['processed'] += 1
                    
                    if result is None:
                        self.stats['failed'] += 1
                        continue
                    
                    if result['closed_positions_count'] == 0 and result['trades_count'] == 0:
                        self.stats['no_data'] += 1
                        logger.warning(f"No data found for {address}")
                        continue
                    
                    if result['passed']:
                        self.stats['passed'] += 1
                        wallets_to_add.append(result)
                        logger.info(f"✅ {address[:10]}... PASSED - WR: {result['winrate']:.2%}, Daily: {result['daily_trades']:.2f}")
                    else:
                        logger.debug(f"❌ {address[:10]}... FAILED - WR: {result['winrate']:.2%}, Daily: {result['daily_trades']:.2f}")
                    
                    # Небольшая задержка для избежания rate limiting
                    time.sleep(0.5)
                    
                except Exception as e:
                    self.stats['api_errors'] += 1
                    logger.error(f"Error analyzing {address}: {e}")
                    continue
        
        return wallets_to_add
    
    def add_to_database(self, wallets: List[Dict], source: str = "csv_import"):
        """Добавить кошельки в базу данных"""
        logger.info(f"Adding {len(wallets)} wallets to database...")
        
        added_count = 0
        for wallet in wallets:
            try:
                # Получаем дополнительные данные для БД
                address = wallet['address']
                
                # Получаем общее количество сделок
                all_trades = self.get_trades_polymarket(address)
                total_trades = len(all_trades) if all_trades else wallet.get('trades_count', 0)
                
                # Получаем все закрытые позиции для расчета общего winrate и PnL
                all_closed = self.get_closed_positions_polymarket(address)
                if not all_closed:
                    all_closed = self.get_closed_positions_hashdive(address)
                
                winrate, pnl_total = self.calculate_winrate_and_pnl(all_closed)
                
                # Рассчитываем общую частоту сделок
                if all_trades and len(all_trades) > 1:
                    timestamps = []
                    for trade in all_trades:
                        trade_time = trade.get("timestamp") or trade.get("time")
                        if trade_time:
                            try:
                                if isinstance(trade_time, str):
                                    trade_dt = datetime.fromisoformat(trade_time.replace('Z', '+00:00'))
                                else:
                                    trade_dt = datetime.fromtimestamp(trade_time, tz=timezone.utc)
                                timestamps.append(trade_dt)
                            except Exception:
                                continue
                    
                    if len(timestamps) >= 2:
                        time_span = (max(timestamps) - min(timestamps)).total_seconds() / (24 * 3600)
                        daily_freq = len(all_trades) / max(1.0, time_span)
                    else:
                        daily_freq = wallet.get('daily_trades', 0.0)
                else:
                    daily_freq = wallet.get('daily_trades', 0.0)
                
                # Получаем последнюю сделку
                last_trade_at = None
                if all_trades:
                    for trade in all_trades:
                        trade_time = trade.get("timestamp") or trade.get("time")
                        if trade_time:
                            try:
                                if isinstance(trade_time, str):
                                    last_trade_at = datetime.fromisoformat(trade_time.replace('Z', '+00:00')).isoformat()
                                else:
                                    last_trade_at = datetime.fromtimestamp(trade_time, tz=timezone.utc).isoformat()
                                break
                            except Exception:
                                continue
                
                # Добавляем в БД
                self.db.upsert_wallet(
                    address=address,
                    display=address[:10] + "...",
                    traded=total_trades,
                    win_rate=winrate,
                    pnl_total=pnl_total,
                    daily_freq=daily_freq,
                    source=source,
                    last_trade_at=last_trade_at
                )
                
                added_count += 1
                logger.info(f"✅ Added {address[:10]}... to database")
                
            except Exception as e:
                logger.error(f"Error adding {wallet['address']} to database: {e}")
                continue
        
        logger.info(f"Successfully added {added_count} wallets to database")
        return added_count
    
    def calculate_winrate_and_pnl(self, closed_positions: List[Dict]) -> Tuple[float, float]:
        """Рассчитать winrate и общий PnL"""
        if not closed_positions:
            return 0.0, 0.0
        
        wins = 0
        pnl_sum = 0.0
        
        for position in closed_positions:
            pnl = float(position.get("realizedPnl", 0) or position.get("realized_pnl", 0) or 0)
            pnl_sum += pnl
            if pnl > 0:
                wins += 1
        
        winrate = wins / len(closed_positions) if closed_positions else 0.0
        return winrate, pnl_sum
    
    def print_stats(self):
        """Вывести статистику"""
        print("\n" + "=" * 70)
        print("📊 Статистика анализа")
        print("=" * 70)
        print(f"Всего кошельков в CSV: {self.stats['total']}")
        print(f"Обработано: {self.stats['processed']}")
        print(f"Прошли фильтры: {self.stats['passed']}")
        print(f"Не прошли: {self.stats['failed']}")
        print(f"Ошибки API: {self.stats['api_errors']}")
        print(f"Нет данных: {self.stats['no_data']}")
        print("=" * 70)


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 analyze_csv_wallets.py <csv_file_path> [--resume]")
        print("Example: python3 analyze_csv_wallets.py ~/Downloads/filtered_wallets_subset\\(1\\).csv")
        print("\nOptions:")
        print("  --resume    Продолжить с места остановки (пропустить уже обработанные)")
        sys.exit(1)
    
    csv_path = sys.argv[1]
    resume = "--resume" in sys.argv
    
    if not os.path.exists(csv_path):
        logger.error(f"CSV file not found: {csv_path}")
        sys.exit(1)
    
    analyzer = WalletAnalyzer()
    
    try:
        # Обрабатываем CSV
        print(f"\n{'='*70}")
        print("🚀 Начинаем анализ кошельков из CSV")
        print(f"{'='*70}")
        print(f"Файл: {csv_path}")
        print(f"Фильтры: Winrate > {MIN_WINRATE:.0%}, Daily trades <= {MAX_DAILY_TRADES}")
        print(f"Период анализа: последняя неделя")
        if resume:
            print("Режим: Продолжение (resume)")
        print(f"{'='*70}\n")
        
        wallets = analyzer.process_csv(csv_path, resume=resume)
        
        # Выводим статистику
        analyzer.print_stats()
        
        if wallets:
            print(f"\n✅ Найдено {len(wallets)} кошельков, прошедших фильтры")
            response = input("\nДобавить эти кошельки в базу данных? (y/n): ").strip().lower()
            
            if response == 'y':
                print("\nДобавляем в базу данных...")
                
                # Добавляем в БД
                added = analyzer.add_to_database(wallets, source="csv_filtered_import")
                
                print(f"\n✅ Успешно добавлено {added} кошельков в базу данных")
            else:
                print("\n⚠️  Добавление в БД отменено пользователем")
        else:
            print("\n⚠️  Не найдено кошельков, прошедших фильтры")
    
    except KeyboardInterrupt:
        print("\n\n⚠️  Прервано пользователем")
        analyzer.print_stats()
        print("\n💡 Совет: Запустите снова с флагом --resume для продолжения")
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        analyzer.print_stats()


if __name__ == "__main__":
    main()

