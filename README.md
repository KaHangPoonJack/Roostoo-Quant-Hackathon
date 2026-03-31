# 🏆 Quant Trading Bot - Hackathon Submission

## 📋 Executive Summary

**Project Name:** Multi-Coin ML-Powered Quantitative Trading Bot  
**Competition:** Roostoo Quant Hackathon 2026  
**Trading Strategy:** Chandelier Exit + Supertrend with ML Filter  
**Asset Class:** Cryptocurrency Perpetual Swaps  
**Trading Horizon:** Intraday (15-minute candles, max 3-hour holds)  
**Portfolio:** 25 cryptocurrencies traded in parallel  

---

## 🎯 Trading Strategy Overview

### Core Philosophy

This trading bot combines **technical analysis** with **machine learning** to identify and execute high-probability breakout trades across 25 cryptocurrency pairs. The strategy uses a dual-confirmation system where both the technical indicator (Chandelier Exit) and ML model must agree before entering a trade.

### Strategy Components

| Component | Purpose | Technology |
|-----------|---------|------------|
| **Entry Signal** | Identify trend reversals | Chandelier Exit + Supertrend |
| **Trade Filter** | Validate breakout probability | LightGBM + XGBoost Ensemble |
| **Position Sizing** | Dynamic risk allocation | ML confidence-based |
| **Exit Strategy** | Profit taking + risk management | Ladder TP + Time-based exit |
| **Risk Management** | Protect capital | Class-based Stop Loss |

---

## 📊 Technical Strategy Details

### 1. Chandelier Exit (Primary Signal Generator)

The **Chandelier Exit** is a trend-following indicator designed to keep traders in the trend until a definitive reversal occurs. It hangs an Average True Range (ATR) multiple below the highest high (for longs) or above the lowest low (for shorts).

#### Configuration:
```python
ATR Period: 22          # Lookback period for ATR calculation
ATR Multiplier: 3       # Standard multiplier (non-US market)
ATR Multiplier (US): 3  # Adjusted multiplier during US market hours
Timeframe: 15 minutes   # Candle interval
```

#### Calculation:
```
Long Stop  = Highest High (22 periods) - (3 × ATR₂₂)
Short Stop = Lowest Low (22 periods) + (3 × ATR₂₂)

Buy Signal:  Price crosses above Short Stop → Dir = 1
Sell Signal: Price crosses below Long Stop  → Dir = -1
```

#### US Market Hours Adjustment:
During US market open (9:30 AM - 4:00 PM EST), volatility typically increases. The strategy accounts for this by using a separate ATR multiplier configuration.

---

### 2. Supertrend Indicator (Trend Confirmation)

The **Supertrend** indicator provides additional trend confirmation and helps filter false signals from the Chandelier Exit.

#### Configuration:
```python
Supertrend ATR Period: 2
Supertrend Factor: 0.5
```

#### Calculation:
```
HL2 = (High + Low) / 2
Upper Band = HL2 + (0.5 × ATR₂)
Lower Band = HL2 - (0.5 × ATR₂)

Trend Direction:
- Uptrend (Dir = -1): Price > Upper Band
- Downtrend (Dir = 1): Price < Lower Band
```

#### Entry Confirmation Rules:
```
LONG Entry:  Chandelier Buy Signal AND Supertrend = Uptrend
SHORT Entry: Chandelier Sell Signal AND Supertrend = Downtrend
```

---

### 3. Time-Based Exit (Maximum Hold Duration)

To prevent capital from being tied up in non-performing trades, a hard time limit is enforced:

```python
Maximum Hold Period: 12 candles (3 hours)
Minimum Hold Period: 1 candle (15 minutes)

Exit Condition:
IF (bars_held >= 12) AND (P&L < 0.5%):
    → Force Close Position
```

This ensures the bot continuously rotates capital into fresh opportunities rather than waiting indefinitely for marginal profits.

---

## 🤖 Machine Learning Model Architecture

### Model Overview

The ML component serves as a **pre-trade filter** that predicts the magnitude of price movements over the next 12 bars (3 hours). Only trades with high ML confidence are executed, significantly improving win rate.

### Ensemble Architecture

