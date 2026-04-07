from flask import Flask, Response, request, redirect, render_template, url_for
import string, random, base64, requests, json, time, operator, math, re
from json import JSONDecodeError
from datetime import timedelta, datetime
from google.transit import gtfs_realtime_pb2
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
transitVariables: list[str] = ['mtaAPIKey', 'lineData', 'mtaAPIURIs']
mtaAPIKey: str = emptyTypes[str]
lineData: list[dict[str, str]] = emptyTypes[list]
lineMapping: dict[tuple[str, str], str] = emptyTypes[dict]
lineList: list[str] = emptyTypes[list]
mtaAPIURIs: list[str] = emptyTypes[list]
schedule: dict = {}

apiVariables: list[str] = emptyTypes[list]
appVariables: list[str] = spotifyAPIVariables + spotifyTokenVariables + transitVariables + ['apiVariables'] + ['lineMapping', 'lineList'] + ['schedule']

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

def fetchSchedules() -> None:
    weekday_url="https://www.panynj.gov/path/en/schedules-maps/weekday-schedules.html"
    weekday_schedule=HtmlTable(weekday_url)
    weekday_schedule=weekday_schedule.get_weekday_tables()
    weekend_url="https://www.panynj.gov/path/en/schedules-maps/weekend-schedules.html"
    weekend_schedule=HtmlTable(weekend_url)
    weekend_schedule=weekend_schedule.get_weekend_tables()
    setGlobalVariable('schedule', weekday_schedule | weekend_schedule)
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
    fetchSchedules()
    return authResponse.status_code

@quickView.route("/")
def genAuthCode() -> Response:
    loadJSONVariables()
    if checkForEmptyGlobalVariables(apiVariables):
        return redirect(url_for('startSetup'))
    lineData.sort(key=operator.itemgetter('priority'))
    setGlobalVariable('lineMapping', {(l['line'], l['stop']): l['priority'] for l in lineData})
    setGlobalVariable('lineList', list(set([l[0] for l in lineMapping])))
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

# def addScheduledTimes(realTimeTransit: dict):
#     for i in realTimeTransit:
#         for j in realTimeTransit[i]:
#             if len(j) < 1 or len([t for time in realTimeTransit[i][j] if time >= 10]) == 0:
#                realTimeTransit[i][j] = realTimeTransit[i][j] + [t for  ]
                
def fetchTransitTimes() -> dict:
    pathJSON = requests.get("https://www.panynj.gov/bin/portauthority/ridepath.json", headers={'User-Agent':'Firefox'}).json()
    groveSt = [destinationData['messages'] for destinationData in [stationData['destinations'] for stationData in pathJSON['results'] if stationData['consideredStation'] == 'GRV'][0] if destinationData['label'] == 'ToNY'][0]
    exchangePlace = [destinationData['messages'] for destinationData in [stationData['destinations'] for stationData in pathJSON['results'] if stationData['consideredStation'] == 'EXP'][0] if destinationData['label'] == 'ToNY'][0]
    pathTimes = {'Grove St':{'WTC':{}, '33S':{}}, 'Exchange Place':{'WTC':{}}}
    mappings = {'Grove St':groveSt, 'Exchange Place':exchangePlace}
    for i in mappings:
        for j in mappings[i]:
            if pathTimes[i][j['target']] != {}:
                pathTimes[i][j['target']]['tTA'] = pathTimes[i][j['target']]['tTA'] + ', ' + str(math.floor(int(j['secondsToArrival'])/60)) + ' mins'
                if pathTimes[i][j['target']]['sTA'] > int(j['secondsToArrival']):
                    pathTimes[i][j['target']]['hS'] = j['headSign']
            else:
                pathTimes[i][j['target']]['sTA'] = int(j['secondsToArrival'])
                pathTimes[i][j['target']]['tTA'] = str(math.floor(int(j['secondsToArrival'])/60)) + ' mins'
                pathTimes[i][j['target']]['hS'] = j['headSign']
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