# -*- coding: utf-8 -*-
"""Benchmarking.ipynb

Automatically generated by Colaboratory.

Original file is located at
    https://colab.research.google.com/drive/1D9FIkQEV3kcyv8rpXIRfq9wz84cOlVbj

# Benchmarking

## Setup
"""

from google.colab import drive
drive.mount('/content/drive')

# Commented out IPython magic to ensure Python compatibility.
# %cd /content/drive/MyDrive/Dissertation/4_Benchmarking

import os
import json
import pandas as pd
import numpy as np

"""## Utils"""

# calculate profit
def calculate_profit(position_size, trade_direction, entry_price, exit_price):

    fixed_t_cost = 0.0001  # hopefully we can increase this at some point
    size_multiplier = 1.0  # this is a hyperparameter we can play around with
    position_size = position_size * size_multiplier

    # fixed transaction cost
    t_cost = fixed_t_cost * position_size

    price_change = (exit_price - entry_price) / entry_price

    if trade_direction == 1:
        profit = price_change * position_size
    elif trade_direction == -1:
        profit = -price_change * position_size
    else:
        return 0

    trade_profit = profit - t_cost

    return trade_profit

# percentage change
def pct_change(old_value, new_value):
    change = new_value - old_value
    percentage_change = (change / old_value)
    return percentage_change

# metrics class
class Metrics(object):
    def __init__(self, marginal_returns, total_return):
        self.returns = marginal_returns
        self.total_return = total_return

    def risk(self):
        return np.std(self.returns)

    def max_drawdown(self):
        cumulative_returns = [1]
        [cumulative_returns.append(cumulative_returns[-1] * (1 + r)) for r in self.returns]
        try:
            max_drawdown = max([(max(cumulative_returns[:i+1]) - cumulative_returns[i]) /
                            max(cumulative_returns[:i+1]) for i in range(1, len(cumulative_returns))])
        except:
            return 0
        return max_drawdown

    def calmar_ratio(self):
        md = self.max_drawdown()
        if md == 0:
            return self.total_return
        else:
            return self.total_return / md

    def win_rate(self):
        positive_returns = [r for r in self.returns if r > 0]
        try:
            win_rate = len(positive_returns) / len(self.returns)
        except:
            return 0
        return win_rate

    def average_return(self):
        try:
            return np.mean(self.returns)
        except:
            return 0

    def average_pos_returns(self):
        try:
            positive_returns = [r for r in self.returns if r > 0]
            return sum(positive_returns) / len(positive_returns)
        except:
            return 0

"""## Buy & Hold"""

result_dict = {}

for pair in ['AUDUSD', 'EURGBP', 'EURUSD', 'USDCAD']:

    # load data
    starting_balance = 100

    df_start = pd.read_parquet(f'../1_DataTransformation/TransformedData/0.00013/{pair}/Window_0/test.parquet.gzip')
    if pair == 'EURUSD':
        df_finish = pd.read_parquet(f'../1_DataTransformation/TransformedData/0.00013/{pair}/Window_14/test.parquet.gzip')
    else:
        df_finish = pd.read_parquet(f'../1_DataTransformation/TransformedData/0.00013/{pair}/Window_18/test.parquet.gzip')

    # enter buy trade on first price
    entry_price = df_start['DCC'].iloc[0]
    exit_price = df_finish['DCC'].iloc[-1]

    # exit trade on last price
    profit = calculate_profit(starting_balance, 1, entry_price, exit_price)
    final_balance = starting_balance + profit

    # record return
    total_return = pct_change(starting_balance, final_balance) * 100
    result_dict['Return (%)'] = total_return

    print(f'{pair}: {total_return:.2f}%')

    # save results
    result_dir = f'./Results/BH/'
    os.makedirs(result_dir, exist_ok=True)
    with open(os.path.join(result_dir, f'{pair}.json'), 'w') as f:
        json.dump(result_dict, f, indent=4)

df_start

"""## RSI Strategy"""



"""## DC based MAC Strategy"""

pair = 'EURUSD'  # repeat for all pairs
for pair in ['AUDUSD', 'EURGBP', 'EURUSD', 'USDCAD']:
    for theta in ['0.00013', '0.00017', '0.00023']:

        if pair == 'EURUSD':
            n_windows = 15
        else:
            n_windows = 18

        starting_balance = 100
        balance = starting_balance

        trades = []
        result_dict = {'Return (%)': [], 'Risk (%)': [], 'Maximum Drawdown (%)': [], 'Calmar Ratio': [], 'Win Rate (%)': [],
            'Average Return (%)': [], 'Ave. Positive Returns (%)': []}

        for window in range(n_windows):
            window_start_balance = balance
            # load data
            cols = ['DCC']
            df = pd.read_parquet(f'../1_DataTransformation/TransformedData/{theta}/{pair}/Window_{window}/test.parquet.gzip', columns=cols)

            # apply moving averages
            fast_period = 7
            slow_period = 14
            df['MA_fast'] = df['DCC'].rolling(window=fast_period).mean()
            df['MA_slow'] = df['DCC'].rolling(window=slow_period).mean()
            df = df.dropna()

            # trading loop
            position = 0
            previous_state = False
            for idx, row in df.iterrows():

                local_price_balance = balance

                # generate signal
                if row['MA_fast'] <= row['MA_slow']:
                    current_state = False
                elif row['MA_fast'] > row['MA_slow']:
                    current_state = True

                # apply trading logic
                if current_state == True and previous_state == False:
                    # buy signal
                    entry_price = row['DCC']
                    position_size = balance
                    direction = 1

                elif (current_state == False and previous_state == True) or idx == len(df):
                    # exit signal
                    exit_price = row['DCC']
                    profit = calculate_profit(position_size, direction, entry_price, exit_price)
                    balance += profit

                    trades.append({'Position Size': position_size, 'Trade Type': 'Long',
                                'Entry Price': entry_price, 'Exit Price': exit_price, 'Profit': profit,
                                'Marginal Return': pct_change(local_price_balance, balance)})

                    # reset variables
                    entry_price = np.nan
                    position_size = np.nan
                    direction = np.nan
                    exit_price = np.nan

                previous_state = current_state

            window_end_balance = balance

        marginal_returns = [trade['Marginal Return'] for trade in trades]
        # log total metrics
        total_return = (balance - 100) / 100  # calcualte from starting balance of 100
        full_metrics = Metrics(marginal_returns, total_return)
        result_dict = {}
        result_dict['Return (%)'] = total_return * 100
        result_dict['Risk (%)'] = full_metrics.risk() * 100
        result_dict['Maximum Drawdown (%)'] = full_metrics.max_drawdown() * 100
        result_dict['Calmar Ratio'] = full_metrics.calmar_ratio()
        result_dict['Win Rate (%)'] = full_metrics.win_rate() * 100
        result_dict['Average Return (%)'] = full_metrics.average_return() * 100
        result_dict['Ave. Positive Returns (%)'] = full_metrics.average_pos_returns() * 100

        print(f'{pair} @ {theta} Total Return: {round(total_return * 100, 2)}% Final Balance: £{round(balance, 2)}')

        # save results
        result_dir = f'./Results/DC_MAC/{theta}'
        os.makedirs(result_dir, exist_ok=True)
        with open(os.path.join(result_dir, f'{pair}.json'), 'w') as f:
            json.dump(result_dict, f, indent=4)

result_dict