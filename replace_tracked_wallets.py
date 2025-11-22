#!/usr/bin/env python3
"""
Скрипт для замены всех отслеживаемых кошельков на новые из файла.
Очищает текущую базу данных и добавляет новые кошельки.
"""

import os
import sys
import logging
from db import PolymarketDB
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def read_wallet_addresses(file_path: str) -> list:
    """Читает адреса кошельков из файла"""
    addresses = []
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and line.startswith('0x') and len(line) == 42:
                    addresses.append(line.lower())
        logger.info(f"Прочитано {len(addresses)} адресов из файла {file_path}")
        return addresses
    except Exception as e:
        logger.error(f"Ошибка при чтении файла {file_path}: {e}")
        return []


def replace_wallets(db: PolymarketDB, addresses: list, source: str = "filtered_new_criteria"):
    """Заменяет все кошельки в базе данных на новые адреса"""
    try:
        with db.get_connection() as conn:
            cursor = conn.cursor()
            
            # Подсчитываем текущее количество кошельков
            cursor.execute("SELECT COUNT(*) FROM wallets")
            old_count = cursor.fetchone()[0]
            logger.info(f"Текущее количество кошельков в базе: {old_count}")
            
            # Удаляем все существующие кошельки
            cursor.execute("DELETE FROM wallets")
            logger.info("✅ Все существующие кошельки удалены из базы")
            
            # Добавляем новые кошельки
            added_count = 0
            now = db.now_iso()
            
            for address in addresses:
                try:
                    cursor.execute("""
                        INSERT INTO wallets(
                            address, display, traded_total, win_rate, 
                            realized_pnl_total, daily_trading_frequency, 
                            source, added_at, updated_at, last_trade_at
                        )
                        VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        address.lower(),
                        address[:10] + "...",
                        0,  # traded_total - будет обновлено при анализе
                        0.0,  # win_rate - будет обновлено при анализе
                        0.0,  # realized_pnl_total - будет обновлено при анализе
                        0.0,  # daily_trading_frequency - будет обновлено при анализе
                        source,
                        now,
                        now,
                        None  # last_trade_at - будет обновлено при анализе
                    ))
                    added_count += 1
                except Exception as e:
                    logger.error(f"Ошибка при добавлении кошелька {address}: {e}")
                    continue
            
            conn.commit()
            logger.info(f"✅ Добавлено {added_count} новых кошельков в базу данных")
            
            # Проверяем итоговое количество
            cursor.execute("SELECT COUNT(*) FROM wallets")
            new_count = cursor.fetchone()[0]
            logger.info(f"Итоговое количество кошельков в базе: {new_count}")
            
            return added_count
            
    except Exception as e:
        logger.error(f"Ошибка при замене кошельков: {e}")
        return 0


def main():
    """Основная функция"""
    if len(sys.argv) < 2:
        logger.error("Использование: python replace_tracked_wallets.py <путь_к_файлу>")
        sys.exit(1)
    
    file_path = sys.argv[1]
    
    if not os.path.exists(file_path):
        logger.error(f"Файл не найден: {file_path}")
        sys.exit(1)
    
    logger.info("=" * 80)
    logger.info("Замена отслеживаемых кошельков")
    logger.info("=" * 80)
    
    # Инициализируем базу данных
    db_path = os.getenv("DB_PATH", "polymarket_notifier.db")
    db = PolymarketDB(db_path)
    logger.info(f"База данных: {db_path}")
    
    # Читаем адреса из файла
    addresses = read_wallet_addresses(file_path)
    
    if not addresses:
        logger.error("Не удалось прочитать адреса из файла")
        sys.exit(1)
    
    # Подтверждение
    logger.warning(f"⚠️  ВНИМАНИЕ: Все существующие кошельки будут удалены!")
    logger.warning(f"Будет добавлено {len(addresses)} новых кошельков")
    
    # Заменяем кошельки
    added_count = replace_wallets(db, addresses, source="filtered_new_criteria_20251115")
    
    if added_count > 0:
        logger.info("=" * 80)
        logger.info("✅ Замена кошельков завершена успешно!")
        logger.info(f"Добавлено кошельков: {added_count}")
        logger.info("=" * 80)
    else:
        logger.error("❌ Не удалось добавить кошельки")
        sys.exit(1)


if __name__ == "__main__":
    main()

