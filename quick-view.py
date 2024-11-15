from flask import Flask, redirect, request, render_template, url_for
import string, random, base64, requests
from datetime import timedelta, datetime
import json
from google.transit import gtfs_realtime_pb2

app = Flask(__name__)

def gen_random_string(length):
    letters = string.ascii_letters + string.digits
    return ''.join(random.choice(letters) for i in range(length))

client = '845c0f9f7bc444b28e6d0a842903a07f'
secret = '16b0a5a6be4f4283bec856f6a919e3a3'
scope = 'user-read-playback-state'
redirect_uri = 'http://192.168.1.4:5000/callback'
mta_api_key = '3b28c3c0-9493-498c-851d-94861a97326a'
access_token = ''
refresh_token = ''
expires_at = datetime.today()

@app.route("/")
def get_auth_code():
    state = gen_random_string(16)
    return redirect('https://accounts.spotify.com/authorize?' + f'response_type=code&client_id={client}&scope={scope}&redirect_uri={redirect_uri}&state={state}')

@app.route("/callback")
def get_auth_token():
    global access_token
    global refresh_token
    global expires_at
    code = request.args.get('code')
    state = request.args.get('state')
    if state is None:
        return "<p>Error: state is null</p>"
    form_data = {'code': code, 'redirect_uri': redirect_uri, 'grant_type':'authorization_code'}
    headers = {'content_type':'application/x-www-form-urlencoded', 'Authorization': 'Basic ' + base64.b64encode((client + ':' +secret).encode('ascii')).decode('ascii')}
    auth = requests.post('https://accounts.spotify.com/api/token', data=form_data, headers=headers)
    auth = auth.json()
    access_token = auth['access_token']
    refresh_token = auth['refresh_token']
    expires_at = datetime.today() + timedelta(seconds=auth['expires_in'])
    return redirect('/spotify')

def get_spotify_playback_data():
    global access_token
    app.logger.debug(access_token)
    player_headers = {'Authorization':'Bearer ' + access_token}
    player_info = requests.get('https://api.spotify.com/v1/me/player', headers=player_headers)
    app.logger.debug(player_info.status_code)
    if player_info.status_code == 200:
        json_data = player_info.json()
        json_data['status_code'] = 200
        return json_data
    return {'status_code': player_info.status_code, 'is_playing': False}

@app.route("/playback-data")
def get_spotify_playback_state():
    status = get_spotify_playback_data()
    app.logger.debug(status['is_playing'])
    if status['status_code'] == 200:
        return {
        "status_code":status['status_code'],
        "is_playing":status['is_playing'],
        "name": status['item']['name'],
        "artists": [i['name'] for i in status['item']['artists']],
        "cover_art": status['item']['album']['images'][0]['url']
        }
    return {
        "status_code":status['status_code'],
        "is_playing":status['is_playing'],
    }

@app.route("/spotify")
def display_playback_data():
    global access_token
    if access_token == '':
        return redirect(url_for('get_auth_code'))
    data = get_spotify_playback_data()
    if data['is_playing'] == True:
        return render_template('spotify.html', title=data['item']['name'], img_url=data['item']['album']['images'][0]['url'], artists=', '.join([i['name'] for i in data['item']['artists']]))
    else:
        return redirect(url_for('realtime_transit'))

def fetch_subway_times():
    subway_feed = gtfs_realtime_pb2.FeedMessage()
    subway_times = requests.get('https://api-endpoint.mta.info/Dataservice/mtagtfsfeeds/nyct%2Fgtfs-ace')
    subway_feed.ParseFromString(subway_times.content)
    subway_arrival_times = {'A':[], 'C':[]}
    for entity in subway_feed.entity:
        if entity.HasField('trip_update'):
            if entity.trip_update.trip.route_id in ('A', 'C'):
                for s in entity.trip_update.stop_time_update:
                    if s.stop_id == 'A48N':
                        num_min = round((datetime.fromtimestamp(s.arrival.time) - datetime.now()).total_seconds() / 60)
                        if num_min <= 40 and num_min > 5:
                            subway_arrival_times[entity.trip_update.trip.route_id].append(num_min)
    for k in subway_arrival_times:
        subway_arrival_times[k].sort()
    return subway_arrival_times

def fetch_bus_times():
    bus_feed = gtfs_realtime_pb2.FeedMessage()
    bus_times = requests.get('https://gtfsrt.prod.obanyc.com/tripUpdates?key=' + mta_api_key)
    bus_feed.ParseFromString(bus_times.content)
    bus_arrival_times = {'B46':[], 'B46+':[]}
    buses = [('B46', 0), ('B46+', 1)]
    stops = ['303625', '307728']
    for entity in bus_feed.entity:
        if entity.HasField('trip_update'):
            route_id = entity.trip_update.trip.route_id
            direction = entity.trip_update.trip.direction_id
            if (route_id, direction) in buses:
                line = buses.index((route_id, direction))
                for s in entity.trip_update.stop_time_update:
                    if s.stop_id == stops[line]:
                        num_min = round((datetime.fromtimestamp(s.arrival.time) - datetime.now()).total_seconds() / 60)
                        if num_min <= 40 and num_min > 0:
                            bus_arrival_times[route_id].append(num_min)
    for k in bus_arrival_times:
        bus_arrival_times[k].sort()
    return bus_arrival_times

@app.route("/realtime-transit")
def realtime_transit():
    global access_token
    if access_token == '':
        return redirect(url_for('get_auth_code'))
    subway = fetch_subway_times()
    bus = fetch_bus_times()
    transit_times = {'Subway': subway, 'Bus': bus}
    app.logger.debug('fetched subway times')
    return render_template('transit.html', times=transit_times)

@app.get("/transit-times")
def fetch_times():
    transit_times = {'Subway': fetch_subway_times(), 'Bus': fetch_bus_times()}
    app.logger.debug(json.dumps(transit_times))
    return json.dumps(transit_times)
