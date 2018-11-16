# RH Profit and Loss

A python script to get a quick look at your profit and loss from trading options and individual equities on Robinhood, sum dividend payouts, and generate your trading history. 

## Download the repo
From the command line: 

`git clone git@github.com:trevorwelch/rh-profit-and-loss.git`

`cd rh-profit-and-loss`

## Run it, run it

Run with defaults (this will process your full account history):

`python3 get_profit_and_loss.py --username <username> --password <password>` 

For example: `python3 get_profit_and_loss.py --username 'timmyturtlehands' --password 'LovePizzaFhdjeiw!11one'`

You'll see output like:

```
From November 4, 2018 to November 15, 2018, your total PnL is $486.45
You've made $390.1 buying and selling individual equities, received $16.35 in dividends, and made $80.0 on options trades
With your starting allocation of $10000, if you had just bought and held QQQ, your PnL would have been $-51.49
```

## Run it with custom options

### See your PnL over a specified date range	

If you want to find out how your portfolio performed over only a given date range:

`python3 get_profit_and_loss.py --username <username> --password <password> --start_date <start_date> --end_date <end_date>` 

### Export CSV files for further exploration

- The script can output a number of CSV files:
	- `pnl_df.csv` shows your profit-and-loss per ticker, and any dividends you've been paid out (dividends are not summed into `net_pnl`)
	- `divs_raw.csv` is the full data dump of your dividend history (and future dividends)
	- `orders.csv` contains all of your individual buys and sells in raw format, whether they executed or not 
	- `options_orders_history_df.csv` contains a simplified record of your options purchases

Use flag `--csv` to enable this.

### Export dataframes as pickles for further exploration:

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

Use flag `--pickle` to enable pickling of dataframes.

### Example command with custom options

`python3 get_profit_and_loss.py --username 'timmyturtlehands' --password 'LovePizzaFhdjeiw!22222' --start_date 'July 1, 2018' --end_date 'November 10, 2018' --starting_allocation '5000' --csv`

### Requirements

```
numpy
pandas
requests
six
```

#### other notes and 'bibliography' ;)

- If the stock isn't sold yet, it uses the last sale price from IEX to calculate your unrealized PnL. 

- The `symbols_and_instruments_url` is a lookup table that provides RH's internal instrument ids for symbols, and vice versa, which are needed to interact with the API. By saving and updating this pickle, you reduce the amount of requests you make to the RH API. 

- Special thanks to everyone who maintains the unofficial RH Python library, of which a modified version is included in this repo (https://github.com/Jamonek/Robinhood) 

- For the buy-and-hold calculation, QQQ historical data is from (https://www.kaggle.com/qks1lver/amex-nyse-nasdaq-stock-histories) and IEX, depending on how far back you're going. 