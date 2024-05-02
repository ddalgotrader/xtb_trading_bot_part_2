

import pandas as pd

import config
from xAPIConnector import *
import time
import datetime
import smtplib, ssl
from config import *
from email.message import EmailMessage
#import warnings
#warnings.simplefilter(action='ignore', category=FutureWarning)
class XtbTrader():

    def __init__(self, instrument, interval, lookback, strategy, units, session_end,
                 csv_results_path, client=None, email_info=True, close_order_after_session=False):

        '''

        Description
        ===============================================
        Python module let you trade with your strategy wit XTB broker

        :argument
        *client -> XTB API client
        *ssid -> stream session id required to start streaming candles
        *instrument -> string - instrument you want to trade on e.g. 'EURUSD'
        *interval -> string - trading interval, {'1min', '5min', '15min', '30min', '1h', '4h', '1D'}
        *lookback -> int - how many candles look back to calculate your strategy indicator e.g. 1000
        *strategy -> name of defined strategy in python,
        *units -> float number of units of given instrument
        *session_end -> SESSION END IN FORMAT'yyyy-mm-dd HH:MM:SS
        *csv_results_path -> str, filepath where store dataframe with price data and trading results
        *email_info ->boolean, sending email info about trading session events
        *close_order_after_session -> boolean, order shoul be active after session e.g. for a weekend



        '''

        self.email_info=email_info
        self.last_signal=None
        self.terminate_session=False
        self.instrument = instrument
        self.interval = interval
        self.lookback = lookback
        self.strategy = strategy
        self.units = units
        self.session_end=session_end
        self.csv_results_path = csv_results_path
        self.interval_dict = {'1min': 1, '5min': 5, '15min': 15, '30min': 30, '1h': 60, '4h': 240, '1D': 1440}
        self.collect_live = False
        self.live_df = pd.DataFrame()
        self.strategy = strategy
        self.position_closed = False
        self.check_hist = True
        self.session_history = []
        self.session_hist_df = pd.DataFrame()
        self.trade_counter = 0
        self.client = client
        self.cmd_dict = {0: 'Buy', 1: 'Sell', 2: 'Buy_limit', 3: 'Sell_limit', 4: 'Buy_stop', 5: 'Sell_stop'}
        self.session_started = False
        self.session_start = datetime.datetime.now()

        self.email_sender=sender
        self.email_receiver=receiver
        self.email_port=port
        self.email_server=server
        self.email_password=email_pwd
        self.current_candle=None
        self.close_order_after_session=close_order_after_session
        self.not_candle=False
        self.end_session_date=datetime.datetime.strptime(self.session_end, '%Y-%m-%d %H:%M:%S').strftime("%a,%d %b, %Y, %H:%M:%S")

        self.end_to_file_name = self.session_end.replace('-','').replace(':','').replace(' ','')
        self.start_to_file_name=self.session_start.strftime("%Y%m%d%H%M%S")
        self.start_session_date = self.session_start.strftime("%a,%d %b, %Y, %H:%M:%S")
        self.start_message=(f'Trading session on {self.instrument} with interval of {self.interval}, session end - {self.session_end} , strategy -{self.strategy.__name__}\n'
                       f'START SESSION AT {self.start_session_date}')


        print(self.start_message)

        print(self.start_session_date)
        print(self.end_session_date)

        try:
            with open('valid_xtb_symbols.json') as f:

                valid_symbols_dict = json.load(f)

            self.valid_symbols = valid_symbols_dict['symbols']

            if self.instrument not in self.valid_symbols:
                raise InvalidSymbol(self.instrument, self.valid_symbols)
        except FileNotFoundError:
            pass
        if self.interval not in list(self.interval_dict.keys()):
            raise InvalidInterval(self.interval)

    def __repr__(self):

        return f'XtbTrader || instrument={self.instrument}; interval={self.interval}; strategy={self.strategy}; units={self.units}; end of session={self.end}'

    def history_converter(self, history):

        '''
        Description
        ===============================================
        Private method converting history of prices from json format to pandas df

        :param
        history -> json - json data with history for given instrument - result of method get_last_n_candles

        :return
        pandas df
        '''
        df_dict = history['returnData']['rateInfos']
        digits = history['returnData']['digits']

        df = pd.DataFrame.from_dict(df_dict)

        df['time'] = df['ctm'].apply(lambda x: datetime.datetime.fromtimestamp(x / 1000))
        df['open'] = df['open'] / (10 ** digits)
        df['close'] = df['open'] + df['close'] / (10 ** digits)
        df['high'] = df['open'] + df['high'] / (10 ** digits)
        df['low'] = df['open'] + df['low'] / (10 ** digits)
        df = df[['time', 'open', 'high', 'low', 'close', 'vol']]
        df.set_index("time", inplace=True, drop=True)
        df = self.strategy(df)

        return df

    def get_last_n_candles(self, client):

        '''
        Description
        ===============================================
        Method returns last n candles from given interval

        '''

        args = {
            'info': {
                'period': self.interval_dict[self.interval],
                'ticks': self.lookback * (-1),
                'symbol': self.instrument,
                'start': client.commandExecute('getServerTime')['returnData']['time']
            }}

        data = client.commandExecute('getChartRangeRequest', arguments=args)
        if data['status'] == False:
            raise APIResponseException(data, send_email=self.email_info)

        df = self.history_converter(data)



        self.raw_data = df.copy()
        self.raw_data = self.strategy(self.raw_data)

        self.last_bar = self.raw_data.index[-1]



    def procCandle(self, msg):

        self.procLive=True

        '''
        Description
        ===============================================
        Method processing message from XTB API to pandas df format

        :param
        msg -> message from XTB server

        :return

        pandas df

        '''





        record = pd.DataFrame.from_records(msg['data'], index=[pd.to_datetime(datetime.datetime.fromtimestamp(
            msg['data']['ctm'] / 1000))])
        record = record[['open', 'high', 'low', 'close', 'vol']]
        self.last_candle = record.resample('1min', label='right').last().index[-1]
        

        if (self.last_candle - self.last_bar > pd.to_timedelta(self.interval)) & (self.collect_live == False):
            



            self.collect_live = True
            collect_data_message='START COLLECTING LIVE DATA\nWaiting for first trade signal...\n=================================.'
            print(collect_data_message)
            self.start_message=self.start_message+'\n'+collect_data_message

            if self.email_info == True:
                self.send_email_info(self.start_message)


        if self.collect_live == True:

            if self.interval != '1min':

                self.live_df = pd.concat([self.live_df, record])

                idx_to_check=self.live_df.index[-1]+pd.to_timedelta('1min')
                if idx_to_check.minute%self.interval_dict[self.interval]==0:

                #if self.last_candle - self.live_df.index[0] == pd.to_timedelta(self.interval):

                    self.live_df = self.live_df.resample(self.interval).agg(
                        {"open": "first", "high": "max", "low": "min", "close": "last", "vol": "sum"}).dropna()
                    self.raw_data = pd.concat([self.raw_data, self.live_df])
                    self.live_df_len_control=len(self.live_df)
                    self.live_df = pd.DataFrame()
                    self.raw_data = self.strategy(self.raw_data)
                    self.last_bar=self.raw_data.index[-1]
                    if self.trade_counter == 0:

                        if self.start_order_pos != None:

                            if self.start_order_pos == 0:

                                if self.raw_data['position'].iloc[-1] == 0:
                                    self.close_order()

                                if self.raw_data['position'].iloc[-1] == -1:
                                    self.raw_data['position'].iloc[-2] = 1

                            if self.start_order_pos == 1:

                                if self.raw_data['position'].iloc[-1] == 0:
                                    self.close_order()

                                if self.raw_data['position'].iloc[-1] == 1:
                                    self.raw_data['position'].iloc[-2] = -1

                        else:

                            if self.raw_data['position'].iloc[-1] != 0:
                                self.raw_data['position'].iloc[-2] = 0

                    self.trade()


            else:

                self.raw_data = pd.concat([self.raw_data, record])
                self.raw_data = self.strategy(self.raw_data)


                if self.trade_counter == 0:

                    if self.start_order_pos!=None:

                        if self.start_order_pos == 0:


                            if self.raw_data['position'].iloc[-1] == 0:
                                self.close_order()


                            if self.raw_data['position'].iloc[-1] == -1:
                                self.raw_data['position'].iloc[-2] = 1

                        if self.start_order_pos == 1:


                            if self.raw_data['position'].iloc[-1] == 0:
                                self.close_order()


                            if self.raw_data['position'].iloc[-1] == 1:
                                self.raw_data['position'].iloc[-2] = -1

                    else:

                        if self.raw_data['position'].iloc[-1] != 0:
                            self.raw_data['position'].iloc[-2] = 0



                self.trade()


            if (datetime.datetime.now().hour%4==0)&(datetime.datetime.now().minute == 45):
                print('procCandle works',self.last_bar)



    def close_session(self, session_dead=False):


        if self.close_order_after_session==True:
            self.close_order()
            self.getTradeHistory(self.order_hist)


        close_session_message=self.check_end_status()
        end_session = datetime.datetime.now().strftime("%a,%d %b, %Y, %H:%M:%S")
        close_session_message=close_session_message+f'\nTRADING SESSION END AT {end_session}\n'
        if session_dead == True:
            close_session_message=close_session_message+"API doesn'respond session end\n"

        self.save_history()
        if len(self.session_history) > 0:
            close_session_message=close_session_message+f"Profit generated during trading session: {self.session_hist_df['cum_profit'].iloc[-1]}\n"

        close_session_message=close_session_message+f'Number of trades in session: {self.trade_counter}\n=================================================\n'
        if self.close_order_after_session==False:
            close_session_message=close_session_message+'Defined not closing order after session check if your order is closed'
        print(close_session_message)
        if self.email_info == True:
            self.send_email_info(close_session_message)
        time.sleep(5)
    def trade(self):

        '''

        Description
        ===============================================
        Method creating new order and closing orders depends on current position and strategy
        '''

        df = self.raw_data.copy()

        if df['position'].iloc[-2] == 1:
            if df['position'].iloc[-1] == -1:
                self.close_order()
                self.getTradeHistory(self.order_hist)
                self.save_history()

                if self.position_closed:
                    self.open_position('sell')


            if df['position'].iloc[-1] == 0:
                self.close_order()
                self.getTradeHistory(self.order_hist)
                self.save_history()


        if df['position'].iloc[-2] == -1:
            if df['position'].iloc[-1] == 1:
                self.close_order()
                self.getTradeHistory(self.order_hist)
                self.save_history()

                if self.position_closed:
                    self.open_position('buy')


            if df['position'].iloc[-1] == 0:
                self.close_order()

                self.getTradeHistory(self.order_hist)
                self.save_history()


        if df['position'].iloc[-2] == 0:
            if df['position'].iloc[-1] == 1:

                
                self.open_position('buy')



            if df['position'].iloc[-1] == -1:

                self.open_position('sell')



    def close_order(self):
        '''
        Description
        ===============================================
        Method that close active trading positions

        '''
        order_to_close = self.client.commandExecute("getTrades", arguments={'openedOnly': True})
        if order_to_close ['status'] == False:
            raise APIResponseException(order_to_close, send_email=self.email_info)

        if len(order_to_close['returnData']) > 0:

            order_close = self.client.commandExecute("tradeTransaction", arguments={
                'tradeTransInfo': {
                    'order': order_to_close['returnData'][-1]['order'],
                    'type': TransactionType.ORDER_CLOSE,
                    'volume': order_to_close['returnData'][-1]['volume'],
                    'symbol': order_to_close['returnData'][-1]['symbol'],
                    'price': order_to_close['returnData'][-1]['close_price'],

                }

            })

            if order_close['status'] == False:
                raise APIResponseException(order_close, send_email=self.email_info)

            self.check_order_closed(order_to_close)




        else:

            self.order_hist = None
            self.check_hist = False
            self.position_closed = True

    def open_position(self, position_type):

        '''
        Description
        ===============================================
        Method opening new trading position
        :param

        *position_type-> str {'buy','sell'}

        '''

        positions_dict = {'sell': TransactionSide.SELL, 'buy': TransactionSide.BUY}
        ask_bid_dict = {'sell': 'bid', 'buy': 'ask'}

        order_type = positions_dict[position_type]
        ask_bid = ask_bid_dict[position_type]

        order = self.client.commandExecute("tradeTransaction", arguments={
            'tradeTransInfo': {
                'cmd': order_type,
                'volume': self.units,
                'symbol': self.instrument,
                'price': self.client.commandExecute("getSymbol", arguments={'symbol': self.instrument})['returnData'][
                    ask_bid]

            }

        })

        if order['status'] == False:
            raise APIResponseException(order, send_email=self.email_info)

        order_num = order['returnData']['order']

        self.check_order(order_num)

        if self.trade_counter == 1:
            start_session = datetime.datetime.now().strftime("%a,%d %b, %Y, %H:%M:%S")
            print(
                f'START TRADING AT {start_session} |instrument: {self.instrument}| strategy: {self.strategy.__name__} | interval: {self.interval}')
            self.session_started = True

        self.check_opened_position(self.current_order_num)

    def getTradeHistory(self, order):

        '''
        Description
        ===============================================
        Method summarizing closed possition and whole trading session
        :param

        *order-> json, last closed order

        '''

        if (self.check_hist) & (self.order_hist != None):

            hist_record = None
            order_num = order['order']

            retry = 0
            while True:
                order_history = self.client.commandExecute("getTradesHistory", arguments={'end': 0, 'start': 0})
                time.sleep(0.5)
                if order_history['status'] == False:
                    raise APIResponseException(order_history, send_email=self.email_info)

                retry += 1
                if retry > 15:
                    break

                if type(order_history) == dict:
                    if 'status' in order_history.keys():
                        if order_history['status'] == True:
                            found_hist_order = False
                            for d in order_history['returnData']:

                                if order_num == d['position']:
                                    found_hist_order = True
                                    print(f'Trade {order_num} saved in trades history')
                                    hist_record = d
                                    self.session_history.append(hist_record)
                                    self.session_hist_df = pd.DataFrame.from_dict(self.session_history)
                                    self.session_hist_df['cum_profit'] = self.session_hist_df['profit'].cumsum()
                                    self.close_message=(f"Closed trade {order_num} details:\n"
                                                     f"Open price: {hist_record['open_price']}\n"
                                                     f"Close price: {hist_record['close_price']}\n"
                                                     f"Trade profit: {hist_record['profit']}\n")


                                    if 'cum_profit' in self.session_hist_df.columns:
                                        self.close_message=self.close_message+f"Cumulative profit for whole trading session: {self.session_hist_df['cum_profit'].iloc[-1]}\n"

                                    self.close_message=self.close_message+f'Number of trades in session: {self.trade_counter}\n=======================================================\n'

                                    print(self.close_message)
                                    if self.email_info == True:
                                        self.send_email_info(self.close_message)

                                    break

                            if found_hist_order == True:
                                break

            if hist_record == None:
                print(f'Order {order_num} not found in history')
                print('==========================================')
                pass

        

    def check_opened_position(self, current_order):

        '''
        Description
        ===============================================
        Method confirming that order that was sent is opened

        :param
        *current_order-> int, order that was sent to broker

        '''
        retry = 0
        while True:
            trade_details = self.client.commandExecute('getTrades', arguments={"openedOnly": True})
            time.sleep(0.5)
            if trade_details['status'] == False:
                raise APIResponseException(trade_details, send_email=self.email_info)

            retry += 1
            if retry > 10:
                print(f'Not found order {current_order}')
                break

            if type(trade_details) == dict:
                if 'status' in trade_details.keys():
                    if trade_details['status'] == True:
                        if len(trade_details['returnData']) > 0:
                            if current_order == trade_details['returnData'][-1]['order2']:
                                open_price = trade_details['returnData'][-1]['open_price']
                                position = self.cmd_dict[trade_details['returnData'][-1]['cmd']]
                                trade_position = trade_details['returnData'][-1]['position']
                                open_time = datetime.datetime.now().strftime("%a,%d %b, %Y, %H:%M:%S")

                                open_pos_message=(f'{position} order number {current_order} with position {trade_position} at {open_time} with open price {open_price} accepted\n'
                                                  '-----------------------------------------------------------------------------------------------------------------')
                                print(open_pos_message)
                                if self.email_info == True:
                                    self.send_email_info(open_pos_message)

                                break
                    else:
                        print(trade_details)
                        break

    def check_order(self, order_num):

        '''
        Description
        ===============================================
        Method check order status

        :param
        *order_num-> int, order that was sent to broker

        '''
        retry = 0
        while True:

            check_order = self.client.commandExecute("tradeTransactionStatus", arguments={'order': order_num})
            time.sleep(0.5)
            if check_order['status'] == False:
                raise APIResponseException(check_order, send_email=self.email_info)

            retry += 1
            if retry > 15:
                print('Cannot specify transaction status')
                break
            if type(check_order) == dict:
                if 'status' in check_order.keys():
                    if check_order['status'] == True:
                        order_status = check_order['returnData']['requestStatus']
                        if order_status == 3:
                            self.trade_counter = self.trade_counter + 1
                            self.current_order_num = check_order['returnData']['order']

                            break
                        if order_status == 4:
                            print(f"Order {order_num} has been rejected")
                            self.current_order_num = 0
                            break

                        if order_status == 1:
                            print(f"Order {order_num} has error")
                            self.current_order_num = 0
                            break
                    else:
                        print(check_order)
                        break

    def check_order_closed(self, order_to_close):

        '''
        Description
        ===============================================
        Method check if position is closed

        :param
        *order_to_close-> json, order that was sent to close

        '''

        retry = 0
        while True:
            check_order = self.client.commandExecute("getTrades", arguments={'openedOnly': True})
            time.sleep(0.5)
            if check_order['status'] == False:
                raise APIResponseException(check_order, send_email=self.email_info)
            retry += 1
            if retry > 10:
                print('Cannot specify if order is closed')
                break

            if type(check_order) == dict:
                if 'status' in check_order.keys():
                    if check_order['status'] == True:
                        self.check_hist = True
                        self.order_hist = order_to_close['returnData'][-1]
                        print(f"Trade {self.order_hist['order']} closed")
                        self.position_closed = True
                        break

                    else:
                        print(check_order)
                        break
    def collectAlive(self,msg):

        self.last_signal=datetime.datetime.fromtimestamp(int((msg['data']['timestamp'])/1000))


    def send_email_info(self, message, subject='Trading session info'):

        try:
            msg = EmailMessage()
            msg.set_content(message)

            msg['Subject'] = f'{subject} {self.start_session_date}-{self.end_session_date}'
            msg['From'] = self.email_sender
            msg['To'] = self.email_receiver
            context = ssl.create_default_context()
            server = smtplib.SMTP_SSL(self.email_server, self.email_port)
            server.login(self.email_sender, self.email_password)
            server.send_message(msg)
            server.quit()

        except smtplib.SMTPException as e:

            print('SMTP Error Occured, email not sent')
            print(e)
            pass

    def save_history(self):

        self.raw_data.to_csv(
            f'{self.csv_results_path}/trading_session_{self.instrument}_{self.interval}_{self.start_to_file_name}_{self.end_to_file_name}_{self.strategy.__name__}_strategy.csv')
        if len(self.session_history) > 0:
            self.session_hist_df.to_csv(
                f'{self.csv_results_path}/session_history_{self.instrument}_{self.interval}_{self.start_to_file_name}_{self.end_to_file_name}_{self.strategy.__name__}_strategy.csv')

    def check_start_status(self,client):
        self.start_order_pos=None
        start_order = client.commandExecute("getTrades", arguments={'openedOnly': True})
        if start_order['status'] == False:
            raise APIResponseException(start_order, send_email=self.email_info)

        if len(start_order['returnData']) > 0:
            self.start_order_pos = start_order['returnData'][-1]['cmd']
            self.start_order_num = start_order['returnData'][-1]['position']

            if self.start_order_pos == 0:
                order_info = f'There is still active order {self.start_order_num} with long position'

            if self.start_order_pos == 1:
                order_info = f'There is still active order {self.start_order_num} with short position'
            self.start_message = self.start_message + '\n' + order_info
            print(order_info)

    def check_end_status(self):

        end_order = self.client.commandExecute("getTrades", arguments={'openedOnly': True})
        if end_order['status'] == False:
            raise APIResponseException(end_order, send_email=self.email_info)

        if len(end_order['returnData']) > 0:
            end_order_pos = end_order['returnData'][-1]['cmd']
            end_order_num = end_order['returnData'][-1]['position']

            if end_order_pos == 0:
                order_info = f'There is still active order {end_order_num} with long position, cum profit is presented without this trade'
            if end_order_pos == 1:
                order_info = f'There is still active order {end_order_num} with short position, cum profit is presented without this trade'


            return order_info

        else:
            return 'No active trades'


