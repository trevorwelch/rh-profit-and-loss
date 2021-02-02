# RH Profit and Loss

A Python script to get a look at your trading history from trading options and individual equities on Robinhood: calculate profit/loss, sum dividend payouts and generate buy-and-hold comparison. 

_UPDATE 2020-01-21 This code is so bad I almost want to delete it from my GH, but it works - and I've seen it get some of attention so I'm pushing this small update to make it usable (at least until RH changes their API again). Thanks to @nikhilsaraf who forked it and fixed the auth'ing problem._

## Features

- *Calculate individual equities' trading pnl, dividends received, options trading pnl*
- *Export CSV files with individual trades and other info*
- *Export pickled dataframes*
- *Specify date range to compare over*
- *Print percent pnl*

## Download the repo
From the command line: 

```
git clone git@github.com:trevorwelch/rh-profit-and-loss.git
cd rh-profit-and-loss
```

## Run it, run it

### First, grab an oauth token from your browser

* Navigate to Robinhood.com, log out if you're already logged in.
* Right Click > Inspect Element 
* Click on Network tab
* In the "Filter" text entry, type "token" 
* With the network monitor open, login to Robinhood
* You will see a few JSON files, find the one that has 'access_token' in the return, and copy that whole string

Run with defaults (this will process your full account history, starting from your first trade):

`python3 get_profit_and_loss.py --username <username> --password <password> --access_token <longtextblob>` 

For example: 

`python3 get_profit_and_loss.py --username 'timmyturtlehands@gmail.com' --password 'LovePizza!11one' --access_token <longtextblob>`

You'll see output like:

```
From November 4, 2018 to today, your total PnL is $486.45
You've made $390.1 buying and selling individual equities, received $16.35 in dividends, and made $80.0 on options trades
With your starting allocation of $10000, if you had just bought and held QQQ, your PnL would have been $-51.49
```

## Run it and utilize other features

### See how your portfolio performed over a specified date range	

#### Specify `--start_date` and `--end_date` args

For example:

`python3 get_profit_and_loss.py --username 'timmyturtlehands@gmail.com' --password 'LovePizza!11one'  --access_token <longtextblob> --start_date 'July 1, 2018' --end_date 'August 1, 2018'` 

### Export CSV files for further exploration

#### Use the `--csv` flag

The script can output a number of CSV files:
	- `pnl_df.csv` shows your profit-and-loss per ticker, and any dividends you've been paid out (dividends are not summed into `net_pnl`)
	- `divs_raw.csv` is the full data dump of your dividend history (and future dividends)
	- `orders.csv` contains all of your individual buy and sell orders (including orders that didn't execute)
	- `options_orders_history_df.csv` contains a simplified record of your options activity

For example:

`python3 get_profit_and_loss.py --username 'timmyturtlehands@gmail.com' --password 'LovePizza!11one'  --access_token <longtextblob> --csv`

### Export dataframes as pickles for further exploration:

#### Use the `--pickle` flag

Similar exports to the CSV section, but as pickled dataframes which can be loaded directly into pandas for further exploration like so:
```
import pandas as pd
df_pnl = pd.read_pickle('df_pnl')

# Find worst ticker and best ticker, dataframe is already sorted by net_pnl
best_ticker = df_pnl.iloc[0].name
best_ticker_pnl = df_pnl.iloc[0].net_pnl
worst_ticker = df_pnl.iloc[-1].name
worst_ticker_pnl = df_pnl.iloc[-1].net_pnl

print("Your best individual equities trade over this time period was with {}, with ${} in gains".format(best_ticker, best_ticker_pnl))
print("Your worst individual equities trade over this time period was with {}, with ${} in gains".format(worst_ticker, worst_ticker_pnl))
```

For example:

`python3 get_profit_and_loss.py --username 'timmyturtlehands@gmail.com' --password 'LovePizza!11one' --pickle`

### Example command with custom options chained together

`python3 get_profit_and_loss.py --username 'timmyturtlehands@gmail.com' --password 'LovePizzaFhdjeiw!22222' --start_date 'July 1, 2018' --end_date 'November 10, 2018' --starting_allocation '5000' --csv`

### Requirements

```
numpy
pandas
requests
six
```

#### other notes and 'bibliography' ;)

- Includes unrealized gains (so, positions you haven't closed yet / stocks you haven't sold yet)

- The `symbols_and_instruments_url` is a lookup table that provides RH's internal instrument ids for symbols, and vice versa, which are needed to interact with the API. By saving and updating this pickle, you reduce the amount of requests you make to the RH API. 

- Special thanks to everyone who maintains the unofficial RH Python library, of which a heavily modified, out-of-date version is included in this repo (https://github.com/Jamonek/Robinhood) 

- Some of the order history code is borrowed from (https://github.com/rmccorm4/Robinhood-Scraper/blob/master/Robinhood/robinhood_pl.py) 