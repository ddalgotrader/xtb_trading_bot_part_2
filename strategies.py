import pandas as pd
import numpy as np
import talib as ta

def contrarian(df, window=1):
    df["returns"] = np.log(df['close'] / df['close'].shift(1))
    df["position"] = -np.sign(df["returns"].rolling(window).mean())
    return df
def rsi(data, down_level=30, up_level=70, window=14, return_only_indicator=False, position_kind='position'):
    ''' Prepares the Data for Backtesting.
    '''
    df = data.copy()



    df['RSI'] = ta.RSI(df['close'], window)

    df['RSI_shift'] = df['RSI'].shift(1)

    conditions = [((df['RSI'] < down_level) & (df['RSI_shift'] > down_level)),
                  ((df['RSI'] > up_level) & (df['RSI_shift'] < up_level))]

    values = [1, -1]

    df['position_ch'] = np.select(conditions, values, 0)
    df['position'] = df['position_ch'].replace(0, method='ffill')

    return df

