# -*- coding: utf-8 -*-
"""
Created on Tue Feb 26 18:19:38 2019

@author: wan


Summary:
    
    Arbitrage bot between Binance exchange and KuCoin exchange. As the liquidity
    of KuCoin is low, the data of KuCoin is acquired first, and then the data of 
    Binance is triggered. The acquisition of some symbols information sometimes
    results in an exception, then carry out exception processing to ensure the 
    stability of arbitrage robot. 
    
    Set 0.001 for both slippage and fee, calculate the net profit after deducting 
    the extra expense, and print out the arbitrage decision and key information 
    if the profit is still considerable. At the same time, carry on the risk hint 
    to the arbitrage opportunity with small available volume, because it may cause 
    the trade failure. 
    
    In order to maximize profit, it's necessary to capture as many current arbitrage
    opportunities as possible and reduce the running time of inefficient cycles. 
    Therefore, symbols list is constantly updated. 
    
    Finally, save the trade record to a local excel file.
 
    
"""

import ccxt
import time
import arrow
import xlwt
from dateutil.parser import parse

class Arbitrage():

    def __init__(self, *args, **kwargs):

        self.common_symbol()   
        self.initialize()

    def initialize(self):
        # Initialize function for bot  
        self.accumulate = 0   #initial accumulate profit
        
        self.count = 0         
        self.trade_record()   #initiailize trade_record
        
        self.delay = 0        #set delay
        self.count_time = 0   #count cycles

        print('start') 
        
    def common_symbol(self):
        #Find same symbols between exchanges
        symbol_list = {}
        self.exchange_list = []
        for exchange_name in ['kucoin2','binance']:
            self.exchange = getattr(ccxt,exchange_name)()
            if self.exchange:
                self.exchange_list.append(self.exchange)
                
        for self.exchange in self.exchange_list:
            self.exchange.load_markets()
            symbol_list[self.exchange.name] = self.exchange.symbols
        
        #calculate intersection
        self.inter = []
        for i in range(len(symbol_list.keys())):
            if len(self.inter) == 0:
                self.inter= symbol_list[list(symbol_list.keys())[i]]
            elif len(self.inter) > 0: 
                self.inter = list((set(self.inter).union(set(symbol_list[list(symbol_list.keys())[i]])))^(set(self.inter)^set(symbol_list[list(symbol_list.keys())[i]])))

