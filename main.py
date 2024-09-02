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

# Customizable variables
portfolio_balance = 100
trade_amount = 10
fee_rate = 0.001
ema_period_5 = 5
ema_period_15 = 15

# Add the Pair variable
Pairs = [
    "BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "XRPUSDT", "DOGEUSDT", "TONUSDT", "ADAUSDT", "TRXUSDT", "AVAXUSDT"
]

app = Flask(__name__)

def calculate_indicators(prices):
    df = pd.DataFrame(prices, columns=['close'])
    df['ema_5'] = ta.ema(df['close'], length=ema_period_5)
    df['ema_15'] = ta.ema(df['close'], length=ema_period_15)
    return df.iloc[-1]

class TradingStrategy:
    def __init__(self, pairs):
        self.pairs = pairs
        self.positions = {pair: {'Long': False, 'Short': False} for pair in pairs}
        self.entry_prices = {pair: {'Long': None, 'Short': None} for pair in pairs}
        self.total_trades = 0
        self.trades_in_profit = 0
        self.total_profit_loss = 0
        self.max_drawdown = 0
        self.lowest_balance = portfolio_balance
        self.close_prices = {pair: deque(maxlen=ema_period_15) for pair in pairs}
        self.prev_ema_5 = {pair: None for pair in pairs}
        self.prev_ema_15 = {pair: None for pair in pairs}

        self.pair_stats = {pair: {
            'Price': 0,
            'Hedge': 0,
            'Longs': 0,
            'Shorts': 0,
            'In Profit': 0,
            'Total P/L': 0,
            'Current P/L': 0
        } for pair in pairs}

        self.overall_stats = {
            'Total P/L': 0,
            'Portfolio Balance': portfolio_balance,
            'Total Trades': 0,
            'Trades in Profit': 0,
            'Accuracy': 0,
            'Max Drawdown': 0
        }

    def process_price(self, pair, timestamp, open_price, high_price, low_price, close_price, volume):
        self.pair_stats[pair]['Price'] = close_price
        self.close_prices[pair].append(close_price)

        if len(self.close_prices[pair]) == ema_period_15:
            indicators = calculate_indicators(list(self.close_prices[pair]))
            ema_5 = indicators['ema_5']
            ema_15 = indicators['ema_15']

            if self.prev_ema_5[pair] is not None and self.prev_ema_15[pair] is not None:
                if self.prev_ema_5[pair] <= self.prev_ema_15[pair] and ema_5 > ema_15:
                    self.open_long_position(pair, timestamp, close_price)
                elif self.prev_ema_5[pair] >= self.prev_ema_15[pair] and ema_5 < ema_15:
                    self.open_short_position(pair, timestamp, close_price)

            self.prev_ema_5[pair] = ema_5
            self.prev_ema_15[pair] = ema_15

        self.update_current_pl(pair, close_price)

    def open_long_position(self, pair, timestamp, price):
        if not self.positions[pair]['Long']:
            self.positions[pair]['Long'] = True
            self.entry_prices[pair]['Long'] = price
            self.pair_stats[pair]['Longs'] += 1
            self.update_stats(pair, price)

    def open_short_position(self, pair, timestamp, price):
        if not self.positions[pair]['Short']:
            self.positions[pair]['Short'] = True
            self.entry_prices[pair]['Short'] = price
            self.pair_stats[pair]['Shorts'] += 1
            self.update_stats(pair, price)

    def update_current_pl(self, pair, current_price):
        total_pl = 0
        if self.positions[pair]['Long']:
            long_pl = (current_price - self.entry_prices[pair]['Long']) / self.entry_prices[pair]['Long'] * trade_amount
            total_pl += long_pl
        if self.positions[pair]['Short']:
            short_pl = (self.entry_prices[pair]['Short'] - current_price) / self.entry_prices[pair]['Short'] * trade_amount
            total_pl += short_pl

        total_pl -= trade_amount * fee_rate * (self.positions[pair]['Long'] + self.positions[pair]['Short'])
        self.pair_stats[pair]['Current P/L'] = total_pl

    def update_stats(self, pair, current_price):
        self.pair_stats[pair]['Price'] = current_price
        self.pair_stats[pair]['Hedge'] = sum(self.positions[pair].values())

        self.overall_stats['Total P/L'] = self.total_profit_loss
        self.overall_stats['Portfolio Balance'] = portfolio_balance + self.total_profit_loss
        self.overall_stats['Total Trades'] = self.total_trades
        self.overall_stats['Trades in Profit'] = self.trades_in_profit
        self.overall_stats['Accuracy'] = (self.trades_in_profit / self.total_trades) * 100 if self.total_trades > 0 else 0
        self.overall_stats['Max Drawdown'] = self.max_drawdown * 100

