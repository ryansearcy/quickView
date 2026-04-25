from flask import Flask, Response, redirect, render_template, url_for
import requests, json, time, math, re
from json import JSONDecodeError
from datetime import datetime
from typing import Any
from selenium import webdriver
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.firefox.service import Service as FirefoxService
from webdriver_manager.firefox import GeckoDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup

quickView = Flask(__name__)

emptyString: str = ''
emptyTypes: dict[type, Any] = {str: emptyString, list: [], dict: {}, datetime: datetime.today()}

#Transit Variables
transitVariables = ['stations', 'schedule']
stations: list = emptyTypes[list]
schedule: dict = {}
#Weather Variables
weatherVariables = ['weather', 'temp']
weather: str = emptyTypes[str]
temp: str = emptyTypes[str]
weatherEmojiMapping = {
    'Partly cloudy': '9925',
    'Sunny': '9728',
    'Clear': '9728',
    'Overcast': 'x2601',
    'Mist': '127745',
    'Fog': '127745',
    'Rain': '127783'
}

apiVariables: list[str] = emptyTypes[list]
appVariables: list[str] = ['apiVariables'] + transitVariables + weatherVariables

class HtmlTable(object):
    '''
    HtmlTable
    '''

    def __init__(self, url):
        '''
        Constructor
        '''
        firefoxOptions = Options()
        firefoxOptions.binary_location = "/snap/firefox/current/usr/lib/firefox/firefox"
        firefoxOptions.add_argument('--headless')
        firefoxOptions.add_argument('--disable-gpu')
        firefoxDriver = webdriver.Firefox(options=firefoxOptions)
        firefoxDriver.get(url)
        time.sleep(1)
        page = firefoxDriver.page_source
        firefoxDriver.quit()
        #self.html_page = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'})
        #print(requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}).text)

        self.soup = BeautifulSoup(page, 'html.parser')
        #self.body = self.soup.find("table")
        #print(self.body)

    def get_weekday_tables(self,header_tag:str=None)->dict:
        
        tables = {'Weekday':{}}
        for i,table in enumerate(self.soup.find_all("table")):
            fields = []
            record= {}
            for td in table.find_all('tr', recursive=True)[0].find_all('td', recursive=True):
                    text = re.sub("\n", "", td.text)
                    label = re.search(".+?(?=Arrival)|.+?(?=Departure)|(?<=Arrival at).*", text)[0].strip()
                    label = re.sub("\\xa0", "", label)
                    label = re.sub("Exchange", "Exchange Place", label)
                    label = re.sub("33 St", "33S", label)
                    label = re.sub("\\.", "", label)
                    fields.append(label)
                    record[label] = []
            #print(fields)
            for i, tr in enumerate(table.find_all('tr', recursive=True)):
                if i == 0:
                        continue
                for j, td in enumerate(tr.find_all('td', recursive=True)):
                    record[fields[j]].append(td.text)
            #print(record)
                if fields[len(fields)-1] not in tables:
                    tables['Weekday'][fields[len(fields)-1]] = {}
                    tables['Weekday'][fields[len(fields)-1]][fields[0]] = record
                else:
                    if fields[0] in tables['Weekday'][fields[len(fields)-1]]:
                        continue
                    else:
                        tables['Weekday'][fields[len(fields)-1]][fields[0]] = record    
            
        return tables

    def get_weekend_tables(self,header_tag:str=None)->dict:

        tables = {'Saturday':{}, 'Sunday':{}}
        k = 0
        c1 = 0
        c2 = 0
        for i,table in enumerate(self.soup.find_all("table")):
            fields = []
            record= {}
            for td in table.find_all('tr', recursive=True)[0].find_all('td', recursive=True):
                    text = re.sub("\n", "", td.text)
                    label = re.search(".+?(?=Arrival)|.+?(?=Departure)|(?<=Arrival at).*", text)[0].strip()
                    label = re.sub("\\xa0", "", label)
                    label = re.sub("Exchange", "Exchange Place", label)
                    label = re.sub("33 St", "33S", label)
                    label = re.sub("\\.", "", label)
                    fields.append(label)
                    record[label] = []
            #print(fields)
            for i, tr in enumerate(table.find_all('tr', recursive=True)):
                if i == 0:
                        continue
                for j, td in enumerate(tr.find_all('td', recursive=True)):
                    record[fields[j]].append(td.text)
            #print(record)
            if k == 0:
                if fields[len(fields)-1] not in tables['Saturday']:
                    tables['Saturday'][fields[len(fields)-1]] = {}
                    tables['Saturday'][fields[len(fields)-1]][fields[0]] = record
                    c1+=1
                else:
                    if fields[0] in tables['Saturday'][fields[len(fields)-1]]:
                        tables['Sunday'][fields[len(fields)-1]] = {}
                        tables['Sunday'][fields[len(fields)-1]][fields[0]] = record
                        k+=1
                        c2+=1
                        continue
                    else:
                        tables['Saturday'][fields[len(fields)-1]][fields[0]] = record
                        c1+=1
            if k == 1 and c2 < c1:
                if fields[len(fields)-1] not in tables['Sunday']:
                    tables['Sunday'][fields[len(fields)-1]] = {}
                    tables['Sunday'][fields[len(fields)-1]][fields[0]] = record
                    c2+=1
                else:
                    if fields[0] in tables['Sunday'][fields[len(fields)-1]]:
                        print(fields[0] + ' - ' + fields[len(fields)-1])
                        break
                    else:
                        tables['Sunday'][fields[len(fields)-1]][fields[0]] = record
                        c2+=1
            
        return tables

