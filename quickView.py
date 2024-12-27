from flask import Flask, Response, request, redirect, render_template, url_for
import string, random, base64, requests, json, time
from json import JSONDecodeError
from datetime import timedelta, datetime
from google.transit import gtfs_realtime_pb2
from typing import Any
from selenium import webdriver
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.firefox.service import Service as FirefoxService
from webdriver_manager.firefox import GeckoDriverManager

quickView = Flask(__name__)

type Line = str
type StopID = str
type TripID = str

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
transitVariables: list[str] = ['mtaAPIKey', 'subwayData', 'subwayMinMaxAway', 'busData', 'busMinMaxAway', 'mtaAPIURIs']
mtaAPIKey: str = emptyTypes[str]
subwayData: dict[Line, dict[StopID, TripID]] = emptyTypes[dict]
subwayMinMaxAway: dict[Line, dict[str, int]] = emptyTypes[dict]
busData: dict[Line, dict[StopID, TripID]] = emptyTypes[dict]
busMinMaxAway: dict[str, dict[str, int]] = emptyTypes[dict]
mtaAPIURIs: dict[str, str] = emptyTypes[dict]

apiVariables: list[str] = emptyTypes[list]
appVariables: list[str] = spotifyAPIVariables + spotifyTokenVariables + transitVariables + ['apiVariables']

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
        jsonFile = open("config.json", "r")
        try:
            jsonData = json.load(jsonFile)
            for variable in jsonData:
                setGlobalVariable(variable, jsonData[variable], False)
        except JSONDecodeError:
            jsonFile.close()
            return
    except:
        jsonFile = open("config.json", "x")
    jsonFile.close()
    return

def writeJSONVariables(variables: dict[str, Any]) -> None:
    jsonFile = open("config.json", "r")
    try:
        jsonData = json.load(jsonFile)
    except JSONDecodeError:
        jsonData = emptyTypes[dict]
    jsonFile.close()
    for v in variables:
        jsonData[v] = variables[v]
    jsonFile = open("config.json", "w")
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
        #quickView.logger.debug('Refresh data: ' + authJSON.__str__())
        setGlobalVariable('accessToken', authJSON['access_token'])
        if 'refresh_token' in authJSON:
            setGlobalVariable('refresh_token', authJSON['refresh_token'])
        setGlobalVariable('expiresAt', datetime.today() + timedelta(seconds=(round(authJSON['expires_in']*0.75))))
    return authResponse.status_code

@quickView.route("/")
def genAuthCode() -> Response:
    loadJSONVariables()
    if checkForEmptyGlobalVariables(apiVariables):
        return redirect(url_for('startSetup'))
    state: str = genRandomString(16)
    firefoxOptions = Options()
    firefoxOptions.add_argument('-headless')
    firefoxDriver = webdriver.Firefox(service=FirefoxService(GeckoDriverManager().install()), options=firefoxOptions)
    firefoxDriver.get('https://accounts.spotify.com/authorize?' + f'response_type=code&client_id={clientID}&scope={appScope}&redirect_uri={redirectUri}&state={state}')
    spotifyUsernameInput = firefoxDriver.find_element(value='login-username')
    spotifyUsernameInput.send_keys(spotifyUsername)
    spotifyPasswordInput = firefoxDriver.find_element(value='login-password')
    spotifyPasswordInput.send_keys(spotifyPassword)
    firefoxDriver.find_element(value='login-button').click()
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
    #quickView.logger.debug('accessToken Value: ' + accessToken)
    playbackHeaders: dict = {'Authorization':'Bearer ' + accessToken}
    playbackInfo: Response = requests.get('https://api.spotify.com/v1/me/player', headers=playbackHeaders)
    #quickView.logger.debug('Playback State Response Code: ' + playbackInfo.status_code.__str__())
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

def fetchTransitTimes(apiURI: str, lineData: dict, minMaxAway: dict) -> dict:
    transitFeed = gtfs_realtime_pb2.FeedMessage()
    transitTimes = requests.get(apiURI)
    transitFeed.ParseFromString(transitTimes.content)
    arrivalTimes = {line: {stop: [] for stop in lineData[line]} for line in lineData}
    minTimes = {line: {stop: None for stop in lineData[line]} for line in lineData}
    for entity in transitFeed.entity:
        if entity.HasField('trip_update') != True:
            continue
        routeID = entity.trip_update.trip.route_id
        tripID = entity.trip_update.trip.trip_id
        if routeID not in lineData.keys():
            continue
        lineStops = lineData[routeID].keys()
        for stopTimeUpdate in entity.trip_update.stop_time_update:
            stopID = stopTimeUpdate.stop_id
            if stopID not in lineStops:
                continue
            minutesAway = round((datetime.fromtimestamp(stopTimeUpdate.arrival.time) - datetime.now()).total_seconds() / 60)
            if minutesAway > minMaxAway[routeID]['max'] or minutesAway < minMaxAway[routeID]['min']:
                continue
            if minTimes[routeID][stopID] is None or minutesAway < minTimes[routeID][stopID]:
                #if lineData[routeID][stopID] != tripID:
                    #busData[(routeID, stopID)] = lastStopID
                minTimes[routeID][stopID] = minutesAway
            arrivalTimes[routeID][stopID].append(minutesAway)
    for line in arrivalTimes:
        for stop in arrivalTimes[line]:
            timesLength: int = len(arrivalTimes[line][stop])
            if  timesLength == 0:
                arrivalTimes[line][stop] = 'No Departures'
            else:
                if timesLength > 4:
                    arrivalTimes[line][stop] = arrivalTimes[line][stop][:4]
                arrivalTimes[line][stop].sort()
                arrivalTimes[line][stop] = ', '.join([str(times) for times in arrivalTimes[line][stop]])
            arrivalTimes[line][stop] = 'To ' + lineData[line][stop] + ':<br>' + arrivalTimes[line][stop]
    return arrivalTimes

@quickView.route("/realtime-transit")
def realtimeTransit() -> str:
    if checkForEmptyGlobalVariables(spotifyTokenVariables):
        return redirect(url_for('genAuthCode'))
    transitTimes = {'Subway': fetchTransitTimes(mtaAPIURIs['Subway'], subwayData, subwayMinMaxAway), 'Bus': fetchTransitTimes(mtaAPIURIs['Bus'], busData, busMinMaxAway)}
    #quickView.logger.debug('Successfully fetched transit times')
    return render_template('transit.html', times=transitTimes, keep_trailing_newline=True)

@quickView.get("/transit-times")
def fetchTimes() -> str:
    transitTimes = {'Subway': fetchTransitTimes(mtaAPIURIs['Subway'], subwayData, subwayMinMaxAway), 'Bus': fetchTransitTimes(mtaAPIURIs['Bus'], busData, busMinMaxAway)}
    #quickView.logger.debug('Transit Times: ' + json.dumps(transitTimes))
    return json.dumps(transitTimes)