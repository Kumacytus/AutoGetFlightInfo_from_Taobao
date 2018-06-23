# -*- coding: utf-8 -*-
import configparser
import csv
import datetime
import hashlib
import importlib
import json
import msvcrt
import os
import random
import re
import shutil
import smtplib
import ssl
import sys
import threading
import time
import urllib.request
from binascii import b2a_hex, a2b_hex
from email.mime.text import MIMEText
from Crypto.Cipher import AES

ssl._create_default_https_context = ssl._create_unverified_context

importlib.reload(sys)

input_timeout = 10

cityFile = csv.DictReader(open('citycode.csv', 'r', encoding='utf-8-sig'))
cityDict = {}
for item in cityFile:
    cityDict[item['cityName']] = item['cityCode']


# config.ini -> dict
class MyConfigDict(configparser.ConfigParser):
    def ini2dict(self):
        configdict = dict(self._sections)
        for item in configdict:
            configdict[item] = dict(configdict[item])
        return configdict


# encryption and decryption module
class MyCrypt(object):
    def __init__(self, key):
        self.key = hashlib.md5(key.encode('utf-8')).hexdigest()
        self.mode = AES.MODE_CFB
        self.salt = b'0000000000000000'

    def encrypt(self, text):
        cipher = AES.new(self.key.encode('utf-8'), self.mode, self.salt)
        ntext = text + ('\0' * (16 - (len(text) % 16)))
        return b2a_hex(cipher.encrypt(ntext.encode('utf-8'))).decode()

    def decrypt(self, text):
        cipher = AES.new(self.key.encode('utf-8'), self.mode, self.salt)
        t = cipher.decrypt(a2b_hex(text))
        return t.rstrip('\0'.encode('utf-8')).decode()


# time limited input module
def input_with_timeout(prompt, timeout=30.0):
    print('%s\n(Will automatically run the latest config in %s secs...)\ny/n? -> ' % (prompt, timeout))
    finishat = time.time() + timeout
    result = ''
    while True:
        if msvcrt.kbhit():
            chr = msvcrt.getch()
            if ord(chr) == 13:
                result = ''
            else:
                result += chr.decode()
            return result
        else:
            if time.time() > finishat:
                return ''


# press any key to stop
def input_thread(pause):
    msvcrt.getch()
    pause.append(True)


# get the information of flights
def getdate(depCity, arrCity, startDate, endDate):
    startdate = (datetime.datetime.strptime(startDate, '%Y-%m-%d') + datetime.timedelta(-3)).date()
    enddate = (datetime.datetime.strptime(endDate, '%Y-%m-%d') + datetime.timedelta(-3)).date()
    url = 'https://r.fliggy.com/cheapestCalendar/pc?_ksTS=1529541363310_2508&callback=jsonp2509&bizType=1&searchBy=1278&depCityCode=%s&arrCityCode=%s&leaveDate=%s&backDate=%s&calendarType=1&tripType=1' % (
        depCity, arrCity, startdate, enddate)
    price_html = urllib.request.urlopen(url).read().strip()

    pattern = r'jsonp2509\((.+?)\)'
    re_rule = re.compile(pattern)

    prihtm_exist = 1
    while prihtm_exist == 1 or (json_data == []):
        if re.findall(pattern, price_html.decode('utf-8')):
            json_data = re.findall(pattern, price_html.decode('utf-8'))[0]
            prihtm_exist = 0
        else:
            print('[%s] Ooops! The page crashed! [QAQ Try again after 10 mins...' % datetime.datetime.now().strftime(
                '%m-%d %H:%M'))
            time.sleep(600)

    price_json = json.loads(json_data)

    flights = []
    for i in range(7):
        date = (datetime.datetime.strptime(str(startdate), '%Y-%m-%d') + datetime.timedelta(i)).date()
        flights += price_json['result'][str(date)]  # flights info

    flights.sort(key=lambda x: x['price'])

    return flights


# automatically send info email
def sendMail(departure, arrival, price, depart_date, back_date, url, mailadr):
    _user = '************'  # server email address
    _pwd = '**********'  # server email password
    _to = mailadr
    msg = MIMEText('%s%s%s%s%s%s' % (departure, arrival, price, depart_date, back_date, url), 'plain', 'utf-8')
    msg['Subject'] = 'SPECIAL PRICE flight coming!'
    msg['From'] = _user
    msg['To'] = _to
    try:
        s = smtplib.SMTP_SSL('smtp.*****', 465)
        s.login(_user, _pwd)
        s.sendmail(_user, _to, msg.as_string())
        s.quit()
        print('Email Success!')

    except smtplib.SMTPException:
        print('Email Failed...')


