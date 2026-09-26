import urllib.request
import json

test_cases = [
    ("https://www.youtube.com/watch?v=gset79KMmt0", "Snowman (Sia)"),
    ("https://www.youtube.com/watch?v=d8IT-16kA8M", "Manwa Laage (Happy New Year)"),
    ("https://www.youtube.com/watch?v=nyuo9-OjNNg", "I Wanna Be Yours (Arctic Monkeys)"),
    ("Manwa Laage", "Direct Search Text")
]

for query, label in test_cases:
    req = urllib.request.Request(
        'https://anything-to-audio-am.vercel.app/api/recognize/url',
        data=json.dumps({'url': query}).encode(),
        headers={'Content-Type': 'application/json'}
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode())
            song = data.get('song') or {}
            print(f"[{label}] -> Matched: {data.get('matched')} | Title: {song.get('title')} | Artist: {song.get('artist')}")
    except Exception as e:
        print(f"[{label}] -> Error: {e}")
