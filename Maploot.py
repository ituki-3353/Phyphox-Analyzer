import pandas as pd
import folium

# 位置情報CSV読み込み
df = pd.read_csv('Location.csv', encoding='utf-8')
df = df.dropna(subset=['Latitude (°)', 'Longitude (°)'])

# ルート座標（[緯度, 経度] のリスト）
route = df[['Latitude (°)', 'Longitude (°)']].values.tolist()

# 地図の中心をルートの最初の地点に
m = folium.Map(location=route[0], zoom_start=16)

# ルートを線で追加
folium.PolyLine(
    locations=route,
    color='red',
    weight=4,
    opacity=0.8
).add_to(m)

# スタート/ゴールにマーカー追加（任意）
folium.Marker(route[0], popup='Start', icon=folium.Icon(color='green')).add_to(m)
folium.Marker(route[-1], popup='End', icon=folium.Icon(color='blue')).add_to(m)

# HTMLとして保存してブラウザで表示
m.save('route_map.html')
print('route_map.html をブラウザで開いてください')
