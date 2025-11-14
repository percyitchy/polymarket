#!/usr/bin/env python3
"""Update wallets - remove high-trade wallets and specific addresses"""
import sqlite3

# Addresses to remove
addresses_to_remove = [
    "0xd218e474776403a330142299f7796e8ba32eb5c9",
    "0x204f72f35326db932158cba6adff0b9a1da95e14",
    "0x212954857f5efc138748c33d032a93bf95974222",
    "0x134a63b764ac7b008356e8db1857db94e6b09e42",
    "0x6ffb4354cbe6e0f9989e3b55564ec5fb8646a834",
    "0x781caf04d98a281712caf1677877c442789fdb68",
    "0x8749194e5105c97c3d134e974e103b44eea44ea4",
    "0xf68a281980f8c13828e84e147e3822381d6e5b1b",
    "0x842dabdbf420acea760af817fe7c85a249179d4d",
    "0xf699a6477fa8e385987f8ae6a3657b2e106107e1",
    "0x6239c6fa473f967d46dab883a09dd327be32c24f",
    "0x1ff49fdcb6685c94059b65620f43a683be0ce7a5"
]

conn = sqlite3.connect('polymarket_notifier.db')
cursor = conn.cursor()

# Get all wallets
cursor.execute('SELECT address, traded_total FROM wallets')
all_wallets = cursor.fetchall()

print(f"📊 Total wallets: {len(all_wallets)}")

# Find wallets with >1200 trades
high_trade_wallets = [addr for addr, trades in all_wallets if trades > 1200]
print(f"💰 Wallets with >1200 trades: {len(high_trade_wallets)}")

# Remove specified addresses
print(f"\n🗑️  Removing {len(addresses_to_remove)} specified addresses...")
for addr in addresses_to_remove:
    cursor.execute('DELETE FROM wallets WHERE address = ?', (addr,))
    print(f"   ✓ Removed {addr}")

# Remove wallets with >1200 trades
print(f"\n🗑️  Removing wallets with >1200 trades...")
removed_high = 0
for addr in high_trade_wallets:
    cursor.execute('DELETE FROM wallets WHERE address = ?', (addr,))
    removed_high += 1
    print(f"   ✓ Removed {addr} ({removed_high} total)")

conn.commit()

# Final count
cursor.execute('SELECT COUNT(*) FROM wallets')
remaining = cursor.fetchone()[0]

print(f"\n✅ Done!")
print(f"   Removed: {len(addresses_to_remove) + removed_high} wallets")
print(f"   Remaining: {remaining} wallets")

conn.close()

