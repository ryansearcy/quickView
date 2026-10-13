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
    'partly cloudy': '9925',             # ⛅
    'sunny': '9728',                     # ☀️
    'clear': '9728',                     # ☀️
    'overcast': '9729',                  # ☁️
    'mist': '127745',                    # 🌁
    'fog': '127745',                     # 🌁
    'smoky haze': '127745',
    'rain': '127783',                    # 🌧️

    # Additional cloudy & overcast conditions
    'cloudy': '9729',                    # ☁️
    'patchy cloudy': '9925',             # ⛅

    # Additional fog & visibility conditions
    'freezing fog': '127745',            # 🌁

    # Rain, drizzle & showers
    'light rain': '127783',              # 🌧️
    'heavy rain': '127783',              # 🌧️
    'moderate rain': '127783',           # 🌧️
    'patchy rain possible': '127783',    # 🌧️
    'patchy light rain': '127783',       # 🌧️
    'light rain shower': '127783',       # 🌧️
    'moderate or heavy rain shower': '127783', # 🌧️
    'torrential rain shower': '127783',  # 🌧️
    'heavy rain at times': '127783',     # 🌧️
    'patchy light drizzle': '127783',    # 🌧️
    'light drizzle': '127783',           # 🌧️
    'freezing drizzle': '127783',        # 🌧️
    'heavy freezing drizzle': '127783',  # 🌧️

    # Thunderstorms
    'thundery outbreaks possible': '9928',    # ⛈️
    'patchy light rain with thunder': '9928', # ⛈️
    'moderate or heavy rain with thunder': '9928', # ⛈️
    'patchy light snow with thunder': '9928', # ⛈️
    'moderate or heavy snow with thunder': '9928', # ⛈️

    # Snow, sleet & ice pellets
    'snow': '127784',                    # 🌨️
    'light snow': '127784',              # 🌨️
    'heavy snow': '127784',              # 🌨️
    'moderate snow': '127784',           # 🌨️
    'patchy snow possible': '127784',    # 🌨️
    'patchy light snow': '127784',       # 🌨️
    'patchy moderate snow': '127784',    # 🌨️
    'patchy heavy snow': '127784',       # 🌨️
    'light snow showers': '127784',      # 🌨️
    'moderate or heavy snow showers': '127784', #🌨️
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
    w = requests.get(f"""https://wttr.in/{city}?format=%C""").text.strip().lower()
    t = re.search(r"\d+", requests.get(f"""https://wttr.in/{city}?format=%t""").text)[0]
    w = weatherEmojiMapping.get(w, '2754')
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
                