class InvalidInterval(Exception):
    """Exception raised when invalid trading interval occured.

    Attributes:
        interval -- interval which caused the error
        message -- explanation of the error
    """

    def __init__(self, interval,
                 message="Choose from one of possible intervals of trading {'1min', '5min', '15min', '30min', '1h', '4h', '1D'}"):
        self.interval = interval
        self.message = message
        super().__init__(self.message)


class InvalidSymbol(Exception):
    """Exception raised when invalid trading symbol occured.

    Attributes:
        symbol -- symbol which caused the error
        valid_symbols -- list of valid symbols
        message -- explanation of the error
    """

    def __init__(self, symbol, valid_symbols):
        self.valid_symbols = valid_symbols
        self.symbol = symbol
        self.message = f"Symbol {self.symbol} is invalid, choose from one of possible instruments:  {self.valid_symbols}"
        super().__init__(self.message)

class APIResponseException(Exception):

    def __init__(self, resp, send_email=True):
        self.resp=resp
        self.message=f"error code={self.resp['errorCode']}, error description={self.resp['errorDescr']}"
        super().__init__(self.message)
        if send_email==True:
            try:
                msg = EmailMessage()
                msg.set_content(self.message)
                subject='Trading session API error'
                msg['Subject'] = f'{subject}'
                msg['From'] = config.sender
                msg['To'] = config.receiver
                context = ssl.create_default_context()
                server = smtplib.SMTP_SSL(config.server, config.port)
                server.login(config.sender, config.email_pwd)
                server.send_message(msg)
                server.quit()
            except smtplib.SMTPException as e:

                print('SMTP Error Occured, email not sent')
                print(e)
                pass



