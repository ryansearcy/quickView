from flask import Flask, Response, request, redirect, render_template, url_for
import string, random, base64, requests, json
from json import JSONDecodeError
from datetime import timedelta, datetime
from google.transit import gtfs_realtime_pb2
from typing import Any

quickView = Flask(__name__)

type Line = str
type StopID = str
type TripID = str

emptyString: str = ''
emptyTypes: dict[type, Any] = {str: emptyString, list: [], dict: {}, datetime: datetime(1900, 1, 1)}

#Spotify API variables
spotifyAPIVariables: list[str] = ['clientID', 'clientSecret', 'appScope', 'redirectUri', 'deviceID']
clientID: str = emptyTypes[str]
clientSecret: str = emptyTypes[str]
appScope: str = emptyTypes[str]
redirectUri: str = emptyTypes[str]
deviceID: str = emptyTypes[str]
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

appVariables: list[str] = spotifyAPIVariables + spotifyTokenVariables + transitVariables
appVariablesSet: set[str] = set(appVariables)

def checkForEmptyGlobalVariables(variableNames: list[str] | str) -> bool:
    if type(variableNames) == str:
        variables = [variableNames]
    else:
        variables = variableNames
    if set(variables).issubset(appVariablesSet) is False:
        raise ValueError('variables are not in editable global scope')
    globalVars = globals()
    return [globalVars[v] == emptyTypes[type(globalVars[v])] for v in variables].__contains__(True)

def setGlobalVariable(variableName: str, value) -> None:
    globalVariables = globals()
    if globalVariables.keys().__contains__(variableName) is False:
        raise ValueError('Variable does not exist')
    if type(globalVariables[variableName]) != type(value):
        raise ValueError('Value type does not match variable')
    globals()[variableName] = value
    return

def loadJSONVariables(name: str) -> None:
    jsonFile = open("variableData/" + name + ".json", "r")
    jsonData = json.load(jsonFile)
    for variable in jsonData:
        setGlobalVariable(variable, jsonData[variable])
    return

def genRandomString(length: int) -> str:
    letters = string.ascii_letters + string.digits
    return emptyString.join(random.choice(letters) for i in range(length))

@quickView.route("/")
def genAuthCode() -> Response:
    loadJSONVariables('spotifyVariables')
    loadJSONVariables('transitVariables')
    state: str = genRandomString(16)
    return redirect('https://accounts.spotify.com/authorize?' + f'response_type=code&client_id={clientID}&scope={appScope}&redirect_uri={redirectUri}&state={state}')

@quickView.route("/callback")
def genAuthToken() -> Response:
    authCode: str = request.args.get('code')
    state = request.args.get('state')
    if state is None:
        quickView.logger.debug('Returned State is null')
        return "<h1>Error: state is null</h1>"
    formData = {'code': authCode, 'redirect_uri': redirectUri, 'grant_type':'authorization_code'}
    headers = {'content_type':'application/x-www-form-urlencoded', 'Authorization': 'Basic ' + base64.b64encode((clientID + ':' +clientSecret).encode('ascii')).decode('ascii')}
    authResponse = requests.post('https://accounts.spotify.com/api/token', data=formData, headers=headers).json()
    setGlobalVariable('accessToken', authResponse['access_token'])
    setGlobalVariable('refreshToken', authResponse['refresh_token'])
    setGlobalVariable('expiresAt', datetime.today() + timedelta(seconds=authResponse['expires_in']))
    return redirect('/spotify')

def getSpotifyPlaybackData() -> dict:
    if checkForEmptyGlobalVariables('accessToken'):
        return {'status_code': 500, 'is_playing': False}
    quickView.logger.debug('accessToken Value: ' + accessToken)
    playbackHeaders: dict = {'Authorization':'Bearer ' + accessToken}
    playbackInfo: Response = requests.get('https://api.spotify.com/v1/me/player', headers=playbackHeaders)
    quickView.logger.debug('Playback State Response Code: ' + playbackInfo.status_code.__str__())
    try:
        playbackData = playbackInfo.json()
    except JSONDecodeError:
        return {'status_code': playbackInfo.status_code, 'is_playing': False}
    quickView.logger.debug('Device ID: ' + playbackData['device']['id'])
    playbackData: dict[str, str | int | bool] = {
        'status_code': playbackInfo.status_code if checkForEmptyGlobalVariables('deviceID') or playbackData['device']['id'] == deviceID else 204,
        'is_playing': playbackData['is_playing'] if 'is_playing' in playbackData and (checkForEmptyGlobalVariables('deviceID') or playbackData['device']['id'] == deviceID) else False,
        'name': playbackData['item']['name'] if 'item' in playbackData else '',
        'artists': ', '.join([artist['name'] for artist in playbackData['item']['artists']]) if 'item' in playbackData else '',
        'cover_art': playbackData['item']['album']['images'][0]['url'] if 'item' in playbackData else ''
    }
    return playbackData

@quickView.route("/playback-data")
def getPlaybackState() -> dict:
    playbackData = getSpotifyPlaybackData()
    quickView.logger.debug('Currently Playing?: ' + playbackData['is_playing'].__str__())
    return json.dumps(playbackData)

@quickView.route("/spotify")
def displayPlaybackData():
    if checkForEmptyGlobalVariables(spotifyTokenVariables):
        return redirect(url_for('genAuthCode'))
    playbackData = getSpotifyPlaybackData()
    if playbackData['is_playing']:
        return render_template('spotify.html', title=playbackData['name'], artists=playbackData['artists'], cover_art=playbackData['cover_art'])
    else:
        return redirect(url_for('realtimeTransit'))

def fetchTransitTimes(apiURI: str, lineData: dict, minMaxAway: dict):
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
            if len(arrivalTimes[line][stop]) == 0:
                arrivalTimes[line][stop] = 'No Departure Times Available'
            else:
                arrivalTimes[line][stop].sort()
                arrivalTimes[line][stop] = ', '.join([str(times) for times in arrivalTimes[line][stop]])
            arrivalTimes[line][stop] = 'To ' + lineData[line][stop] + ':<br>' + arrivalTimes[line][stop]
    return arrivalTimes

@quickView.route("/realtime-transit")
def realtimeTransit():
    if checkForEmptyGlobalVariables(spotifyTokenVariables):
        return redirect(url_for('genAuthCode'))
    transitTimes = {'Subway': fetchTransitTimes(mtaAPIURIs['Subway'], subwayData, subwayMinMaxAway), 'Bus': fetchTransitTimes(mtaAPIURIs['Bus'], busData, busMinMaxAway)}
    quickView.logger.debug('Successfully fetched transit times')
    return render_template('transit.html', times=transitTimes, keep_trailing_newline=True)

@quickView.get("/transit-times")
def fetchTimes():
    transitTimes = {'Subway': fetchTransitTimes(mtaAPIURIs['Subway'], subwayData, subwayMinMaxAway), 'Bus': fetchTransitTimes(mtaAPIURIs['Bus'], busData, busMinMaxAway)}
    quickView.logger.debug('Transit Times: ' + json.dumps(transitTimes))
    return json.dumps(transitTimes)
