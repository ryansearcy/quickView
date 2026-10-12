from flask import Flask, Response, request, redirect, render_template, url_for
import string, random, base64, requests, json, time, operator, math, re
from json import JSONDecodeError
from datetime import timedelta, datetime
from typing import Any
from selenium import webdriver
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.firefox.service import Service as FirefoxService
from webdriver_manager.firefox import GeckoDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup
import python_weather
import asyncio

quickView = Flask(__name__)

emptyString: str = ''
emptyTypes: dict[type, Any] = {str: emptyString, list: [], dict: {}, datetime: datetime.today()}

#Spotify API variables
spotifyAPIVariables: list[str] = ['clientID', 'clientSecret', 'appScope', 'redirectUri', 'deviceID', 'spotifyUsername', 'spotifyPassword']
clientID: str = emptyTypes[str]
clientSecret: str = emptyTypes[str]
authCode: str = emptyTypes[str]
appScope: str = emptyTypes[str]
redirectUri: str = emptyTypes[str]
deviceID: str = emptyTypes[str]
spotifyUsername = emptyTypes[str]
spotifyPassword = emptyTypes[str]
#Spotify Token Variables
spotifyTokenVariables: list[str] = ['accessToken', 'refreshToken', 'expiresAt']
accessToken: str = emptyTypes[str]
refreshToken: str = emptyTypes[str]
expiresAt: datetime = emptyTypes[datetime]
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
appVariables: list[str] = spotifyAPIVariables + spotifyTokenVariables + ['apiVariables'] + transitVariables + weatherVariables

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

def genRandomString(length: int) -> str:
    letters = string.ascii_letters + string.digits
    return emptyString.join(random.choice(letters) for i in range(length))

def fetchAuthToken(authCode: int) -> int:
    formData = {'code': authCode, 'redirect_uri': redirectUri, 'grant_type':'authorization_code'}
    headers = {'Content-Type':'application/x-www-form-urlencoded', 'Authorization': 'Basic ' + base64.b64encode((clientID + ':' +clientSecret).encode('ascii')).decode('ascii')}
    authResponse = requests.post('https://accounts.spotify.com/api/token', data=formData, headers=headers)
    if authResponse.status_code == 200:
        authJSON = authResponse.json()
        setGlobalVariable('accessToken', authJSON['access_token'])
        setGlobalVariable('refreshToken', authJSON['refresh_token'])
        setGlobalVariable('expiresAt', datetime.today() + timedelta(seconds=(round(authJSON['expires_in']*0.75))))
    return authResponse.status_code

def refreshAuthToken() -> int:
    formData = {'refresh_token': refreshToken, 'grant_type':'refresh_token'}
    headers = {'Authorization': 'Basic ' + base64.b64encode((clientID + ':' +clientSecret).encode('ascii')).decode('ascii')}
    authResponse = requests.post('https://accounts.spotify.com/api/token', data=formData, headers=headers)
    if authResponse.status_code == 200:
        authJSON = authResponse.json()
        setGlobalVariable('accessToken', authJSON['access_token'])
        if 'refresh_token' in authJSON:
            setGlobalVariable('refresh_token', authJSON['refresh_token'])
        setGlobalVariable('expiresAt', datetime.today() + timedelta(seconds=(round(authJSON['expires_in']*0.75))))
    return authResponse.status_code

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
    state: str = genRandomString(16)
    quickView.logger.debug('Starting firefox headless')
    firefoxOptions = Options()
    firefoxOptions.binary_location = "/snap/firefox/current/usr/lib/firefox/firefox"
    firefoxOptions.add_argument('--headless')
    firefoxDriver = webdriver.Firefox(options=firefoxOptions)
    firefoxDriver.get('https://accounts.spotify.com/en/login?allow_password=1')
    spotifyUsernameInput = firefoxDriver.find_element(value='username')
    spotifyUsernameInput.send_keys(spotifyUsername)
    spotifyPasswordInput = firefoxDriver.find_element(value='password')
    spotifyPasswordInput.send_keys(spotifyPassword)
    firefoxDriver.find_element(By.XPATH, "//form").submit()
    time.sleep(2)
    firefoxDriver.get('https://accounts.spotify.com/authorize?' + f'response_type=code&client_id={clientID}&scope={appScope}&redirect_uri={redirectUri}&state={state}')
    quickView.logger.debug('https://accounts.spotify.com/authorize?' + f'response_type=code&client_id={clientID}&scope={appScope}&redirect_uri={redirectUri}&state={state}')
    while checkForEmptyGlobalVariables('accessToken'):
        quickView.logger.debug('waiting for login')
        time.sleep(1)
    firefoxDriver.quit()
    return redirect(url_for('displayPlaybackData'))

