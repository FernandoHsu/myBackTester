import numpy as np
import pandas as pd

def get_sharpe_ratio(returns, risk_free=0, periods='Daily'):
	"""
	Create the Sharpe ratio for the strategy, based on a benchmark of zero

	:param returns - A pandas Series representing period percentage returns.
	:param periods - Daily (252), Hourly (252*6.5), Minutely(252*6.5*60) etc.
	:return:
	"""
	if not returns:
		raise ValueError('Input value returns is None.')
	assert periods == 'Daily' or periods == 'Hour' or periods == 'Minute', ''
	assert risk_free >= 0 and risk_free <= 1, 'risk_free rate must lie in [0,1]'

	period = {'Daily': 252, 'Hour': 252*6.5, 'Minute': 252*6.5*60}
	return np.sqrt(period[periods]) * np.mean(returns) / np.std(returns)

def create_drawdowns(equity_curve):
	"""

	:param equity_curve - A pandas Series representing period percentage returns.
	:return: res - list of tuple(drawdown, duration) sorted by drawdown in descending order
	"""
	# Set up the High Water Mark
	# Then create the drawdown and duration series
	hwm = [0]
	drawdown = pd.Series(index=equity_curve.index)
	duration = pd.Series(index=equity_curve.index)

	# Loops over the index range
	for t,_ in enumerate(equity_curve.index):
		# update current high water mark
		cur_hwm = max(hwm[t-1], equity_curve[t])
		hwm.append(cur_hwm)
		# update current drawdown and duration
		drawdown[t] = hwm[t] - equity_curve[t]
		duration[t] = 0 if drawdown[t]==0 else duration[t-1]+1

	# sort by drawdown value in descending order
	res = sorted(zip(drawdown, duration), key=lambda obj:obj[0], reverse=True)
	return res

def get_max_drawdowns(equity_curve):
	"""

	:param equity_curve - A pandas Series representing period percentage returns.
	:return: drawdown, duration - Highest peak-to-trough drawdown and duration.
	"""
	if not equity_curve:
		raise ValueError('Input value equity_curve is None.')
	res = create_drawdowns(equity_curve)
	return res[0][0], res[0][1]