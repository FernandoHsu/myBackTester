"""
Portfolio do the following things:
* generate signal by SignalEvent objects: These signal are used by a portfolio object in order to make decisions on whether to send orders
* manage order by OrderEvent objects: optimize portfolio by risk factors and position sizing techniques
* update holding by FillEvent objects: update position and value of holding equity
"""
import datetime
import numpy as np
import pandas as pd
import queue

from abc import ABCMeta, abstractmethod
from math import floor

from event import FillEvent, OrderEvent
from performance import get_sharpe_ratio, get_max_drawdowns

class Portfolio(object):
	"""
	The Portfolio class handles the positions and market
	value of all instruments at a resolution of a "bar",
	i.e. secondly, minutely, 5-min, 30-min, 60 min or EOD.
	"""

	__metaclass__ = ABCMeta

	@abstractmethod
	def update_signal(self, event):
		"""
		Acts on a SignalEvent to generate new orders
		based on the portfolio logic.
		"""
		raise NotImplementedError("Should implement update_signal()")

	@abstractmethod
	def update_fill(self, event):
		"""
		Updates the portfolio current positions and holdings
		from a FillEvent.
		"""
		raise NotImplementedError("Should implement update_fill()")

class NaivePortfolio(Portfolio):
    """
	The NaivePortfolio object is designed to send orders to
	a brokerage object with a constant quantity size blindly,
	without any risk management or position sizing.
	It is used to test simpler strategies such as BuyAndHoldStrategy.
	"""
	def __init__(self, bars, events, start_date, init_capital=100000.0):
		"""
		:param bars: The DataHandler object with current market data.
		:param events: The Event Queue object.
		:param start_date: The start date (bar) of the portfolio.
		:param init_capital: The starting capital in USD.
		"""
		self.bars = bars
		self.events = events
		self.symbol_list = self.bars.symbol_list
		self.start_date = start_date
		self.init_capital = init_capital

		self.all_position = self.construct_all_positions()
		self.current_positions = dict( (k,v) for k,v in [(s,0) for s in self.symbol_list] )

		self.all_holdings = self.construct_all_holdings()
		self.current_holdings = self.construct_current_holdings()
		self.equity_curve = None

	def construct_all_positions(self):
		"""
		Constructs the positions list using the start_date
        to determine when the time index will begin.

		:return:
		"""
		d = dict( (k,v) for k,v in [(s,0) for s in self.symbol_list] )
		d['datetime'] = self.start_date
		return [d]

	def construct_all_holdings(self):
		"""
		Constructs the holdings list using the start_date
        to determine when the time index will begin.

		:return:
		"""
		d = dict( (k,v) for k,v in [(s,0) for s in self.symbol_list] )
		d['datetime'] = self.start_date
		d['cash'] = self.init_capital
		d['commission'] = 0.0
		d['total']  = self.init_capital
		return [d]


	def construct_current_holdings(self):
		"""
		This constructs the dictionary which will hold the instantaneous
        value of the portfolio across all symbols.

		:return:
		"""
		d = dict( (k,v) for k,v in [(s,0) for s in self.symbol_list] )
		d['cash'] = self.init_capital
		d['commission'] = 0.0
		d['total']  = self.init_capital
		return [d]

	def update_timeindex(self, event):
		"""
        Adds a new record to the positions matrix for the current market data bar.
        This reflects the PREVIOUS bar, i.e. all current market data at this stage is known (OLHCVI).
		Makes use of a MarketEvent from the events queue.

		:param event:
		:return:
		"""
		bars = {sym:self.bars.get_latest_bars(sym, N=1) for sym in self.symbol_list}

		# update positions
		dp = dict((k, v) for k, v in [(s, 0) for s in self.symbol_list])
		dp['datetime'] = bars[self.symbol_list[0]][0][1]
		for s in self.symbol_list:
			dp[s] = self.current_positions[s]
		self.all_position.append(dp)

		# Update holdings
		dh = dict((k, v) for k, v in [(s, 0) for s in self.symbol_list])
		dh['datetime'] = bars[self.symbol_list[0]][0][1]
		dh['cash'] = self.current_holdings['cash']
		dh['commission'] = self.current_holdings['commission']
		dh['total'] = self.current_holdings['cash']
		for s in self.symbol_list:
			# # Approximation to the real value by close price
			market_val = self.current_positions[s] * bars[s][0][5]
			dh[s] = market_val
			dh['total'] += market_val
		self.all_holdings.append(dh)

	def update_positions_from_fill(self, fill):
		"""
		Takes a FilltEvent object and updates the position matrix
        to reflect the new position.

		:param fill: The FillEvent object to update the positions with.
		:return:
		"""
		# Check whether the fill is a buy or sell
		fill_dir = 0
		if fill.direction == 'BUY':
			fill_dir = 1
		if fill.direction == 'SELL':
			fill_dir = -1

		# Update positions list with new quantities
		self.current_positions[fill.symbol] += fill_dir * fill.quantity

	def update_holdings_from_fill(self, fill):
		"""
		Takes a FillEvent object and updates the holdings matrix
        to reflect the holdings value.

		:param fill: The FillEvent object to update the holdings with.
		:return:
		"""
		# Check whether the fill is a buy or sell
		fill_dir = 0
		if fill.direction == 'BUY':
			fill_dir = 1
		if fill.direction == 'SELL':
			fill_dir = -1

		# Update holdings list with new quantities
		fill_price = self.bars.get_latest_bars(fill.symbol)[0][5]  # Close price
		fill_cost = fill_dir * fill_price * fill.quantity
		self.current_holdings[fill.symbol] += fill_cost
		self.current_holdings['commission'] += fill.commission
		self.current_holdings['cash'] -= (fill_cost + fill.commission)
		self.current_holdings['total'] -= (fill_cost + fill.commission)


	def update_fill(self, event):
		"""
		Updates the portfolio current positions and holdings from a FillEvent.
		:param event: a FillEvent
		:return:
		"""
		if event.type == 'FILL':
			self.update_holdings_from_fill(event)
			self.update_positions_from_fill(event)


	def update_signal(self, event):
		"""
		Acts on a SignalEvent to generate new orders based on the portfolio logic. Then put it in Queue.
		:param event: a SignalEvent
		:return:
		"""
		if event.type == 'SIGNAL':
			order_event = self.generate_naive_order(event)
			self.events.put(order_event)

	def generate_naive_order(self, signal):
		"""
		Simply transacts an OrderEvent object as a constant quantity sizing of the signal object,
		, without risk management or position sizing considerations.

		:param signal: an SignalEvent object
		:return: an OrderEvent object
		"""
		order = None
		symbol = signal.symbol
		direction = signal.signal_type
		strength = signal.strength

		mkt_quantity = floor(100 * strength)
		cur_quantity = self.current_positions[symbol]
		order_type = 'MKT'

		if direction == 'LONG' and cur_quantity == 0:
			order = OrderEvent(symbol, order_type, mkt_quantity, 'BUY')
		if direction == 'SHORT' and cur_quantity == 0:
			order = OrderEvent(symbol, order_type, mkt_quantity, 'SELL')

		if direction == 'EXIT' and cur_quantity > 0:
			order = OrderEvent(symbol, order_type, abs(cur_quantity), 'SELL')
		if direction == 'EXIT' and cur_quantity < 0:
			order = OrderEvent(symbol, order_type, abs(cur_quantity), 'BUY')

		return order

	def create_equity_curve_dataframe(self):
		"""
		Creates a pandas DataFrame from the all_holdings
        list of dictionaries.
		:return:
		"""
		curve = pd.DataFrame(self.all_holdings)
		curve.set_index('datetime', inplace=True)
		curve['returns'] = curve['total'].pct_change()
		curve['equity_curve'] = (1.0+curve['returns']).cumprod()
		self.equity_curve = curve

	def output_summary_stats(self):
		"""
		Creates a list of summary statistics for the portfolio such
		as Sharpe Ratio and drawdown information.
		"""
		self.create_equity_curve_dataframe()
		total_return = self.equity_curve['equity_curve'][-1]
		returns = self.equity_curve['returns']
		pnl = self.equity_curve['equity_curve']

		sharpe_ratio = get_sharpe_ratio(returns)
		max_dd, dd_duration = get_max_drawdowns(pnl)

		return [("Total Return", "%0.2f%%" % ((total_return - 1.0) * 100.0)),
				 ("Sharpe Ratio", "%0.2f" % sharpe_ratio),
				 ("Max Drawdown", "%0.2f%%" % (max_dd * 100.0)),
				 ("Drawdown Duration", "%d" % dd_duration)]