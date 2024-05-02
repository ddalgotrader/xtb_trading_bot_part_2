XtbTrader.py - Python module to automatic algorithmic trading on XTB trading platform.

1. Example initialize trading session

   xt = XtbTrader(instrument='EURUSD', interval='5min', lookback=1000, strategy=rsi,
                   units=0.1, session_end=<SESSION END IN FORMAT'yyyy-mm-dd HH:MM:SS', csv_results_path=<GOOGLE STORAGE PATH gs://...>, email_info=True, close_order_after_session=False)



   Description
        ===============================================
        Python module let you trade with your strategy wit XTB broker

        :argument
        
        *instrument -> string - instrument you want to trade on e.g. 'EURUSD'
        *interval -> string - trading interval, {'1min', '5min', '15min', '30min', '1h', '4h', '1D'}
        *lookback -> int - how many candles look back to calculate your strategy indicator e.g. 1000
        *strategy -> name of defined strategy in python,
        *units -> float number of units of given instrument
        *session_end -> SESSION END IN FORMAT'yyyy-mm-dd HH:MM:SS
        *csv_results_path -> str, filepath where store dataframe with price data and trading results
        *email_info ->boolean, sending email info about trading session events
        *close_order_after_session -> boolean, order should be active after session e.g. for a weekend


   IMPORTANT EMAIL NOTIFICATIONS!!!

   If email_info attribute is set to True you have to define email server specifications in config.py file

  user_id=<XTB API USER ID REAL OR DEMO>
  pwd=<XTB PASSWORD>
  sender=<YOUR EMAIL ADDRESS SENDER>
  receiver=<YOUR EMAIL ADDRESS RECEIVER>
  port=<EMAIL PORT>
  server=<EMAIL SERVER>
  email_pwd=<EMAIL PASSWORD>

   
