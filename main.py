from datetime import datetime
from collections import deque
import asyncio
import websockets
import json
from flask import Flask, render_template_string
from threading import Thread
import time

# Customizable variables
portfolio_balance = 1000
trade_amount = 100
fee_rate = 0.001

# Add the Pair variable
Pairs = ["BTCUSDT"]

app = Flask(__name__)

class TradingStrategy:
    def __init__(self, pairs):
        self.pairs = pairs
        self.positions = {pair: None for pair in pairs}
        self.entry_prices = {pair: None for pair in pairs}
        self.take_profit_prices = {pair: None for pair in pairs}
        self.total_trades = 0
        self.trades_in_profit = 0
        self.total_profit_loss = 0
        self.max_drawdown = 0
        self.lowest_balance = portfolio_balance
        self.last_price = {pair: None for pair in pairs}
        self.next_long_price = {pair: None for pair in pairs}
        self.next_short_price = {pair: None for pair in pairs}

        self.pair_stats = {pair: {
            'Price': 0,
            'Position': 'None',
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

    def process_price(self, pair, timestamp, price):
        self.pair_stats[pair]['Price'] = price

        if self.last_price[pair] is None:
            self.last_price[pair] = price
            self.next_long_price[pair] = price - 100
            self.next_short_price[pair] = price + 100

        if self.positions[pair] is not None:
            if self.positions[pair] == "Long":
                current_pl = (price - self.entry_prices[pair]) * (trade_amount / self.entry_prices[pair])
            else:
                current_pl = (self.entry_prices[pair] - price) * (trade_amount / self.entry_prices[pair])
            current_pl -= trade_amount * fee_rate
            self.pair_stats[pair]['Current P/L'] = current_pl
        else:
            self.pair_stats[pair]['Current P/L'] = 0

        if self.positions[pair] is None:
            if price <= self.next_long_price[pair]:
                self.open_long_position(pair, timestamp, price)
            elif price >= self.next_short_price[pair]:
                self.open_short_position(pair, timestamp, price)
        else:
            self.check_exit_conditions(pair, timestamp, price)

        self.last_price[pair] = price

    def open_long_position(self, pair, timestamp, price):
        self.positions[pair] = "Long"
        self.entry_prices[pair] = price
        self.take_profit_prices[pair] = price + 100
        self.pair_stats[pair]['Longs'] += 1
        self.update_stats(pair, price)

    def open_short_position(self, pair, timestamp, price):
        self.positions[pair] = "Short"
        self.entry_prices[pair] = price
        self.take_profit_prices[pair] = price - 100
        self.pair_stats[pair]['Shorts'] += 1
        self.update_stats(pair, price)

    def check_exit_conditions(self, pair, timestamp, price):
        if self.positions[pair] == "Long":
            if price >= self.take_profit_prices[pair]:
                self.close_position(pair, timestamp, self.take_profit_prices[pair], True)
        elif self.positions[pair] == "Short":
            if price <= self.take_profit_prices[pair]:
                self.close_position(pair, timestamp, self.take_profit_prices[pair], True)

    def close_position(self, pair, timestamp, exit_price, is_profit):
        self.total_trades += 1

        if is_profit:
            self.trades_in_profit += 1
            self.pair_stats[pair]['In Profit'] += 1

        if self.positions[pair] == "Long":
            profit_loss = (exit_price - self.entry_prices[pair]) * (trade_amount / self.entry_prices[pair])
        else:
            profit_loss = (self.entry_prices[pair] - exit_price) * (trade_amount / self.entry_prices[pair])

        profit_loss -= trade_amount * fee_rate
        self.total_profit_loss += profit_loss
        self.pair_stats[pair]['Total P/L'] += profit_loss

        current_balance = portfolio_balance + self.total_profit_loss
        drawdown = (portfolio_balance - current_balance) / portfolio_balance
        self.max_drawdown = max(self.max_drawdown, drawdown)
        self.lowest_balance = min(self.lowest_balance, current_balance)

        self.positions[pair] = None
        self.entry_prices[pair] = None
        self.take_profit_prices[pair] = None
        self.next_long_price[pair] = exit_price - 100
        self.next_short_price[pair] = exit_price + 100
        self.update_stats(pair, exit_price)

    def update_stats(self, pair, current_price):
        self.pair_stats[pair]['Price'] = current_price
        self.pair_stats[pair]['Position'] = self.positions[pair] or 'None'

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
                <th>Position</th>
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
                <td>{{ stats['Position'] }}</td>
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
    uri = f"wss://fstream.binance.com/stream?streams={'/'.join([pair.lower() + '@aggTrade' for pair in Pairs])}"

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
    
    timestamp = datetime.fromtimestamp(data['T'] / 1000)
    price = float(data['p'])

    strategy.process_price(pair, timestamp, price)

def run_flask():
    app.run(host='0.0.0.0', port=8080)

if __name__ == "__main__":
    flask_thread = Thread(target=run_flask)
    flask_thread.start()
    asyncio.get_event_loop().run_until_complete(connect_to_binance_futures())
