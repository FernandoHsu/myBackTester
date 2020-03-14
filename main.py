
### Declare the components with respective parameters
bars = DataHandler(..)
strategy = Strategy(..)
port = Portfolio(..)
broker = ExecutionHandler(..)

### Outer loops: update market data if live trading
while True:
	# Update the bars (specific backtest code, as opposed to live trading)
	if bars.continue_backtest == True:
		bars.update_bars()
	else:
		break

	### Inner loops: handle event queue object
	while True:
		try:
			event = events.get(False)
		except Queue.Empty:
			break
		else:
			if event is not None:
				if event.type == 'MARKET':
					strategy.caculate_signal(event)
					port.update_timeindex(event)
				elif event.type == 'SIGNAL':
					port.update_signal(event)
				elif event.type == 'ORDER':
					broker.execute_order(event)
				elif event.type == 'FILL':
					port.update_fill(event)
	# 1 min break
	time.sleep(60)