@quickView.route("/setup")
def startSetup() -> None:
    return

@quickView.route("/callback")
def genAuthToken() -> Response:
    authCode = request.args.get('code')
    state = request.args.get('state')
    if state is None:
        quickView.logger.debug('Returned State is null')
        return "<h1>Error: state is null</h1>"
    fetchAuthToken(authCode)
    return redirect(url_for('displayPlaybackData'))

def getSpotifyPlaybackData() -> dict:
    if checkForEmptyGlobalVariables('accessToken'):
        return {'status_code': 401, 'is_playing': False}
    if expiresAt <= datetime.today():
        refreshAuthToken()
    playbackHeaders: dict = {'Authorization':'Bearer ' + accessToken}
    playbackInfo: Response = requests.get('https://api.spotify.com/v1/me/player', headers=playbackHeaders)
    if playbackInfo.status_code == 200:
        playbackData = playbackInfo.json()
        quickView.logger.debug('Device ID: ' + playbackData['device']['name'])
        playbackData: dict[str, str | int | bool] = {
            'status_code': playbackInfo.status_code if checkForEmptyGlobalVariables('deviceID') or playbackData['device']['name'] == deviceID else 204,
            'is_playing': playbackData['is_playing'] if 'is_playing' in playbackData and (checkForEmptyGlobalVariables('deviceID') or playbackData['device']['name'] == deviceID) else False,
            'name': playbackData['item']['name'] if 'item' in playbackData else '',
            'artists': ', '.join([artist['name'] for artist in playbackData['item']['artists']]) if 'item' in playbackData else '',
            'cover_art': playbackData['item']['album']['images'][0]['url'] if 'item' in playbackData else ''
        }
    else:
        if playbackInfo.status_code != 204:
            setGlobalVariable(['accessToken', 'refreshToken'], emptyTypes[str])
        playbackData: dict[str, int | bool] = {'status_code': playbackInfo.status_code, 'is_playing': False}
    return playbackData

@quickView.route("/playback-data")
def getPlaybackState() -> dict:
    playbackData = getSpotifyPlaybackData()
    #quickView.logger.debug('Currently Playing?: ' + playbackData['is_playing'].__str__())
    return json.dumps(playbackData)

@quickView.route("/spotify")
def displayPlaybackData() -> Response:
    if checkForEmptyGlobalVariables(spotifyTokenVariables):
        return redirect(url_for('genAuthCode'))
    playbackData = getSpotifyPlaybackData()
    if playbackData['is_playing']:
        return render_template('spotify.html', title=playbackData['name'], artists=playbackData['artists'], cover_art=playbackData['cover_art'])
    else:
        return redirect(url_for('realtimeTransit'))
    
@quickView.route("/previous-song")
def previousSong():
    previousSuccess = requests.post('https://api.spotify.com/v1/me/player/previous', headers={'Authorization':'Bearer ' + accessToken})
    if previousSuccess.status_code == 204:
        quickView.logger.debug('Successfully went to previous')
    else:
        quickView.logger.debug('Error when previous: ' + previousSuccess.status_code.__str__())
    return {'status': previousSuccess.status_code}

@quickView.get("/pause-song")
def pauseSong():
    pauseSuccess = requests.put('https://api.spotify.com/v1/me/player/pause', headers={'Authorization':'Bearer ' + accessToken})
    if pauseSuccess.status_code == 204:
        quickView.logger.debug('Successfully Paused')
    else:
        quickView.logger.debug('Error when pausing: ' + pauseSuccess.status_code.__str__())
    return {'status': pauseSuccess.status_code}

@quickView.route("/next-song")
def nextSong():
    nextSuccess = requests.post('https://api.spotify.com/v1/me/player/next', headers={'Authorization':'Bearer ' + accessToken})
    if nextSuccess.status_code == 204:
        quickView.logger.debug('Successfully went to previous')
    else:
        quickView.logger.debug('Error when previous: ' + nextSuccess.status_code.__str__())
    return {'status': nextSuccess.status_code}
                
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
    if checkForEmptyGlobalVariables(spotifyTokenVariables):
        return redirect(url_for('genAuthCode'))
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