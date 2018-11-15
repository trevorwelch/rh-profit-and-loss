import pandas as pd
import requests
import time
import datetime
import numpy as np
import sys
import pytz
import random
import json
import csv
import pandas as pd
pd.options.mode.chained_assignment = None  # default='warn', to silence the errors about copy
import Robinhood


### ORDER HISTORY STUFF ###

def fetch_json_by_url(my_trader, url):
    return my_trader.session.get(url).json()

def get_symbol_from_instrument_url(url, df):

    try:
        symbol = df.loc[url]['symbol']
    
    except Exception as e:
        response = requests.get(url)
        symbol = response.json()['symbol']
        df.at[url, 'symbol'] = symbol
        # time.sleep(np.random.randint(low=0, high=2, size=(1))[0])
   
    return symbol, df


def order_item_info(order, my_trader, df):
    #side: .side,  price: .average_price, shares: .cumulative_quantity, instrument: .instrument, date : .last_transaction_at
    symbol, df = get_symbol_from_instrument_url(order['instrument'], df)
    
    order_info_dict = {
        'side': order['side'],
        'avg_price': order['average_price'],
        'order_price': order['price'],
        'order_quantity': order['quantity'],
        'shares': order['cumulative_quantity'],
        'symbol': symbol,
        'id': order['id'],
        'date': order['last_transaction_at'],
        'state': order['state'],
        'type': order['type']
    }

    return order_info_dict

def get_all_history_orders(my_trader):
    
    orders = []
    past_orders = my_trader.order_history()
    orders.extend(past_orders['results'])

    while past_orders['next']:
        # print("{} order fetched".format(len(orders)))
        next_url = past_orders['next']
        past_orders = fetch_json_by_url(my_trader, next_url)
        orders.extend(past_orders['results'])
    # print("{} order fetched".format(len(orders)))

    return orders

def mark_pending_orders(row):
    if row.state == 'queued' or row.state == 'confirmed':
        order_status_is_pending = True
    else:
        order_status_is_pending = False
    return order_status_is_pending
# df_order_history.apply(mark_pending_orders, axis=1)    

def get_order_history(my_trader):
    
    # Get unfiltered list of order history
    past_orders = get_all_history_orders(my_trader)

    # Load in our pickled database of instrument-url lookups
    instruments_df = pd.read_pickle('symbol_and_instrument_urls')

    # Create a big dict of order history
    orders = [order_item_info(order, my_trader, instruments_df) for order in past_orders]

    # Save our pickled database of instrument-url lookups
    instruments_df.to_pickle('symbol_and_instrument_urls')

    df = pd.DataFrame.from_records(orders)
    df['ticker'] = df['symbol']

    columns = ['ticker', 'state', 'order_quantity', 'shares', 'avg_price', 'date', 'id', 'order_price', 'side', 'symbol', 'type']
    df = df[columns]

    df['is_pending'] = df.apply(mark_pending_orders, axis=1)

    return df, instruments_df

### END ORDER HISTORY GETTING STUFF ####     

### GET CURRENT POSITIONS ###
def get_positions(my_trader):

    open_positions = my_trader.positions()['results']

    what_we_own = {}

    for each in open_positions:

        quantity = int(float(each['quantity']))

        if quantity > 0:

            instruments_df = pd.read_pickle('symbol_and_instrument_urls')

            ticker, _ = get_symbol_from_instrument_url(each['instrument'], instruments_df)

            purchase_price = round(float(each['average_buy_price']), 2)

            total_cost = round(float(purchase_price * quantity), 2)

            asset = {}
            asset['ticker'] = ticker
            asset['quantity'] = quantity
            asset['purchase_price'] = purchase_price
            asset['date_purchased'] = each['updated_at']

            what_we_own[ticker] = asset

    df = pd.DataFrame.from_records(what_we_own).T
    df['ticker'] = df.index
    df = df.reset_index(drop=True)
    df['date_purchased'] = pd.to_datetime(df['date_purchased'])

    return df

def pending_orders(df_order_history):

    df_pending_orders = df_order_history[df_order_history['is_pending'] == True]
    
    df_pending_orders['order_price'] = pd.to_numeric(df_pending_orders['order_price'], errors='coerce')
    df_pending_orders['order_quantity'] = pd.to_numeric(df_pending_orders['order_quantity'], errors='coerce')
    
    df_pending_orders['cost_of_allocation'] = df_pending_orders['order_price']*df_pending_orders['order_quantity']
    
    return df_pending_orders