strategy = TradingStrategy(Pairs)

@app.route('/')
def index():
    template = '''
    <!DOCTYPE html>
    <html>
    <head>
        <title>Trading Strategy Stats</title>
        <style>
            table { border-collapse: collapse; width: 100%; margin-bottom: 20px; }
            th, td { border: 1px solid black; padding: 8px; text-align: left; }
            th { background-color: #f2f2f2; }
            .positive { color: green; }
            .negative { color: red; }
        </style>
        <script>
            function refreshPage() {
                location.reload();
            }
            setInterval(refreshPage, 1000);
        </script>
    </head>
    <body>
        <h1>Pair Stats</h1>
        <table>
            <tr>
                <th>Pair</th>
                <th>Price</th>
                <th>Hedge</th>
                <th>Longs</th>
                <th>Shorts</th>
                <th>In Profit</th>
                <th>Total P/L</th>
                <th>Current P/L</th>
            </tr>
            {% for pair, stats in pair_stats.items() %}
            <tr>
                <td>{{ pair }}</td>
                <td>${{ "%.2f"|format(stats['Price']) }}</td>
                <td>{{ stats['Hedge'] }}</td>
                <td>{{ stats['Longs'] }}</td>
                <td>{{ stats['Shorts'] }}</td>
                <td>{{ stats['In Profit'] }}</td>
                <td>${{ "%.2f"|format(stats['Total P/L']) }}</td>
                <td class="{{ 'positive' if stats['Current P/L'] > 0 else 'negative' if stats['Current P/L'] < 0 else '' }}">
                    ${{ "%.2f"|format(stats['Current P/L']) }}
                </td>
            </tr>
            {% endfor %}
        </table>

        <h1>Overall Stats</h1>
        <table>
            <tr>
                <th>Metric</th>
                <th>Value</th>
            </tr>
            {% for metric, value in overall_stats.items() %}
            <tr>
                <td>{{ metric }}</td>
                <td>
                    {% if metric in ['Total P/L', 'Portfolio Balance'] %}
                        ${{ "%.2f"|format(value) }}
                    {% elif metric in ['Accuracy', 'Max Drawdown'] %}
                        {{ "%.2f"|format(value) }}%
                    {% else %}
                        {{ value }}
                    {% endif %}
                </td>
            </tr>
            {% endfor %}
        </table>
    </body>
    </html>
    '''
    return render_template_string(template, pair_stats=strategy.pair_stats, overall_stats=strategy.overall_stats)

async def connect_to_binance_futures():
    uri = f"wss://fstream.binance.com/stream?streams={'/'.join([pair.lower() + '@kline_1m' for pair in Pairs])}"

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
                break

    await asyncio.sleep(5)
    await connect_to_binance_futures()

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

    strategy.process_price(pair, open_time, open_price, high_price, low_price, close_price, volume)

def run_flask():
    app.run(host='0.0.0.0', port=8080)

if __name__ == "__main__":
    flask_thread = Thread(target=run_flask)
    flask_thread.start()
    asyncio.get_event_loop().run_until_complete(connect_to_binance_futures())
