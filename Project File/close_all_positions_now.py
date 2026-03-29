"""
close_all_positions_now.py
==========================
Emergency script to close ALL open positions immediately at MARKET price
"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from core.roostoo_client import get_balance, place_roostoo_order, get_roostoo_position

# List of all possible trading pairs
TRADING_PAIRS = [
    "BTC/USD", "ETH/USD", "SOL/USD", "DOGE/USD", "PEPE/USD",
    "PAXG/USD", "TRX/USD", "FET/USD", "SUI/USD", "ASTER/USD",
    "LTC/USD", "XLM/USD", "VIRTUAL/USD", "FIL/USD", "ONDO/USD",
    "SHIB/USD", "HBAR/USD", "WIF/USD", "BONK/USD", "OPEN/USD",
    "LINEA/USD", "PENDLE/USD", "CFX/USD", "1000CHEEMS/USD", "MIRA/USD"
]

def close_all_positions():
    """Close all open positions at MARKET price"""
    print("\n" + "="*70)
    print("🚨 EMERGENCY CLOSE ALL POSITIONS")
    print("="*70 + "\n")
    
    # Get balance to find all positions
    print("📊 Fetching account balance...")
    balance_data = get_balance()
    
    if not balance_data or not balance_data.get('Success'):
        print("❌ Failed to fetch balance")
        return
    
    wallet = balance_data.get('Wallet', {}) or balance_data.get('SpotWallet', {})
    
    if not wallet:
        print("⚠️  No wallet data found")
        return
    
    # Find all coins with balance (excluding USD)
    positions_to_close = []
    for coin, amounts in wallet.items():
        if coin == 'USD':
            continue
        
        free_balance = float(amounts.get('Free', 0))
        if free_balance > 0.001:  # Only close meaningful positions
            positions_to_close.append({
                'coin': coin,
                'balance': free_balance
            })
    
    if not positions_to_close:
        print("✅ No open positions to close")
        return
    
    print(f"\n⚠️  Found {len(positions_to_close)} position(s) to close:\n")
    print(f"{'Coin':<20} {'Balance':<20}")
    print("-" * 40)
    for pos in positions_to_close:
        print(f"{pos['coin']:<20} {pos['balance']:<20.4f}")
    print("-" * 40)
    
    # Confirm before closing
    print(f"\n❗ This will SELL ALL {len(positions_to_close)} position(s) at MARKET price!")
    response = input("\n   Are you sure? Type 'YES' to confirm: ").strip()
    
    if response.upper() != 'YES':
        print("\n❌ Canceled by user")
        return
    
    # Close all positions
    print(f"\n⏳ Closing all positions...\n")
    
    closed_count = 0
    failed_count = 0
    
    for pos in positions_to_close:
        coin = pos['coin']
        pair = f"{coin}/USD"
        balance = pos['balance']
        
        print(f"📌 Closing {coin}...")
        
        # Place MARKET SELL order
        order_id = place_roostoo_order(
            pair=pair,
            side="SELL",
            order_type="MARKET",
            quantity=str(balance)
        )
        
        if order_id:
            print(f"   ✅ SOLD {balance:.4f} {coin} @ MARKET | Order ID: {order_id}")
            closed_count += 1
        else:
            print(f"   ❌ FAILED to sell {coin}")
            failed_count += 1
        
        # Small delay between orders
        import time
        time.sleep(0.5)
    
    # Summary
    print("\n" + "="*70)
    print("📊 CLOSING SUMMARY")
    print("="*70)
    print(f"   ✅ Successfully closed: {closed_count} position(s)")
    print(f"   ❌ Failed: {failed_count} position(s)")
    print("="*70 + "\n")
    
    # Check final balance
    print("💰 Checking final balance...")
    final_balance = get_balance()
    
    if final_balance and final_balance.get('Success'):
        wallet = final_balance.get('Wallet', {}) or final_balance.get('SpotWallet', {})
        
        remaining_positions = []
        for coin, amounts in wallet.items():
            if coin == 'USD':
                continue
            
            free_balance = float(amounts.get('Free', 0))
            if free_balance > 0.001:
                remaining_positions.append({
                    'coin': coin,
                    'balance': free_balance
                })
        
        if remaining_positions:
            print(f"\n⚠️  {len(remaining_positions)} position(s) still open:")
            for pos in remaining_positions:
                print(f"   - {pos['coin']}: {pos['balance']:.4f}")
            print("\n   These may be locked in pending orders.")
        else:
            print("\n✅ All positions closed successfully!")
        
        # Show USD balance
        if 'USD' in wallet:
            usd_balance = float(wallet['USD'].get('Free', 0))
            print(f"\n💵 USD Balance: ${usd_balance:,.2f}")
    
    print("\n" + "="*70 + "\n")


if __name__ == "__main__":
    try:
        close_all_positions()
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
