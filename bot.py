import alpaca_trade_api as tradeapi
import pandas as pd
import time
import os
from datetime import datetime

# ── Configuración ──────────────────────────────────────────────────
API_KEY    = os.environ.get("ALPACA_API_KEY")
API_SECRET = os.environ.get("ALPACA_API_SECRET")
BASE_URL   = "https://paper-api.alpaca.markets"

SYMBOL     = "BTC/USD"
TIMEFRAME  = "4Hour"
RISK_PCT   = 0.02   # 2% de riesgo por operación
LOOKBACK   = 5      # velas para calcular el stop

api = tradeapi.REST(API_KEY, API_SECRET, BASE_URL, api_version='v2')

# ── Funciones ──────────────────────────────────────────────────────
def get_bars():
    bars = api.get_crypto_bars(SYMBOL, tradeapi.rest.TimeFrame.Hour4, limit=60).df
    bars = bars[bars.index.get_level_values('symbol') == 'BTC/USD']
    bars.index = bars.index.get_level_values('timestamp')
    return bars

def calcular_emas(bars):
    bars['ema10'] = bars['close'].ewm(span=10, adjust=False).mean()
    bars['ema20'] = bars['close'].ewm(span=20, adjust=False).mean()
    bars['ema50'] = bars['close'].ewm(span=50, adjust=False).mean()
    return bars

def hay_senal(bars):
    prev = bars.iloc[-2]
    curr = bars.iloc[-1]
    # Cruce EMA10 sobre EMA20 + precio sobre EMA50
    cruce = prev['ema10'] < prev['ema20'] and curr['ema10'] > curr['ema20']
    tendencia = curr['close'] > curr['ema50']
    return cruce and tendencia

def calcular_stops(bars, entry_price):
    lowest_low = bars['low'].iloc[-LOOKBACK:].min()
    stop_loss  = lowest_low
    take_profit = entry_price + 2 * (entry_price - stop_loss)
    return round(stop_loss, 2), round(take_profit, 2)

def en_posicion():
    try:
        pos = api.get_position('BTCUSD')
        return float(pos.qty) > 0
    except:
        return False

def ejecutar_orden(entry_price, stop_loss, take_profit):
    cuenta = api.get_account()
    capital = float(cuenta.cash)
    riesgo_usd = capital * RISK_PCT
    qty = round(riesgo_usd / (entry_price - stop_loss), 6)
    
    print(f"[{datetime.now()}] ENTRADA — Precio: {entry_price} | Stop: {stop_loss} | TP: {take_profit} | Qty: {qty}")
    
    api.submit_order(
        symbol=SYMBOL,
        qty=qty,
        side='buy',
        type='market',
        time_in_force='gtc'
    )
    # Stop loss
    api.submit_order(
        symbol=SYMBOL,
        qty=qty,
        side='sell',
        type='stop',
        stop_price=stop_loss,
        time_in_force='gtc'
    )
    # Take profit
    api.submit_order(
        symbol=SYMBOL,
        qty=qty,
        side='sell',
        type='limit',
        limit_price=take_profit,
        time_in_force='gtc'
    )

# ── Loop principal ─────────────────────────────────────────────────
print("Bot iniciado...")
while True:
    try:
        bars = get_bars()
        bars = calcular_emas(bars)
        
        if not en_posicion():
            if hay_senal(bars):
                entry = bars['close'].iloc[-1]
                sl, tp = calcular_stops(bars, entry)
                ejecutar_orden(entry, sl, tp)
            else:
                print(f"[{datetime.now()}] Sin señal. Esperando...")
        else:
            print(f"[{datetime.now()}] En posición. Monitoreando...")
        
        time.sleep(60 * 60 * 4)  # espera 4 horas
        
    except Exception as e:
        print(f"[{datetime.now()}] Error: {e}")
        time.sleep(60)