```
┌─────────────────────────────────────────────────────┐
│              ML ENSEMBLE PREDICTOR                   │
├─────────────────────────────────────────────────────┤
│  ┌─────────────────┐      ┌─────────────────┐      │
│  │   LightGBM      │      │    XGBoost      │      │
│  │   Classifier    │      │   Classifier    │      │
│  └────────┬────────┘      └────────┬────────┘      │
│           └──────────┬─────────────┘               │
│                      ▼                              │
│           ┌──────────────────┐                      │
│           │  Weighted Average │                     │
│           │    Ensemble      │                      │
│           └────────┬─────────┘                      │
│                    ▼                                │
│         ┌─────────────────────┐                     │
│         │  Final Probability  │                     │
│         │   Distribution      │                     │
│         └─────────────────────┘                     │
└─────────────────────────────────────────────────────┘
```

---

### Target Variable (Multi-Class Classification)

The model predicts price movement magnitude over a **12-bar horizon (3 hours)**:

| Class | Label | Price Movement | Trading Action |
|-------|-------|----------------|----------------|
| **0** | No Trade | < 1% | Skip trade |
| **1** | Small Breakout | 1% - 3% | Conservative position (2%) |
| **2** | Medium Breakout | 3% - 5% | Moderate position (4-6%) |
| **3** | Large Breakout | > 5% | Aggressive position (6-8%) |

#### Labeling Logic:
```python
# Forward-looking label assignment
def assign_label(current_bar, horizon=12):
    max_price = max(High[current_bar : current_bar + horizon])
    min_price = min(Low[current_bar : current_bar + horizon])
    
    max_deviation = max(
        abs(max_price - close) / close,
        abs(min_price - close) / close
    )
    
    # Check for reversal constraint (no >0.5% reversal within 3h)
    reversal_check = validate_no_reversal(current_bar, horizon, threshold=0.005)
    
    if max_deviation < 0.01:
        return 0  # No trade
    elif max_deviation < 0.03 and reversal_check:
        return 1  # Small breakout
    elif max_deviation < 0.05 and reversal_check:
        return 2  # Medium breakout
    elif reversal_check:
        return 3  # Large breakout
    else:
        return 0  # Reversal risk too high
```

---

### Feature Engineering

The model uses a comprehensive feature set across multiple categories:

#### 1. Technical Indicators (Price-Based)
| Category | Features |
|----------|----------|
| **Trend** | SMA (10, 20, 50), EMA (9, 21), MACD, ADX |
| **Momentum** | RSI (14), Stochastic, Williams %R, CCI |
| **Volatility** | Bollinger Bands, ATR, Keltner Channel |
| **Volume** | OBV, Volume SMA, VWAP, Money Flow Index |

#### 2. Price Action Features
- Open, High, Low, Close (OHLC)
- Candlestick patterns (Doji, Hammer, Engulfing)
- Higher Highs / Lower Lows detection
- Price momentum (1, 3, 5, 10-bar returns)
- Gap analysis (open vs previous close)

#### 3. Volatility Metrics
- Historical volatility (rolling 10, 20, 30 bars)
- ATR ratio (current vs average)
- Bollinger Band width
- True Range expansion/contraction

#### 4. Volume Analysis
- Volume surge detection (vs 20-bar average)
- Accumulation/Distribution
- Buy/Sell pressure ratio
- Volume-weighted price changes

#### 5. Market Structure
- Support/Resistance levels
- Pivot points (daily, weekly)
- Round number proximity
- All-time high/low distance

#### 6. Macro Features (Planned/Configurable)
- S&P 500 correlation
- DXY (US Dollar Index) movement
- BTC dominance (for altcoins)
- VIX (volatility index)

---

### Model Training Pipeline

```
┌────────────────────────────────────────────────────────────┐
│                    TRAINING PIPELINE                        │
├────────────────────────────────────────────────────────────┤
│                                                             │
│  1. DATA COLLECTION                                        │
│     └─→ Binance 15m OHLCV (3+ years per coin)             │
│                                                             │
│  2. FEATURE ENGINEERING                                    │
│     └─→ Calculate 50+ technical indicators                │
│         └─→ Normalize/Standardize features                │
│                                                             │
│  3. LABEL GENERATION                                       │
│     └─→ Forward-looking 12-bar prediction                 │
│         └─→ Apply reversal constraint filter              │
│                                                             │
│  4. TRAIN/TEST SPLIT                                       │
│     └─→ 80% Train / 20% Test (time-series split)         │
│                                                             │
│  5. MODEL TRAINING                                         │
│     ├─→ LightGBM (500 estimators, max_depth=6)           │
│     └─→ XGBoost (500 estimators, max_depth=5)            │
│                                                             │
│  6. ENSEMBLE CALIBRATION                                   │
│     └─→ Optimize weighting via cross-validation          │
│                                                             │
│  7. MODEL EXPORT                                           │
│     └─→ Save as .rm (Roostoo Model) format               │
│                                                             │
└────────────────────────────────────────────────────────────┘
```