def checkForEmptyGlobalVariables(variableNames: list[str] | str) -> bool:
    if type(variableNames) == str:
        variables = [variableNames]
    else:
        variables = variableNames
    if set(variables).issubset(set(appVariables)) is False:
        raise ValueError('variables are not in editable global scope')
    globalVars = globals()
    return [globalVars[v] == emptyTypes[type(globalVars[v])] for v in variables].__contains__(True)

def setGlobalVariable(variableName: str | list[str], value: Any, writeToJSON: bool=False) -> None:
    if type(variableName) == str:
        globalVariables = globals()
        if variableName not in appVariables:
            raise ValueError('Variable does not exist in editable scope')
        if type(globalVariables[variableName]) != type(value):
            quickView.logger.debug('globalVariable type is ' + type(globalVariables[variableName]).__name__ + ' while value type is ' + type(value).__name__)
            raise ValueError('Value type does not match variable')
        globals()[variableName] = value
        if writeToJSON:
            writeJSONVariables({variableName: value})
    else:
        for v in variableName:
            setGlobalVariable(v, value)
        if writeToJSON:
            writeJSONVariables({v: value for v in variableName})
    return

def loadJSONVariables() -> None:
    try:
        jsonFile = open("configPATH.json", "r")
        try:
            jsonData = json.load(jsonFile)
            for variable in jsonData:
                setGlobalVariable(variable, jsonData[variable], False)
        except JSONDecodeError:
            jsonFile.close()
            return
    except:
        jsonFile = open("configPATH.json", "x")
    jsonFile.close()
    return

def writeJSONVariables(variables: dict[str, Any]) -> None:
    jsonFile = open("configPATH.json", "r")
    try:
        jsonData = json.load(jsonFile)
    except JSONDecodeError:
        jsonData = emptyTypes[dict]
    jsonFile.close()
    for v in variables:
        jsonData[v] = variables[v]
    jsonFile = open("configPATH.json", "w")
    jsonFile.write(json.dumps(jsonData))
    jsonFile.close()
    return

def fetchSchedules() -> None:
    weekday_url="https://www.panynj.gov/path/en/schedules-maps/weekday-schedules.html"
    weekday_schedule=HtmlTable(weekday_url)
    weekday_schedule=weekday_schedule.get_weekday_tables()
    weekend_url="https://www.panynj.gov/path/en/schedules-maps/weekend-schedules.html"
    weekend_schedule=HtmlTable(weekend_url)
    weekend_schedule=weekend_schedule.get_weekend_tables()
    setGlobalVariable('schedule', weekday_schedule | weekend_schedule)
    return

