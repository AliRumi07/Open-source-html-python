import time
import requests
import hmac
import base64
import json
import asyncio
import websockets

# Customizable variables
api_key = "bg_d122aaf7588fbf0ef65a61e648809622"
secret_key = "cf70a251b36ffd63bcda028682c43091502afb4dee270e8000f3754147fa533a"
passphrase = "strongPASSWORD1"

base_url = "https://api.bitget.com"
place_order_endpoint = "/api/v2/mix/order/place-order"
tpsl_order_endpoint = "/api/v2/mix/order/place-tpsl-order"

symbol = "SBTCSUSDT"  # You can change this to "SETHSUSDT" or "SXRPSUSDT"
product_type = "usdt-futures"
margin_coin = "SUSDT"
size = "0.001"  # trade size
leverage = "1"  # leverage
side = "sell"  # Change to "sell" for a sell order
trade_side = "open"
order_type = "market"

ws_uri = "wss://ws.bitget.com/mix/v1/stream"

price_precision = {
    "SBTCSUSDT": 1,
    "SETHSUSDT": 1,
    "SXRPSUSDT": 3,
    # Add more pairs and their respective precisions here
}

tp_percentage = 0.003  # 0.3%
sl_percentage = 0.003  # 0.3%

async def get_symbol_price(symbol):
    async with websockets.connect(ws_uri) as websocket:
        # Subscribe to the symbol ticker
        subscribe_message = {
            "op": "subscribe",
            "args": [
                {
                    "instType": "mc",
                    "channel": "ticker",
                    "instId": symbol
                }
            ]
        }
        await websocket.send(json.dumps(subscribe_message))

        while True:
            response = await websocket.recv()
            data = json.loads(response)

            if 'data' in data:
                price = float(data['data'][0]['last'])
                return price

async def main():
    current_price = await get_symbol_price(symbol)

    # Calculate TP and SL prices based on side
    if side == "buy":
        tp_price = current_price * (1 + tp_percentage)
        sl_price = current_price * (1 - sl_percentage)
        hold_side = "long"
    elif side == "sell":
        tp_price = current_price * (1 - tp_percentage)
        sl_price = current_price * (1 + sl_percentage)
        hold_side = "short"
    else:
        raise ValueError("Invalid side. Must be 'buy' or 'sell'.")

    # Round prices according to the price precision
    precision = price_precision.get(symbol, 2)  # Default to 2 decimal places if not found
    tp_price = round(tp_price, precision)
    sl_price = round(sl_price, precision)

    # Generate timestamp
    timestamp = str(int(time.time() * 1000))

    # Prepare the request body for placing an order
    place_order_body = {
        "symbol": symbol,
        "productType": product_type,
        "marginMode": "crossed",
        "marginCoin": margin_coin,
        "size": size,
        "side": side,
        "tradeSide": trade_side,
        "orderType": order_type,
        "clientOid": f"demo_trade_{timestamp}"
    }

    # Convert body to JSON string
    place_order_body_str = json.dumps(place_order_body)

    # Generate the signature for placing an order
    place_order_message = timestamp + "POST" + place_order_endpoint + place_order_body_str
    place_order_signature = base64.b64encode(hmac.new(secret_key.encode('utf-8'), place_order_message.encode('utf-8'), digestmod='sha256').digest()).decode('utf-8')

    # Prepare headers
    headers = {
        "ACCESS-KEY": api_key,
        "ACCESS-SIGN": place_order_signature,
        "ACCESS-TIMESTAMP": timestamp,
        "ACCESS-PASSPHRASE": passphrase,
        "Content-Type": "application/json",
        "locale": "en-US"
    }

    # Send the request to place the order
    place_order_response = requests.post(base_url + place_order_endpoint, headers=headers, data=place_order_body_str)

    # Prepare the request body for the TPSL order
    tpsl_order_body_profit = {
        "marginCoin": margin_coin,
        "productType": product_type,
        "symbol": symbol,
        "planType": "profit_plan",
        "triggerPrice": str(tp_price),
        "triggerType": "mark_price",
        "executePrice": "0",
        "holdSide": hold_side,
        "size": size,
        "clientOid": f"tp_trade_{timestamp}"
    }

    # Convert body to JSON string
    tpsl_order_body_profit_str = json.dumps(tpsl_order_body_profit)

    # Generate a new timestamp for the TPSL order
    timestamp = str(int(time.time() * 1000))

    # Generate the signature for the take profit order
    tpsl_order_message_profit = timestamp + "POST" + tpsl_order_endpoint + tpsl_order_body_profit_str
    tpsl_order_signature_profit = base64.b64encode(hmac.new(secret_key.encode('utf-8'), tpsl_order_message_profit.encode('utf-8'), digestmod='sha256').digest()).decode('utf-8')

    # Update headers with new signature and timestamp
    headers["ACCESS-SIGN"] = tpsl_order_signature_profit
    headers["ACCESS-TIMESTAMP"] = timestamp

    # Send the request to place the take profit order
    tpsl_order_response_profit = requests.post(base_url + tpsl_order_endpoint, headers=headers, data=tpsl_order_body_profit_str)

    # Prepare the request body for the stop loss order
    tpsl_order_body_loss = {
        "marginCoin": margin_coin,
        "productType": product_type,
        "symbol": symbol,
        "planType": "loss_plan",
        "triggerPrice": str(sl_price),
        "triggerType": "mark_price",
        "executePrice": "0",
        "holdSide": hold_side,
        "size": size,
        "clientOid": f"sl_trade_{timestamp}"
    }

    # Convert body to JSON string
    tpsl_order_body_loss_str = json.dumps(tpsl_order_body_loss)

    # Generate a new timestamp for the stop loss order
    timestamp = str(int(time.time() * 1000))

    # Generate the signature for the stop loss order
    tpsl_order_message_loss = timestamp + "POST" + tpsl_order_endpoint + tpsl_order_body_loss_str
    tpsl_order_signature_loss = base64.b64encode(hmac.new(secret_key.encode('utf-8'), tpsl_order_message_loss.encode('utf-8'), digestmod='sha256').digest()).decode('utf-8')

    # Update headers with new signature and timestamp
    headers["ACCESS-SIGN"] = tpsl_order_signature_loss
    headers["ACCESS-TIMESTAMP"] = timestamp

    # Send the request to place the stop loss order
    tpsl_order_response_loss = requests.post(base_url + tpsl_order_endpoint, headers=headers, data=tpsl_order_body_loss_str)

if __name__ == "__main__":
    asyncio.run(main())
