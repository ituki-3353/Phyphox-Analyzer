import math
import os
import pandas as pd
import folium
from folium import Element
import webbrowser

# ==== 0) カレントディレクトリのファイル名 ====
loc_path = 'Location.csv'
ori_path = 'Orientation.csv'

if not os.path.exists(loc_path):
    print('Location.csv がカレントディレクトリにありません')
    raise SystemExit
if not os.path.exists(ori_path):
    print('Orientation.csv がカレントディレクトリにありません')
    raise SystemExit

print('Location:', os.path.abspath(loc_path))
print('Orientation:', os.path.abspath(ori_path))

# ==== 1) 読み込み ====
loc = pd.read_csv(loc_path, encoding='utf-8')
ori = pd.read_csv(ori_path, encoding='utf-8')

loc = loc[['Time (s)', 'Latitude (°)', 'Longitude (°)']].dropna()
ori = ori[['Time (s)', 'Yaw (°)', 'Pitch (°)', 'Roll (°)']].dropna()

# ==== 2) 時刻でマージ（最近傍） ====
loc = loc.sort_values('Time (s)')
ori = ori.sort_values('Time (s)')

merged = pd.merge_asof(
    loc,
    ori,
    on='Time (s)',
    direction='nearest',
    suffixes=('', '_ori')
)

merged = merged.dropna(subset=['Latitude (°)', 'Longitude (°)', 'Yaw (°)'])

# ==== 3) 距離・速度計算 ====
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

print('--- summary ---')
print(f'測定時間: {total_time_s:.1f} s')
print(f'走行距離: {total_dist_m/1000:.3f} km')
print(f'平均速度: {avg_speed_kmh:.2f} km/h')

# ==== 4) マップ生成 ====
route = merged[['Latitude (°)', 'Longitude (°)']].values.tolist()
center = route[len(route)//2]

m = folium.Map(location=center, zoom_start=16)

folium.PolyLine(
    locations=route,
    color='red',
    weight=4,
    opacity=0.6
).add_to(m)

folium.Marker(route[0], popup='Start', icon=folium.Icon(color='green')).add_to(m)
folium.Marker(route[-1], popup='End', icon=folium.Icon(color='blue')).add_to(m)

# サマリボックス
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
Time: {total_time_s:.1f} s<br>
Distance: {total_dist_m/1000:.3f} km<br>
Avg speed: {avg_speed_kmh:.2f} km/h
</div>
"""
m.get_root().html.add_child(Element(summary_html))

# 向き付きポイント（詳細軌道）
step = 10  # 密度調整
for i in range(0, len(merged), step):
    row = merged.iloc[i]
    lat = row['Latitude (°)']
    lon = row['Longitude (°)']

    tooltip_html = (
        f"<div style='font-size:20px; padding:6px 10px;'>"
        f"{row['cumulative_distance_m']/1000:.3f} km | "
        f"{row['speed_km_h']:.1f} km/h | "
        f"Alt {row['Height (m)']:.1f} m<br>"
        f"Yaw {row['Yaw (°)']:.1f}° | "
        f"Pitch {row['Pitch (°)']:.1f}° | "
        f"Roll {row['Roll (°)']:.1f}°"
        f"</div>"
    )

    folium.CircleMarker(
        location=[lat, lon],
        radius=3,
        color='black',
        fill=True,
        fill_opacity=0.9,
        tooltip=tooltip_html
    ).add_to(m)

# ==== 5) 保存してブラウザで開く ====
out_html = 'location_orientation_map.html'
m.save(out_html)
print(out_html, 'を開きます')

webbrowser.open('file://' + os.path.realpath(out_html))

merged.to_csv('Location_Orientation_merged.csv', index=False)
print('Location_Orientation_merged.csv にマージ結果を出力しました')
