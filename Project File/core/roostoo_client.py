"""
roostoo_client.py
=================
Roostoo Exchange API Client
EXACTLY matching bot.py working pattern
Credentials from config/settings.py (not hardcoded)
"""

import json
import hmac
import hashlib
import time
import threading
import requests
from datetime import datetime, timezone
from typing import Optional, Dict, List, Tuple
from collections import deque

# Import credentials from settings (NOT hardcoded)
from config.settings import ROOSTOO_API_KEY, ROOSTOO_SECRET_KEY, ROOSTOO_BASE_URL

# ================= SHARED BALANCE CACHE =================
# Global cache to store balance fetched once per candle
# All coin traders will use this shared value
_global_balance_cache = {
    'balance': 0.0,
    'timestamp': None,
    'candle_timestamp': None,  # Track which candle this balance is for
    'lock': threading.Lock(),  # Thread-safe access
    'refreshing': False  # Track if a refresh is in progress
}

# ================= API RATE LIMITER =================
# Global rate limiter for all Roostoo API calls
# Prevents 429 errors by spacing out requests
class RoostooRateLimiter:
    """
    Thread-safe rate limiter for Roostoo API calls.
    Ensures requests are spaced out to avoid 429 errors.
    """
    
    def __init__(self, min_interval_seconds=1.0, max_retries=3, base_backoff_seconds=2.0):
        """
        Args:
            min_interval_seconds: Minimum time between API calls (default: 1 second)
            max_retries: Max retry attempts on 429 error
            base_backoff_seconds: Base wait time for exponential backoff
        """
        self.min_interval = min_interval_seconds
        self.max_retries = max_retries
        self.base_backoff = base_backoff_seconds
        self.lock = threading.Lock()
        self.last_request_time = 0.0
        self.request_history = deque(maxlen=100)  # Track recent requests
    
    def wait_if_needed(self):
        """Wait if necessary to maintain minimum interval between requests"""
        with self.lock:
            now = time.time()
            elapsed = now - self.last_request_time
            
            if elapsed < self.min_interval:
                sleep_time = self.min_interval - elapsed
                time.sleep(sleep_time)
            
            self.last_request_time = time.time()
    
    def execute_with_retry(self, func, *args, **kwargs):
        """
        Execute an API function with rate limiting and automatic retry on 429.
        
        Args:
            func: API function to call (e.g., get_balance, place_order)
            *args, **kwargs: Arguments to pass to the function
            
        Returns:
            Function result or None if all retries failed
        """
        last_error = None
        
        for attempt in range(self.max_retries + 1):
            try:
                # Wait to maintain rate limit
                self.wait_if_needed()
                
                # Execute the API call
                result = func(*args, **kwargs)
                
                # Check if result indicates 429 error
                if isinstance(result, dict):
                    # Check for HTTP error in response
                    if result.get('Code') == 429 or 'rate limit' in str(result.get('Message', '')).lower():
                        raise Exception("429 Rate Limit Error")
                
                # Success!
                self.request_history.append({
                    'time': datetime.now(timezone.utc),
                    'function': func.__name__,
                    'success': True
                })
                return result
                
            except Exception as e:
                error_str = str(e)
                last_error = e
                
                # Check if it's a 429 error
                is_rate_limit = (
                    '429' in error_str or 
                    'rate limit' in error_str.lower() or
                    (hasattr(e, 'response') and getattr(e, 'response', None) and getattr(e.response, 'status_code', 0) == 429)
                )
                
                if is_rate_limit and attempt < self.max_retries:
                    # Exponential backoff: 2s, 4s, 8s...
                    backoff_time = self.base_backoff * (2 ** attempt)
                    print(f"⚠️  Rate limit hit (attempt {attempt + 1}/{self.max_retries + 1}). Waiting {backoff_time:.1f}s...")
                    
                    self.request_history.append({
                        'time': datetime.now(timezone.utc),
                        'function': func.__name__,
                        'success': False,
                        'error': '429'
                    })
                    
                    time.sleep(backoff_time)
                else:
                    # Not a 429 error or max retries reached
                    print(f"❌ API call failed: {error_str}")
                    if attempt == self.max_retries:
                        print(f"   Max retries ({self.max_retries}) reached, giving up")
                    break
        
        # All retries failed
        return None
    
    def get_stats(self) -> Dict:
        """Get rate limiter statistics"""
        with self.lock:
            recent_requests = list(self.request_history)[-10:]
            success_count = sum(1 for r in recent_requests if r.get('success', False))
            return {
                'total_recent': len(recent_requests),
                'success_rate': f"{(success_count / len(recent_requests) * 100):.1f}%" if recent_requests else "N/A",
                'last_request': recent_requests[-1]['time'].strftime('%H:%M:%S') if recent_requests else None,
                'min_interval': f"{self.min_interval}s"
            }

