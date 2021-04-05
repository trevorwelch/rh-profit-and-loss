import argparse
import csv
import os
import numpy as np
import sys
import json
import pandas as pd
import requests
import operator
import traceback
import sys

import TW_robinhood_scripts as rh
import Robinhood

def rh_profit_and_loss(username=None, password=None, access_token=None, starting_allocation=5000, start_date=None, end_date=None, csv_export=1, buy_and_hold=0, pickle=0, options=1):

    # from rmccorm4 Robinhood-Scraper
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

    def calculate_itemized_pl(stocks, my_trader):
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
                
                price = my_trader.last_trade_price(stock.symbol)[0][0]
                last_price = float(price)

                # Add currently held shares from net_pl as if selling now (unrealized PnL)
                stock.net_pl += stock.net_shares * last_price
                    
            # Should handle free gift stocks
            elif stock.net_shares < 0:
                stock.symbol += ' '

    def calculate_outstanding_options(my_trader):
        owned = my_trader.options_owned()

        pending = None

        if (len(owned) > 0):
            df_owned = pd.DataFrame(owned)

            df_owned['quantity'] = pd.to_numeric(df_owned['quantity'])
            df_owned['average_price'] = pd.to_numeric(df_owned['average_price'])
            df_owned['trade_value_multiplier'] = pd.to_numeric(df_owned['trade_value_multiplier'])

            pending = df_owned[
                df_owned['quantity'] > 0
            ]

            pending = pending[['chain_symbol', 'quantity', 'average_price', 'option_id', 'trade_value_multiplier']].reset_index(drop=True)

            pending['avg_option_cost'] = pending['average_price']/pending['trade_value_multiplier']

            current_option_values = []
            for each in pending['option_id'].values:
                try:
                    current_price = my_trader.get_option_market_data(each)['adjusted_mark_price']
                except Exception:
                    current_price = np.nan
                
                current_option_values.append(current_price)

            pending['current_option_values'] = [float(x) for x in current_option_values]
            pending['current_value'] = pending['current_option_values']*pending['quantity']*100

            pending['date'] = pd.Timestamp.now()
            pending = pending.set_index('date')

            pending.to_csv('pending_options_orders_df.csv')

            pending['position_effect'] = 'pending'
            pending['value'] = pending['current_value']
            pending['ticker'] = pending['chain_symbol']

            pending['original_value'] = pending['quantity'] * pending['average_price']

        return pending


    # INSTANTIATE ROBINHOOD my_trader #
    my_trader = Robinhood.Robinhood()
    logged_in = my_trader.set_oath_access_token(username, password, access_token)
    if not logged_in:
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

    if pickle == 1:
        df_orders.to_pickle('df_orders_history')

    if start_date == 'January 1, 2012':
        start_date = df_orders.iloc[0]['date'].strftime('%B %d, %Y')

    df_orders.set_index('side').to_csv('orders.csv', header=None)
    stocks = itemize_stocks()
    calculate_itemized_pl(stocks, my_trader)

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
    
    # Read the pnl we generated       
    df_pnl = pd.read_csv('stockwise_pl.csv')

    # Get dividends from Robinhood
    dividends = Robinhood.Robinhood.dividends(my_trader)

    # Put the dividends in a dataframe
    list_of_records = []
    for each in dividends['results']:
        list_of_records.append(pd.DataFrame(pd.Series(each)).T)

    df_dividends = pd.concat(list_of_records)
    df_dividends = df_dividends.set_index('id')
    df_dividends['id'] = df_dividends.index

    # Load in our pickled database of instrument-url lookups
    instruments_df = pd.read_pickle('symbol_and_instrument_urls')
    
    df_dividends['ticker'] = np.nan
    for each in df_dividends.itertuples():
        symbol, instruments_df = rh.get_symbol_from_instrument_url(each.instrument, instruments_df)
        df_dividends.loc[each.id, 'ticker'] = symbol

    if pickle == 1:
        df_dividends.to_pickle('df_dividends')

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

    # Calculate the dividends received (or that are confirmed you will receive in the future)
    dividends_paid = float(df_pnl.sum()['div_payouts'])

    # Calculate the total pnl 
    pnl = float(df_pnl.sum()['net_pnl'])

    # When printing the final output, if no date was provided, print "today"
    if end_date == 'January 1, 2030':
        end_date_string = 'today'
    else:
        end_date_string = end_date

    # Retrieve options history
    if options == 1:
        try:
            df_options_orders_history = rh.get_all_history_options_orders(my_trader)
            pending_options = calculate_outstanding_options(my_trader)

            options_pnl = 0

            if (pending_options is not None and pending_options.len() > 0):
                df_options = pd.concat([
                    df_options_orders_history,
                    pending_options[['ticker', 'value', 'position_effect']],
                ])

                # More hacky shit cause this code is a mess
                df_options = df_options.reset_index()
                df_options['date'] = pd.to_datetime(df_options['date'], utc=True)
                df_options = df_options.set_index(df_options['date'])

                if csv_export == 1:
                    df_options.to_csv('options_orders_history_df.csv')
                if pickle == 1:
                    df_options.to_pickle('df_options_orders_history')

                df_options = df_options[start_date:end_date]
                options_pnl = df_options['value'].sum()

        except Exception as e:
            print(traceback.format_exc())
            print(sys.exc_info()[0])
            options_pnl = 0

    total_pnl = round(pnl + dividends_paid + options_pnl, 2)


    # Print final output            
    print("~~~")
    print("From {} to {}, your total PnL is ${}".format(start_date, end_date_string, total_pnl))
    print("You've made ${} buying and selling individual equities, received ${} in dividends, and ${} on options trades".format(round(pnl,2), round(dividends_paid,2), round(options_pnl,2)))
    
    # Calculate ROI, if the user input a starting allocation
    if roi == 1:

        # Calculate Stocks ROI 
        long_entries = df_orders[
            (df_orders['side'] == 'buy')
            &
            (df_orders['state'] == 'filled')
        ]

        long_entries['value'] = pd.to_numeric(long_entries['price'])*pd.to_numeric(long_entries['shares'])

        starting_stock_investment = long_entries['value'].sum() 

        stocks_roi = rh.pct_change(
            pnl+starting_stock_investment,
            starting_stock_investment
            )
        print("Your return-on-investment (ROI) for stock trades is: %{}".format(stocks_roi))

        # Calculate Options ROI
        # More hacky shit cause this code is a mess
        df_options_orders_history = df_options_orders_history.reset_index()
        df_options_orders_history['date'] = pd.to_datetime(df_options_orders_history['date'], utc=True)
        df_options_orders_history = df_options_orders_history.set_index(df_options_orders_history['date'])

        df_options_orders_history = df_options_orders_history[start_date:end_date]
        options_entries = df_options_orders_history[
            df_options_orders_history['value'] < 0
        ]

        starting_options_investment = options_entries['value'].sum()*-1

        options_roi = rh.pct_change(
            options_pnl+starting_options_investment,
            starting_options_investment
            )
        print("Your return-on-investment (ROI) for options trades is: %{}".format(options_roi))

        # print(starting_options_investment)
        # print(options_pnl)
        # print(pnl)
        # print(starting_stock_investment)

        return_on_investment = rh.pct_change(
            options_pnl+starting_options_investment+pnl+starting_stock_investment,
            starting_options_investment+starting_stock_investment
            )
        print("Your return-on-investment (ROI) on overall capital deployed is: %{}".format(return_on_investment))
    
    if buy_and_hold == 1:
        print("With a starting allocation of ${}, if you had just bought and held QQQ, your PnL would be ${}".format(starting_allocation, round(QQQ_buy_and_hold_gain,2)))
    print("~~~")
    # Delete the csv we were processing earlier
    # os.remove('stockwise_pl.csv')

