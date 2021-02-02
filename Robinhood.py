"""Robinhood.py: a collection of utilities for working with Robinhood's Private API """

#Standard libraries
import logging
import warnings

import robin_stocks as r

from enum import Enum

#External dependencies
from six.moves.urllib.parse import unquote  # pylint: disable=E0401
from six.moves.urllib.request import getproxies  # pylint: disable=E0401
from six.moves import input

import getpass
import requests
import six
import dateutil
import urllib

#Application-specific imports
try: 
    from . import exceptions as RH_exception
    from . import endpoints
except Exception as e:
    import exceptions as RH_exception
    import endpoints

import random

class Bounds(Enum):
    """Enum for bounds in `historicals` endpoint """

    REGULAR = 'regular'
    EXTENDED = 'extended'


class Transaction(Enum):
    """Enum for buy/sell orders """

    BUY = 'buy'
    SELL = 'sell'


class Robinhood:
    """Wrapper class for fetching/parsing Robinhood endpoints """

    session = None
    username = None
    password = None
    headers = None
    auth_token = None
    oauth_token = None

    logger = logging.getLogger('Robinhood')
    logger.addHandler(logging.NullHandler())


    ###########################################################################
    #                       Logging in and initializing
    ###########################################################################

    def __init__(self):
        self.session = requests.session()
        self.session.proxies = getproxies()
        self.headers = {
            "Accept": "*/*",
            "Accept-Encoding": "gzip, deflate",
            "Accept-Language": "en;q=1, fr;q=0.9, de;q=0.8, ja;q=0.7, nl;q=0.6, it;q=0.5",
            "Content-Type": "application/x-www-form-urlencoded; charset=utf-8",
            "Connection": "keep-alive",
            "User-Agent": "Robinhood/6.28.0 (com.robinhood.release.Robinhood; build:5771; iOS 11.4.1) Alamofire/4.5.1"
        }
        self.session.headers = self.headers
        self.auth_method = self.login_prompt

    def login_required(function):  # pylint: disable=E0213
        """ Decorator function that prompts user for login if they are not logged in already. Can be applied to any function using the @ notation. """
        def wrapper(self, *args, **kwargs):
            if 'Authorization' not in self.headers:
                self.auth_method()
            return function(self, *args, **kwargs)  # pylint: disable=E1102
        return wrapper

    def login_prompt(self):  # pragma: no cover
        """Prompts user for username and password and calls login() """

        username = input("Username: ")
        password = getpass.getpass()

        return self.login(username=username, password=password)

    def set_oath_access_token(self, username, password, access_token):
        self.username = username
        self.password = password
        self.oauth_token = access_token
        self.headers['Authorization'] = 'Bearer ' + self.oauth_token
        return True

    def login(self, username, password, mfa_code=None):

            self.username = username
            self.password = password
            
            # try getting access_token with new API
            l = r.login(username, password)
            if 'access_token' in l.keys():
                self.oauth_token = l['access_token']
                self.headers['Authorization'] = 'Bearer ' + self.oauth_token
                print(l)
                return True
            # /try getting access_token with new API

            payload = {
                'client_id': 'c82SH0WZOsabOXGP2sxqcj34FxkvfnWRZBKlBjFS',
                'expires_in': 86400,
                'grant_type': 'password',
                'password': self.password,
                'scope': 'internal',
                'username': self.username
            }

            if mfa_code:
                payload['mfa_code'] = mfa_code

            try:
                res = self.session.post('https://api.robinhood.com/oauth2/token/', data=payload, timeout=300)
                res.raise_for_status()
                data = res.json()
            except requests.exceptions.HTTPError:
                raise RH_exception.LoginFailed()

            if 'mfa_required' in data.keys():           # pragma: no cover
                raise RH_exception.TwoFactorRequired()  # requires a second call to enable 2FA

            if 'access_token' in data.keys():
                self.oauth_token = data['access_token']
                self.headers['Authorization'] = 'Bearer ' + self.oauth_token
                return True

            return False


    def logout(self):
        """Logout from Robinhood

        Returns:
            (:obj:`requests.request`) result from logout endpoint

        """

        try:
            req = self.session.post(endpoints.logout(), timeout=300)
            req.raise_for_status()
        except requests.exceptions.HTTPError as err_msg:
            warnings.warn('Failed to log out ' + repr(err_msg))

        self.headers['Authorization'] = None
        self.auth_token = None

        return req


    ###########################################################################
    #                               GET DATA
    ###########################################################################

    def investment_profile(self):
        """Fetch investment_profile """

        res = self.session.get(endpoints.investment_profile(), timeout=300)
        res.raise_for_status()  # will throw without auth
        data = res.json()

        return data


    def instruments(self, stock):
        """Fetch instruments endpoint

            Args:
                stock (str): stock ticker

            Returns:
                (:obj:`dict`): JSON contents from `instruments` endpoint
        """

        res = self.session.get(endpoints.instruments(), params={'query': stock.upper()}, timeout=300)
        res.raise_for_status()
        res = res.json()

        # if requesting all, return entire object so may paginate with ['next']
        if (stock == ""):
            return res

        return res['results']


    def instrument(self, id):
        """Fetch instrument info

            Args:
                id (str): instrument id

            Returns:
                (:obj:`dict`): JSON dict of instrument
        """
        url = str(endpoints.instruments()) + str(id) + "/"

        try:
            req = requests.get(url, timeout=300)
            req.raise_for_status()
            data = req.json()
        except requests.exceptions.HTTPError:
            raise RH_exception.InvalidInstrumentId()

        return data


    def quote_data(self, stock=''):
        """Fetch stock quote

            Args:
                stock (str): stock ticker, prompt if blank

            Returns:
                (:obj:`dict`): JSON contents from `quotes` endpoint
        """

        url = None

        if stock.find(',') == -1:
            url = str(endpoints.quotes()) + str(stock) + "/"
        else:
            url = str(endpoints.quotes()) + "?symbols=" + str(stock)

        #Check for validity of symbol
        try:
            req = requests.get(url, headers=self.headers, timeout=300)
            req.raise_for_status()
            data = req.json()
        except requests.exceptions.HTTPError:
            raise RH_exception.InvalidTickerSymbol()


        return data


    # We will keep for compatibility until next major release
    def quotes_data(self, stocks):
        """Fetch quote for multiple stocks, in one single Robinhood API call

            Args:
                stocks (list<str>): stock tickers

            Returns:
                (:obj:`list` of :obj:`dict`): List of JSON contents from `quotes` endpoint, in the
                    same order of input args. If any ticker is invalid, a None will occur at that position.
        """

        url = str(endpoints.quotes()) + "?symbols=" + ",".join(stocks)

        try:
            req = requests.get(url, headers=self.headers, timeout=300)
            req.raise_for_status()
            data = req.json()
        except requests.exceptions.HTTPError:
            raise RH_exception.InvalidTickerSymbol()


        return data["results"]


    def get_quote_list(self,
                       stock='',
                       key=''):
        """Returns multiple stock info and keys from quote_data (prompt if blank)

            Args:
                stock (str): stock ticker (or tickers separated by a comma)
                , prompt if blank
                key (str): key attributes that the function should return

            Returns:
                (:obj:`list`): Returns values from each stock or empty list
                               if none of the stocks were valid

        """

        #Creates a tuple containing the information we want to retrieve
        def append_stock(stock):
            keys = key.split(',')
            myStr = ''
            for item in keys:
                myStr += stock[item] + ","

            return (myStr.split(','))


        #Prompt for stock if not entered
        if not stock:   # pragma: no cover
            stock = input("Symbol: ")

        data = self.quote_data(stock)
        res = []

        # Handles the case of multple tickers
        if stock.find(',') != -1:
            for stock in data['results']:
                if stock is None:
                    continue
                res.append(append_stock(stock))

        else:
            res.append(append_stock(data))

        return res


    def get_quote(self, stock=''):
        """Wrapper for quote_data """

        data = self.quote_data(stock)
        return data["symbol"]

    def get_historical_quotes(self, stock, interval, span, bounds=Bounds.REGULAR):
        """Fetch historical data for stock

            Note: valid interval/span configs
                interval = 5minute | 10minute + span = day, week
                interval = day + span = year
                interval = week
                TODO: NEEDS TESTS

            Args:
                stock (str): stock ticker
                interval (str): resolution of data
                span (str): length of data
                bounds (:enum:`Bounds`, optional): 'extended' or 'regular' trading hours

            Returns:
                (:obj:`dict`) values returned from `historicals` endpoint
        """
        if type(stock) is str:
            stock = [stock]

        if isinstance(bounds, str):  # recast to Enum
            bounds = Bounds(bounds)

        params = {
            'symbols': ','.join(stock).upper(),
            'interval': interval,
            'span': span,
            'bounds': bounds.name.lower()
        }

        res = self.session.get(endpoints.historicals(), params=params, timeout=300)
        return res.json()


    def get_news(self, stock):
        """Fetch news endpoint
            Args:
                stock (str): stock ticker

            Returns:
                (:obj:`dict`) values returned from `news` endpoint
        """

        return self.session.get(endpoints.news(stock.upper()), timeout=300).json()


    def print_quote(self, stock=''):    # pragma: no cover
        """Print quote information
            Args:
                stock (str): ticker to fetch

            Returns:
                None
        """

        data = self.get_quote_list(stock, 'symbol,last_trade_price')
        for item in data:
            quote_str = item[0] + ": $" + item[1]
            print(quote_str)
            self.logger.info(quote_str)


    def print_quotes(self, stocks):  # pragma: no cover
        """Print a collection of stocks

            Args:
                stocks (:obj:`list`): list of stocks to pirnt

            Returns:
                None
        """

        if stocks is None:
            return

        for stock in stocks:
            self.print_quote(stock)


    def ask_price(self, stock=''):
        """Get asking price for a stock

            Note:
                queries `quote` endpoint, dict wrapper

            Args:
                stock (str): stock ticker

            Returns:
                (float): ask price
        """

        return self.get_quote_list(stock, 'ask_price')


    def ask_size(self, stock=''):
        """Get ask size for a stock

            Note:
                queries `quote` endpoint, dict wrapper

            Args:
                stock (str): stock ticker

            Returns:
                (int): ask size
        """

        return self.get_quote_list(stock, 'ask_size')


    def bid_price(self, stock=''):
        """Get bid price for a stock

            Note:
                queries `quote` endpoint, dict wrapper

            Args:
                stock (str): stock ticker

            Returns:
                (float): bid price
        """

        return self.get_quote_list(stock, 'bid_price')


    def bid_size(self, stock=''):
        """Get bid size for a stock

            Note:
                queries `quote` endpoint, dict wrapper

            Args:
                stock (str): stock ticker

            Returns:
                (int): bid size
        """

        return self.get_quote_list(stock, 'bid_size')


    def last_trade_price(self, stock=''):
        """Get last trade price for a stock

            Note:
                queries `quote` endpoint, dict wrapper

            Args:
                stock (str): stock ticker

            Returns:
                (float): last trade price
        """

        return self.get_quote_list(stock, 'last_trade_price')


    def previous_close(self, stock=''):
        """Get previous closing price for a stock

            Note:
                queries `quote` endpoint, dict wrapper

            Args:
                stock (str): stock ticker

            Returns:
                (float): previous closing price
        """

        return self.get_quote_list(stock, 'previous_close')


    def previous_close_date(self, stock=''):
        """Get previous closing date for a stock

            Note:
                queries `quote` endpoint, dict wrapper

            Args:
                stock (str): stock ticker

            Returns:
                (str): previous close date
        """

        return self.get_quote_list(stock, 'previous_close_date')


    def adjusted_previous_close(self, stock=''):
        """Get adjusted previous closing price for a stock

            Note:
                queries `quote` endpoint, dict wrapper

            Args:
                stock (str): stock ticker

            Returns:
                (float): adjusted previous closing price
        """

        return self.get_quote_list(stock, 'adjusted_previous_close')


    def symbol(self, stock=''):
        """Get symbol for a stock

            Note:
                queries `quote` endpoint, dict wrapper

            Args:
                stock (str): stock ticker

            Returns:
                (str): stock symbol
        """

        return self.get_quote_list(stock, 'symbol')


    def last_updated_at(self, stock=''):
        """Get last update datetime

            Note:
                queries `quote` endpoint, dict wrapper

            Args:
                stock (str): stock ticker

            Returns:
                (str): last update datetime
        """

        return self.get_quote_list(stock, 'last_updated_at')


    def last_updated_at_datetime(self, stock=''):
        """Get last updated datetime

            Note:
                queries `quote` endpoint, dict wrapper
                `self.last_updated_at` returns time as `str` in format: 'YYYY-MM-ddTHH:mm:ss:000Z'

            Args:
                stock (str): stock ticker

            Returns:
                (datetime): last update datetime

        """

        #Will be in format: 'YYYY-MM-ddTHH:mm:ss:000Z'
        datetime_string = self.last_updated_at(stock)
        result = dateutil.parser.parse(datetime_string)

        return result

    def get_account(self):
        """Fetch account information

            Returns:
                (:obj:`dict`): `accounts` endpoint payload
        """

        res = self.session.get(endpoints.accounts(), timeout=300)
        res.raise_for_status()  # auth required
        res = res.json()

        return res['results'][0]


    def get_url(self, url):
        """
            Flat wrapper for fetching URL directly
        """

        return self.session.get(url, timeout=300).json()

    def get_popularity(self, stock=''):
        """Get the number of robinhood users who own the given stock

            Args:
                stock (str): stock ticker

            Returns:
                (int): number of users who own the stock
        """
        stock_instrument = self.get_url(self.quote_data(stock)["instrument"])["id"]
        return self.get_url(endpoints.instruments(stock_instrument, "popularity"))["num_open_positions"]

    def get_tickers_by_tag(self, tag=None):
        """Get a list of instruments belonging to a tag

            Args: tag - Tags may include but are not limited to:
                * top-movers
                * etf
                * 100-most-popular
                * mutual-fund
                * finance
                * cap-weighted
                * investment-trust-or-fund

            Returns:
                (List): a list of Ticker strings
        """
        instrument_list = self.get_url(endpoints.tags(tag))["instruments"]
        return [self.get_url(instrument)["symbol"] for instrument in instrument_list]

    ###########################################################################
    #                           GET OPTIONS INFO
    ###########################################################################

    def get_options(self, stock, expiration_dates, option_type):
        """Get a list (chain) of options contracts belonging to a particular stock

            Args: stock ticker (str), list of expiration dates to filter on (YYYY-MM-DD), and whether or not its a 'put' or a 'call' option type (str).

            Returns:
                Options Contracts (List): a list (chain) of contracts for a given underlying equity instrument
        """
        instrumentid = self.get_url(self.quote_data(stock)["instrument"])["id"]
        if(type(expiration_dates) == list):
            _expiration_dates_string = expiration_dates.join(",")
        else:
            _expiration_dates_string = expiration_dates
        chain_id = self.get_url(endpoints.chain(instrumentid))["results"][0]["id"]
        return [contract for contract in self.get_url(endpoints.options(chain_id, _expiration_dates_string, option_type))["results"]]

    def get_option_market_data(self, optionid):
            """Gets a list of market data for a given optionid.
            Args: (str) option id
            Returns: dictionary of options market data.
            """
            market_data = {}
            try:
                market_data = self.get_url(endpoints.option_market_data(optionid)) or {}
            except requests.exceptions.HTTPError:
                raise RH_exception.InvalidOptionId()
            return market_data

    def options_owned(self):
        options = self.get_url(endpoints.options_base() + "positions/?nonzero=true")
        options = options['results']
        return options

    def get_option_marketdata(self, instrument):
        info = self.get_url(endpoints.market_data() + "options/?instruments=" + instrument)
        return info['results'][0]

    def get_option_chainid(self, symbol):
        stock_info = self.get_url(self.endpoints['instruments'] + "?symbol=" + symbol)
        stock_id = stock_info['results'][0]['id']
        params = {}
        params['equity_instrument_ids'] = stock_id
        chains = self.get_url(endpoints.options_base() + "chains/", params = params)
        chains = chains['results']
        chain_id = None

        for chain in chains:
            if chain['can_open_position'] == True:
                chain_id = chain['id']

        return chain_id

    def get_option_quote(self, arg_dict):
        chain_id = self.get_option_chainid(arg_dict.pop('symbol', None))
        arg_dict['chain_id'] = chain_id
        option_info = self.get_url(self.endpoints.options_base()+ "instruments/", params = arg_dict)
        option_info = option_info['results']
        exp_price_list = []

        for op in option_info:
            mrkt_data = self.get_option_marketdata(op['url'])
            op_price = mrkt_data['adjusted_mark_price']
            exp = op['expiration_date']
            exp_price_list.append((exp, op_price))

        exp_price_list.sort()

        return exp_price_list


    ###########################################################################
    #                           GET FUNDAMENTALS
    ###########################################################################

    def get_fundamentals(self, stock=''):
        """Find stock fundamentals data

            Args:
                (str): stock ticker

            Returns:
                (:obj:`dict`): contents of `fundamentals` endpoint
        """

        #Prompt for stock if not entered
        if not stock:   # pragma: no cover
            stock = input("Symbol: ")

        url = str(endpoints.fundamentals(str(stock.upper())))

        #Check for validity of symbol
        try:
            req = requests.get(url, timeout=300)
            req.raise_for_status()
            data = req.json()
        except requests.exceptions.HTTPError:
            raise RH_exception.InvalidTickerSymbol()


        return data


    def fundamentals(self, stock=''):
        """Wrapper for get_fundamentlals function """

        return self.get_fundamentals(stock)


    ###########################################################################
    #                           PORTFOLIOS DATA
    ###########################################################################

    def portfolios(self):
        """Returns the user's portfolio data """

        req = self.session.get(endpoints.portfolios(), timeout=300)
        req.raise_for_status()

        return req.json()['results'][0]


    def adjusted_equity_previous_close(self):
        """Wrapper for portfolios

            Returns:
                (float): `adjusted_equity_previous_close` value

        """

        return float(self.portfolios()['adjusted_equity_previous_close'])


    def equity(self):
        """Wrapper for portfolios

            Returns:
                (float): `equity` value
        """

        return float(self.portfolios()['equity'])


    def equity_previous_close(self):
        """Wrapper for portfolios

            Returns:
                (float): `equity_previous_close` value
        """

        return float(self.portfolios()['equity_previous_close'])


    def excess_margin(self):
        """Wrapper for portfolios

            Returns:
                (float): `excess_margin` value
        """

        return float(self.portfolios()['excess_margin'])


    def extended_hours_equity(self):
        """Wrapper for portfolios

            Returns:
                (float): `extended_hours_equity` value
        """

        try:
            return float(self.portfolios()['extended_hours_equity'])
        except TypeError:
            return None


    def extended_hours_market_value(self):
        """Wrapper for portfolios

            Returns:
                (float): `extended_hours_market_value` value
        """

        try:
            return float(self.portfolios()['extended_hours_market_value'])
        except TypeError:
            return None


    def last_core_equity(self):
        """Wrapper for portfolios

            Returns:
                (float): `last_core_equity` value
        """

        return float(self.portfolios()['last_core_equity'])


    def last_core_market_value(self):
        """Wrapper for portfolios

            Returns:
                (float): `last_core_market_value` value
        """

        return float(self.portfolios()['last_core_market_value'])


    def market_value(self):
        """Wrapper for portfolios

            Returns:
                (float): `market_value` value
        """

        return float(self.portfolios()['market_value'])

    @login_required
    def order_history(self, orderId=None):
        """Wrapper for portfolios
            Optional Args: add an order ID to retrieve information about a single order.
            Returns:
                (:obj:`dict`): JSON dict from getting orders
        """

        return self.session.get(endpoints.orders(orderId), timeout=300).json()
    @login_required
    
    def options_order_history(self, orderId=None):
        """Wrapper for portfolios
            Optional Args: add an order ID to retrieve information about a single order.
            Returns:
                (:obj:`dict`): JSON dict from getting orders
        """

        return self.session.get(endpoints.options_orders(orderId), timeout=300).json()


    def dividends(self):
        """Wrapper for portfolios

            Returns:
                (:obj: `dict`): JSON dict from getting dividends
        """

        return self.session.get(endpoints.dividends(), timeout=300).json()


    ###########################################################################
    #                           POSITIONS DATA
    ###########################################################################

    def positions(self):
        """Returns the user's positions data

            Returns:
                (:object: `dict`): JSON dict from getting positions
        """

        return self.session.get(endpoints.positions(), timeout=300).json()


    def securities_owned(self):
        """Returns list of securities' symbols that the user has shares in

            Returns:
                (:object: `dict`): Non-zero positions
        """

        return self.session.get(endpoints.positions() + '?nonzero=true', timeout=300).json()