def fetchTransitTimes():
    pathJSON = requests.get("https://www.panynj.gov/bin/portauthority/ridepath.json", headers={'User-Agent': 'Firefox'}).json()
    pathTimes = {}
    
    # Comprehensive bidirectional PATH line sequences and their associated headsigns
    PATH_LINES = {
        'World Trade Center': ['NWK', 'HAR', 'JSQ', 'GRV', 'EXP', 'WTC'],
        'Newark': ['WTC', 'EXP', 'GRV', 'JSQ', 'HAR', 'NWK'],
        '33rd Street via Hoboken': ['JSQ', 'GRV', 'NEW', 'HOB', 'CHR', '09S', '14S', '23S', '33S'],
        'Journal Square (via Hoboken)': ['33S', '23S', '14S', '09S', 'CHR', 'HOB', 'NEW', 'GRV', 'JSQ'],
        '33rd Street': ['JSQ', 'GRV', 'NEW', 'CHR', '09S', '14S', '23S', '33S'],
        'Journal Square': ['33S', '23S', '14S', '09S', 'CHR', 'NEW', 'GRV', 'JSQ'],
        'Hoboken to WTC': ['HOB', 'NEW', 'EXP', 'WTC'],
        'World Trade Center to Hoboken': ['WTC', 'EXP', 'NEW', 'HOB'],
        'Hoboken to 33rd': ['HOB', 'CHR', '09S', '14S', '23S', '33S'],
        'Hoboken': ['33S', '23S', '14S', '09S', 'CHR', 'HOB']
    }

    travel_times = {('JSQ', 'GRV'): 5, ('GRV', 'EXP'): 3, ('EXP', 'WTC'): 3, ('GRV', 'NEW'): 3, ('NEW', 'HOB'): 4, ('NEW', 'CHR'): 12, ('HOB', 'CHR'): 12, ('CHR', '09S'): 1, ('09S', '14S'): 2, ('14S', '23S'): 1, ('23S', '33S'): 2}
    
    def get_predecessor_code(curr_code, headsign, target_station):
        line = PATH_LINES.get(headsign)
        if not line:
            for l_name, l_stations in PATH_LINES.items():
                if curr_code in l_stations and target_station in l_stations:
                    line = l_stations
                    break
        
        if not line:
            return None
            
        if curr_code in line and target_station in line:
            curr_idx = line.index(curr_code)
            target_idx = line.index(target_station)
            
            if curr_idx < target_idx:
                if curr_idx > 0:
                    return line[curr_idx - 1]
            elif curr_idx > target_idx:
                if curr_idx < len(line) - 1:
                    return line[curr_idx + 1]
                    
        return None

    def get_station_messages(considered_station, directions):
        messages = []
        for stationData in pathJSON.get('results', []):
            if stationData.get('consideredStation') == considered_station:
                for destinationData in stationData.get('destinations', []):
                    if not directions or destinationData.get('label') in directions:
                        messages.extend(destinationData.get('messages', []))
        return messages

    code_to_name = {s['consideredStation']: s['stationName'] for s in stations}

    # Step 1: Initialize data structure based on user requested stations
    for s in stations:
        pathTimes[s['stationName']] = {
            dest.strip(): {'seconds': [], 'headsigns': []} 
            for dest in s['destinations'].split(',')
        }

    # Step 2: Populate raw arrival seconds from API data
    for s in stations:
        station_name = s['stationName']
        considered = s['consideredStation']
        directions = [d.strip() for d in s['direction'].split(',')]
        
        messages = get_station_messages(considered, directions)
        
        for j in messages:
            target = j.get('target')
            if target in pathTimes[station_name]:
                try:
                    sec = int(j['secondsToArrival'])
                    pathTimes[station_name][target]['seconds'].append(sec)
                    pathTimes[station_name][target]['headsigns'].append(j.get('headSign', target))
                except (ValueError, TypeError):
                    continue

    # Step 3: Fallback check with deduplication, max-2 cap, and debug logging
    print("--- [DEBUG] Starting Fallback Processing ---")
    for s_info in stations:
        station_name = s_info['stationName']
        considered = s_info['consideredStation']
        
        if station_name not in pathTimes:
            continue
            
        for target in pathTimes[station_name]:
            data = pathTimes[station_name][target]
            
            # Debug log current state
            print(f"[DEBUG] Station: {station_name} | Target: {target} | Initial Raw Seconds Count: {len(data['seconds'])}")
            
            # If less than 2 arrival times, apply fallback logic
            if len(data['seconds']) < 2:
                print(f"[DEBUG] -> Triggered fallback for {station_name} ({target}) because count ({len(data['seconds'])}) < 2")
                
                headsign_context = data['headsigns'][0] if data['headsigns'] else target
                prev_code = get_predecessor_code(considered, headsign_context, target)
                
                if not prev_code:
                    print(f"[DEBUG] -> Warning: Could not find predecessor code for {considered} heading to {target}")
                    continue
                
                prev_station_name = code_to_name.get(prev_code, prev_code)
                print(f"[DEBUG] -> Identified predecessor station code: {prev_code} ({prev_station_name})")
                
                prev_messages = get_station_messages(prev_code, [])
                
                prev_seconds = []
                prev_headsigns = []
                for j in prev_messages:
                    if j.get('target') == target:
                        try:
                            sec = int(j['secondsToArrival'])
                            prev_seconds.append(sec)
                            prev_headsigns.append(j.get('headSign', target))
                        except (ValueError, TypeError):
                            continue
                
                if prev_seconds:
                    travel_constant_mins = travel_times.get((prev_code, considered), travel_times.get((considered, prev_code), 3))
                    travel_constant_secs = travel_constant_mins * 60
                    print(f"[DEBUG] -> Using travel offset: {travel_constant_mins} mins ({travel_constant_secs} secs) from {prev_station_name}")
                    
                    fallback_seconds = [sec + travel_constant_secs for sec in prev_seconds]
                    
                    existing_seconds = set(data['seconds'])
                    combined_seconds = list(data['seconds'])
                    
                    for fs in fallback_seconds:
                        if not any(abs(fs - existing) < 180 for existing in existing_seconds):
                            combined_seconds.append(fs)
                            existing_seconds.add(fs)
                            
                    data['seconds'] = combined_seconds
                    if not data['headsigns'] and prev_headsigns:
                        data['headsigns'] = list(prev_headsigns)
                        
                    print(f"[DEBUG] -> Successfully updated seconds list for {station_name}: {data['seconds']}")
                else:
                    print(f"[DEBUG] -> Warning: Predecessor station {prev_station_name} had no active arrivals for target {target}")

    print("--- [DEBUG] Finished Fallback Processing ---\n")

    # Step 4: Final sorting, capping at max 2 times, stringification and formatting
    formatted_pathTimes = {}
    for station_name in pathTimes:
        formatted_pathTimes[station_name] = {}
        for target, data in pathTimes[station_name].items():
            secs = sorted(data['seconds'])[:2]
            if not secs:
                formatted_pathTimes[station_name][target] = {}
                continue
            
            t_mins_list = [str(math.floor(s / 60)) + ' mins' for s in secs]
            tTA_str = ', '.join(t_mins_list)
            
            sTA_val = secs[0]
            
            hS_val = target
            if data['headsigns']:
                hs_raw = data['headsigns'][0]
                match hs_raw:
                    case '33rd Street':
                        hS_val = '33rd St'
                    case '33rd Street via Hoboken':
                        hS_val = '33rd via HOB'
                    case _:
                        hS_val = target
                        
            formatted_pathTimes[station_name][target] = {
                'sTA': sTA_val,
                'tTA': tTA_str,
                'hS': hS_val
            }

    return formatted_pathTimes

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