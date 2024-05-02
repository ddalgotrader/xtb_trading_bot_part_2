import datetime
from XtbTrader import *
from xAPIConnector import *
from config import *
import ssl
import warnings
from strategies import *
from pandas.errors import SettingWithCopyWarning
warnings.simplefilter(action='ignore', category=(SettingWithCopyWarning))
warnings.simplefilter(action='ignore', category=FutureWarning)
import os


try:
    #instantiate trading session
    warning_candle_counter=0
    xt = XtbTrader(instrument='EURUSD', interval='5min', lookback=1000, strategy=rsi,
                   units=0.1, session_end=<SESSION END IN FORMAT'yyyy-mm-dd HH:MM:SS', csv_results_path=<GOOGLE STORAGE PATH gs://...>, email_info=True, close_order_after_session=False)


    client = APIClient()
    resp = client.execute(loginCommand(user_id, pwd))

    if resp['status']==False:
        raise APIResponseException(resp, send_email=xt.email_info)
    xt.get_last_n_candles(client)
    xt.check_start_status(client)
    xt.client=client
    ssid = resp['streamSessionId']
    
    #connect to XTB API Client
    sclient = APIStreamClient(ssId=ssid, candleFun=xt.procCandle, aliveFun=xt.collectAlive)
    
    #function that sends 'KEEP ALIVE' message every 3 seconds with current timestamp
    sclient.subscribeAlive()
    
    #stream of candles every 1 minute
    sclient.subscribeCandle(xt.instrument)



    while True:

	#current duration of trading session
	session_lasting = (datetime.datetime.now() - xt.session_start).total_seconds()
	
	
	#ping to XTB API every 5 minutes
        if int(session_lasting)%300==0:
            client.commandExecute('ping')
            sclient.execute(dict(command='ping', streamSessionId=ssid))



	#refresh client and stream client connection after every 12 hours
        if (datetime.datetime.now().hour%12==0)&(datetime.datetime.now().minute==30)&(datetime.datetime.now().second==30):
            print('Reconnecting API due to meet reconnecting time')
            sclient.unsubscribeCandle(xt.instrument)
            sclient.unsubscribeAlive()
            client.disconnect()
            message='Reconnecting API due to meet reconnecting time'
            subject='Trading session info reconnect'
            if xt.email_info==True:
                xt.send_email_info(message,subject)
            time.sleep(2)
            client = APIClient()
            resp = client.execute(loginCommand(user_id, pwd))
            if resp['status'] == False:
                raise APIResponseException(resp, send_email=xt.email_info)

            xt.client=client


            ssid = resp['streamSessionId']
            sclient = APIStreamClient(ssId=ssid, candleFun=xt.procCandle,
                                          aliveFun=xt.collectAlive)
                                          
            sclient.subscribeAlive()
            sclient.subscribeCandle(xt.instrument)
            
            time.sleep(1.5)
	
	
	#check if last bar for given interval is delivered
        if (datetime.datetime.now().minute % xt.interval_dict[xt.interval] == 0) & (
                datetime.datetime.now().second == 25):

            candle_diff = (datetime.datetime.now() - xt.last_bar).total_seconds()
            time.sleep(1)

            if candle_diff > (pd.to_timedelta(xt.interval).total_seconds() + 40):

                message = f'Last candle not delivered, check problem - login to xStation'
                if warning_candle_counter < 3:
                    print(message)
                    subject = 'Trading session warning'
                    if xt.email_info == True:
                        xt.send_email_info(message, subject)
                    time.sleep(1)
                warning_candle_counter += 1
	
	
	#last_signal is timestamp from 'KEEP ALIVE' message if last message is older than 60 seconds from now session is closed due to not responding API
        if xt.last_signal!=None:
            if ((datetime.datetime.now()-xt.last_signal).total_seconds())>60:
                print(xt.last_signal)
                xt.close_order_after_session = True
                xt.close_session(session_dead=True)

                break
                
        #if current duration of session is longer than duration defined in xt session is finished, logs are saved in file on the disk 
        if datetime.datetime.now()>datetime.datetime.strptime(xt.session_end, '%Y-%m-%d %H:%M:%S'):
            sclient.unsubscribeCandle(xt.instrument)
            sclient.unsubscribeAlive()
            xt.close_session()
            client.disconnect()

            break




# if session is closed by press CTRL+C, behaviour is the same like in finished session
except KeyboardInterrupt:

    xt.close_order_after_session = True
    xt.close_session()
    client.disconnect()
    
    
#info when SSL Error occured 
except ssl.SSLError:



    message='Connection was closed due to SSL error, close your trade manually'
    print(message)
    subject='Trading session error'
    if xt.email_info==True:
        xt.send_email_info(message=message,subject=subject)
    os.system(f'tmux capture-pane -pS - > {xt.strategy.__name__}_{xt.instrument}_{xt.interval}_{xt.end_to_file_name}.log')
    
    
#info when Key Error occured
except KeyError as e:



    subject = 'Trading session error'
    print(message)
    if xt.email_info == True:
        xt.send_email_info(message=message, subject=subject)
    sclient.unsubscribeCandle(xt.instrument)
    sclient.unsubscribeAlive()
    xt.close_order_after_session = True
    xt.close_session()
    client.disconnect()




