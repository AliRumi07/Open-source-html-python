import numpy as np
import pandas as pd
import pandas_ta as ta
from datetime import datetime
from collections import deque
import asyncio
import websockets
import json
from flask import Flask, render_template_string
from threading import Thread
import time
import subprocess
import requests

# Customizable variables
Timeframe = '1m'
ema_period_10 = 10
ema_period_20 = 20
rsi_period = 14
bb_period = 20
bb_std = 2

# Add the Pair variable
Pairs = ["BTCUSDT"]

app = Flask(__name__)

def calculate_indicators(prices):
    df = pd.DataFrame(prices, columns=['close'])
    df['ema_10'] = ta.ema(df['close'], length=ema_period_10)
    df['ema_20'] = ta.ema(df['close'], length=ema_period_20)
    df['rsi'] = ta.rsi(df['close'], length=rsi_period)
    bb = ta.bbands(df['close'], length=bb_period, std=bb_std)
    df['bb_lower'] = bb['BBL_20_2.0']
    df['bb_upper'] = bb['BBU_20_2.0']
    return df.iloc[-1]

def get_historical_data(symbol, interval, limit=20):
    base_url = "https://fapi.binance.com/fapi/v1/klines"
    params = {
        "symbol": symbol,
        "interval": interval,
        "limit": limit
    }
    response = requests.get(base_url, params=params)
    data = response.json()
    
    df = pd.DataFrame(data, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume', 'close_time', 'quote_asset_volume', 'number_of_trades', 'taker_buy_base_asset_volume', 'taker_buy_quote_asset_volume', 'ignore'])
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
    df['close'] = df['close'].astype(float)
    return df[['timestamp', 'close']]

class TradingStrategy:
    def __init__(self, pairs):
        self.pairs = pairs
        self.close_prices = {pair: deque(maxlen=100) for pair in pairs}
        self.last_ema_10 = {pair: None for pair in pairs}
        self.last_ema_20 = {pair: None for pair in pairs}
        self.bot_status = "Bot is running..."
        
        # Initialize with historical data
        for pair in pairs:
            historical_data = get_historical_data(pair, Timeframe)
            self.close_prices[pair].extend(historical_data['close'].tolist())
            
            if len(self.close_prices[pair]) == 100:
                indicators = calculate_indicators(list(self.close_prices[pair]))
                self.last_ema_10[pair] = indicators['ema_10']
                self.last_ema_20[pair] = indicators['ema_20']

    def process_price(self, pair, timestamp, close_price, is_closed):
        if is_closed:
            self.close_prices[pair].append(close_price)

        if len(self.close_prices[pair]) == 100:
            indicators = calculate_indicators(list(self.close_prices[pair]))
            ema_10 = indicators['ema_10']
            ema_20 = indicators['ema_20']
            rsi = indicators['rsi']
            bb_lower = indicators['bb_lower']
            bb_upper = indicators['bb_upper']

            if self.last_ema_10[pair] is not None and self.last_ema_20[pair] is not None:
                if (self.last_ema_10[pair] <= self.last_ema_20[pair] and ema_10 > ema_20 and
                    40 <= rsi <= 60 and close_price <= bb_lower):
                    self.open_long_position(pair)
                elif (self.last_ema_10[pair] >= self.last_ema_20[pair] and ema_10 < ema_20 and
                      40 <= rsi <= 60 and close_price >= bb_upper):
                    self.open_short_position(pair)

            self.last_ema_10[pair] = ema_10
            self.last_ema_20[pair] = ema_20

    def open_long_position(self, pair):
        print(f"Opening long position for {pair}")
        subprocess.run(["python", "btc_long.py"])

    def open_short_position(self, pair):
        print(f"Opening short position for {pair}")
        subprocess.run(["python", "btc_short.py"])

strategy = TradingStrategy(Pairs)

@app.route('/')
def index():
    template = '''
    <!DOCTYPE html>
    <html>
    <head>
        <title>Trading Bot Status</title>
        <style>
            body { font-family: Arial, sans-serif; display: flex; justify-content: center; align-items: center; height: 100vh; margin: 0; }
            .status { font-size: 24px; padding: 20px; border: 1px solid #ccc; border-radius: 5px; }
        </style>
        <script>
            function refreshPage() {
                location.reload();
            }
            setInterval(refreshPage, 5000);
        </script>
    </head>
    <body>
        <div class="status">{{ bot_status }}</div>
    </body>
    </html>
    '''
    return render_template_string(template, bot_status=strategy.bot_status)

async def connect_to_binance_futures():
    uri = f"wss://fstream.binance.com/stream?streams={'/'.join([pair.lower() + '@kline_' + Timeframe for pair in Pairs])}"

    async with websockets.connect(uri) as websocket:
        print("Connected to Binance Futures WebSocket")

        last_ping_time = time.time()

        while True:
            try:
                message = await asyncio.wait_for(websocket.recv(), timeout=1)
                process_message(json.loads(message))

                current_time = time.time()
                if current_time - last_ping_time > 60:
                    await websocket.ping()
                    last_ping_time = current_time
                    print("Ping sent to keep connection alive")

            except asyncio.TimeoutError:
                current_time = time.time()
                if current_time - last_ping_time > 60:
                    await websocket.ping()
                    last_ping_time = current_time
                    print("Ping sent to keep connection alive")

            except websockets.exceptions.ConnectionClosed:
                print("WebSocket connection closed. Attempting to reconnect...")
                strategy.bot_status = "Bot is not running. Attempting to reconnect..."
                break

    await asyncio.sleep(5)
    await connect_to_binance_futures()

def process_message(message):
    stream = message['stream']
    pair = stream.split('@')[0].upper()
    data = message['data']
    candle = data['k']

    open_time = datetime.fromtimestamp(candle['t'] / 1000)
    close_price = float(candle['c'])
    is_closed = candle['x']

    strategy.process_price(pair, open_time, close_price, is_closed)

def run_flask():
    app.run(host='0.0.0.0', port=8080)

if __name__ == "__main__":
    flask_thread = Thread(target=run_flask)
    flask_thread.start()
    asyncio.get_event_loop().run_until_complete(connect_to_binance_futures())