#### Hyperparameters (Per-Coin Optimization):
```python
# LightGBM Configuration
lightgbm_params = {
    'n_estimators': 500,
    'max_depth': 6,
    'learning_rate': 0.05,
    'num_leaves': 31,
    'min_child_samples': 20,
    'subsample': 0.8,
    'colsample_bytree': 0.8,
    'reg_alpha': 0.1,
    'reg_lambda': 0.1
}

# XGBoost Configuration
xgboost_params = {
    'n_estimators': 500,
    'max_depth': 5,
    'learning_rate': 0.05,
    'subsample': 0.8,
    'colsample_bytree': 0.8,
    'gamma': 0.1,
    'reg_alpha': 0.1,
    'reg_lambda': 1.0
}
```

---

### Inference Pipeline (Live Trading)

```
┌─────────────────────────────────────────────────────────────┐
│                    LIVE PREDICTION FLOW                      │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  1. FETCH REAL-TIME DATA                                   │
│     └─→ Binance 15m candle (every 15 min)                 │
│                                                             │
│  2. FEATURE CALCULATION                                    │
│     └─→ Compute 50+ features from latest candle          │
│                                                             │
│  3. MODEL INFERENCE                                        │
│     ├─→ LightGBM prediction (probabilities)              │
│     └─→ XGBoost prediction (probabilities)               │
│                                                             │
│  4. ENSEMBLE AGGREGATION                                   │
│     └─→ Weighted average → Final probability distribution│
│                                                             │
│  5. TRADING DECISION                                       │
│     IF breakout_prob (Class 1+2+3) >= 0.70:              │
│         → APPROVE TRADE                                   │
│     ELSE:                                                 │
│         → REJECT TRADE                                    │
│                                                             │
│  6. POSITION SIZING                                        │
│     IF breakout_prob >= 0.95: size = 8%                  │
│     ELIF breakout_prob >= 0.90: size = 6%                │
│     ELIF breakout_prob >= 0.80: size = 4%                │
│     ELIF breakout_prob >= 0.70: size = 2%                │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

#### Prediction Output Example:
```json
{
  "symbol": "ETH/USDT",
  "timestamp": "2026-03-31T10:00:00Z",
  "price": 3250.50,
  "predicted_class": 2,
  "probabilities": {
    "class_0": 0.15,
    "class_1": 0.25,
    "class_2": 0.40,
    "class_3": 0.20
  },
  "breakout_probability": 0.85,
  "recommendation": "ENTER_MEDIUM",
  "position_size_pct": 0.06,
  "tp_target": 0.03,
  "sl_limit": 0.015
}
```

---

## 💼 Portfolio Management

### Multi-Coin Architecture

The bot trades **25 cryptocurrencies** simultaneously, each with its own dedicated ML model:

#### Original 5 Coins:
1. **BTC** (Bitcoin) - Market leader, highest liquidity
2. **ETH** (Ethereum) - Smart contract platform
3. **SOL** (Solana) - High-performance blockchain
4. **DOGE** (Dogecoin) - Meme coin, high volatility
5. **PEPE** (Pepe) - Meme coin, extreme volatility

#### Additional 20 Coins:
6. PAXG, 7. TRX, 8. FET, 9. SUI, 10. ASTER, 11. LTC, 12. XLM, 13. VIRTUAL, 14. FIL, 15. ONDO, 16. SHIB, 17. HBAR, 18. WIF, 19. BONK, 20. OPEN, 21. LINEA, 22. PENDLE, 23. CFX, 24. 1000CHEEMS, 25. MIRA

### Independent Model Per Coin

```
┌─────────────────────────────────────────────────────────────┐
│              MULTI-COIN TRADING ARCHITECTURE                │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐     │
│  │  BTC Trader  │  │  ETH Trader  │  │  SOL Trader  │ ... │
│  ├──────────────┤  ├──────────────┤  ├──────────────┤     │
│  │ BTC ML Model │  │ ETH ML Model │  │ SOL ML Model │     │
│  │ (LightGBM +  │  │ (LightGBM +  │  │ (LightGBM +  │     │
│  │  XGBoost)    │  │  XGBoost)    │  │  XGBoost)    │     │
│  └──────────────┘  └──────────────┘  └──────────────┘     │
│                                                             │
│  Each trader runs in parallel with:                        │
│  - Independent ML predictions                              │
│  - Independent CE signals                                  │
│  - Independent position management                         │
│  - Shared capital pool                                     │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### Capital Allocation

