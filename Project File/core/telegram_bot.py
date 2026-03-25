"""
telegram_bot.py
===============
Telegram notification functions for trading bot
"""

import urllib.parse
import requests
from config.settings import TAKE_PROFIT_PCT, STOP_LOSS_PCT, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, ML_CONFIDENCE_THRESHOLD
from datetime import datetime, timezone


def send_telegram_message(message: str):
    """Send a message to your Telegram chat via bot"""
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = {
            'chat_id': TELEGRAM_CHAT_ID,
            'text': message,
            'parse_mode': 'HTML'  # Allows basic HTML formatting
        }
        
        response = requests.post(url, data=payload, timeout=10)
        if response.status_code != 200:
            print(f"⚠️ Telegram notification failed: {response.text}")
        else:
            print("✅ Telegram notification sent")
        return response.json()
    except Exception as e:
        print(f"⚠️ Error sending Telegram message: {e}")
        return None


def send_consolidated_ml_predictions(predictions_dict: dict):
    """
    Send consolidated ML predictions for all coins in ONE message
    Called once per candle from multi_coin_manager
    
    Args:
        predictions_dict: Dict mapping symbol -> ml_prediction
    """
    try:
        if not predictions_dict:
            return
        
        # Build summary table
        summary_lines = []
        for symbol, pred in sorted(predictions_dict.items()):
            probs = pred['probabilities']
            predicted_class = pred['predicted_class']
            breakout_prob = probs[1] + probs[2] + probs[3]
            recommendation = pred['recommendation']
            price = pred['price']
            
            # Color-code by confidence
            if breakout_prob >= 0.95:
                status = "🟢 STRONG"
            elif breakout_prob >= 0.90:
                status = "🟡 GOOD"
            elif breakout_prob >= 0.80:
                status = "🔵 OK"
            else:
                status = "⚪ WAIT"
            
            summary_lines.append(
                f"{symbol:<8} ${price:>8.2f} | Class {predicted_class} | "
                f"{breakout_prob*100:5.1f}% | {status:<12} | {recommendation}"
            )
        
        # Build full message
        message = (
            f"🔮  <b>ML PREDICTIONS - ALL 25 COINS</b>\n"
            f"Time: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}\n\n"
            f"<b>SUMMARY (Symbol | Price | Class | Prob | Status | Rec):</b>\n"
            f"{'=' * 85}\n"
        )

        for line in summary_lines:
            message += f"{line}\n"

        message += (
            f"{'=' * 85}\n\n"
            f"<b>Legend:</b>\n"
            f"🟢 STRONG = Prob >= 95% | 🟡 GOOD = Prob >= 90% | "
            f"🔵 OK = Prob >= 80% | ⚪ WAIT = Prob < 80%\n\n"
            f"<b>Trading Rule:</b> ENTER if Breakout Prob >= {ML_CONFIDENCE_THRESHOLD*100:.0f}%\n"
        )
        
        send_telegram_message(message)
        
        # Also log to terminal
        print(f"\n{'='*85}")
        print(f"🔮 ML PREDICTIONS SENT - {len(predictions_dict)} coins")
        print(f"{'='*85}")
        for line in summary_lines[:5]:  # Show first 5 in terminal
            print(line)
        print(f"... and {len(predictions_dict) - 5} more coins")
        print(f"{'='*85}\n")
        
    except Exception as e:
        print(f"Error sending consolidated ML predictions: {e}")
        import traceback
        traceback.print_exc()


def send_ml_prediction_message(prediction: dict):
    """
    Send ML prediction to Telegram with ALL class probabilities
    """
    try:
        probs = prediction['probabilities']
        predicted_class = prediction['predicted_class']

        # Get actual TP/SL % from settings (class-based)
        tp_pct = TAKE_PROFIT_PCT.get(predicted_class, 0.01) * 100
        sl_pct = STOP_LOSS_PCT.get(predicted_class, 0.015) * 100

        message = (
            f"🔮  <b>ML PREDICTION UPDATE</b>\n"
            f"Symbol: {prediction['symbol']}\n"
            f"Time: {prediction['timestamp'].strftime('%Y-%m-%d %H:%M:%S UTC')}\n"
            f"Price: ${prediction['price']:.2f}\n"
            f"Predicted Class: {predicted_class}\n"
            f"Confidence: {prediction['confidence']*100:.1f}%\n"
            f"All Class Probabilities:\n"
            f"   Class 0 (No Trade):     {probs[0]*100:6.2f}%\n"
            f"   Class 1 (1-3%):         {probs[1]*100:6.2f}%\n"
            f"   Class 2 (3-5%):         {probs[2]*100:6.2f}%\n"
            f"   Class 3 (>5%):          {probs[3]*100:6.2f}%\n"
            f"Recommendation: {prediction['recommendation']}\n"
            f"TP/SL Settings:\n"
            f"   Stop Loss: {sl_pct:.2f}% (Class {predicted_class})\n"
            f"   Take Profit: {tp_pct:.1f}% (Class {predicted_class})\n"
            f"Suggested Size: {prediction['position_size_pct']*100:.1f}%\n"
        )
        send_telegram_message(message)
    except Exception as e:
        print(f"Error sending ML prediction: {e}")


