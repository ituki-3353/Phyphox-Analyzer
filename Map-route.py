import os
import math
import webbrowser
import pandas as pd
import tkinter as tk
from tkinter import ttk

from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

import folium
from folium import Element

# ===== 0) ファイル存在チェック =====
LOC_FILE = 'Location.csv'
ORI_FILE = 'Orientation.csv'

if not os.path.exists(LOC_FILE):
    print('Location.csv がカレントディレクトリにありません')
    raise SystemExit
if not os.path.exists(ORI_FILE):
    print('Orientation.csv がカレントディレクトリにありません')
    raise SystemExit

print('Location:', os.path.abspath(LOC_FILE))
print('Orientation:', os.path.abspath(ORI_FILE))

# ===== 1) 読み込み =====
loc = pd.read_csv(LOC_FILE, encoding='utf-8')
ori = pd.read_csv(ORI_FILE, encoding='utf-8')

# Location 側に Height がない場合は、この行を適宜調整
loc = loc[['Time (s)', 'Latitude (°)', 'Longitude (°)', 'Height (m)']].dropna()
ori = ori[['Time (s)', 'Yaw (°)', 'Pitch (°)', 'Roll (°)']].dropna()

# ===== 2) Location と Orientation を時刻でマージ =====
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

# ===== 3) 距離・速度・時間計算 =====
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

# ===== 4) HTML ルートマップ生成（Location + Orientation） =====
route = merged[['Latitude (°)', 'Longitude (°)']].values.tolist()
center = route[len(route)//2]

m = folium.Map(location=center, zoom_start=16)

# ルート線
folium.PolyLine(
    locations=route,
    color='red',
    weight=4,
    opacity=0.6
).add_to(m)

# スタート・ゴール
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
Time: {format_hhmmss(total_time_s)} ({total_time_s:.1f} s)<br>
Distance: {total_dist_m/1000:.3f} km<br>
Avg speed: {avg_speed_kmh:.2f} km/h
</div>
"""
m.get_root().html.add_child(Element(summary_html))

# 一定間隔ごとの詳細ポイント（高度 + 姿勢）
step = 10  # 小さくすると点が増える

for i in range(0, len(merged), step):
    row = merged.iloc[i]
    lat = row['Latitude (°)']
    lon = row['Longitude (°)']

    tooltip_html = (
        f"<div style='font-size:16px; padding:6px 10px;'>"
        f"{row['cumulative_distance_m']/1000:.3f} km | "
        f"{row['speed_km_h']:.1f} km/h<br>"
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

MAP_FILE = 'route_map_orientation.html'
m.save(MAP_FILE)

# マージ済み CSV も保存（解析用）
merged.to_csv('Location_Orientation_merged.csv', index=False)

# ===== 5) Tkinter GUI 構築（高度グラフ・速度グラフ・サマリ） =====
root = tk.Tk()
root.title("Phyphox Location + Orientation Viewer")
root.geometry("1100x700")

main_frame = ttk.Frame(root)
main_frame.pack(fill="both", expand=True)

main_frame.columnconfigure(0, weight=3)
main_frame.columnconfigure(1, weight=1)
main_frame.rowconfigure(0, weight=1)
main_frame.rowconfigure(1, weight=1)

# 高度グラフ
fig_alt = Figure(figsize=(5, 3), dpi=100)
ax_alt = fig_alt.add_subplot(111)
ax_alt.plot(merged['Time (s)'], merged['Height (m)'])
ax_alt.set_title("Altitude vs Time")
ax_alt.set_xlabel("Time (s)")
ax_alt.set_ylabel("Height (m)")
ax_alt.grid(True)

canvas_alt = FigureCanvasTkAgg(fig_alt, master=main_frame)
canvas_alt.draw()
canvas_alt.get_tk_widget().grid(row=0, column=0, sticky="nsew")

# 速度グラフ
fig_spd = Figure(figsize=(5, 3), dpi=100)
ax_spd = fig_spd.add_subplot(111)
ax_spd.plot(merged['Time (s)'], merged['speed_km_h'])
ax_spd.set_title("Speed vs Time")
ax_spd.set_xlabel("Time (s)")
ax_spd.set_ylabel("Speed (km/h)")
ax_spd.grid(True)

canvas_spd = FigureCanvasTkAgg(fig_spd, master=main_frame)
canvas_spd.draw()
canvas_spd.get_tk_widget().grid(row=1, column=0, sticky="nsew")

# 右側サマリ
summary_frame = ttk.Frame(main_frame, padding=10)
summary_frame.grid(row=0, column=1, rowspan=2, sticky="nsew")

start_lat = merged.iloc[0]['Latitude (°)']
start_lon = merged.iloc[0]['Longitude (°)']
end_lat   = merged.iloc[-1]['Latitude (°)']
end_lon   = merged.iloc[-1]['Longitude (°)']

ttk.Label(summary_frame, text="Summary", font=("Meiryo", 14, "bold")).pack(anchor="w", pady=(0, 8))

ttk.Label(summary_frame, text=f"Start:  {start_lat:.6f}, {start_lon:.6f}").pack(anchor="w", pady=2)
ttk.Label(summary_frame, text=f"End:    {end_lat:.6f}, {end_lon:.6f}").pack(anchor="w", pady=2)
ttk.Label(summary_frame, text=f"Time:   {format_hhmmss(total_time_s)}  ({total_time_s:.1f} s)").pack(anchor="w", pady=2)
ttk.Label(summary_frame, text=f"Dist:   {total_dist_m/1000:.3f} km").pack(anchor="w", pady=2)
ttk.Label(summary_frame, text=f"Vavg:   {avg_speed_kmh:.2f} km/h").pack(anchor="w", pady=2)

def open_map():
    webbrowser.open('file://' + os.path.realpath(MAP_FILE))

ttk.Button(summary_frame, text="ルートマップを開く", command=open_map).pack(anchor="w", pady=(20, 5))
ttk.Label(summary_frame, text=f"HTML: {MAP_FILE}", foreground="gray").pack(anchor="w", pady=2)

root.mainloop()
