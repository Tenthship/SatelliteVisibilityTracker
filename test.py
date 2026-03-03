from skyfield.api import load, wgs84

ts = load.timescale()
t = ts.now()

print(ts)