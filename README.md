# Calculate profit and loss, get dividend history from RH

## Download the repo
From the command line: `git clone 


## Run it, run it

From the directory you cloned the repository into, run it like so:

`python3 get_profit_and_loss.py <username> <password>` 

If you want to find out how much you made over only a given date range, and simulate a buy-and-hold to compare it to:

`python3 get_profit_and_loss.py <username> <password> <start_date> <end_date> <starting_equity>` 

Make sure the commands are in that order, and each is in quotes, like:
`python3 get_profit_and_loss.py 'timmyturtlehands' 'LovePizzaFhdjeiw!22222' 'July 1, 2018' 'November 10, 2018' '5000'`

You'll see output like:
```
From July 1, 2018 to November 10, 2018, you've made $28.62 on trades with dividends, $951.94 on trades without dividends, for a total PnL of $980.56.
With your starting portfolio of $10000, if you had just bought and held SPY, you would have made $4161.21
```

Hope you enjoy it!

### Other bonuses & notes

- If the stock isn't sold yet, it uses the last sale price from IEX to calculate your unrealized PnL and adds that in. 

- The script outputs a number of CSV files that include dividend payouts, complete list of trades made, and profit per ticker for the date range provided. You can mess with these in Excel/Google Docs:
- - `pnl_df.csv` which shows your profit-and-loss per ticker, and any dividends you've been paid out (not summed into PnL)
- - `divs_raw.csv` which is the full data dump with your dividend history (and future dividends)
- - `orders.csv` which contains all of your individual buys and sells in raw format, whether they executed or not 
	
- If you change `pickle=0` to `pickle=1` on line 249, it will export pickled pandas dataframes you can open in a Jupyter notebook for more exploration/manipulation. 

- The `symbols_and_instruments_url` is a pickled lookup table that provides RH's internal instrument id for symbols, and vice versa, which are needed to interact with the API. By saving and updating this pickle, you reduce the amount of requests you make to the RH API. 

- Special thanks to everyone who maintains the main Python library, of which I modified and use bits and pieces of  (https://github.com/Jamonek/Robinhood) 

### Requirements

```
numpy
pandas
requests
six
```