#        self.symbols=['BCH/USDT']                
        self.symbols = self.inter    
        
    def run(self): 
        #Running robot
        while True:
            self.arbitrage()

    def arbitrage(self):
        #Handle data, find arbitrage opportuity
        self.symbol_profit = {}      #dict for record profitable symbols
        time.sleep(self.delay)
        
        for self.symbol in self.symbols:
            #parameters setting
            self.max_bid1 = 0
            self.min_ask1 = 10000
            self.bid_exchange = 0
            self.ask_exchange = 0
            self.bid_time = 0
            self.ask_time = 0
            self.bid_amount = 0
            self.ask_amount = 0
            date_time = 0
            date_time_B = 0
            date_time_K = 0
            
            #set fee & slippage
            self.fee_percentage = 0.001
            self.slippage = 0.001
            
            #expect profit threshold
            self.threshold = 0.01

            for exchange in self.exchange_list:
                #load market
                exchange.load_markets()

                try:
                    #get symbol infomation
                    orderbook = exchange.fetchTicker(self.symbol)
                    orderbook1 = exchange.fetch_order_book(self.symbol)
                except Exception as e:
                    print('Warning: exception is {},exchange is {},symbol is {}'.format(e.args[0], exchange.name, self.symbol))
                    print('--------------------------------')
                    continue
        
                if exchange.name == 'Binance':
                    #get binance time
                    date_time_B = parse(orderbook['datetime']) if orderbook['datetime']!= None else None
                    date_time = arrow.get(date_time_B).to('local').format('YYYY-MM-DD HH:mm:ss')
                elif exchange.name == 'KuCoin':
                    #get kucoin time
                    date_time_K = parse(exchange.iso8601(orderbook['info']['time'])) if len(orderbook['info'])>0 else None
                    date_time = arrow.get(date_time_K).to('local').format('YYYY-MM-DD HH:mm:ss')
                
                #since kucoin has low liquility, after kucoin receive data then continue
                if date_time_K != 0: 
                    #get price & availabe vol
                    bid1 = orderbook['bid'] if orderbook['bid'] != None else None
                    self.bid1_amount = orderbook1['bids'][0][1] if len(orderbook1['bids'])>0 else None
                    ask1 = orderbook['ask'] if orderbook['ask'] != None else None
                    self.ask1_amount = orderbook1['asks'][0][1] if len(orderbook1['asks'])>0 else None

                    #find highest bid                         
                    if bid1 and (bid1 > self.max_bid1):
                        self.max_bid1 = bid1
                        self.bid_exchange = exchange
                        self.bid_time = date_time
                        self.bid_amount = self.bid1_amount
                    #find lowest ask   
                    if ask1 and (ask1 < self.min_ask1):
                        self.min_ask1 = ask1
                        self.ask_exchange = exchange
                        self.ask_time = date_time
                        self.ask_amount = self.ask1_amount        
                
            self.decision_output()    
        self.profit_list()
            
    def decision_output(self):
        #Printout arbitrage decision
        if self.bid_exchange!=0 and self.ask_exchange!=0 and self.bid_time!=0 and self.ask_time!=0:
            if self.bid_exchange.name != self.ask_exchange.name:
                #spread calculate
                self.price_diff = self.max_bid1 - self.min_ask1
                #expect profit calculate
                self.expected_profit = self.price_diff - self.min_ask1*self.fee_percentage - self.max_bid1*self.fee_percentage - self.min_ask1*self.slippage - self.max_bid1*self.slippage

                if self.expected_profit > self.threshold: #expect profit threshold
                    self.accumulate = self.accumulate + self.expected_profit
                    self.symbol_profit[self.symbol] =  self.expected_profit

                    print('symbol "{}" find good arbitrage opportunity \nbid_time:{}, ask_time:{} \nprice_diff:{}, expected_profit:{}, accumulate_profit:{} \nbuy at {}, amount_available {}, {} \nsell at {}, amount_available {}, {}'.
                          format(str(self.symbol),self.bid_time,self.ask_time,round(self.price_diff,5),round(self.expected_profit,5),round(self.accumulate,5), round(self.min_ask1,5),self.ask_amount,self.ask_exchange.name,
                                 round(self.max_bid1,5),self.bid_amount,self.bid_exchange.name))
                    if self.bid_amount<1 or self.ask_amount<1:
                        print ('\nWarning: Less amount available')
                    print('--------------------------------')
                    self.count += 1
                    self.trade_record() #save to local               
                if self.price_diff < 0:
                    pass
          
    def profit_list(self):
        #Try to save cycle time and capture more current arbitrage 
        #Keep rebuild symbols list with the opportunity existing symbols
        
        #different algorithms for each profitable symbol list length
        if len(self.symbol_profit)>=5:   
            #current 5 symbols profitable, enough opportunity, cycle for these symbols
            self.delay = 2
            self.symbol_list_rearrange()
            self.count_time = 0
            
        elif len(self.symbol_profit)>0 and len(self.symbol_profit)<5 and self.count_time<=30:
            #cuurent lower than 5 symbols profitable, keep cycle for 1 min
            self.delay = 2
            self.symbol_list_rearrange()
            #calculate cycle time, after 1 minues reload check for all symbols
            self.count_time += 1
            
        elif len(self.symbol_profit)==0 or self.count_time>30:
            #reload all symbols if none profitable symbols, or cycle times for <5 lagger than 1 minues(30)
            self.delay = 0
            self.symbols = self.inter
            self.count_time = 0
    
    def symbol_list_rearrange(self):
        #rearrange profitable symbols with descending order
        items=self.symbol_profit.items() 
        backitems=[[v[1],v[0]] for v in items] 
        backitems.sort(reverse=True)
        new_list = [backitems[i][1] for i in range(0,len(backitems))]
#        print (new_list, 'length:',len(self.symbol_profit), "cycletime:",self.count_time)
        
        #reset symbols list
        self.symbols = new_list
        
    def trade_record(self):
        #Save trade to excel file
        if self.count == 0:
            
            row0 = ["symbol","bid_time","ask_time","price_diff","expected_profit","accumulate_profit",
                    "buy_price","buy_amount","exchange1","sell_price","sell_amount","exchange2","slippage","fee"]
           
            self.myWorkbook = xlwt.Workbook()
            self.mySheet = self.myWorkbook.add_sheet('A Test Sheet')
            
            for i in range(len(row0)):
                self.mySheet.write(0, i, row0[i])
            
            self.myWorkbook.save('trade_record.xls')
                        
        elif self.count > 0:

            self.new_trade = []
            self.new_trade.append(self.symbol)
            self.new_trade.append(self.bid_time)
            self.new_trade.append(self.ask_time)
            self.new_trade.append(self.price_diff)
            self.new_trade.append(self.expected_profit)
            self.new_trade.append(self.accumulate)
            self.new_trade.append(self.min_ask1)
            self.new_trade.append(self.ask_amount)
            self.new_trade.append(self.ask_exchange.name)
            self.new_trade.append(self.max_bid1)
            self.new_trade.append(self.bid_amount)
            self.new_trade.append(self.bid_exchange.name)
            self.new_trade.append(self.slippage)
            self.new_trade.append(self.fee_percentage)
            
            row = self.new_trade
            
            for i in range(len(row)):
                self.mySheet.write(self.count, i, row[i])
            
            self.myWorkbook.save('trade_record.xls')

            
if __name__ == "__main__":    
    arbitrage = Arbitrage()
    arbitrage.run()
    
    

    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    