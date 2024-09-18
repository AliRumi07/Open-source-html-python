import numpy as np
import pandas as pd
import pandas_ta as ta
from datetime import datetime
import asyncio
import websockets
import json
from flask import Flask, render_template_string
from threading import Thread
import subprocess
import requests

# Customizable variables
Timeframe = '1m'
williams_period = 14
williams_threshold = -50

# Add the Pair variable
Pairs = ["BTCUSDT"]

app = Flask(__name__)

def calculate_indicators(data):
    df = pd.DataFrame(data, columns=['high', 'low', 'close'])
    df['williams_r'] = ta.willr(df['high'], df['low'], df['close'], length=williams_period)
    return df.iloc[-1]

class TradingStrategy:
    def __init__(self, pairs):
        self.pairs = pairs
        self.price_data = {pair: [] for pair in pairs}
        self.bot_status = "Bot is running..."
        self.previous_williams_r = {pair: None for pair in pairs}

    def run_bnb_long(self):
        try:
            subprocess.Popen(["python", "btc_long.py"])
            print("Running btc_long.py")
        except Exception as e:
            print(f"Error running btc_long.py: {e}")

    def run_bnb_short(self):
        try:
            subprocess.Popen(["python", "btc_short.py"])
            print("Running btc_short.py")
        except Exception as e:
            print(f"Error running btc_short.py: {e}")

    def process_price(self, pair, timestamp, open_price, high_price, low_price, close_price, volume, is_closed):
        if is_closed:
            self.price_data[pair].append([high_price, low_price, close_price])
            if len(self.price_data[pair]) > williams_period:
                self.price_data[pair] = self.price_data[pair][-williams_period:]

            if len(self.price_data[pair]) == williams_period:
                indicators = calculate_indicators(self.price_data[pair])
                williams_r = indicators['williams_r']

                if self.previous_williams_r[pair] is not None:
                    if self.check_long_entry(williams_r):
                        self.run_bnb_long()
                    elif self.check_short_entry(williams_r):
                        self.run_bnb_short()

                self.previous_williams_r[pair] = williams_r

    def check_long_entry(self, williams_r):
        return self.previous_williams_r[Pairs[0]] <= williams_threshold and williams_r > williams_threshold

    def check_short_entry(self, williams_r):
        return self.previous_williams_r[Pairs[0]] >= williams_threshold and williams_r < williams_threshold

strategy = TradingStrategy(Pairs)

@app.route('/')
def index():
    template = '''
    <!DOCTYPE html>
    <html>
    <head>
        <title>Trading Bot Status</title>
        <style>
            body { font-family: Arial, sans-serif; text-align: center; padding-top: 50px; }
            .status { font-size: 24px; font-weight: bold; }
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

def get_historical_klines(symbol, interval, limit=14):
    url = f"https://fapi.binance.com/fapi/v1/klines"
    params = {
        "symbol": symbol,
        "interval": interval,
        "limit": limit
    }
    response = requests.get(url, params=params)
    if response.status_code == 200:
        return response.json()
    else:
        print(f"Error fetching historical data: {response.status_code}")
        return None

async def connect_to_binance_futures():
    uri = f"wss://fstream.binance.com/stream?streams={'/'.join([pair.lower() + '@kline_' + Timeframe for pair in Pairs])}"

    # Fetch historical data before connecting to WebSocket
    for pair in Pairs:
        historical_data = get_historical_klines(pair, Timeframe)
        if historical_data:
            for kline in historical_data:
                high_price = float(kline[2])
                low_price = float(kline[3])
                close_price = float(kline[4])
                strategy.price_data[pair].append([high_price, low_price, close_price])
            print(f"Fetched {len(historical_data)} historical data points for {pair}")

    async with websockets.connect(uri) as websocket:
        print("Connected to Binance Futures WebSocket")

        while True:
            message = await websocket.recv()
            process_message(json.loads(message))

def process_message(message):
    stream = message['stream']
    pair = stream.split('@')[0].upper()
    data = message['data']
    candle = data['k']

    open_time = datetime.fromtimestamp(candle['t'] / 1000)
    open_price = float(candle['o'])
    high_price = float(candle['h'])
    low_price = float(candle['l'])
    close_price = float(candle['c'])
    volume = float(candle['v'])
    is_closed = candle['x']

    strategy.process_price(pair, open_time, open_price, high_price, low_price, close_price, volume, is_closed)

def run_flask():
    app.run(host='0.0.0.0', port=8080)

if __name__ == "__main__":
    flask_thread = Thread(target=run_flask)
    flask_thread.start()
    asyncio.get_event_loop().run_until_complete(connect_to_binance_futures())
