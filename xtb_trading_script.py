import datetime
from XtbTrader import *
from xAPIConnector import *
from config import *
import sys
import warnings
from strategies import *
import os
warnings.simplefilter(action='ignore', category=FutureWarning)



#instantiate trading session
xt = XtbTrader(instrument='EURUSD', interval='1min', lookback=100, strategy=contrarian,
               units=0.1, duration=0.5, csv_results_path='gs://trading-bot-xtb-bucket')

#connect to XTB API Client
client = APIClient()
resp = client.execute(loginCommand(user_id, pwd))
xt.get_last_n_candles(client)
xt.client=client
ssid = resp['streamSessionId']

#connect to XTB API Stream Client
sclient = APIStreamClient(ssId=ssid, candleFun=xt.procCandle, aliveFun=xt.collectAlive)

#function that sends 'KEEP ALIVE' message every 3 seconds with current timestamp
sclient.subscribeAlive()

#stream of candles every 1 minute
sclient.subscribeCandle(xt.instrument)

try:
    while True:

        #current duration of trading session
        session_lasting = (datetime.datetime.now() - xt.session_start).total_seconds()
	
	
	#ping to XTB API every 5 minutes	
        if int(session_lasting)%300==0:
            client.commandExecute('ping')
            sclient.execute(dict(command='ping', streamSessionId=ssid))

       
	#last_signal is timestamp from 'KEEP ALIVE' message if last message is older than 60 seconds from now session is closed due to not responding API
        if xt.last_signal!=None:
            if ((datetime.datetime.now()-xt.last_signal).total_seconds())>60:
                
                sclient.unsubscribeCandle(xt.instrument)
		sclient.unsubscribeAlive()
		xt.close_session()
		client.disconnect()
                os.system(f'tmux capture-pane -pS - > {xt.strategy.__name__}_{xt.instrument}_{xt.interval}_{xt.end_to_file_name}.log')

            break
            	print(f'Session terminated due to not responding API last keep alive signal -{xt.last_signal}')
            	os.system(f'tmux capture-pane -pS - > {xt.strategy.__name__}_{xt.instrument}_{xt.interval}_{xt.end_to_file_name}.log')
            	
                break
                
        #if current duration of session is longer than duration defined in xt session is finished, logs are saved in file on the disk        
        if session_lasting >= datetime.timedelta(hours=xt.duration).total_seconds():
            
            sclient.unsubscribeCandle(xt.instrument)
            sclient.unsubscribeAlive()
            xt.close_session()
            client.disconnect()
            os.system(f'tmux capture-pane -pS - > {xt.strategy.__name__}_{xt.instrument}_{xt.interval}_{xt.end_to_file_name}.log')

            break


# if session is closed by press CTRL+C, behaviour is the same like in finished session
except KeyboardInterrupt:

    sclient.unsubscribeCandle(xt.instrument)
            sclient.unsubscribeAlive()
            xt.close_session()
            client.disconnect()
            os.system(f'tmux capture-pane -pS - > {xt.strategy.__name__}_{xt.instrument}_{xt.interval}_{xt.end_to_file_name}.log')

            break

