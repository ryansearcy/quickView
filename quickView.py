from flask import Flask, Response, redirect, render_template, url_for
import requests, json, time, math, re
from json import JSONDecodeError
from datetime import datetime
from typing import Any

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
    'Partly cloudy': '9925',            # ⛅
    'Sunny': '9728',                    # ☀️
    'Clear': '9728',                    # ☀️
    'Overcast': 'x2601',                # ☁️
    'Mist': '127745',                   # 🌁
    'Fog': '127745',                    # 🌁
    'Rain': '127783',                   # 🌧️

    # Additional cloudy & overcast conditions
    'Cloudy': '9729',                   # ☁️
    'Patchy cloudy': '9925',            # ⛅

    # Additional fog & visibility conditions
    'Freezing fog': '127745',           # 🌁

    # Rain, drizzle & showers
    'Light rain': '127783',             # 🌧️
    'Heavy rain': '127783',             # 🌧️
    'Moderate rain': '127783',          # 🌧️
    'Patchy rain possible': '127783',   # 🌧️
    'Patchy light rain': '127783',      # 🌧️
    'Light rain shower': '127783',      # 🌧️
    'Moderate or heavy rain shower': '127783', # 🌧️
    'Torrential rain shower': '127783', # 🌧️
    'Heavy rain at times': '127783',    # 🌧️
    'Patchy light drizzle': '127783',   # 🌧️
    'Light drizzle': '127783',          # 🌧️
    'Freezing drizzle': '127783',       # 🌧️
    'Heavy freezing drizzle': '127783', # 🌧️

    # Thunderstorms
    'Thundery outbreaks possible': '9928',    # ⛈️
    'Patchy light rain with thunder': '9928', # ⛈️
    'Moderate or heavy rain with thunder': '9928', # ⛈️
    'Patchy light snow with thunder': '9928', # ⛈️
    'Moderate or heavy snow with thunder': '9928', # ⛈️

    # Snow, sleet & ice pellets
    'Snow': '127784',                   # 🌨️
    'Light snow': '127784',             # 🌨️
    'Heavy snow': '127784',             # 🌨️
    'Moderate snow': '127784',          # 🌨️
    'Patchy snow possible': '127784',   # 🌨️
    'Patchy light snow': '127784',      # 🌨️
    'Patchy moderate snow': '127784',   # 🌨️
    'Patchy heavy snow': '127784',      # 🌨️
    'Light snow showers': '127784',     # 🌨️
    'Moderate or heavy snow showers': '127784', # 🌨️
    'Blowing snow': '127784',           # 🌨️
    'Blizzard': '127784',               # 🌨️
    'Sleet': '127783',                  # 🌧️
    'Light sleet': '127783',
    'Moderate or heavy sleet': '127783',
    'Light sleet showers': '127783',
    'Moderate or heavy sleet showers': '127783',
    'Ice pellets': '127783',
    'Light showers of ice pellets': '127783',
    'Moderate or heavy showers of ice pellets': '127783'
}

apiVariables: list[str] = emptyTypes[list]
appVariables: list[str] = ['apiVariables'] + transitVariables + weatherVariables

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