# Get current prices from RH and return by row
def check_prices(df, my_trader):

    df.index = df.ticker
    
    list_of_tickers_to_check = list(df.ticker)
    print("Checking prices for:", list_of_tickers_to_check)
    
    list_of_tickers_below_entry = []
    
    df['recent_ask_price'] = np.nan
    
    quotes = my_trader.quotes_data(list_of_tickers_to_check)
    
    for index, each in enumerate(quotes):
        df.loc[quotes[index]['symbol'], 'recent_ask_price'] = quotes[index]['ask_price']
        df.loc[quotes[index]['symbol'], 'recent_bid_price'] = quotes[index]['bid_price']
        df.loc[quotes[index]['symbol'], 'recent_last_trade_price'] = quotes[index]['last_trade_price']
        df.loc[quotes[index]['symbol'], 'url'] = quotes[index]['instrument']
    
    df['recent_ask_price'] = pd.to_numeric(df['recent_ask_price'], errors='coerce')
    df['recent_last_trade_price'] = pd.to_numeric(df['recent_last_trade_price'], errors='coerce')
    df['recent_bid_price'] = pd.to_numeric(df['recent_bid_price'], errors='coerce')
    
    return df, quotes

def check_entry_sl_tp(df):    

    def last_trade_price_below_entry(row):

        if row.recent_last_trade_price < 0.1:
            return "No last trade price"
        elif row.entry_price >= row.recent_last_trade_price:
            return True
        else:
            return False

    def ask_price_below_entry(row):
        if row.recent_ask_price < 0.1:
            return "No ask price"
        elif row.entry_price >= row.recent_ask_price:
            return True
        else:
            return False    

    def last_trade_price_below_stop_loss(row):
        
        if row.recent_last_trade_price < 0.1:
            return "No last trade price"
        if row.type_of_trade == 'SHORT':
            if row.stop_loss <= row.recent_last_trade_price:
                return True
            else:
                return False
        else:
            if row.stop_loss >= row.recent_last_trade_price:
                return True
            else:
                return False

    def bid_price_below_stop_loss(row):

        if row.recent_bid_price < 0.1:
            return "No bid price"
        if row.type_of_trade == 'SHORT':
            if row.stop_loss <= row.recent_bid_price:
                return True
            else:
                return False
        else:   
            if row.stop_loss >= row.recent_bid_price:
                return True
            else:
                return False    

    def last_trade_price_above_take_profit(row):

        if row.recent_last_trade_price < 0.1:
            return "No last trade price"
        if row.type_of_trade == 'SHORT':
            if row.take_profit >= row.recent_last_trade_price:
                return True
            else:
                return False
        else:
            if row.take_profit <= row.recent_last_trade_price:
                return True
            else:
                return False

    def bid_price_above_above_take_profit(row):
        
        if row.recent_bid_price < 0.1:
            return "No bid price"
        if row.type_of_trade == 'SHORT': 
            if row.take_profit >= row.recent_bid_price:
                return True
            else:
                return False 
        else: 
            if row.take_profit <= row.recent_bid_price:
                return True
            else:
                return False   

    def stop_loss_hit(row):
        
        if row.last_trade_price_below_stop_loss == True or row.bid_price_below_stop_loss == True:
            return True
        else:
            return False

    def entry_price_hit(row):
        
        if row.last_trade_price_below_entry == True or row.ask_price_below_entry == True:
            return True
        else:
            return False 

    def take_profit_hit(row):
        
        if row.last_trade_price_above_take_profit == True or row.bid_price_above_above_take_profit == True:
            return True
        else:
            return False 

    df['last_trade_price_below_entry'] = df.apply(last_trade_price_below_entry, axis=1)
    df['ask_price_below_entry'] = df.apply(ask_price_below_entry, axis=1)
    df['last_trade_price_below_stop_loss'] = df.apply(last_trade_price_below_stop_loss, axis=1)
    df['bid_price_below_stop_loss'] = df.apply(bid_price_below_stop_loss, axis=1)
    df['last_trade_price_above_take_profit'] = df.apply(last_trade_price_above_take_profit, axis=1)
    df['bid_price_above_above_take_profit'] = df.apply(bid_price_above_above_take_profit, axis=1)
    df['stop_loss_hit'] = df.apply(stop_loss_hit, axis=1)
    df['entry_price_hit'] = df.apply(entry_price_hit, axis=1)
    df['take_profit_hit'] = df.apply(take_profit_hit, axis=1)

    return df

# Check if a ticker is in our positions df
def check_if_ticker_is_owned(ticker, df_positions):
    tickers_owned = list(df_positions.ticker)
    if ticker in tickers_owned:
        return 'owned'
    else:
        return 'not owned'

def check_if_order_pending(ticker, df_pending_orders):
    tickers_pending = list(df_pending_orders.ticker)
    if ticker in tickers_pending:
        return 'pending'
    else:
        return 'not pending'