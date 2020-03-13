"""
Source: https://www.quantstart.com/articles/Event-Driven-Backtesting-with-Python-Part-VIII
See also
- download Trader Workstation and create an Interactive Brokers demo account
  (http://www.quantstart.com/articles/Interactive-Brokers-Demo-Account-Signup-Tutorial)
- how to create a basic interface to the IB API using IbPy
  (http://www.quantstart.com/articles/Using-Python-IBPy-and-the-Interactive-Brokers-API-to-Automate-Trades)


The essential idea of the IBExecutionHandler class is to receive OrderEvent instances from the events queue
and then to execute them directly against the Interactive Brokers order API using the IbPy library.
The class will also handle the "Server Response" messages sent back via the API. At this stage, the only action
taken will be to create corresponding FillEvent instances that will then be sent back to the events queue.

Notice that this class is only for example hence not includes:
- execution optimisation logic
- sophisticated error handling
"""

import datetime
import time

from ib.ext.Contract import Contract
from ib.ext.Order import Order
from ib.opt import ibConnection, message

from event import FillEvent, OrderEvent
from execution import ExecutionHandler

class IBExecutionHandler(ExecutionHandler):
    """
    Handles order execution via the Interactive Brokers
    API, for use against accounts when trading live
    directly.
    """
	def __init__(self, events, order_routing="SMART", currency="USD"):
		"""
		:param events:
		:param order_routing:
		:param currency:
		"""
		self.events = events
		self.order_routing = order_routing
		self.currency = currency
		self.fill_dict = {}

		self.tws_conn = self.create_tws_connection()
		self.order_id = self.create_init_order_id()
		self.register_handlers()

	def _error_handler(self, msg):
		"""
		Handles the capturing of error messages
		:param msg:
		:return:
		"""
		print("Server Error: %s" % msg)

	def _reply_handler(self, msg):
		"""
		Handles of server replies
		:param msg:
		:return:
		"""
		# Handle open order orderId processing
		if msg.typeName == "openOrder" and \
			msg.orderId == self.order_id and \
			not self.fill_dict.has_key(msg.orderId):
			self.create_fill_dict_entrp(msg)

		# Handle Fills
		if msg.typeName == "orderStatus" and \
			msg.status == "Filled" and \
			self.fill_dict[msg.orderId]["filled"] == False:
			self.create_fill(msg)
		print("Server Response: %s, %s\n" % msg.typeName, msg)

	def create_tws_connection(self):
		"""
    	Connect to the Trader Workstation (TWS)
    	- port: 7496
    	- clientId: 10

    	The clientId is chosen by us and we will need  separate IDs for both the execution connection and
    	market data connection, if the latter is used elsewhere.
    	"""
		tws_conn = ibConnection()
		tws_conn.connect()
		return tws_conn

	def create_init_order_id(self):
		"""
        Creates the initial order ID used for Interactive
        Brokers to keep track of submitted orders.
        """
		# There is scope for more logic here, but we
		# will use "1" as the default for now.
		return 1


	def register_handlers(self):
		"""
        Register the error and server reply
        message handling functions.
        """
		# Assign the error handling function defined above
        # to the TWS connection
        self.tws_conn.register(self._error_handler, 'Error')

		# Assign all of the server reply messages to the
        # reply_handler function defined above
        self.tws_conn.registerAll(self._reply_handler)

	def create_contract(self, symbol, sec_type, exch, prim_exch, curr):
		"""
		Create a Contract object defining what will
        be purchased, at which exchange and in which currency.

		:param symbol - The ticker symbol for the contract
		:param sec_type - The security type for the contract ('STK' is 'stock')
		:param exch - The exchange to carry out the contract on
		:param prim_exch - The primary exchange to carry out the contract on
		:param curr - The currency in which to purchase the contract
		:return:
		"""
		contract = Contract()
		contract.m_symbol = symbol
		contract.m_secType = sec_type
		contract.m_exchange = exch
		contract.m_primaryExch = prim_exch
		contract.m_currency = curr
		return contract

	def create_order(self, order_type, quantity, action):
		"""
		Create an Order object (Market/Limit) to go long/short

		:param order_type: 'MKT', 'LMT' for market or limit order
		:param quantity: Integral numbers of assets to order
		:param action: 'BUY' or 'SELL'
		:return: order object
		"""
		order = Order()
		order.m_orderType = order_type
		order.m_totalQuantity = quantity
		order.m_action = action
		return order

	def create_fill_dict_entry(self, msg):
		"""
		Creates an entry in the Fill Dictionary that lists orderIds and provides security information. This is
        needed for the event-driven behaviour of the IB server message behaviour.

		:param msg:
		:return:
		"""
		self.fill_dict[msg.orderId] = {
			"symbol":msg.contract.m_symbol,
			"exchange":msg.contract.m_exchange,
			"direction":msg.order.m_action,
			"filled":False
		}

	def create_fill(self, msg):
		"""
		Handles the creation of the FillEvent that will be placed onto the events queue subsequent to an order
        being filled.

		:param msg:
		:return:
		"""
		fd = self.fill_dict[msg.orderId]

		# Prepare the fill data
		symbol = fd["symbol"]
		exchange = fd["exchange"]
		direction = fd["direction"]
		filled = msg.filled
		fill_cost = msg.avgFillPrice

		# Create a fill event object
		fill_event = FillEvent(
			datetime.datetime.utcnow(), symbol,
			exchange, filled, direction, fill_cost
		)

		# Make sure that multiple messages don't create
		# additional fills.
		self.fill_dict[msg.orderId]["filled"] = True

		# Place the fill event onto the event queue
		self.events.put(fill_event)

	def execute_order(self, event):
		"""
		Creates the necessary InteractiveBrokers order object and submits it to IB via their API.
        The results are then queried in order to generate a corresponding Fill object, which is placed back on
        the event queue.

		:param event: Order event object
		:return:
		"""
		if event.type == 'ORDER':
			# Prepare the parameters for the asset order
			asset = event.symbol
			asset_type = "STK"
			order_type = event.order_type
			quantity = event.quantity
			direction = event.direction

			# Create the Interactive Brokers contract via the passed Order event
            ib_contract = self.create_contract(
                asset, asset_type, self.order_routing,
                self.order_routing, self.currency
            )

			# Create the Interactive Brokers order via the passed Order event
            ib_order = self.create_order(
                order_type, quantity, direction
            )

			# Use the connection to the send the order to IB
            self.tws_conn.placeOrder(
                self.order_id, ib_contract, ib_order
            )

			# NOTE: This following line is crucial, it ensures the order goes through!
            time.sleep(1)
			self.order_id += 1