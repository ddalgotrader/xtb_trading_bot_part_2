import datetime
from XtbTrader import *
from xAPIConnector import *
from config import *
import sys
import warnings
from strategies import *
import os
warnings.simplefilter(action='ignore', category=FutureWarning)




xt = XtbTrader(instrument='EURUSD', interval='1min', lookback=1000, strategy=contrarian,
               units=0.1, duration=0.1, csv_results_path='/home/slawomir/PycharmProjects/XtbTrader/results')

client = APIClient()
resp = client.execute(loginCommand(user_id, pwd))
xt.get_last_n_candles(client)
xt.client=client
ssid = resp['streamSessionId']
sclient = APIStreamClient(ssId=ssid, candleFun=xt.procCandle, aliveFun=xt.collectAlive)
sclient.subscribeAlive()
sclient.subscribeCandle('EURUSD')

try:
    while True:


        session_lasting = (datetime.datetime.now() - xt.session_start).total_seconds()

        if int(session_lasting)%300==0:
            client.commandExecute('ping')
            sclient.execute(dict(command='ping', streamSessionId=ssid))

        if int(session_lasting)>=15:
            sclient.unsubscribeAlive()

        if xt.last_signal!=None:
            if ((datetime.datetime.now()-xt.last_signal).total_seconds())>60:
                print(xt.last_signal)
                xt.close_session(session_dead=True)

                break
        if session_lasting >= datetime.timedelta(hours=xt.duration).total_seconds():
            sclient.unsubscribeCandle('EURUSD')
            sclient.unsubscribeAlive()
            xt.close_session()
            client.disconnect()

            break

except KeyboardInterrupt:

    xt.close_session()
    client.disconnect()

