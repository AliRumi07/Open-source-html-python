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

# Customizable variables
Timeframe = '1m'
portfolio_balance = 1000
trade_amount = 100
take_profit = 0.002
fee_rate = 0.001
ema_period_5 = 5
ema_period_15 = 15

# Add the Pair variable
Pairs = [ "BTCUSDT" ]

app = Flask(__name__)

def calculate_indicators(prices):
    df = pd.DataFrame(prices, columns=['close'])
    df['ema_5'] = ta.ema(df['close'], length=ema_period_5)
    df['ema_15'] = ta.ema(df['close'], length=ema_period_15)
    return df.iloc[-1]

class TradingStrategy:
    def __init__(self, pairs):
        self.pairs = pairs
        self.positions = {pair: {"Long": False, "Short": False} for pair in pairs}
        self.entry_prices = {pair: {"Long": None, "Short": None} for pair in pairs}
        self.take_profit_prices = {pair: {"Long": None, "Short": None} for pair in pairs}
        self.total_trades = 0
        self.trades_in_profit = 0
        self.total_profit_loss = 0
        self.max_drawdown = 0
        self.lowest_balance = portfolio_balance
        self.close_prices = {pair: deque(maxlen=ema_period_15) for pair in pairs}
        self.candle_data = {pair: deque(maxlen=3) for pair in pairs}  # Store last 3 candles
        self.last_ema_5 = {pair: None for pair in pairs}
        self.last_ema_15 = {pair: None for pair in pairs}

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

    def process_price(self, pair, timestamp, open_price, high_price, low_price, close_price, volume, is_closed):
        self.pair_stats[pair]['Price'] = close_price

        current_pl = 0
        if self.positions[pair]["Long"]:
            current_pl += (close_price - self.entry_prices[pair]["Long"]) / self.entry_prices[pair]["Long"] * trade_amount
        if self.positions[pair]["Short"]:
            current_pl += (self.entry_prices[pair]["Short"] - close_price) / self.entry_prices[pair]["Short"] * trade_amount
        
        current_pl -= (self.positions[pair]["Long"] + self.positions[pair]["Short"]) * trade_amount * fee_rate
        self.pair_stats[pair]['Current P/L'] = current_pl

        if is_closed:
            self.close_prices[pair].append(close_price)
            self.candle_data[pair].append({'open': open_price, 'high': high_price, 'low': low_price, 'close': close_price})

        if len(self.close_prices[pair]) == ema_period_15:
            indicators = calculate_indicators(list(self.close_prices[pair]))
            ema_5 = indicators['ema_5']
            ema_15 = indicators['ema_15']

            if self.last_ema_5[pair] is not None and self.last_ema_15[pair] is not None:
                if self.last_ema_5[pair] <= self.last_ema_15[pair] and ema_5 > ema_15:
                    self.open_long_position(pair, timestamp, close_price)
                elif self.last_ema_5[pair] >= self.last_ema_15[pair] and ema_5 < ema_15:
                    self.open_short_position(pair, timestamp, close_price)

            self.last_ema_5[pair] = ema_5
            self.last_ema_15[pair] = ema_15

            self.check_take_profit(pair, timestamp, close_price)

        self.update_max_drawdown()
        self.update_stats(pair, close_price)

    def open_long_position(self, pair, timestamp, price):
        if not self.positions[pair]["Long"]:
            self.positions[pair]["Long"] = True
            self.entry_prices[pair]["Long"] = price
            self.take_profit_prices[pair]["Long"] = price * (1 + take_profit)
            self.pair_stats[pair]['Longs'] += 1
            self.pair_stats[pair]['Hedge'] += 1
            self.update_stats(pair, price)
            subprocess.run(["python", "btc_long.py"])

    def open_short_position(self, pair, timestamp, price):
        if not self.positions[pair]["Short"]:
            self.positions[pair]["Short"] = True
            self.entry_prices[pair]["Short"] = price
            self.take_profit_prices[pair]["Short"] = price * (1 - take_profit)
            self.pair_stats[pair]['Shorts'] += 1
            self.pair_stats[pair]['Hedge'] += 1
            self.update_stats(pair, price)
            subprocess.run(["python", "btc_short.py"])

    def check_take_profit(self, pair, timestamp, current_price):
        if self.positions[pair]["Long"] and current_price >= self.take_profit_prices[pair]["Long"]:
            self.close_position(pair, timestamp, current_price, "Long")
        if self.positions[pair]["Short"] and current_price <= self.take_profit_prices[pair]["Short"]:
            self.close_position(pair, timestamp, current_price, "Short")

    def close_position(self, pair, timestamp, exit_price, position_type):
        self.total_trades += 1
        self.trades_in_profit += 1
        self.pair_stats[pair]['In Profit'] += 1

        if position_type == "Long":
            profit_loss = (exit_price - self.entry_prices[pair]["Long"]) / self.entry_prices[pair]["Long"] * trade_amount
        else:
            profit_loss = (self.entry_prices[pair]["Short"] - exit_price) / self.entry_prices[pair]["Short"] * trade_amount

        profit_loss -= trade_amount * fee_rate
        self.total_profit_loss += profit_loss
        self.pair_stats[pair]['Total P/L'] += profit_loss

        self.positions[pair][position_type] = False
        self.entry_prices[pair][position_type] = None
        self.take_profit_prices[pair][position_type] = None
        self.pair_stats[pair]['Hedge'] -= 1
        self.update_stats(pair, exit_price)

    def update_max_drawdown(self):
        current_balance = portfolio_balance + self.total_profit_loss
        drawdown = (portfolio_balance - current_balance) / portfolio_balance
        self.max_drawdown = max(self.max_drawdown, drawdown)
        self.lowest_balance = min(self.lowest_balance, current_balance)

    def update_stats(self, pair, current_price):
        self.pair_stats[pair]['Price'] = current_price

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
    is_closed = candle['x']

    strategy.process_price(pair, open_time, open_price, high_price, low_price, close_price, volume, is_closed)

def run_flask():
    app.run(host='0.0.0.0', port=8080)

if __name__ == "__main__":
    flask_thread = Thread(target=run_flask)
    flask_thread.start()
    asyncio.get_event_loop().run_until_complete(connect_to_binance_futures())
