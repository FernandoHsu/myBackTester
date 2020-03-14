"""

MarketEvent
This is triggered when the outer while loop begins a new "heartbeat".
It occurs when the DataHandler object receives a new update of market data for any symbols which are currently being tracked.
It is used to trigger the Strategy object generating new trading signals. The event object simply contains an
identification that it is a market event, with no other structure.

SignalEvent
The Strategy object utilises market data to create new SignalEvents. The SignalEvent contains a ticker symbol,
a timestamp sor when it was generated and a direction (long or short). The SignalEvents are utilised by the Portfolio
object as advice for how to trade.

* OrderEvent
When a Portfolio object receives SignalEvents it assesses them in the wider context of the portfolio,
in terms of risk and position sizing. This ultimately leads to OrderEvents that will be sent to an ExecutionHandler.

* FillEvent
When an ExecutionHandler receives an OrderEvent it must transact the order.
Once an order has been transacted it generates a FillEvent, which describes the cost of purchase or sale
as well as the transaction costs, such as fees or slippage.

"""

class Event(object):
	"""
    Event is base class providing an interface for all subsequent
    (inherited) events, that will trigger further events in the
    trading infrastructure.
    """
	pass


class MarketEvent(Event):
	"""
	It occurs when the DataHandler object receives a new update of market data for any symbols
	which are currently being tracked.
	It is used to trigger the Strategy object generating new trading signals.
    """

	def __init__(self):
		"""
		Initialises the MarketEvent.
		"""
		self.type = 'MARKET'


class SignalEvent(Event):
	"""
	Handles the event of sending a Signal
	Created by strategy object and received by portfolio object
	"""
	def __init__(self,symbol, datetime, signal_type):
		"""
		Initize the SingalEvent
		:param symbol: the ticker symbol, e.g. AAPL
		:param datetime: '%%Y-%%M-%%D'
		:param signal_type: 'LONG', 'SHORT', 'EXIT'
		"""
		assert signal_type == 'LONG' or signal_type == 'SHORT' or signal_type == 'EXIT', 'Input value error: signal_type'

		self.type = 'SIGNAL'
		self.symbol = symbol
		self.datetime = datetime
		self.signal_type = signal_type

class OrderEvent(Event):
	"""
	Handle the event of sending an Order to an execution system.
	"""

	def __init__(self, symbol, order_type, quantity, direction):
		"""
		Initialize the OrderEvent

		:param symbol: the instrument to trade, e.g. AAPL
		:param order_type: 'MKT' or 'LMT' for market or limit
		:param quantity: Non-negative integar for quantity
		:param direction: 'BUY' or 'SELL' for long or short
		"""
		assert order_type == 'MKT' or order_type == 'LMT', 'Input value error: order_type'
		assert quantity >= 0, 'Input value error: quantity'
		assert isinstance(quantity, int), 'Input type error: quantity'
		assert direction == 'BUY' or direction == 'SELL', 'Input value error: direction'

	def print_order(self):
		"""
		Outputs the values within the Order.
		"""
		print("Order: Symbol=%s, Type=%s, Quantity=%s, Direction=%s" % (self.symbol, self.order_type, self.quantity, self.direction))

class FillEvent(Event):
	"""
	Encapsulates the notation of a Filled Order, as returned from a brokerage.
	Stroes the quantity of an instrument actually filled and at what price.
	In addition, stores the commission of the trade from the brokerage.
	"""

	def __init__(self, timeindex, symbol, exchange, quantity, direction, fill_cost, commission=None):
		"""
		If commission is not provided, the Fill object will calculate it based on the trade size and
		Interactive Brokers fees.

		:param timeindex: the bar-resolution when the order was filled.
		:param symbol: The instrument which was filled.
		:param exchange: The exchange where the order was filled.
		:param quantity: The filled quantity.
		:param direction: The direction of fill ('BUY' or 'SELL')
		:param fill_cost: The holdings value in dollars.
		:param commission: An optional commission sent from IB.
		"""
		self.type = 'FILL'
		self.timeindex = timeindex
		self.symbol = symbol
		self.exchange = exchange
		self.quantity = quantity
		self.direction = direction
		self.fill_cost = fill_cost

		# caculate commision
		if commission is None:
			self.commission = self.caculate_ib_commission()
		else:
			self.commission = commission

	def caculate_ib_commission(self):
		"""
		Calculates the fees of trading based on an Interactive Brokers fee structure for API, in USD.
		This does not include exchange or ECN fees.

		Based on "US API Directed Orders":
		https://www.interactivebrokers.com/en/index.php?f=commission&p=stocks2

		:return: cost of broker commission
		"""
		full_cost = 1.3
		if self.quantity <= 500:
			full_cost = max(1.3, 0.013 * self.quantity)
		else:
			full_cost = max(1.3, 0.008 * self.quantity)
		full_cost = min(full_cost, 0.5 / 100.0 * self.quantity * self.fill_cost)
		return full_cost