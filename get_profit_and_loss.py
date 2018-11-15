import csv
import os
import numpy as np
import sys
import json
import pandas as pd
import requests
import operator
import TW_robinhood_scripts as rh
import Robinhood

def rh_profit_and_loss(username=None, password=None, starting_equity=5000, start_date=None, end_date=None, csv_export=1, buy_and_hold=0, pickle=0):

    class Order:
        def __init__(self, side, symbol, shares, price, date, state):
            self.side = side
            self.symbol = symbol
            self.shares = float(shares)
            self.price = float(price)
            self.date = date
            self.state = state
        
        def pl(self):
            if self.side == 'buy':
                return -1 * int(self.shares) * float(self.price)
            else:
                return int(self.shares) * float(self.price)

    class Stock:
        def __init__(self, symbol):
            self.symbol = symbol
            self.orders = []
            self.net_shares = 0
            self.net_pl = 0


    def itemize_stocks():
        
        # Create list for each stock
        stocks = {}
        with open('orders.csv', 'r') as csvfile:
            lines = csv.reader(csvfile, delimiter=',')
            for line in lines:
                
                ticker = line[1]
                
                price = line[3]
                
                # Check for header or invalid entries
                if ticker == 'symbol' or price == '':
                    continue

                # Add stock to dict if not already in there
                if ticker not in stocks:
                    stocks[ticker] = Stock(ticker)
            
                # Add order to stock
                stocks[ticker].orders.append(Order(line[0], line[1], line[2], line[3], line[4], line[5]))
        return stocks

    def calculate_itemized_pl(stocks):
        for stock in stocks.values():
            for order in stock.orders:
                if order.side == 'buy':
                    stock.net_shares += order.shares
                else:
                    stock.net_shares -= order.shares
                # order.pl() is positive for selling and negative for buying
                stock.net_pl += order.pl()

            # Handle outstanding shares - should be current positions
            if stock.net_shares > 0:
                
                requestResponse = requests.get("https://api.iextrading.com/1.0/stock/{}/price".format(stock.symbol.lower()))
                json = requestResponse.json()
                last_price = float(json)

                # Add currently held shares from net_pl as if selling now (unrealized PnL)
                stock.net_pl += stock.net_shares * last_price
                    
            # Should handle free gift stocks
            elif stock.net_shares < 0:
                stock.symbol += 'RH Free Gift'


    # INSTANTIATE ROBINHOOD my_trader #
    my_trader = Robinhood.Robinhood()
    logged_in = my_trader.login(username=username, password=password)
    my_account = my_trader.get_account()['url']



    df_order_history, _ = rh.get_order_history(my_trader)
    df_orders = df_order_history[['side', 'symbol', 'shares', 'avg_price', 'date', 'state']]
    df_orders.columns = ['side', 'symbol', 'shares', 'price', 'date', 'state']

    # Filter for input dates
    df_orders['date'] = pd.to_datetime(df_orders['date'])
    df_orders = df_orders.sort_values('date')
    df_orders = df_orders.set_index('date')
    df_orders = df_orders[start_date:end_date]
    df_orders['date'] = df_orders.index

    df_orders.set_index('side').to_csv('orders.csv', header=None)
    stocks = itemize_stocks()
    calculate_itemized_pl(stocks)

    with open('stockwise_pl.csv', 'w') as outfile:
        writer = csv.writer(outfile, delimiter=',')
        writer.writerow(['SYMBOL', 'net_pnl', 'n_trades'])
        sorted_pl = sorted(stocks.values(), key=operator.attrgetter('net_pl'), reverse=True)
        total_pl = 0
        total_trades = 0
        for stock in sorted_pl:
            num_trades = len(stock.orders)
            writer.writerow([stock.symbol, '{0:.2f}'.format(stock.net_pl), len(stock.orders)])
            total_pl += stock.net_pl
            total_trades += num_trades
        writer.writerow(['Totals', total_pl, total_trades])
        # print('Created', outfile.name, 'in this directory.')
        
    df_pnl = pd.read_csv('stockwise_pl.csv')

    dividends = Robinhood.Robinhood.dividends(my_trader)

    list_of_records = []
    for each in dividends['results']:
        list_of_records.append(pd.DataFrame(pd.Series(each)).T)

    df_dividends = pd.concat(list_of_records)

    # Load in our pickled database of instrument-url lookups
    instruments_df = pd.read_pickle('symbol_and_instrument_urls')

    df_dividends = df_dividends.set_index('id')

    df_dividends['id'] = df_dividends.index

    
    df_dividends['ticker'] = np.nan
    for each in df_dividends.itertuples():
        symbol, instruments_df = rh.get_symbol_from_instrument_url(each.instrument, instruments_df)
        df_dividends.loc[each.id, 'ticker'] = symbol

    if pickle == 1:
        df_dividends.to_pickle('dividends_df')

    if csv_export == 1:
        df_dividends.to_csv('divs_raw.csv')
        # df_pnl.to_csv('pnl.csv')

    # Filter df_dividends
    df_dividends['record_date'] = pd.to_datetime(df_dividends['record_date'])
    df_dividends = df_dividends.sort_values('record_date')
    df_dividends = df_dividends.set_index('record_date')
    df_dividends = df_dividends[start_date:end_date]
    # convert numbers to actual numbers
    df_dividends['amount'] = pd.to_numeric(df_dividends['amount'])

    # Group dividend payouts by ticker and sum
    df_divs_summed = df_dividends.groupby('ticker').sum()

    # Set a column to the ticker
    df_divs_summed['ticker'] = df_divs_summed.index

    # For the stockwise pnl, set index to the ticker ('SYMBOL')
    df_pnl = df_pnl.set_index('SYMBOL')

    try:
        df_pnl = df_pnl.drop('Totals')
    except KeyError as e:
        print("Totals row not found")

    # Set div payouts column
    df_pnl['div_payouts'] = np.nan

    # For each in the summed 
    for each in df_divs_summed.itertuples():
        amount = each.amount
        df_pnl.loc[each.ticker, 'div_payouts'] = amount
    
    if pickle == 1:
        df_divs_summed.to_pickle('df_divs_summed')
        df_pnl.to_pickle('df_pnl')

    if csv_export == 1:
        # df_divs_summed.to_csv('divs_summed_df.csv')
        df_pnl.to_csv('pnl_df.csv')

    # Create a df that only includes the dividend payouts
    df_pnl_divs_only = df_pnl[df_pnl['div_payouts'].isnull() == False]

    # Create a df that only includes non-div paying trades
    pnl_no_divs = df_pnl[df_pnl['div_payouts'].isnull() == True]

    # Calculate profit and loss including div payouts on the divs_only df
    df_pnl_divs_only['pnl_with_divs'] = pd.to_numeric(df_pnl_divs_only['net_pnl']) + pd.to_numeric(df_pnl_divs_only['div_payouts'])

    # Re-sort the divs_only data from highest to lowest
    df_pnl_divs_only = df_pnl_divs_only.sort_values('pnl_with_divs', ascending=False)

    # Calculate the sum of the divs_only trades, now including the dividends
    div_only_pnl = df_pnl_divs_only['pnl_with_divs'].sum()

    # Calculate the sum of the non_divs trades
    total_pnl_non_div = pnl_no_divs['net_pnl'].sum()

    if buy_and_hold == 1:

        requestResponse = requests.get("https://api.iextrading.com/1.0/stock/spy/chart/5y")
        json = requestResponse.json()
        df_spy = pd.DataFrame(json)
        df_spy.index = pd.to_datetime(df_spy['date'])
        df_spy = df_spy[start_date:end_date]

        SPY_starting_price = float(df_spy.iloc[0]['close'])

        SPY_ending_price = float(df_spy.iloc[-1]['close'])

        SPY_buy_and_hold_gain = starting_equity*(SPY_ending_price - SPY_starting_price)/SPY_starting_price

    if end_date == 'January 1, 2020':
        end_date_string = 'today'
    else:
        end_date_string = end_date

    print("From {} to {}, you've made ${} on trades with dividends, ${} on trades without dividends, for a total PnL of ${}.".format(start_date, end_date_string, round(div_only_pnl,2), round(total_pnl_non_div,2), round((round(total_pnl_non_div,2) + round(div_only_pnl,2)), 2)))
    
    if buy_and_hold == 1:
        print("With your starting portfolio of ${}, if you had just bought and held SPY, you would have made ${}".format(starting_equity, round(SPY_buy_and_hold_gain,2)))
    
    # Delete the csv we were processing earlier
    os.remove('stockwise_pl.csv')

    return total_pnl_non_div, div_only_pnl

if __name__ == '__main__':

    try:
        start_date = sys.argv[3]
    except Exception as e:
        start_date = 'January 1, 2015'

    try:
        end_date = sys.argv[4]
    except Exception as e:
        end_date = 'January 1, 2020'
    
    try:
        starting_equity = int(sys.argv[5])
    except Exception as e:
        starting_equity = 10000

    rh_profit_and_loss(username=sys.argv[1], 
                        password=sys.argv[2], 
                        start_date=start_date, 
                        end_date=end_date, 
                        starting_equity=starting_equity, 
                        csv_export=1, 
                        buy_and_hold=1, 
                        pickle=0)