```python
# Per-coin allocation
allocation_per_coin = 1.0  # 100% of available balance (shared pool)

# Dynamic position sizing based on ML confidence
if breakout_probability >= 0.95:
    position_size = balance * 0.08  # 8%
elif breakout_probability >= 0.90:
    position_size = balance * 0.06  # 6%
elif breakout_probability >= 0.80:
    position_size = balance * 0.04  # 4%
elif breakout_probability >= 0.70:
    position_size = balance * 0.02  # 2%
else:
    position_size = 0  # No trade
```

---

## 🛡️ Risk Management

### Take Profit Strategy (Ladder Exit)

Instead of exiting all at once, the bot uses a **ladder TP system** to maximize profits while securing gains:

#### Class-Based TP Levels:
```python
TAKE_PROFIT_PCT = {
    1: 0.01,  # Class 1: 1% TP
    2: 0.03,  # Class 2: 3% TP
    3: 0.05   # Class 3: 5% TP
}

# Extended ladder for partial exits
TP_LADDER_LEVELS = [
    0.01, 0.02, 0.03, 0.04, 0.05,  # 1-5%
    0.06, 0.07, 0.08, 0.09, 0.10,  # 6-10%
    0.11, 0.12, 0.13, 0.14, 0.15,  # 11-15%
    0.16, 0.17, 0.18, 0.19, 0.20   # 16-20%
]
```

#### Partial Exit Logic:
```
Price hits TP Level 1 (1%): Close 10% of position
Price hits TP Level 2 (2%): Close 15% of position
Price hits TP Level 3 (3%): Close 20% of position
...
Price reverses from highest TP: Close remaining position
```

---

### Stop Loss Strategy

Class-based stop loss with risk-reward optimization:

```python
STOP_LOSS_PCT = {
    1: 0.01,   # Class 1: 1% SL (RRR 1:1)
    2: 0.015,  # Class 2: 1.5% SL (RRR 1:2)
    3: 0.025   # Class 3: 2.5% SL (RRR 1:2)
}
```

#### SL Placement Logic:
```python
# Long Position
entry_price = 100.00
predicted_class = 2  # 3-5% target
sl_pct = 0.015       # 1.5% SL for Class 2

stop_loss = entry_price * (1 - 0.015)  # $98.50
take_profit = entry_price * (1 + 0.03) # $103.00

# Risk-Reward Ratio: 1:2
```

---

### Position Management Rules

| Rule | Description |
|------|-------------|
| **Max Hold Time** | 12 candles (3 hours) - forced exit |
| **Min Hold Time** | 1 candle (15 min) - no premature exits |
| **Cooldown Period** | 2 candles (30 min) after exit before re-entry |
| **Reversal Protection** | 3 consecutive reversal checks before exit |
| **Duplicate Entry Prevention** | Fresh position check before each entry |
| **Cache Management** | Balance cache refreshed once per candle |

---

