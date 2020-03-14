"""
DataHandler class
This is a class hierarchy that allows both historic backtesting and live trading, via the same class interface
"""


import datetime
import os, os.path
import pandas as pd

from abc import ABCMeta, abstractmethod

from event import MarketEvent

class DataHandler(object):
	"""
	DataHandler is an abstract base class providing an interface for
	all subsequent (inherited) data handlers (both live and historic).

	The goal of a (derived) DataHandler object is to output a generated
	set of bars (OLHCVI) for each symbol requested.

	This will replicate how a live strategy would function as current
	market data would be sent "down the pipe". Thus a historic and live
	system will be treated identically by the rest of the backtesting suite.
	"""

	# mark as abstract base class(ABC)
	__metaclass__ = ABCMeta

	# pure virtual method (must be override)
	@abstractmethod
	def get_latest_bars(self, symbol, N=1):
		"""
		:param symbol: a list of bars of a symbol
		:param N: numbers of bar to be return
		:return: the last N bars from the symbol list, or fewer if less bars are available
		"""
		raise NotImplementedError("Should implement get_latest_bars()")

	@abstractmethod
	def update_bars(self):
		"""
		Pushes the latest bar to the latest symbol structure for all symbols in the symbol list
		:return:
		"""
		raise NotImplementedError("Should implement update_bars()")

class HistoricCSVDataHandler(DataHandler):
	"""
	Derived class to read CSV files for each requested symbol from disk and provide an interface
	to obtain the "latest" bar in a manner identical to a live trading interface
	"""
	def __init__(self, events, csv_dir, symbol_list):
		"""
		Initialises the historic data handler by requesting the location of the CSV files and a list of symbols.

		:param events: The Event Queue
		:param csv_dir: Absolute directory path to the CSV files.
		:param symbol_list: A list of symbol strings, which are all assumed of the form 'symbol.csv'
		"""
		self.events = events
		self.csv_dir = csv_dir
		self.symbol_list = symbol_list

		self.symbol_data = {}
		self.latest_symbol_data = {}
		self.continue_backtest = True

		self._open_convert_csv_files()

	# private function
	def _open_convert_csv_files(self):
		"""
		Opens the CSV files from the data directory, converting
		them into pandas DataFrames within a symbol dictionary.

		For this handler it will be assumed that the data is
		taken from DTN IQFeed. Thus its format will be respected.
		"""
		comb_index = None
		for s in self.symbol_list:
			# Load the CSV file with no header information, indexed on date
			self.symbol_data[s] = pd.io.parsers.read_csv(
				os.path.join(self.csv_dir, '%s.csv' % s),
				header=0, index_col=0,
				names=['datetime', 'open', 'low', 'high', 'close', 'volume', 'oi']
			)

			# Combine the index to pad forward values
			if comb_index is None:
				comb_index = self.symbol_data[s].index
			else:
				comb_index.union(self.symbol_data[s].index)

			# Set the latest symbol_data to None
			self.latest_symbol_data[s] = []

		# Reindex the dataframes
		for s in self.symbol_list:
			self.symbol_data[s] = self.symbol_data[s].reindex(index=comb_index, method='pad').iterrows()

	def _get_new_bar(self, symbol):
		"""
		return the latest bar from the data feed as a tuple iterator
		:param symbol:
		:return: tuple of (sybmbol, datetime, open, low, high, close, volume)
		"""
		for b in self.symbol_data:
			yield tuple([symbol,
						 datetime.datetime.strptime(b[0], '%Y-%m-%d %H:%M:%S'),
						 b[1][0], b[1][1], b[1][2], b[1][3], b[1][4]])

	# public function
	def get_latest_bars(self, symbol, N=1):
		"""
		function overrided
		:param symbol: a list of bars of a symbol
		:param N: numbers of bar to be return
		:return: the last N bars from the symbol list, or fewer if less bars are available
		"""
		try:
			bar_list = self.latest_symbol_data[symbol]
		except KeyError:
			print("That symbol %s is not available in the historical data set." % (symbol))
		else:
			return bar_list[-N:]


	def update_bars(self):
		"""
		overrided function
		:return:
		"""
		for s in self.symbol_list:
			try:
				bar = self._get_new_bar(s).next()
			except StopIteration:
				self.continue_backtest = False
			else:
				if bar is not None:
					self.latest_symbol_data[s].append(bar)
		self.events.put(MarketEvent())