if __name__ == '__main__':

    # Parse command line arguments
    parser = argparse.ArgumentParser()  
    parser.add_argument("--username", help="username (required)")
    parser.add_argument("--password", help="password (required)")
    parser.add_argument("--access_token", help="oath access_token (required)")
    parser.add_argument("--start_date", help="begin date for calculations")
    parser.add_argument("--end_date", help="begin date for calculations")
    parser.add_argument("--csv", help="save csvs along the way", action="store_true")
    parser.add_argument("--pickle", help="save pickles along the way", action="store_true")

    args = parser.parse_args()

    if args.username and args.password and args.access_token:
        print("Working...")
    else:
        print("Please enter a username and password and access_token and try again!")
        sys.exit()

    # check for flag
    if args.csv:  
        csv_export = 1
    else:
        csv_export = 0

    # check for flag
    if args.pickle:  
        pickle = 1
    else:
        pickle = 0

    # check for start date
    if args.start_date:
        start_date = args.start_date
    else:
        start_date = 'January 1, 2012'
    
    # check for end date
    if args.end_date:
        end_date = args.end_date
    else:
        end_date = 'January 1, 2030'

    roi = 1

    rh_profit_and_loss(username=args.username, 
                        password=args.password,
                        access_token=args.access_token,
                        start_date=start_date, 
                        end_date=end_date,
                        csv_export=csv_export, 
                        buy_and_hold=0,
                        options=1, 
                        pickle=pickle)