def getWeather() -> str:
    city = "Jersey+City"
    w = requests.get(f"""https://wttr.in/{city}?format=%C""").text
    t = re.search(r"\d+", requests.get(f"""https://wttr.in/{city}?format=%t""").text)[0]
    w = weatherEmojiMapping[w]
    quickView.logger.debug(w)
    quickView.logger.debug(t)
    setGlobalVariable('weather', w)
    setGlobalVariable('temp', t)
    return

@quickView.route("/")
def genAuthCode() -> Response:
    loadJSONVariables()
    if checkForEmptyGlobalVariables(apiVariables):
        return redirect(url_for('startSetup'))
    getWeather()
   # fetchSchedules()
    return redirect(url_for('realtimeTransit'))

@quickView.route("/setup")
def startSetup() -> None:
    return

# def addScheduledTimes(realTimeTransit: dict):
#     for i in realTimeTransit:
#         for j in realTimeTransit[i]:
#             if len(j) < 1 or len([t for time in realTimeTransit[i][j] if time >= 10]) == 0:
#                realTimeTransit[i][j] = realTimeTransit[i][j] + [t for  ]
                
def fetchTransitTimes() -> dict:
    pathJSON = requests.get("https://www.panynj.gov/bin/portauthority/ridepath.json", headers={'User-Agent':'Firefox'}).json()
    pathTimes = {}
    mappings = {}
    for s in stations:
        pathTimes[s['stationName']] = {dest: {} for dest in [dest.strip() for dest in s['destinations'].split(',')]}
        for d in [d.strip() for d in s['direction'].split(',')]:
            if s['stationName'] in mappings:
                mappings[s['stationName']] = mappings[s['stationName']] + [destinationData['messages'] for destinationData in [stationData['destinations'] for stationData in pathJSON['results'] if stationData['consideredStation'] == s['consideredStation']][0] if destinationData['label'] == d][0]
            else:
                mappings[s['stationName']] = [destinationData['messages'] for destinationData in [stationData['destinations'] for stationData in pathJSON['results'] if stationData['consideredStation'] == s['consideredStation']][0] if destinationData['label'] == d][0]
    for i in mappings:
        for j in mappings[i]:
            if j['target'] not in pathTimes[i]:
                continue
            if pathTimes[i][j['target']] != {}:
                pathTimes[i][j['target']]['tTA'] = pathTimes[i][j['target']]['tTA'] + ', ' + str(math.floor(int(j['secondsToArrival'])/60)) + ' mins'
                if pathTimes[i][j['target']]['sTA'] > int(j['secondsToArrival']):
                    match(j['headSign']):
                        case '33rd Street':
                            pathTimes[i][j['target']]['hS'] = '33rd St'
                        case '33rd Street via Hoboken':
                            pathTimes[i][j['target']]['hS'] = '33rd via HOB'
                        case _:
                            pathTimes[i][j['target']]['hS'] = j['target']
            else:
                pathTimes[i][j['target']]['sTA'] = int(j['secondsToArrival'])
                pathTimes[i][j['target']]['tTA'] = str(math.floor(int(j['secondsToArrival'])/60)) + ' mins'
                match(j['headSign']):
                        case '33rd Street':
                            pathTimes[i][j['target']]['hS'] = '33rd St'
                        case '33rd Street via Hoboken':
                            pathTimes[i][j['target']]['hS'] = '33rd via HOB'
                        case _:
                            pathTimes[i][j['target']]['hS'] = j['target']
    return pathTimes

@quickView.route("/realtime-transit")
def realtimeTransit() -> str:
    transitTimes = fetchTransitTimes()
    return render_template('transit.html', lines=transitTimes, keep_trailing_newline=True)

@quickView.get("/transit-times")
def fetchTimes() -> str:
    transitTimes = fetchTransitTimes()
    return json.dumps(transitTimes)

@quickView.get("/weather")
def updateWeather() -> str:
    getWeather()
    return json.dumps({'weather': weather, 'temp': temp})