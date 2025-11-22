#!/usr/bin/env python3
"""
Перепроверка всех кошельков с новой фильтрацией (500 последних сделок)
Экспорт результатов в .txt файл
"""

import os
import sys
import time
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional
from db import PolymarketDB
from wallet_analyzer import WalletAnalyzer, MIN_TRADES, WIN_RATE_THRESHOLD, MAX_DAILY_FREQUENCY, MAX_CLOSED_POSITIONS
from dotenv import load_dotenv

load_dotenv()

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def main():
    db = PolymarketDB()
    analyzer = WalletAnalyzer(db=db)
    
    logger.info("=" * 80)
    logger.info("Начало перепроверки кошельков с новой фильтрацией")
    logger.info(f"MAX_CLOSED_POSITIONS: {MAX_CLOSED_POSITIONS}")
    logger.info(f"MIN_TRADES: {MIN_TRADES}")
    logger.info(f"WIN_RATE_THRESHOLD: {WIN_RATE_THRESHOLD:.1%}")
    logger.info(f"MAX_DAILY_FREQUENCY: {MAX_DAILY_FREQUENCY}")
    logger.info("=" * 80)
    
    # Получаем все кошельки из базы данных
    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT address, display, traded_total, win_rate, realized_pnl_total, 
                   daily_trading_frequency, source, last_trade_at
            FROM wallets
            ORDER BY realized_pnl_total DESC
        """)
        all_wallets = cursor.fetchall()
    
    logger.info(f"Всего кошельков в базе: {len(all_wallets)}")
    
    # Результаты перепроверки
    passed_wallets = []
    failed_wallets = []
    error_wallets = []
    
    total = len(all_wallets)
    processed = 0
    
    for address, display, old_traded, old_win_rate, old_pnl, old_daily_freq, source, last_trade_at in all_wallets:
        processed += 1
        if processed % 100 == 0:
            logger.info(f"Обработано: {processed}/{total} ({processed*100//total}%)")
        
        try:
            # Получаем закрытые позиции (последние 500)
            closed_positions = analyzer._get_closed_positions(address, max_positions=MAX_CLOSED_POSITIONS)
            
            if not closed_positions or len(closed_positions) == 0:
                logger.debug(f"{address}: Нет закрытых позиций")
                failed_wallets.append({
                    'address': address,
                    'display': display,
                    'reason': 'no_closed_positions',
                    'old_traded': old_traded,
                    'old_win_rate': old_win_rate,
                    'old_pnl': old_pnl,
                    'old_daily_freq': old_daily_freq,
                    'source': source,
                    'last_trade_at': last_trade_at
                })
                continue
            
            # Пересчитываем winrate и PnL из последних 500 позиций
            new_win_rate, new_pnl_total = analyzer._compute_win_rate_and_pnl(closed_positions)
            
            # Получаем общее количество сделок
            try:
                new_traded = analyzer._get_total_traded(address)
            except Exception as e:
                logger.debug(f"{address}: Ошибка получения traded_total: {e}")
                new_traded = old_traded  # Используем старое значение
            
            # Получаем daily frequency
            try:
                new_daily_freq = analyzer._get_daily_trading_frequency(address)
            except Exception as e:
                logger.debug(f"{address}: Ошибка получения daily_frequency: {e}")
                new_daily_freq = old_daily_freq  # Используем старое значение
            
            # Применяем фильтры
            passed = True
            reason = None
            
            if new_traded < MIN_TRADES:
                passed = False
                reason = f"trades < {MIN_TRADES} ({new_traded})"
            elif new_win_rate < WIN_RATE_THRESHOLD:
                passed = False
                reason = f"win_rate < {WIN_RATE_THRESHOLD:.1%} ({new_win_rate:.1%})"
            elif new_daily_freq is not None and new_daily_freq > MAX_DAILY_FREQUENCY:
                passed = False
                reason = f"daily_freq > {MAX_DAILY_FREQUENCY} ({new_daily_freq:.2f})"
            
            wallet_data = {
                'address': address,
                'display': display,
                'traded': new_traded,
                'win_rate': new_win_rate,
                'pnl': new_pnl_total,
                'daily_freq': new_daily_freq,
                'source': source,
                'last_trade_at': last_trade_at,
                'closed_positions_count': len(closed_positions),
                'old_traded': old_traded,
                'old_win_rate': old_win_rate,
                'old_pnl': old_pnl,
                'old_daily_freq': old_daily_freq
            }
            
            if passed:
                passed_wallets.append(wallet_data)
            else:
                wallet_data['reason'] = reason
                failed_wallets.append(wallet_data)
            
            # Небольшая задержка чтобы не перегружать API
            time.sleep(0.1)
            
        except Exception as e:
            logger.error(f"Ошибка при обработке {address}: {e}")
            error_wallets.append({
                'address': address,
                'display': display,
                'error': str(e),
                'old_traded': old_traded,
                'old_win_rate': old_win_rate,
                'old_pnl': old_pnl,
                'old_daily_freq': old_daily_freq,
                'source': source,
                'last_trade_at': last_trade_at
            })
    
    logger.info("=" * 80)
    logger.info(f"Перепроверка завершена")
    logger.info(f"Прошли фильтры: {len(passed_wallets)}")
    logger.info(f"Не прошли фильтры: {len(failed_wallets)}")
    logger.info(f"Ошибки: {len(error_wallets)}")
    logger.info("=" * 80)
    
    # Создаем имя файла с timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = f"rechecked_wallets_{timestamp}.txt"
    
    # Записываем результаты в файл
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write("=" * 80 + "\n")
        f.write("Перепроверка кошельков с новой фильтрацией (500 последних сделок)\n")
        f.write("=" * 80 + "\n")
        f.write(f"Дата проверки: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"MAX_CLOSED_POSITIONS: {MAX_CLOSED_POSITIONS}\n")
        f.write(f"MIN_TRADES: {MIN_TRADES}\n")
        f.write(f"WIN_RATE_THRESHOLD: {WIN_RATE_THRESHOLD:.1%}\n")
        f.write(f"MAX_DAILY_FREQUENCY: {MAX_DAILY_FREQUENCY}\n")
        f.write("=" * 80 + "\n\n")
        
        f.write(f"✅ Прошли фильтры: {len(passed_wallets)}\n")
        f.write(f"❌ Не прошли фильтры: {len(failed_wallets)}\n")
        f.write(f"⚠️  Ошибки: {len(error_wallets)}\n")
        f.write("=" * 80 + "\n\n")
        
        # Кошельки, которые прошли фильтры
        f.write("=" * 80 + "\n")
        f.write("КОШЕЛЬКИ, КОТОРЫЕ ПРОШЛИ ФИЛЬТРЫ\n")
        f.write("=" * 80 + "\n\n")
        
        for i, wallet in enumerate(passed_wallets, 1):
            f.write(f"{i}. {wallet['address']}\n")
            f.write(f"   Display: {wallet['display']}\n")
            f.write(f"   Trades: {wallet['traded']}, Win Rate: {wallet['win_rate']:.2%}, PnL: ${wallet['pnl']:,.2f}\n")
            daily_freq_str = f"{wallet['daily_freq']:.2f}" if wallet['daily_freq'] is not None else "N/A"
            f.write(f"   Daily Freq: {daily_freq_str}, Source: {wallet['source']}\n")
            f.write(f"   Closed Positions (last {MAX_CLOSED_POSITIONS}): {wallet['closed_positions_count']}\n")
            if wallet['last_trade_at']:
                f.write(f"   Last Trade: {wallet['last_trade_at']}\n")
            # Показываем изменения
            if wallet['old_win_rate'] != wallet['win_rate']:
                f.write(f"   ⚠️  Win Rate изменился: {wallet['old_win_rate']:.2%} → {wallet['win_rate']:.2%}\n")
            f.write("\n")
        
        # Кошельки, которые не прошли фильтры
        f.write("\n" + "=" * 80 + "\n")
        f.write("КОШЕЛЬКИ, КОТОРЫЕ НЕ ПРОШЛИ ФИЛЬТРЫ\n")
        f.write("=" * 80 + "\n\n")
        
        for i, wallet in enumerate(failed_wallets, 1):
            f.write(f"{i}. {wallet['address']}\n")
            f.write(f"   Display: {wallet['display']}\n")
            f.write(f"   Причина: {wallet.get('reason', 'unknown')}\n")
            if 'traded' in wallet:
                f.write(f"   Trades: {wallet['traded']}, Win Rate: {wallet.get('win_rate', 0):.2%}, PnL: ${wallet.get('pnl', 0):,.2f}\n")
                daily_freq_str = f"{wallet['daily_freq']:.2f}" if wallet.get('daily_freq') is not None else "N/A"
                f.write(f"   Daily Freq: {daily_freq_str}\n")
                f.write(f"   Closed Positions (last {MAX_CLOSED_POSITIONS}): {wallet.get('closed_positions_count', 0)}\n")
            # Показываем старые значения
            f.write(f"   Старые значения: Trades={wallet.get('old_traded', 'N/A')}, WR={wallet.get('old_win_rate', 0):.2%}, PnL=${wallet.get('old_pnl', 0):,.2f}\n")
            f.write("\n")
        
        # Кошельки с ошибками
        if error_wallets:
            f.write("\n" + "=" * 80 + "\n")
            f.write("КОШЕЛЬКИ С ОШИБКАМИ\n")
            f.write("=" * 80 + "\n\n")
            
            for i, wallet in enumerate(error_wallets, 1):
                f.write(f"{i}. {wallet['address']}\n")
                f.write(f"   Display: {wallet['display']}\n")
                f.write(f"   Ошибка: {wallet['error']}\n")
                f.write(f"   Старые значения: Trades={wallet['old_traded']}, WR={wallet['old_win_rate']:.2%}, PnL=${wallet['old_pnl']:,.2f}\n")
                f.write("\n")
    
    print("=" * 80)
    print(f"✅ Перепроверка завершена")
    print("=" * 80)
    print(f"Файл: {output_file}")
    print(f"Прошли фильтры: {len(passed_wallets)}")
    print(f"Не прошли фильтры: {len(failed_wallets)}")
    print(f"Ошибки: {len(error_wallets)}")
    print("=" * 80)
    
    # Также создаем простой список только адресов прошедших фильтры
    addresses_file = f"rechecked_wallets_passed_{timestamp}.txt"
    with open(addresses_file, 'w', encoding='utf-8') as f:
        for wallet in passed_wallets:
            f.write(f"{wallet['address']}\n")
    
    print(f"\nТакже создан файл только с адресами прошедших фильтры: {addresses_file}")
    print(f"Всего адресов: {len(passed_wallets)}")

if __name__ == "__main__":
    main()