def send_tp_sl_update_message(symbol: str, entry_price: float,
                               current_price: float, tp_price: float,
                               sl_price: float, pl_pct: float,
                               predicted_class: int):
    """Send TP/SL status update to Telegram"""
    try:
        tp_distance = ((tp_price - current_price) / current_price) * 100
        sl_distance = ((current_price - sl_price) / current_price) * 100

        message = (
            f"📊  <b>TP/SL STATUS UPDATE</b>\n"
            f"Symbol: {symbol}\n"
            f"Entry Price: ${entry_price:.2f}\n"
            f"Current Price: ${current_price:.2f}\n"
            f"P&L: {pl_pct:+.2f}%\n"
            f"Predicted Class: {predicted_class}\n"
            f"Take Profit: ${tp_price:.2f} ({tp_distance:+.2f}% away)\n"
            f"Stop Loss: ${sl_price:.2f} ({sl_distance:+.2f}% away)\n"
            f"Time: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}\n"
        )
        send_telegram_message(message)
    except Exception as e:
        print(f"Error sending TP/SL update: {e}")


def send_tp_triggered_message(symbol: str, entry_price: float,
                               exit_price: float, pl_pct: float,
                               predicted_class: int):
    """Send Take Profit triggered notification"""
    try:
        tp_target = TAKE_PROFIT_PCT.get(predicted_class, 0.01) * 100
        message = (
            f"✅  <b>TAKE PROFIT TRIGGERED</b>\n"
            f"Symbol: {symbol}\n"
            f"Entry Price: ${entry_price:.2f}\n"
            f"Exit Price: ${exit_price:.2f}\n"
            f"P&L: {pl_pct:+.2f}%\n"
            f"TP Target: {tp_target:.1f}%\n"
            f"Predicted Class: {predicted_class}\n"
            f"Time: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}\n"
        )
        send_telegram_message(message)
    except Exception as e:
        print(f"Error sending TP triggered message: {e}")


def send_sl_triggered_message(symbol: str, entry_price: float,
                               exit_price: float, pl_pct: float,
                               predicted_class: int):
    """Send Stop Loss triggered notification"""
    try:
        sl_limit = STOP_LOSS_PCT.get(predicted_class, 0.015) * 100
        message = (
            f"🛑  <b>STOP LOSS TRIGGERED</b>\n"
            f"Symbol: {symbol}\n"
            f"Entry Price: ${entry_price:.2f}\n"
            f"Exit Price: ${exit_price:.2f}\n"
            f"P&L: {pl_pct:+.2f}%\n"
            f"SL Limit: {sl_limit:.2f}% (Class {predicted_class})\n"
            f"Predicted Class: {predicted_class}\n"
            f"Time: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}\n"
        )
        send_telegram_message(message)
    except Exception as e:
        print(f"Error sending SL triggered message: {e}")


def send_trade_entry_message(symbol: str, side: str, entry_price: float,
                             predicted_class: int, probabilities: dict = None):
    """Send trade entry notification (ENTRY SIGNAL)"""
    try:
        probs_text = ""
        if probabilities:
            probs_text = (
                f"\nML Probabilities:\n"
                f"   Class 0: {probabilities.get(0, 0)*100:.1f}%\n"
                f"   Class 1: {probabilities.get(1, 0)*100:.1f}%\n"
                f"   Class 2: {probabilities.get(2, 0)*100:.1f}%\n"
                f"   Class 3: {probabilities.get(3, 0)*100:.1f}%"
            )

        tp_pct = TAKE_PROFIT_PCT.get(predicted_class, 0.01) * 100
        sl_pct = STOP_LOSS_PCT.get(predicted_class, 0.015) * 100

        message = (
            f"🟢  <b>TRADE ENTRY</b>\n"
            f"Symbol: {symbol}\n"
            f"Side: {side}\n"
            f"Entry Price: ${entry_price:.2f}\n"
            f"Predicted Class: {predicted_class}\n"
            f"TP Target: {tp_pct:.1f}%\n"
            f"SL Limit: {sl_pct:.2f}%{probs_text}\n"
            f"Time: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}\n"
        )
        send_telegram_message(message)
    except Exception as e:
        print(f"Error sending trade entry message: {e}")


def send_trade_exit_message(symbol: str, side: str, entry_price: float,
                            exit_price: float, pnl_pct: float, reason: str,
                            predicted_class: int = None):
    """Send trade exit notification (EXIT SIGNAL)"""
    try:
        emoji = "✅" if pnl_pct >= 0 else "❌"

        message = (
            f"{emoji}  <b>TRADE EXIT</b>\n"
            f"Symbol: {symbol}\n"
            f"Side: {side}\n"
            f"Entry Price: ${entry_price:.2f}\n"
            f"Exit Price: ${exit_price:.2f}\n"
            f"P&L: {pnl_pct:+.2f}%\n"
            f"Reason: {reason}\n"
            f"Predicted Class: {predicted_class or 'N/A'}\n"
            f"Time: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}\n"
        )
        send_telegram_message(message)
    except Exception as e:
        print(f"Error sending trade exit message: {e}")