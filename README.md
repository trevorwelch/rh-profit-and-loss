# Calculate profit and loss, get dividend history from RH

## Download the repo
From the command line: 

`git clone git@github.com:trevorwelch/rh-profit-and-loss.git`

`cd rh-profit-and-loss`

## Run it, run it

Run with defaults (from your full account history):

`python3 get_profit_and_loss.py <username> <password>` 

If you want to find out how much you made over only a given date range, and specify how much money you initially invested with to simulate a buy-and-hold strategy for comparison:

`python3 get_profit_and_loss.py <username> <password> <start_date> <end_date> <starting_allocation>` 

Make sure the commands are in that order, and each is in quotes, like:

`python3 get_profit_and_loss.py 'timmyturtlehands' 'LovePizzaFhdjeiw!22222' 'July 1, 2018' 'November 10, 2018' '5000'`

You'll see output like:

```
From November 4, 2018 to November 15, 2018, your total PnL is -$224.0
You've made $-390.1 buying and selling individual equities, received $16.35 in dividends, and made $0.0 on options trades
With your starting allocation of $10000, if you had just bought and held QQQ, you would have made $-51.49
```

Hope you enjoy it!

### Bonus

- The script outputs a number of CSV files that include dividend payouts, complete list of trades made, and profit per ticker for the date range provided. You can mess with these in Excel/Google Docs:
- - `pnl_df.csv` shows your profit-and-loss per ticker, and any dividends you've been paid out (dividends are not summed into `net_pnl`)
- - `divs_raw.csv` is the full data dump of your dividend history (and future dividends)
- - `orders.csv` contains all of your individual buys and sells in raw format, whether they executed or not 
- - `options_orders_history_df.csv` contains a simplified record of your options purchases

### Requirements

```
numpy
pandas
requests
six
```

### Other bonuses & notes

- If the stock isn't sold yet, it uses the last sale price from IEX to calculate your unrealized PnL and adds that in. 

- If you try to specify a date range that starts earlier than 5 years ago, the buy-and-hold won't work. This is due to data limitations with freely available through IEX.
	
- If you change `pickle=0` to `pickle=1` on line 249, it will export pickled pandas dataframes you can open in a Jupyter notebook for more exploration/manipulation. 

- The `symbols_and_instruments_url` is a pickled lookup table that provides RH's internal instrument id for symbols, and vice versa, which are needed to interact with the API. By saving and updating this pickle, you reduce the amount of requests you make to the RH API. 

- Special thanks to everyone who maintains the main Python library, of which I modified and use bits and pieces of  (https://github.com/Jamonek/Robinhood) 

