import urllib.request
import urllib.parse
import json

base_url = "https://api.worldpop.org/v1/services/stats"
params = {
    "dataset": "wpgppop",
    "year": "2020",
    "runasync": "false",
    "geojson": json.dumps({
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {},
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [[[76.94, 11.00],[76.96, 11.00],[76.96, 11.02],[76.94, 11.02],[76.94, 11.00]]]
                }
            }
        ]
    })
}
url = base_url + "?" + urllib.parse.urlencode(params)
try:
    req = urllib.request.Request(url)
    res = urllib.request.urlopen(req)
    data = json.loads(res.read().decode())
    print("Success:", data)
except urllib.error.HTTPError as e:
    print("HTTPError:", e.code, e.read().decode())
except Exception as e:
    print("Error:", e)