# Global rate limiter instance (shared across all API calls)
_rate_limiter = RoostooRateLimiter(min_interval_seconds=1.0, max_retries=3, base_backoff_seconds=2.0)


def _rate_limited_call(func, *args, **kwargs):
    """Helper to execute any Roostoo API call with rate limiting"""
    return _rate_limiter.execute_with_retry(func, *args, **kwargs)


# ================= UTILITY FUNCTIONS =================

def get_timestamp() -> str:
    """Return 13-digit millisecond timestamp"""
    return str(int(time.time() * 1000))


def get_signed_headers(payload: dict = None):
    """
    Generate signed headers for RCL_TopLevelCheck endpoints
    EXACTLY like bot.py - NO Content-Type here!
    """
    if payload is None:
        payload = {}
    
    payload['timestamp'] = get_timestamp()
    sorted_keys = sorted(payload.keys())
    total_params = "&".join(f"{k}={payload[k]}" for k in sorted_keys)
    
    signature = hmac.new(
        ROOSTOO_SECRET_KEY.encode('utf-8'),
        total_params.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()
    
    # NO Content-Type header here (like bot.py)
    headers = {
        'RST-API-KEY': ROOSTOO_API_KEY,
        'MSG-SIGNATURE': signature
    }
    
    return headers, payload, total_params


# ================= PUBLIC ENDPOINTS (No Auth Required) =================

def check_server_time() -> Optional[Dict]:
    """Check API server time"""
    url = f"{ROOSTOO_BASE_URL}/v3/serverTime"
    try:
        res = requests.get(url, timeout=10)
        res.raise_for_status()
        return res.json()
    except requests.exceptions.RequestException as e:
        print(f"Error checking server time: {e}")
        return None


def get_exchange_info() -> Optional[Dict]:
    """Get exchange trading pairs and info"""
    url = f"{ROOSTOO_BASE_URL}/v3/exchangeInfo"
    try:
        res = requests.get(url, timeout=10)
        res.raise_for_status()
        return res.json()
    except requests.exceptions.RequestException as e:
        print(f"Error getting exchange info: {e}")
        return None


def get_ticker(pair: str = None) -> Optional[Dict]:
    """Get ticker for one or all pairs"""
    url = f"{ROOSTOO_BASE_URL}/v3/ticker"
    params = {'timestamp': get_timestamp()}
    if pair:
        params['pair'] = pair
    try:
        res = requests.get(url, params=params, timeout=10)
        res.raise_for_status()
        return res.json()
    except requests.exceptions.RequestException as e:
        print(f"Error getting ticker: {e}")
        return None


# ================= SIGNED ENDPOINTS (Auth Required) =================

def _get_balance_raw() -> Optional[Dict]:
    """Get wallet balances (RCL_TopLevelCheck) - raw API call"""
    url = f"{ROOSTOO_BASE_URL}/v3/balance"
    headers, payload, _ = get_signed_headers({})
    try:
        res = requests.get(url, headers=headers, params=payload, timeout=10)
        res.raise_for_status()
        return res.json()
    except requests.exceptions.RequestException as e:
        print(f"Error getting balance: {e}")
        print(f"Response text: {e.response.text if e.response else 'N/A'}")
        return None


def get_balance() -> Optional[Dict]:
    """Get wallet balances with rate limiting and auto-retry on 429"""
    return _rate_limited_call(_get_balance_raw)


def _get_pending_count_raw() -> Optional[Dict]:
    """Get total pending order count - raw API call"""
    url = f"{ROOSTOO_BASE_URL}/v3/pending_count"
    headers, payload, _ = get_signed_headers({})
    try:
        res = requests.get(url, headers=headers, params=payload, timeout=10)
        res.raise_for_status()
        return res.json()
    except requests.exceptions.RequestException as e:
        print(f"Error getting pending count: {e}")
        print(f"Response text: {e.response.text if e.response else 'N/A'}")
        return None


def get_pending_count() -> Optional[Dict]:
    """Get total pending order count with rate limiting and auto-retry on 429"""
    return _rate_limited_call(_get_pending_count_raw)


def _place_order_raw(pair_or_coin: str, side: str, quantity: str,
                price: float = None, order_type: str = None) -> Optional[Dict]:
    """
    Place a LIMIT or MARKET order - raw API call
    """
    url = f"{ROOSTOO_BASE_URL}/v3/place_order"
    pair = f"{pair_or_coin}/USD" if "/" not in pair_or_coin else pair_or_coin

    if order_type is None:
        order_type = "LIMIT" if price is not None else "MARKET"

    if order_type == 'LIMIT' and price is None:
        print("Error: LIMIT orders require 'price'.")
        return None

    payload = {
        'pair': pair,
        'side': side.upper(),
        'type': order_type.upper(),
        'quantity': str(quantity)
    }
    if order_type == 'LIMIT':
        payload['price'] = str(price)

    # POST request - ADD Content-Type HERE (like bot.py)
    headers, _, total_params = get_signed_headers(payload)
    headers['Content-Type'] = 'application/x-www-form-urlencoded'

    try:
        res = requests.post(url, headers=headers, data=total_params, timeout=10)
        res.raise_for_status()
        return res.json()
    except requests.exceptions.RequestException as e:
        print(f"Error placing order: {e}")
        print(f"Response text: {e.response.text if e.response else 'N/A'}")
        return None


def place_order(pair_or_coin: str, side: str, quantity: str,
                price: float = None, order_type: str = None) -> Optional[Dict]:
    """Place a LIMIT or MARKET order with rate limiting and auto-retry on 429"""
    return _rate_limited_call(
        _place_order_raw, 
        pair_or_coin, side, quantity, price, order_type
    )


def _query_order_raw(order_id: str = None, pair: str = None,
                pending_only: bool = None) -> Optional[Dict]:
    """Query order history or pending orders - raw API call"""
    url = f"{ROOSTOO_BASE_URL}/v3/query_order"
    payload = {}
    if order_id:
        payload['order_id'] = str(order_id)
    elif pair:
        payload['pair'] = pair
        if pending_only is not None:
            payload['pending_only'] = 'TRUE' if pending_only else 'FALSE'

    # POST request - ADD Content-Type HERE (like bot.py)
    headers, _, total_params = get_signed_headers(payload)
    headers['Content-Type'] = 'application/x-www-form-urlencoded'

    try:
        res = requests.post(url, headers=headers, data=total_params, timeout=10)
        res.raise_for_status()
        return res.json()
    except requests.exceptions.RequestException as e:
        print(f"Error querying order: {e}")
        print(f"Response text: {e.response.text if e.response else 'N/A'}")
        return None


def query_order(order_id: str = None, pair: str = None,
                pending_only: bool = None) -> Optional[Dict]:
    """Query order history or pending orders with rate limiting and auto-retry on 429"""
    return _rate_limited_call(
        _query_order_raw,
        order_id=order_id, pair=pair, pending_only=pending_only
    )


def _cancel_order_raw(order_id: str = None, pair: str = None) -> Optional[Dict]:
    """Cancel specific or all pending orders - raw API call"""
    url = f"{ROOSTOO_BASE_URL}/v3/cancel_order"
    payload = {}
    if order_id:
        payload['order_id'] = str(order_id)
    elif pair:
        payload['pair'] = pair

    # POST request - ADD Content-Type HERE (like bot.py)
    headers, _, total_params = get_signed_headers(payload)
    headers['Content-Type'] = 'application/x-www-form-urlencoded'

    try:
        res = requests.post(url, headers=headers, data=total_params, timeout=10)
        res.raise_for_status()
        return res.json()
    except requests.exceptions.RequestException as e:
        print(f"Error canceling order: {e}")
        print(f"Response text: {e.response.text if e.response else 'N/A'}")
        return None


def cancel_order(order_id: str = None, pair: str = None) -> Optional[Dict]:
    """Cancel specific or all pending orders with rate limiting and auto-retry on 429"""
    return _rate_limited_call(
        _cancel_order_raw,
        order_id=order_id, pair=pair
    )


# ================= HELPER FUNCTIONS FOR TRADING BOT =================

def get_rate_limiter_stats() -> Dict:
    """Get rate limiter statistics for monitoring"""
    return _rate_limiter.get_stats()


# === SHARED BALANCE MANAGEMENT (called once per candle) ===

def refresh_balance_cache(ccy: str = "USD") -> float:
    """
    Fetch balance from Roostoo API and update the shared cache.
    Call this ONCE at the start of every candle (15min) from main.py.
    All coin traders will then use this cached value.
    
    Uses a lock and 'refreshing' flag to ensure only ONE refresh happens
    even if multiple traders call this simultaneously.

    Args:
        ccy: Currency to fetch (default: "USD")

    Returns:
        Updated balance value
    """
    global _global_balance_cache

    with _global_balance_cache['lock']:
        # Check if already refreshing (another trader is doing it)
        if _global_balance_cache['refreshing']:
            print("⏳ Balance refresh in progress by another trader, waiting...")
            # Just wait and return the cached value once it's done
            import time
            for _ in range(20):  # Wait up to 2 seconds
                time.sleep(0.1)
                if not _global_balance_cache['refreshing']:
                    break
            return _global_balance_cache['balance']
        
        _global_balance_cache['refreshing'] = True
        
        try:
            data = get_balance()

            if not data:
                print("⚠️  Failed to fetch balance for cache")
                return 0.0

            # Handle both 'Wallet' and 'SpotWallet' formats
            wallet = data.get('Wallet', {}) or data.get('SpotWallet', {})

            if ccy in wallet:
                free_bal = wallet[ccy].get('Free', 0)
                balance = float(free_bal) if free_bal else 0.0
            else:
                balance = 0.0

            now = datetime.now(timezone.utc)
            _global_balance_cache['balance'] = balance
            _global_balance_cache['timestamp'] = now
            # Track which candle this balance is for (15-min intervals)
            _global_balance_cache['candle_timestamp'] = now.replace(minute=(now.minute // 15) * 15, second=0, microsecond=0)

            print(f"💰 Balance cache updated: ${balance:.2f} USD @ {now.strftime('%H:%M:%S')} (candle: {_global_balance_cache['candle_timestamp'].strftime('%H:%M')})")
            return balance
        finally:
            _global_balance_cache['refreshing'] = False


def get_cached_balance(ccy: str = "USD") -> float:
    """
    Get the cached balance value (shared across all traders).
    This does NOT make an API call - uses the cached value only.
    
    Args:
        ccy: Currency to get (default: "USD")
    
    Returns:
        Cached balance value
    """
    global _global_balance_cache
    
    with _global_balance_cache['lock']:
        balance = _global_balance_cache['balance']
        timestamp = _global_balance_cache['timestamp']
        
        if timestamp:
            print(f"📖 Using cached balance: ${balance:.2f} USD (from {timestamp.strftime('%H:%M:%S')})")
        else:
            print(f"⚠️  No cached balance available (cache not initialized)")
        
        return balance


def is_balance_cache_valid() -> bool:
    """
    Check if the balance cache has been initialized for this candle.
    
    Returns:
        True if cache has been populated for current candle, False otherwise
    """
    global _global_balance_cache
    if _global_balance_cache['candle_timestamp'] is None:
        return False
    
    # Check if cache is for current candle
    now = datetime.now(timezone.utc)
    current_candle = now.replace(minute=(now.minute // 15) * 15, second=0, microsecond=0)
    return _global_balance_cache['candle_timestamp'] == current_candle


def get_current_candle_timestamp() -> Optional[datetime]:
    """
    Get the candle timestamp that the cache is for.
    
    Returns:
        Candle timestamp if cache is initialized, None otherwise
    """
    global _global_balance_cache
    return _global_balance_cache.get('candle_timestamp')


# === LEGACY FUNCTIONS (kept for backward compatibility) ===

def get_roostoo_account_info() -> Dict:
    """Get account balance information (wrapper)"""
    data = get_balance()
    return data if data else {}


def get_roostoo_balance(ccy: str = "USD", use_cache: bool = True) -> float:
    """
    Get balance for a specific currency.
    
    Args:
        ccy: Currency to get (default: "USD")
        use_cache: If True, use cached balance (default). If False, fetch fresh from API.
    
    Returns:
        Balance value
    """
    if use_cache:
        return get_cached_balance(ccy)
    
    # Fresh API call (only use this when absolutely necessary)
    data = get_balance()

    if not data:
        return 0.0

    # Handle both 'Wallet' and 'SpotWallet' formats
    wallet = data.get('Wallet', {}) or data.get('SpotWallet', {})

    if ccy in wallet:
        free_bal = wallet[ccy].get('Free', 0)
        return float(free_bal) if free_bal else 0.0

    return 0.0


def get_roostoo_pending_count() -> Dict:
    """Get pending order count (wrapper)"""
    data = get_pending_count()
    return data if data else {'TotalPending': 0, 'OrderPairs': {}}


def get_roostoo_current_price(pair: str = "ETH/USD") -> float:
    """Get current market price for a trading pair"""
    data = get_ticker(pair)
    if data and data.get('Success') and 'Data' in data:
        pair_data = data['Data'].get(pair, {})
        last_price = pair_data.get('LastPrice', 0)
        return float(last_price) if last_price else 0.0
    return 0.0


def calculate_roostoo_order_size(usd_amount: float, coin_price: float,
                                  price_precision: int = 2,
                                  amount_precision: int = 2,
                                  mini_order: float = 1.0) -> str:
    """Calculate valid order size for Roostoo spot trading"""
    coin_amount = usd_amount / coin_price

    # For low-priced coins, use INTEGER quantities (no decimals)
    # This is required by the exchange to avoid "quantity step size error"
    if coin_price < 10:
        # For coins < $0.01, use integer quantities only
        valid_amount = int(coin_amount)
        amount_precision = 0
    else:
        # For normal coins, use standard precision
        precision_multiplier = 10 ** amount_precision
        valid_amount = int(coin_amount * precision_multiplier) / precision_multiplier

    order_value = valid_amount * coin_price
    if order_value < mini_order:
        valid_amount = mini_order / coin_price
        if coin_price < 0.01:
            valid_amount = int(valid_amount)
        else:
            precision_multiplier = 10 ** amount_precision
            valid_amount = int(valid_amount * precision_multiplier) / precision_multiplier

    if amount_precision == 0:
        return f"{int(valid_amount)}"
    else:
        return f"{valid_amount:.{amount_precision}f}"


def place_roostoo_order(pair: str = "ETH/USD",
                        side: str = "BUY",
                        order_type: str = "MARKET",
                        quantity: str = None,
                        price: float = None) -> Optional[str]:
    """Place an order on Roostoo (returns order_id)"""
    data = place_order(pair_or_coin=pair, side=side, quantity=quantity,
                       price=price, order_type=order_type)

    if data and data.get('Success'):
        order_detail = data.get('OrderDetail', {})
        order_id = order_detail.get('OrderID')
        status = order_detail.get('Status')
        print(f"✅ Order placed: ID={order_id}, Status={status}")
        return str(order_id)
    else:
        # Log the error for debugging
        error_msg = data.get('Message', 'Unknown error') if data else 'No response'
        print(f"❌ Order FAILED for {pair}: {error_msg}")
        print(f"   Quantity: {quantity}")
        print(f"   Full Response: {data}")
        return None


def query_roostoo_order(order_id: str = None, pair: str = None, 
                        pending_only: bool = False) -> List:
    """Query order history (returns list of orders)"""
    data = query_order(order_id=order_id, pair=pair, pending_only=pending_only)
    if data and data.get('Success'):
        return data.get('OrderMatched', [])
    return []


def cancel_roostoo_order(order_id: str = None, pair: str = None) -> List:
    """Cancel pending order(s) (returns list of canceled order IDs)"""
    data = cancel_order(order_id=order_id, pair=pair)
    if data and data.get('Success'):
        return data.get('CanceledList', [])
    return []


def close_roostoo_position(pair: str = "ETH/USD", side: str = "SELL") -> Optional[str]:
    """Close position by placing opposite market order"""
    # Get current balance to know how much to sell
    balance_data = get_balance()
    if not balance_data:
        print("⚠️ Could not fetch balance to close position")
        return None
    
    wallet = balance_data.get('Wallet', {}) or balance_data.get('SpotWallet', {})
    coin = pair.split('/')[0]
    
    if coin in wallet:
        free_balance = wallet[coin].get('Free', 0)
        if free_balance and float(free_balance) > 0:
            return place_roostoo_order(
                pair=pair,
                side=side,
                order_type="MARKET",
                quantity=str(free_balance)
            )
    
    print("⚠️ No position to close")
    return None


def get_roostoo_position(pair: str = "ETH/USD") -> Tuple[float, float]:
    """
    Get current position for spot trading
    Returns: (coin_balance, avg_price)
    For spot, we return balance instead of futures position
    """
    coin = pair.split('/')[0]
    balance_data = get_balance()
    
    if not balance_data:
        return 0.0, 0.0
    
    wallet = balance_data.get('Wallet', {}) or balance_data.get('SpotWallet', {})
    
    if coin in wallet:
        free_balance = float(wallet[coin].get('Free', 0))
        return free_balance, 0.0  # Spot doesn't track avg price
    
    return 0.0, 0.0


# ================= LEVERAGE/POSITION MODE (NOT SUPPORTED ON ROOSTOO) =================

def set_roostoo_leverage(inst_id: str = "ETH/USD", lever: int = 1, 
                         mgn_mode: str = "spot") -> Dict:
    """Roostoo is spot-only, leverage not supported"""
    print("⚠️ Roostoo is spot-only trading. Leverage not supported.")
    return {'Success': True, 'Msg': 'Leverage not applicable for spot trading'}


def set_roostoo_position_mode(pos_mode: str = "spot") -> Dict:
    """Roostoo doesn't have position modes like OKX"""
    print("⚠️ Roostoo doesn't support position modes (spot trading only)")
    return {'Success': True, 'Msg': 'Position mode not applicable'}


# ================= HELPER FOR IMPORTS =================

def get_roostoo_client():
    """Helper so other files can import easily"""
    return None