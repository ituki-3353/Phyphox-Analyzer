# make_map.py
import os
import sys
import math
import pandas as pd
import folium
from folium import Element

LOC_FILE = 'Location.csv'
ORI_FILE = 'Orientation.csv'

if not os.path.exists(LOC_FILE) or not os.path.exists(ORI_FILE):
    print('Location.csv または Orientation.csv がありません')
    raise SystemExit

loc = pd.read_csv(LOC_FILE, encoding='utf-8')
ori = pd.read_csv(ORI_FILE, encoding='utf-8')

loc = loc[['Time (s)', 'Latitude (°)', 'Longitude (°)', 'Height (m)']].dropna()
ori = ori[['Time (s)', 'Yaw (°)', 'Pitch (°)', 'Roll (°)']].dropna()

loc = loc.sort_values('Time (s)')
ori = ori.sort_values('Time (s)')

merged = pd.merge_asof(
    loc,
    ori,
    on='Time (s)',
    direction='nearest',
    suffixes=('', '_ori')
).dropna(subset=['Latitude (°)', 'Longitude (°)', 'Yaw (°)'])

t = merged['Time (s)']

def haversine(lat1, lon1, lat2, lon2):
    R = 6371000
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlambda/2)**2
    return 2*R*math.asin(math.sqrt(a))

dists = [0.0]
for i in range(1, len(merged)):
    d = haversine(
        merged.iloc[i-1]['Latitude (°)'],  merged.iloc[i-1]['Longitude (°)'],
        merged.iloc[i]['Latitude (°)'],    merged.iloc[i]['Longitude (°)'],
    )
    dists.append(d)

merged['segment_distance_m'] = dists
merged['cumulative_distance_m'] = merged['segment_distance_m'].cumsum()

dt = t.diff().fillna(0)
speed_ms = merged['segment_distance_m'] / dt.replace(0, pd.NA)
merged['speed_m_s'] = speed_ms.fillna(0)
merged['speed_km_h'] = merged['speed_m_s'] * 3.6

total_time_s = t.iloc[-1] - t.iloc[0]
total_dist_m = merged['cumulative_distance_m'].iloc[-1]
avg_speed_ms = total_dist_m / total_time_s if total_time_s > 0 else 0
avg_speed_kmh = avg_speed_ms * 3.6

def format_hhmmss(sec):
    sec = int(round(sec))
    h = sec // 3600
    m = (sec % 3600) // 60
    s = sec % 60
    return f"{h:02d}:{m:02d}:{s:02d}"

def main(step: int):
    route = merged[['Latitude (°)', 'Longitude (°)']].values.tolist()
    center = route[len(route)//2]

    m = folium.Map(location=center, zoom_start=16)
    map_name = m.get_name()  # JS 側の変数名 [web:216]

    folium.PolyLine(
        locations=route,
        color='red',
        weight=4,
        opacity=0.6
    ).add_to(m)

    folium.Marker(route[0], popup='Start', icon=folium.Icon(color='green')).add_to(m)
    folium.Marker(route[-1], popup='End', icon=folium.Icon(color='blue')).add_to(m)

    summary_html = f"""
    <div style="
        position: fixed;
        top: 10px; left: 10px;
        z-index: 9999;
        background-color: rgba(255, 255, 255, 0.8);
        padding: 8px 12px;
        border-radius: 5px;
        font-size: 12px;
    ">
    <b>Summary</b><br>
    Time: {format_hhmmss(total_time_s)} ({total_time_s:.1f} s)<br>
    Distance: {total_dist_m/1000:.3f} km<br>
    Avg speed: {avg_speed_kmh:.2f} km/h
    </div>

    <div id="point-detail" style="
        position: fixed;
        bottom: 10px; left: 10px;
        z-index: 9999;
        background-color: rgba(0,0,0,0.7);
        color: white;
        padding: 8px 12px;
        border-radius: 5px;
        font-size: 14px;
        min-width: 280px;
    ">
    点をクリックすると詳細を表示します
    </div>
    """
    m.get_root().html.add_child(Element(summary_html))

    # 詳細表示関数
    detail_js = """
    <script>
    function showDetail(dist_km, speed_kmh, alt_m, yaw, pitch, roll, time_s) {
        var div = document.getElementById('point-detail');
        if (!div) return;
        div.innerHTML =
            'Time: ' + time_s.toFixed(2) + ' s<br>' +
            'Dist: ' + dist_km.toFixed(3) + ' km<br>' +
            'Speed: ' + speed_kmh.toFixed(1) + ' km/h<br>' +
            'Alt: ' + alt_m.toFixed(1) + ' m<br>' +
            'Yaw: ' + yaw.toFixed(1) + ' °<br>' +
            'Pitch: ' + pitch.toFixed(1) + ' °<br>' +
            'Roll: ' + roll.toFixed(1) + ' °';
    }
    </script>
    """
    m.get_root().html.add_child(Element(detail_js))

    # 全ポイント情報を JS 用に配列化
    step = max(1, int(step))
    point_data = []
    for i in range(0, len(merged), step):
        row = merged.iloc[i]
        point_data.append({
            "lat": float(row['Latitude (°)']),
            "lon": float(row['Longitude (°)']),
            "dist_km": float(row['cumulative_distance_m'] / 1000.0),
            "speed_kmh": float(row['speed_km_h']),
            "alt_m": float(row['Height (m)']),
            "yaw": float(row['Yaw (°)']),
            "pitch": float(row['Pitch (°)']),
            "roll": float(row['Roll (°)']),
            "time_s": float(row['Time (s)']),
        })

    # Python 側で CircleMarker は描かず、JS でまとめて追加＋クリック登録
    # （JS は window.onload で実行する）[web:216]
    import json
    js_points = json.dumps(point_data)

    click_js_all = f"""
    <script>
    window.onload = function() {{
        var mapObj = {map_name};
        var pts = {js_points};
        for (var i = 0; i < pts.length; i++) {{
            var p = pts[i];
            var marker = L.circleMarker([p.lat, p.lon], {{
                radius: 6,
                color: 'black',
                fill: true,
                fillOpacity: 0.9
            }}).addTo(mapObj);
            (function(p) {{
                marker.on('click', function(e) {{
                    showDetail(p.dist_km, p.speed_kmh, p.alt_m,
                               p.yaw, p.pitch, p.roll, p.time_s);
                }});
            }})(p);
        }}
    }};
    </script>
    """
    m.get_root().html.add_child(Element(click_js_all))

    out_html = f'route_map_step{step}.html'
    m.save(out_html)
    print('created:', out_html)

if __name__ == "__main__":
    step = 10
    if len(sys.argv) >= 2:
        try:
            step = int(sys.argv[1])
        except ValueError:
            pass
    main(step)
