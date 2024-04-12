from flask import Flask, Response, jsonify, abort, redirect
import requests
import json
from deluge_client import DelugeRPCClient
import urllib.parse
import re
import sys

api_token = sys.argv[1]
rss_token = sys.argv[2]
domain = sys.argv[3]
deluge_host = sys.argv[4]
deluge_port = sys.argv[5]
deluge_username = sys.argv[6]
deluge_password = sys.argv[7]
url_stream = sys.argv[8]




MANIFEST = {
    'id': 'org.stremio.Lat-Team',
    'version': '1.0.0',
    'name': 'Lat-Team',
    'description': 'Sitio de streaming de Lat-Team',
    'types': ['movie', 'series'],
    'catalogs': [],
    'resources': [
        {'name': 'stream', 'types': ['movie', 'series'], 'idPrefixes': ['tt', 'hpy']}
    ]
}

app = Flask(__name__)

def respond_with(data):
    resp = jsonify(data)
    resp.headers['Access-Control-Allow-Origin'] = '*'
    resp.headers['Access-Control-Allow-Headers'] = '*'
    return resp

def format_size(size):
    if size > 1024 * 1024 * 1024:
        return f"{round(size / (1024 * 1024 * 1024), 2)} GB"
    else:
        return f"{round(size / (1024 * 1024), 2)} MB"

@app.route('/manifest.json')
def addon_manifest():
    return respond_with(MANIFEST)

@app.route('/stream/<type>/<id>.json')
def addon_stream(type, id):
    if type not in MANIFEST['types']:
        abort(404)
    id = id.replace('tt', '')
    if type == 'movie':
        response = requests.get(f"https://lat-team.com/api/torrents/filter?imdbId={id}&api_token={api_token}")
        lat_team = response.json()
        streams = []
        for item in lat_team['data']:
            size = item['attributes']['size']
            size_formatted = format_size(size)
            title = f"{item['attributes']['name']}\n{item['attributes']['type']}  {item['attributes']['resolution']}  {size_formatted}\nSeeders: {item['attributes']['seeders']}  /   Leechers: {item['attributes']['leechers']}  / Free: {item['attributes']['freeleech']}"
            stream_info = {'title': title, 'url': f"{domain}/redireccionar/{item['id']}"}
            streams.append(stream_info)
        return respond_with({'streams': streams})
    elif type == 'series':
        id_parts = id.split(":")
        season_number, episode_number = id_parts[1], id_parts[2]
        response = requests.get(f"https://lat-team.com/api/torrents/filter?imdbId={id_parts[0]}&api_token={api_token}")
        lat_team = response.json()
        streams = []
        for item in lat_team['data']:
            name = item['attributes']['name']
            if f"S{season_number.zfill(2)}E{episode_number.zfill(2)}" in name:
                size = item['attributes']['size']
                size_formatted = format_size(size)
                title = f"{name}\n{item['attributes']['type']}  {item['attributes']['resolution']}  {size_formatted}\nSeeders: {item['attributes']['seeders']}  /   Leechers: {item['attributes']['leechers']}  / Free: {item['attributes']['freeleech']}"
                stream_info = {'title': title, 'url': f"{domain}/redireccionar2/{season_number}/{episode_number}/{item['id']}"}
                streams.append(stream_info)
            if f"S{season_number.zfill(2)}" in name:
                size = item['attributes']['size']
                size_formatted = format_size(size)
                title = f"{name}\n{item['attributes']['type']}  {item['attributes']['resolution']}  {size_formatted}\nSeeders: {item['attributes']['seeders']}  /   Leechers: {item['attributes']['leechers']}  / Free: {item['attributes']['freeleech']}"
                stream_info = {'title': title, 'url': f"{domain}/redireccionar2/{season_number}/{episode_number}/{item['id']}"}
                streams.append(stream_info)

        return respond_with({'streams': streams})
    
    else:
        abort(404)

@app.route('/redireccionar/<id>')
def redireccionar(id):
    hash = add_torrent(id)
    nueva_url = get_url_stream(hash)
    return redirect(nueva_url, code=301)

@app.route('/redireccionar2/<season>/<episode>/<id>')
def redireccionar2(season, episode, id):
    hash = add_torrent(id)
    file_name = get_torrents(hash, episode)
    nueva_url = get_url_stream2(hash, file_name)
    return redirect(nueva_url, code=301)

def add_torrent(id):
    deluge_client = DelugeRPCClient(deluge_host, int(deluge_port), deluge_username, deluge_password)
    deluge_client.connect()
    if deluge_client.connected:
        print("Conectado a Deluge RPC")
    torrent_url = f'https://lat-team.com/torrent/download/{id}.{rss_token}'
    try:
        result = deluge_client.core.add_torrent_url(torrent_url, {})
        print(result.decode('utf-8'))
        return result.decode('utf-8')
    except Exception as e:
        error_message = str(e)
        start_index = error_message.find("(")
        end_index = error_message.find(")")
        if start_index != -1 and end_index != -1:
            torrent_hash = error_message[start_index + 1: end_index]
            print(f"Error al agregar el torrent: {torrent_hash}")
            return torrent_hash
        else:
            print("Error desconocido al agregar el torrent")
    finally:
        deluge_client.disconnect()

def get_torrents(hash, episode):
    deluge_client = DelugeRPCClient(deluge_host, int(deluge_port), deluge_username, deluge_password)
    deluge_client.connect()
    if deluge_client.connected:
        print("Conectado a Deluge RPC")
    try:
        torrent_status = deluge_client.core.get_torrent_status(hash, ['files'])
        files = torrent_status[b'files']
        for file_info in files:
            file_name_with_extension = file_info[b'path'].decode()
            file_name = file_name_with_extension.split('/')[-1]
            match = re.search(r'E' + episode.zfill(2), file_name)
            if match:
                return urllib.parse.quote(file_name)
    except Exception as e:
        print(e)
    finally:
        deluge_client.disconnect()

def get_url_stream(hash):
    url = f"{url_stream}?infohash={hash}"
    response = requests.request("GET", url, verify=False)
    data = response.json()
    return data["url"]

def get_url_stream2(hash, name):
    url = f"{url_stream}?infohash={hash}&path={name}"
    response = requests.request("GET", url, verify=False)
    data = response.json()
    return data["url"]

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=11470)