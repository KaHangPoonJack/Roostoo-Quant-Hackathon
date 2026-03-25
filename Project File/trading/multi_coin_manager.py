"""
trading/multi_coin_manager.py
=============================
Manages multiple CoinTrader instances in parallel
"""

import time
import threading
from datetime import datetime, timezone, timedelta
from typing import Dict, List
from trading.coin_trader import CoinTrader
from core.telegram_bot import send_telegram_message, send_consolidated_ml_predictions
from config.settings import ML_MODEL_DIR


class MultiCoinManager:
    """
    Manages multiple cryptocurrency traders running in parallel
    Each coin has independent ML model and CE strategy
    """
    
    def __init__(self):
        self.traders: Dict[str, CoinTrader] = {}
        self.is_running = False
        self.monitor_thread = None
        self.ml_predictions_lock = threading.Lock()  # Thread-safe predictions collection
        
        # Coin configuration - 25 coins (5 original + 20 new)
        self.coin_configs = [
            # ===== ORIGINAL 5 COINS =====
            {
                'symbol': 'BTC',
                'binance_symbol': 'BTCUSDT',
                'roostoo_pair': 'BTC/USD',
                'model_dir': str(ML_MODEL_DIR / 'btc_models'),
                'allocation_pct': 1.0
            },
            {
                'symbol': 'ETH',
                'binance_symbol': 'ETHUSDT',
                'roostoo_pair': 'ETH/USD',
                'model_dir': str(ML_MODEL_DIR / 'eth_models'),
                'allocation_pct': 1.0
            },
            {
                'symbol': 'SOL',
                'binance_symbol': 'SOLUSDT',
                'roostoo_pair': 'SOL/USD',
                'model_dir': str(ML_MODEL_DIR / 'sol_models'),
                'allocation_pct': 1.0
            },
            {
                'symbol': 'DOGE',
                'binance_symbol': 'DOGEUSDT',
                'roostoo_pair': 'DOGE/USD',
                'model_dir': str(ML_MODEL_DIR / 'doge_models'),
                'allocation_pct': 1.0
            },
            {
                'symbol': 'PEPE',
                'binance_symbol': 'PEPEUSDT',
                'roostoo_pair': 'PEPE/USD',
                'model_dir': str(ML_MODEL_DIR / 'pepe_models'),
                'allocation_pct': 1.0
            },
            # ===== NEW 20 COINS =====
            {
                'symbol': 'PAXG',
                'binance_symbol': 'PAXGUSDT',
                'roostoo_pair': 'PAXG/USD',
                'model_dir': str(ML_MODEL_DIR / 'paxg_models'),
                'allocation_pct': 1.0
            },
            {
                'symbol': 'TRX',
                'binance_symbol': 'TRXUSDT',
                'roostoo_pair': 'TRX/USD',
                'model_dir': str(ML_MODEL_DIR / 'trx_models'),
                'allocation_pct': 1.0
            },
            {
                'symbol': 'FET',
                'binance_symbol': 'FETUSDT',
                'roostoo_pair': 'FET/USD',
                'model_dir': str(ML_MODEL_DIR / 'fet_models'),
                'allocation_pct': 1.0
            },
            {
                'symbol': 'SUI',
                'binance_symbol': 'SUIUSDT',
                'roostoo_pair': 'SUI/USD',
                'model_dir': str(ML_MODEL_DIR / 'sui_models'),
                'allocation_pct': 1.0
            },
            {
                'symbol': 'ASTER',
                'binance_symbol': 'ASTERUSDT',
                'roostoo_pair': 'ASTER/USD',
                'model_dir': str(ML_MODEL_DIR / 'aster_models'),
                'allocation_pct': 1.0
            },
            {
                'symbol': 'LTC',
                'binance_symbol': 'LTCUSDT',
                'roostoo_pair': 'LTC/USD',
                'model_dir': str(ML_MODEL_DIR / 'ltc_models'),
                'allocation_pct': 1.0
            },
            {
                'symbol': 'XLM',
                'binance_symbol': 'XLMUSDT',
                'roostoo_pair': 'XLM/USD',
                'model_dir': str(ML_MODEL_DIR / 'xlm_models'),
                'allocation_pct': 1.0
            },
            {
                'symbol': 'VIRTUAL',
                'binance_symbol': 'VIRTUALUSDT',
                'roostoo_pair': 'VIRTUAL/USD',
                'model_dir': str(ML_MODEL_DIR / 'virtual_models'),
                'allocation_pct': 1.0
            },
            {
                'symbol': 'FIL',
                'binance_symbol': 'FILUSDT',
                'roostoo_pair': 'FIL/USD',
                'model_dir': str(ML_MODEL_DIR / 'fil_models'),
                'allocation_pct': 1.0
            },
            {
                'symbol': 'ONDO',
                'binance_symbol': 'ONDOUSDT',
                'roostoo_pair': 'ONDO/USD',
                'model_dir': str(ML_MODEL_DIR / 'ondo_models'),
                'allocation_pct': 1.0
            },
            {
                'symbol': 'SHIB',
                'binance_symbol': 'SHIBUSDT',
                'roostoo_pair': 'SHIB/USD',
                'model_dir': str(ML_MODEL_DIR / 'shib_models'),
                'allocation_pct': 1.0
            },
            {
                'symbol': 'HBAR',
                'binance_symbol': 'HBARUSDT',
                'roostoo_pair': 'HBAR/USD',
                'model_dir': str(ML_MODEL_DIR / 'hbar_models'),
                'allocation_pct': 1.0
            },
            {
                'symbol': 'WIF',
                'binance_symbol': 'WIFUSDT',
                'roostoo_pair': 'WIF/USD',
                'model_dir': str(ML_MODEL_DIR / 'wif_models'),
                'allocation_pct': 1.0
            },
            {
                'symbol': 'BONK',
                'binance_symbol': 'BONKUSDT',
                'roostoo_pair': 'BONK/USD',
                'model_dir': str(ML_MODEL_DIR / 'bonk_models'),
                'allocation_pct': 1.0
            },
            {
                'symbol': 'OPEN',
                'binance_symbol': 'OPENUSDT',
                'roostoo_pair': 'OPEN/USD',
                'model_dir': str(ML_MODEL_DIR / 'open_models'),
                'allocation_pct': 1.0
            },
            {
                'symbol': 'LINEA',
                'binance_symbol': 'LINEAUSDT',
                'roostoo_pair': 'LINEA/USD',
                'model_dir': str(ML_MODEL_DIR / 'linea_models'),
                'allocation_pct': 1.0
            },
            {
                'symbol': 'PENDLE',
                'binance_symbol': 'PENDLEUSDT',
                'roostoo_pair': 'PENDLE/USD',
                'model_dir': str(ML_MODEL_DIR / 'pendle_models'),
                'allocation_pct': 1.0
            },
            {
                'symbol': 'CFX',
                'binance_symbol': 'CFXUSDT',
                'roostoo_pair': 'CFX/USD',
                'model_dir': str(ML_MODEL_DIR / 'cfx_models'),
                'allocation_pct': 1.0
            },
            {
                'symbol': '1000CHEEMS',
                'binance_symbol': '1000CHEEMSUSDT',
                'roostoo_pair': '1000CHEEMS/USD',
                'model_dir': str(ML_MODEL_DIR / '1000cheems_models'),
                'allocation_pct': 1.0
            },
            {
                'symbol': 'MIRA',
                'binance_symbol': 'MIRAUSDT',
                'roostoo_pair': 'MIRA/USD',
                'model_dir': str(ML_MODEL_DIR / 'mira_models'),
                'allocation_pct': 1.0
            }
        ]
    
    def initialize_all(self):
        """Initialize all coin traders"""
        print("\n" + "="*70)
        print("🚀 INITIALIZING MULTI-COIN TRADING BOT")
        print("="*70)
        
        for config in self.coin_configs:
            try:
                trader = CoinTrader(
                    symbol=config['symbol'],
                    binance_symbol=config['binance_symbol'],
                    roostoo_pair=config['roostoo_pair'],
                    model_dir=config['model_dir'],
                    allocation_pct=config['allocation_pct']
                )
                trader.initialize()
                self.traders[config['symbol']] = trader
                print(f"✅ {config['symbol']}: Initialized")
            except Exception as e:
                print(f"❌ {config['symbol']}: Failed to initialize - {e}")
        
        print(f"\n✅ {len(self.traders)}/{len(self.coin_configs)} coins ready")
        print("="*70 + "\n")
    
    def start_all(self):
        """Start all coin traders in parallel"""
        print("\n🚀 STARTING ALL TRADERS\n")

        for symbol, trader in self.traders.items():
            trader.start()
            time.sleep(1)  # Stagger starts slightly

        self.is_running = True

        # ✅ START ML PREDICTION SCHEDULER (sends ONE consolidated message per candle)
        self._start_ml_prediction_scheduler()

        # Send startup notification
        send_telegram_message(
            f"🚀 <b>MULTI-COIN TRADING BOT STARTED</b>\n"
            f"-  Coins: {', '.join(self.traders.keys())}\n"
            f"-  Time: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}\n"
            f"-  Each coin has independent ML model + CE strategy\n\n"
            f"📊 ML Predictions: Consolidated message sent every 15min (one message for all 25 coins)"
        )
    
    def stop_all(self):
        """Stop all coin traders"""
        print("\n⏹️ STOPPING ALL TRADERS\n")
        
        self.is_running = False
        
        for symbol, trader in self.traders.items():
            trader.stop()
        
        send_telegram_message(
            f"⏹️ <b>MULTI-COIN TRADING BOT STOPPED</b>\n"
            f"-  Time: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}"
        )
    
    def get_all_status(self) -> Dict:
        """Get status from all traders"""
        from core.api_server import update_trader_state

        statuses = {}
        for symbol, trader in self.traders.items():
            status = trader.get_status()
            statuses[symbol] = status
            # Update API state
            update_trader_state(symbol, status)

        return statuses

    def collect_and_send_ml_predictions(self):
        """
        Collect ML predictions from all traders and send ONE consolidated message
        Called every 15 minutes (each candle)
        """
        if not self.is_running:
            return

        try:
            predictions_dict = {}

            with self.ml_predictions_lock:
                for symbol, trader in self.traders.items():
                    if hasattr(trader, 'last_ml_prediction') and trader.last_ml_prediction:
                        predictions_dict[symbol] = trader.last_ml_prediction
                        print(f"   ✅ {symbol}: Prediction collected (Class {trader.last_ml_prediction['predicted_class']})")
                    else:
                        print(f"   ⚠️  {symbol}: No prediction available")

            if predictions_dict:
                # Send ONE consolidated message for all coins
                print(f"\n📊 Sending consolidated message with {len(predictions_dict)} predictions...")
                send_consolidated_ml_predictions(predictions_dict)
            else:
                print("⚠️  No ML predictions collected from traders")
                print(f"   Total traders: {len(self.traders)}")
                print(f"   Predictions collected: {len(predictions_dict)}")

        except Exception as e:
            print(f"❌ Error collecting ML predictions: {e}")
            import traceback
            traceback.print_exc()

    def _start_ml_prediction_scheduler(self):
        """Start background thread to send consolidated ML predictions every 15 minutes"""
        def run_scheduler():
            print(f"\n{'='*70}")
            print(f"🕐 ML PREDICTION SCHEDULER STARTED")
            print(f"{'='*70}")
            print(f"⏰ Consolidated predictions will be sent every 15 minutes")
            
            # Calculate next 15-minute candle properly
            now = datetime.now(timezone.utc)
            next_minute = ((now.minute // 15) + 1) * 15
            if next_minute >= 60:
                next_candle = now.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
            else:
                next_candle = now.replace(minute=next_minute, second=0, microsecond=0)
            
            print(f"📊 Next prediction: {next_candle.strftime('%Y-%m-%d %H:%M:%S UTC')}")
            print(f"{'='*70}\n")
            
            while self.is_running:
                try:
                    # Wait until next 15-minute candle
                    now = datetime.now(timezone.utc)
                    next_minute = ((now.minute // 15) + 1) * 15
                    if next_minute >= 60:
                        next_candle = now.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
                    else:
                        next_candle = now.replace(minute=next_minute, second=0, microsecond=0)
                    
                    sleep_seconds = (next_candle - now).total_seconds()
                    print(f"⏳ Waiting {sleep_seconds:.0f}s for next candle at {next_candle.strftime('%H:%M:%S UTC')}")
                    time.sleep(sleep_seconds)
                    
                    # Wait 90 seconds for all 25 traders to generate predictions
                    # Traders take 30-40s to start + 5-7s for ML inference each
                    print(f"⏳ Waiting 90s for all 25 traders to generate predictions...")
                    time.sleep(90)
                    
                    # Collect and send predictions
                    if self.is_running:
                        print(f"\n🔮 Collecting ML predictions for all {len(self.traders)} coins...")
                        self.collect_and_send_ml_predictions()
                        
                except Exception as e:
                    print(f"❌ Error in ML prediction scheduler: {e}")
                    time.sleep(60)  # Wait 1 minute on error
        
        scheduler_thread = threading.Thread(target=run_scheduler, daemon=True)
        scheduler_thread.start()
    
    def restart_trader(self, symbol: str):
        """Restart a specific coin trader"""
        if symbol in self.traders:
            self.traders[symbol].stop()
            time.sleep(2)
            self.traders[symbol].start()
            print(f"🔄 {symbol}: Restarted")


# Global manager instance
manager = MultiCoinManager()