## 🏗️ System Architecture

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        TRADING BOT SYSTEM                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │                   DATA LAYER                              │  │
│  ├──────────────────────────────────────────────────────────┤  │
│  │  • Binance API (Real-time 15m candles)                  │  │
│  │  • Roostoo Broker API (Execution)                       │  │
│  │  • Historical Data Cache                                │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │                  ML PREDICTION LAYER                      │  │
│  ├──────────────────────────────────────────────────────────┤  │
│  │  • 25 Independent ML Models (LightGBM + XGBoost)        │  │
│  │  • Feature Engineering Pipeline                         │  │
│  │  • Confidence Scoring & Position Sizing                 │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │                   STRATEGY LAYER                          │  │
│  ├──────────────────────────────────────────────────────────┤  │
│  │  • Chandelier Exit Signal Generator                     │  │
│  │  • Supertrend Confirmation                              │  │
│  │  • ML Filter (Confidence Threshold)                     │  │
│  │  • Entry/Exit Logic                                     │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │                 EXECUTION LAYER                           │  │
│  ├──────────────────────────────────────────────────────────┤  │
│  │  • Order Management (Market/Limit)                      │  │
│  │  • Position Tracking                                    │  │
│  │  • TP/SL Monitoring                                     │  │
│  │  • Risk Management                                      │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │                  MONITORING LAYER                         │  │
│  ├──────────────────────────────────────────────────────────┤  │
│  │  • Web Dashboard (Flask API)                            │  │
│  │  • Telegram Notifications                               │  │
│  │  • Trading History Database                             │  │
│  │  • Daily Performance Reports                            │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

### Thread Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    THREADING MODEL                           │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Main Thread                                               │
│  └─→ API Server (Flask, port 5000)                        │
│  └─→ Daily Report Scheduler                               │
│                                                             │
│  Trader Threads (25 parallel threads)                     │
│  ├─→ BTC Trader Thread                                    │
│  ├─→ ETH Trader Thread                                    │
│  ├─→ SOL Trader Thread                                    │
│  └─→ ... (22 more)                                        │
│      Each thread:                                          │
│      - Waits for 15m candle close                         │
│      - Fetches latest data                                │
│      - Runs ML inference                                  │
│      - Executes strategy logic                            │
│      - Manages TP/SL monitoring                           │
│                                                             │
│  TP/SL Monitoring Threads (25 background threads)         │
│  └─→ Each trader has dedicated TP/SL monitor             │
│      - Checks price every 2 seconds                       │
│      - Triggers partial/full exits                        │
│                                                             │
│  ML Prediction Scheduler (1 thread)                       │
│  └─→ Consolidates predictions every 15 min               │
│  └─→ Sends Telegram summary                               │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## 📡 Data Flow

### Real-Time Trading Loop (Per Coin)

```
Every 15 Minutes (Candle Close):
│
├─ 1. Wait for candle close (UTC 00:00, 00:15, 00:30, ...)
│
├─ 2. Fetch latest candle from Binance
│   └─→ OHLCV data
│
├─ 3. Update strategy dataframe
│   └─→ Append new candle
│
├─ 4. Calculate technical indicators
│   ├─→ Chandelier Exit levels
│   ├─→ Supertrend direction
│   └─→ ATR, momentum, volatility
│
├─ 5. Run ML inference
│   ├─→ Calculate 50+ features
│   ├─→ LightGBM prediction
│   ├─→ XGBoost prediction
│   └─→ Ensemble probabilities
│
├─ 6. Apply trading logic
│   ├─→ Check for existing position
│   │   ├─→ If YES: Check TP/SL exit conditions
│   │   └─→ If NO: Check entry conditions
│   │       ├─→ CE signal (Buy/Sell)
│   │       ├─→ Supertrend confirmation
│   │       ├─→ ML approval (breakout_prob >= 70%)
│   │       └─→ Execute market order
│   │
│   └─→ Start TP/SL monitoring thread (if new position)
│
├─ 7. Update caches
│   ├─→ Balance cache (once per candle for all coins)
│   └─→ Position cache
│
└─ 8. Log to database
    ├─→ ML prediction
    ├─→ Trade entry/exit
    └─→ P&L update
```

---

## 📊 Performance Metrics

### Key Performance Indicators (KPIs)

| Metric | Description | Target |
|--------|-------------|--------|
| **Win Rate** | % of profitable trades | > 55% |
| **Avg P&L** | Average profit/loss per trade | > 0.5% |
| **Sharpe Ratio** | Risk-adjusted returns | > 1.5 |
| **Max Drawdown** | Largest peak-to-trough decline | < 15% |
| **Profit Factor** | Gross profit / Gross loss | > 1.5 |
| **Avg Hold Time** | Average trade duration | 1-3 hours |
| **Trades/Day** | Trading frequency | 10-30 |

