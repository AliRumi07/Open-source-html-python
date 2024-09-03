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
ema_period_5 = 5
ema_period_15 = 15
rsi_period = 3
rsi_overbought = 70
rsi_oversold = 30

# Add the Pair variable
Pairs = ["BTCUSDT"]

BINANCE_BASE_URL = "https://fapi.binance.com"

app = Flask(__name__)

def calculate_indicators(prices):
    df = pd.DataFrame(prices, columns=['close'])
    df['ema_5'] = ta.ema(df['close'], length=ema_period_5)
    df['ema_15'] = ta.ema(df['close'], length=ema_period_15)
    df['rsi'] = ta.rsi(df['close'], length=rsi_period)
    return df.iloc[-1]

def fetch_historical_data(symbol, interval, limit=14):
    endpoint = f"{BINANCE_BASE_URL}/fapi/v1/klines"
    params = {
        "symbol": symbol,
        "interval": interval,
        "limit": limit
    }
    response = requests.get(endpoint, params=params)
    if response.status_code == 200:
        data = response.json()
        return [float(candle[4]) for candle in data]  # Return closing prices
    else:
        print(f"Failed to fetch historical data: {response.status_code}")
        return []

class TradingStrategy:
    def __init__(self, pairs):
        self.pairs = pairs
        self.close_prices = {pair: deque(maxlen=max(ema_period_15, rsi_period)) for pair in pairs}
        self.last_ema_5 = {pair: None for pair in pairs}
        self.last_ema_15 = {pair: None for pair in pairs}
        self.last_rsi = {pair: None for pair in pairs}
        self.bot_status = "Bot is running..."
        
        # Initialize with historical data
        for pair in pairs:
            historical_prices = fetch_historical_data(pair, Timeframe)
            self.close_prices[pair].extend(historical_prices)
            if len(historical_prices) == 14:
                indicators = calculate_indicators(historical_prices)
                self.last_ema_5[pair] = indicators['ema_5']
                self.last_ema_15[pair] = indicators['ema_15']
                self.last_rsi[pair] = indicators['rsi']

    def process_price(self, pair, timestamp, close_price, is_closed):
        if is_closed:
            self.close_prices[pair].append(close_price)

        if len(self.close_prices[pair]) == max(ema_period_15, rsi_period):
            indicators = calculate_indicators(list(self.close_prices[pair]))
            ema_5 = indicators['ema_5']
            ema_15 = indicators['ema_15']
            rsi = indicators['rsi']

            if self.last_ema_5[pair] is not None and self.last_ema_15[pair] is not None and self.last_rsi[pair] is not None:
                if (self.last_ema_5[pair] <= self.last_ema_15[pair] and ema_5 > ema_15) and rsi > rsi_overbought:
                    self.open_long_position(pair)
                elif (self.last_ema_5[pair] >= self.last_ema_15[pair] and ema_5 < ema_15) and rsi < rsi_oversold:
                    self.open_short_position(pair)

            self.last_ema_5[pair] = ema_5
            self.last_ema_15[pair] = ema_15
            self.last_rsi[pair] = rsi

    def open_long_position(self, pair):
        print(f"Opening long position for {pair}")
        subprocess.run(["python", "btc_long.py"])

    def open_short_position(self, pair):
        print(f"Opening short position for {pair}")
        subprocess.run(["python", "btc_short.py"])

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
    strategy = TradingStrategy(Pairs)
    flask_thread = Thread(target=run_flask)
    flask_thread.start()
    asyncio.get_event_loop().run_until_complete(connect_to_binance_futures())
