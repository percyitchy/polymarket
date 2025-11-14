#!/usr/bin/env python3
"""
Импорт трейдеров из CSV файла HashiDive
Извлекает адреса кошельков и добавляет их в очередь анализа
wallet_analyzer сам применит фильтры и добавит прошедших в базу данных
"""

import csv
import re
import logging
import time
from typing import Dict, Set
from db import PolymarketDB
from wallet_analyzer import WalletAnalyzer, AnalysisConfig

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

def extract_addresses_from_csv(csv_file: str) -> Set[str]:
    """Извлекает уникальные адреса кошельков из CSV файла"""
    addresses = set()
    
    logger.info(f"Чтение CSV файла: {csv_file}")
    try:
        with open(csv_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            row_count = 0
            for row in reader:
                row_count += 1
                user_link = row.get('User Link', '')
                if user_link:
                    # Извлекаем адрес из URL: user_address=0x...
                    match = re.search(r'user_address=([0-9a-fA-Fx]+)', user_link)
                    if match:
                        addr = match.group(1).lower()
                        # Проверяем, что это валидный Ethereum адрес
                        if addr.startswith('0x') and len(addr) == 42:
                            addresses.add(addr)
            
            logger.info(f"Обработано строк: {row_count}")
    except Exception as e:
        logger.error(f"Ошибка при чтении CSV: {e}")
        raise
    
    logger.info(f"Найдено уникальных адресов: {len(addresses)}")
    return addresses

def import_traders_from_csv(csv_file: str, wait_for_completion: bool = True):
    """
    Импортирует трейдеров из CSV и добавляет их в очередь анализа
    
    Args:
        csv_file: Путь к CSV файлу
        wait_for_completion: Ждать ли завершения анализа всех кошельков
    """
    # Извлекаем адреса
    addresses = extract_addresses_from_csv(csv_file)
    
    if not addresses:
        logger.warning("Не найдено адресов в CSV файле")
        return
    
    # Инициализируем базу данных и анализатор
    db = PolymarketDB()
    config = AnalysisConfig(api_max_workers=4)
    analyzer = WalletAnalyzer(db, config)
    
    # Формируем словарь кошельков для добавления в очередь
    wallets = {}
    for addr in addresses:
        wallets[addr] = {
            "display": addr,
            "source": "csv_import"
        }
    
    logger.info(f"Добавление {len(wallets)} кошельков в очередь анализа...")
    
    # Добавляем кошельки в очередь
    added_count = analyzer.add_wallets_to_queue(wallets)
    logger.info(f"Добавлено {added_count} кошельков в очередь")
    
    # Запускаем воркеры для анализа
    logger.info("Запуск воркеров анализа...")
    analyzer.start_workers()
    
    try:
        if wait_for_completion:
            # Ждем завершения анализа
            logger.info("Ожидание завершения анализа...")
            max_wait_time = 3600  # Максимум 1 час
            check_interval = 10  # Проверяем каждые 10 секунд
            start_time = time.time()
            
            while True:
                status = analyzer.get_queue_status()
                pending = status.get('pending', 0)
                completed = status.get('completed', 0)
                failed = status.get('failed', 0)
                
                logger.info(f"Статус очереди: pending={pending}, completed={completed}, failed={failed}")
                
                if pending == 0:
                    logger.info("Все кошельки проанализированы!")
                    break
                
                elapsed = time.time() - start_time
                if elapsed > max_wait_time:
                    logger.warning(f"Достигнут лимит времени ожидания ({max_wait_time}s)")
                    break
                
                time.sleep(check_interval)
            
            # Финальный статус
            final_status = analyzer.get_queue_status()
            logger.info(f"Финальный статус: {final_status}")
            
            # Проверяем, сколько кошельков было принято
            from wallet_analyzer import WIN_RATE_THRESHOLD, MIN_TRADES
            tracked = db.get_tracked_wallets(
                min_trades=MIN_TRADES,
                max_trades=1500,
                min_win_rate=WIN_RATE_THRESHOLD,
                max_win_rate=1.0,
                max_daily_freq=35.0,
                limit=10000
            )
            logger.info(f"Всего отслеживаемых кошельков в базе: {len(tracked)}")
            
            # Проверяем, сколько из импортированных было принято
            accepted_from_import = 0
            for addr in addresses:
                if addr.lower() in [w.lower() for w in tracked]:
                    accepted_from_import += 1
            
            logger.info(f"Из импортированных кошельков принято: {accepted_from_import} из {len(addresses)}")
        else:
            logger.info("Воркеры запущены, анализ будет выполняться в фоне")
            logger.info("Используйте daily_wallet_analysis.py для проверки результатов")
    
    finally:
        if wait_for_completion:
            analyzer.stop_workers()
            logger.info("Воркеры остановлены")

if __name__ == "__main__":
    import sys
    
    csv_file = "2025-10-26T23-36_export.csv"
    if len(sys.argv) > 1:
        csv_file = sys.argv[1]
    
    wait_for_completion = True
    if len(sys.argv) > 2 and sys.argv[2].lower() in ('false', '0', 'no', 'background'):
        wait_for_completion = False
    
    logger.info("=" * 80)
    logger.info("ИМПОРТ ТРЕЙДЕРОВ ИЗ CSV")
    logger.info("=" * 80)
    logger.info(f"CSV файл: {csv_file}")
    logger.info(f"Ожидание завершения: {wait_for_completion}")
    logger.info("=" * 80)
    
    try:
        import_traders_from_csv(csv_file, wait_for_completion)
        logger.info("=" * 80)
        logger.info("ИМПОРТ ЗАВЕРШЕН")
        logger.info("=" * 80)
    except Exception as e:
        logger.error(f"Ошибка при импорте: {e}", exc_info=True)
        sys.exit(1)