---

### ML Model Performance Metrics

| Metric | Description | Typical Range |
|--------|-------------|---------------|
| **Accuracy** | % correct class predictions | 45-60% |
| **Precision (Class 1+)** | % of breakout predictions that succeed | 55-65% |
| **Recall (Class 1+)** | % of actual breakouts detected | 60-70% |
| **AUC-ROC** | Area under ROC curve | 0.60-0.70 |
| **Calibration** | Predicted vs actual probability | ±5% |

---

## 🔧 Configuration & Deployment

### Environment Variables

```bash
# Exchange Credentials
ROOSTOO_API_KEY=your_api_key
ROOSTOO_SECRET_KEY=your_secret_key
ROOSTOO_BASE_URL=https://mock-api.roostoo.com

# Data Source (Binance)
BINANCE_API_KEY=your_binance_key
BINANCE_API_SECRET=your_binance_secret

# Notifications
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_CHAT_ID=your_chat_id

# Trading Configuration
ROOSTOO_PAIR=ETH/USD
ROOSTOO_BASE_CURRENCY=USD
POSITION_SIZE_PCT=0.5

# ML Configuration
ML_ENABLED=True
ML_CONFIDENCE_THRESHOLD=0.7
```

---

### File Structure

```
Project File/
├── main.py                      # Entry point
├── config/
│   ├── settings.py              # Configuration constants
│   └── __init__.py
├── core/
│   ├── api_server.py            # Flask REST API
│   ├── binance_client.py        # Binance data fetcher
│   ├── roostoo_client.py        # Roostoo execution client
│   ├── telegram_bot.py          # Notification system
│   ├── trading_history.py       # SQLite database layer
│   └── utils.py                 # Utility functions
├── data/
│   └── fetcher.py               # Historical data loader
├── strategies/
│   └── chandelier_exit.py       # CE strategy implementation
├── trading/
│   ├── coin_trader.py           # Single coin trading logic
│   └── multi_coin_manager.py    # Multi-coin orchestration
├── ML/
│   ├── live_predictor.py        # ML inference engine
│   └── models/                  # Trained model files (.rm)
│       ├── btc_models/
│       ├── eth_models/
│       └── ... (23 more)
├── web/
│   ├── index.html               # Dashboard UI
│   └── static/
│       ├── dashboard.js         # Frontend logic
│       └── style.css            # Styling
├── daily_report.py              # Daily Telegram report
└── requirements.txt             # Python dependencies
```

---

## 🎯 Key Innovations

### 1. Dual-Confirmation System
- **Technical (CE + Supertrend)** provides entry timing
- **ML Filter** validates breakout probability
- Both must agree → Higher quality trades

### 2. Per-Coin ML Models
- Each coin has unique market dynamics
- Dedicated models capture coin-specific patterns
- No one-size-fits-all approach

### 3. Confidence-Based Position Sizing
- Higher ML confidence → Larger position
- Dynamic risk allocation
- Optimizes capital efficiency

### 4. Ladder Take Profit
- Partial exits at multiple levels
- Captures trending moves
- Reduces regret from early exits

### 5. Time-Based Exit
- Prevents dead capital
- Forces rotation into fresh opportunities
- Complements technical exits

### 6. Consolidated Notifications
- Single Telegram message for all 25 coins
- Prevents notification spam
- Easy to scan and digest

---

## 📈 Dashboard Features

### Web Interface (http://localhost:5000)

#### Tabs:
1. **📊 Overview** - Portfolio summary, total P&L, win rate
2. **💰 Coins** - Live status of all 25 traders with ML probabilities
3. **🔮 ML Predictions** - Latest predictions + historical charts
4. **📝 Trade History** - Complete trade log with entry/exit details
5. **📈 Analytics** - Performance charts, win rate by coin, ML class distribution

#### Real-Time Updates:
- Auto-refresh every 2 seconds
- Live P&L tracking
- ML predictions updated every 15 minutes

---

## 📱 Telegram Notifications

### Notification Types:

1. **Trade Entry**
   ```
   🟢 NEW TRADE - BTC
   Side: LONG
   Entry: $67,500.00
   ML Class: 2 (3-5% target)
   Breakout Prob: 85%
   Position Size: 6%
   TP: $69,525.00 (+3%)
   SL: $66,487.50 (-1.5%)
   ```