# main function
def task_query_flight():
    conf = MyConfigDict()
    conf.read('config.ini')
    conf.ini2dict()
    c = conf['Global']

    depcity = list(cityDict.keys())[list(cityDict.values()).index(c['depcity'])]
    arrcity = list(cityDict.keys())[list(cityDict.values()).index(c['arrcity'])]

    if not task_query_flight.has_been_called:
        global pv_key
        pv_key = MyCrypt('I am not happy --- beca se')

        if c['usermail'] == '':
            c['usermail'] = pv_key.encrypt(str(input('Hello New User!\nTell me your email address: ')))
            conf.write(open('config.ini', 'w'))

        print('\n--- The current settings ---\n\nFrom %s(%s) To %s(%s)\n'
              '%s To %s\nDiscount: %s\nPrice up to: %s\n'
              'Refresh interval: %s ~ %s\nUser mail address: %s\n\n--- The current settings ---\n' %
              (depcity, c['depcity'], arrcity, c['arrcity'],
               c['leavedate'], c['backdate'], c['discount'],
               c['price'], c['mininterval'], c['maxinterval'],
               (c['usermail'] if '@' in c['usermail'] else pv_key.decrypt(c['usermail']))))

        default_config = str(input_with_timeout('Do you want to use the current config?', input_timeout))

        while default_config != 'y' and (default_config != ''):
            chan_item = str(input(
                'Please Choose the Changing Item:\n\t1 -> all\n\t'
                '2 -> city\n\t3 -> date\n\t4 -> discount & price\n\t'
                '5 -> refresh interval\n\t6 -> user mail address\n\t'
                '0 -> run the old config file\n GO! -> '))
            if chan_item == '1':
                for k in list(conf['Global'].keys())[:2]:
                    conf['Global'][k] = cityDict[str(input('Enter the %s: ' % k))]
                for k in list(conf['Global'].keys())[2:]:
                    conf['Global'][k] = str(input('Enter the %s: ' % k))
            elif chan_item == '2':
                for k in list(conf['Global'].keys())[:2]:
                    conf['Global'][k] = cityDict[str(input('Enter the %s: ' % k))]
            elif '3' <= chan_item <= '5':
                for k in list(conf['Global'].keys())[2 * int(chan_item) - 4:2 * int(chan_item) - 2]:
                    conf['Global'][k] = str(input('Enter the %s: ' % k))
            elif chan_item == '6':
                for k in list(conf['Global'].keys())[2 * int(chan_item) - 4:]:
                    conf['Global'][k] = pv_key.encrypt(str(input('Enter the %s: ' % k)))
            elif chan_item == '0':
                break
            else:
                print('-' * 18 + '\nNonExistent Number\nContinue after 3 secs...\n' + '-' * 18)
                time.sleep(3)
            default_config = str(input_with_timeout(
                '\nENTER to run the config file, others to modify', input_timeout))

            conf.write(open('config.ini', 'w'))

        with open('price history.txt', 'a', encoding='utf-8-sig') as ph:
            ph.write('')
        with open('flights info.txt', 'a', encoding='utf-8-sig') as f:
            f.write('')

        task_query_flight.has_been_called = True

    depcode = str(conf['Global']['depcity'])
    depcity = str(list(cityDict.keys())[list(cityDict.values()).index(depcode)])
    arrcode = str(conf['Global']['arrcity'])
    arrcity = str(list(cityDict.keys())[list(cityDict.values()).index(arrcode)])
    leavedate = str(conf['Global']['leavedate'])
    backdate = str(conf['Global']['backdate'])
    discount = conf['Global']['discount']
    maxprice = conf['Global']['price']
    mininterval = int(conf['Global']['mininterval'])
    maxinterval = int(conf['Global']['maxinterval'])
    usermail = pv_key.decrypt(str(conf['Global']['usermail']))

    current_time = datetime.datetime.now()

    print('%s To %s\n%s(%s) To %s(%s)' % (leavedate, backdate, depcity, depcode, arrcity, arrcode))
    flights = getdate(depcode, arrcode, leavedate, backdate)
    lowestprice = float('inf')
    # printed = 0
    for f in flights:
        if 0 < f['price']:
            departure = 'from: %s' % f['depCityCode']
            arrival = ' to: %s' % f['arrCityCode'] + ' ' * 8
            price = 'price: %s (discount: %s)' % (f['price'] + f['tax'], f['discount']) + ' ' * 8
            depart_date = 'depart: %s' % f['leaveDate'] + ' ' * 4
            back_date = 'back: %s\n' % f['backDate']
            url = 'https:%s\n' % f['url']

            if (f['price'] + f['tax']) <= lowestprice:
                lowestprice = f['price'] + f['tax']

                if os.path.getsize('price history.txt') <= 10:
                    with open('price history.txt', 'a', encoding='utf-8-sig') as ph:
                        ph.write('%s\t%s\t%s\t%s\n' % (
                            datetime.datetime.now().strftime('%m-%d %H:%M'), lowestprice, f['leaveDate'],
                            f['backDate']))
                with open('price history.txt', 'r', encoding='utf-8-sig') as ph:
                    line = ph.readlines()
                    if str(lowestprice) not in line[-1]:
                        with open('price history.txt', 'a', encoding='utf-8-sig') as ph:
                            ph.write('%s\t%s\t%s\t%s\n' % (
                                datetime.datetime.now().strftime('%m-%d %H:%M'), lowestprice, f['leaveDate'],
                                f['backDate']))

                print('\n--*- The CHEAPEST flight now is -*--\n' + departure + arrival +
                      price + '\n' + depart_date + ' ' * 3 + back_date + url + '-' * 36 + '\n')
                # printed = 1

            if (0 < f['discount'] <= float(discount)) or (f['price'] + f['tax']) <= float(maxprice):
                with open('flights info.txt', 'r', encoding='utf-8-sig') as f:
                    exist = 0
                    for line in f.readlines()[2::4]:
                        if '%s%s%s%s%s' % (departure, arrival, price, depart_date, back_date) in line:
                            exist += 1
                            print('[%s] No tickets for the poor [QAQ' % datetime.datetime.now().strftime('%m-%d %H:%M'))
                            break
                    if exist == 0:
                        print('-' * 10 + '\n' + '[%s]\n' + departure + arrival + price +
                              depart_date + back_date + url % current_time.strftime('%H:%M:%S'))
                        sendMail(departure, arrival, price, depart_date, back_date, url, usermail)
                        with open('flights info.txt', 'a', encoding='utf-8-sig') as f:
                            f.write('-' * 10 + '\n' + '%s%s%s%s%s%s' % (
                                departure, arrival, price, depart_date, back_date, url))

    if current_time.hour == 0 and (0 <= current_time.minute <= 15):
        current_date = current_time.date() + datetime.timedelta(days=-1)
        if not os.path.exists('[%s to %s] price history %s.txt' % (depcode, arrcode, current_date)):
            print('[%s] Will clear current price history data in 3 secs...' % current_time.strftime('%m-%d %H:%M'))
            time.sleep(3)
            shutil.move('price history.txt',
                        r'.\price history\[%s to %s] price history %s.txt' % (depcode, arrcode, current_date))
            print('[%s] Copy price history data SUCCESS! Clear SUCCESS!\n' % current_time.strftime('%m-%d %H:%M'))
        if os.path.exists('flights info.txt') and (os.path.getsize('flights info.txt') >= 10):
            if not os.path.exists('[%s to %s] flights info %s.txt' % (depcode, arrcode, current_date)):
                print('[%s] Will clear current flights data in 3 secs...' % current_time.strftime('%m-%d %H:%M'))
                time.sleep(3)
                shutil.move('flights info.txt',
                            r'.\flight info\[%s to %s] flights info %s.txt' % (depcode, arrcode, current_date))
                print('[%s] Copy flights data SUCCESS! Clear SUCCESS!\n' % current_time.strftime('%m-%d %H:%M'))
        else:
            print('[%s] No tickets for the poor [QAQ\n' % current_time.strftime('%m-%d %H:%M'))

    randomtime = random.randint(mininterval, maxinterval)
    global timer
    timer = threading.Timer(randomtime, task_query_flight)
    timer.setDaemon(True)
    timer.start()
    print('[%s] sleep for %s secs... /Press any key to stop\n' % (current_time.strftime('%H:%M:%S'), randomtime))

    pause = []
    stop = threading.Thread(target=input_thread, args=(pause,))
    stop.start()
    if pause:
        print('[%s] Don\'t wake up me!\n' % (current_time.strftime('%H:%M:%S')))
        timer.cancel()


if __name__ == '__main__':
    task_query_flight.has_been_called = False
    task_query_flight()