2. **Trade Exit**
   ```
   🚨 CLOSED - BTC
   Reason: TP Level 3 Hit
   Exit: $69,525.00
   P&L: +3.00%
   Hold Time: 1h 45min
   ```

3. **Consolidated ML Predictions** (Every 15 min)
   ```
   🔮 ML PREDICTIONS - All 25 Coins
   ┌─────┬───────┬──────────┬─────────┐
   │ Coin│ Class │ Conf     │ Breakout│
   ├─────┼───────┼──────────┼─────────┤
   │ BTC │   2   │  68.5%   │  72.3%  │
   │ ETH │   1   │  71.2%   │  65.8%  │
   │ SOL │   3   │  62.4%   │  81.5%  │
   │ ... │  ...  │   ...    │   ...   │
   └─────┴───────┴──────────┴─────────┘
   ```

4. **Daily Report** (UTC 00:00)
   ```
   ✅ DAILY TRADING REPORT
   📅 Date: 2026-03-31
   📊 Total Trades: 47
   🎯 Win Rate: 57.4% (27W/20L)
   📈 Total P&L: +4.82%
   📈 Avg P&L: +0.10%
   ⭐ Best: SOL (+1.85%)
   🔻 Worst: DOGE (-0.52%)
   ```

---

## 🧪 Testing & Validation

### Backtesting Framework

```python
# Historical backtesting on 3+ years of data
# Walk-forward validation
# Out-of-sample testing

Metrics Tracked:
- Cumulative P&L
- Win rate by coin
- Win rate by ML class
- Avg hold time
- Max drawdown
- Sharpe ratio
```

### Paper Trading Mode

```python
# Run with ML_ENABLED=False to test CE-only strategy
# Run with small position sizes to validate execution
# Monitor Telegram alerts for signal quality
```

---

## 🚀 Deployment Options

### Local Development
```bash
pip install -r requirements.txt
python main.py
# Dashboard: http://localhost:5000
```

### AWS EC2 Production
```bash
# Ubuntu 22.04 EC2 instance
# Docker containerization available
# Systemd service for auto-start
# CloudWatch logging
```

### High Availability
```
- Multi-AZ deployment recommended
- RDS for database (instead of SQLite)
- S3 backup for ML models
- Auto-scaling for high load
```

---

## 📚 References & Inspiration

### Academic Papers:
1. **Chandelier Exit** - Chuck LeBeau's trend-following methodology
2. **LightGBM** - "LightGBM: A Highly Efficient Gradient Boosting Decision Tree" (Microsoft)
3. **XGBoost** - "XGBoost: A Scalable Tree Boosting System" (Chen & Guestrin)

### Technical Indicators:
- **ATR** - J. Welles Wilder Jr., "New Concepts in Technical Trading Systems"
- **Supertrend** - Popularized by Indian trading community

---

## 👥 Team & Contributions

**Solo Developer Project** - Designed, developed, and deployed by a single quantitative developer with expertise in:
- Machine Learning (LightGBM, XGBoost, scikit-learn)
- Algorithmic Trading (Technical Analysis, Risk Management)
- Software Engineering (Python, Async Programming, REST APIs)
- DevOps (AWS, Docker, CI/CD)

---

## 📞 Contact & Support

**GitHub Repository:** [Your GitHub Link]  
**Documentation:** See `/docs` folder for detailed guides  
**Issues:** Open GitHub issues for bugs or feature requests  

---

## ⚠️ Disclaimer

This trading bot is provided for **educational and research purposes** only. Past performance does not guarantee future results. Cryptocurrency trading involves substantial risk of loss. Always test thoroughly in a simulated environment before deploying real capital.

**Not financial advice. Use at your own risk.**

---

## 📄 License

MIT License - See LICENSE file for details

---

<div align="center">

### 🏆 Roostoo Quant Hackathon 2026 Submission

**Built with ❤️ using Python, LightGBM, XGBoost, and Binance API**

[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![LightGBM](https://img.shields.io/badge/lightgbm-3.3+-green.svg)](https://github.com/microsoft/LightGBM)
[![XGBoost](https://img.shields.io/badge/xgboost-1.7+-red.svg)](https://github.com/dmlc/xgboost)

</div>
