import pandas as pd
import matplotlib.pyplot as plt

df = pd.read_csv('Location.csv', encoding='utf-8')

# 欠損を除外（念のため）
df = df.dropna(subset=['Latitude (°)', 'Longitude (°)'])

plt.figure(figsize=(8, 8))

# 経度を横軸、緯度を縦軸にして線でつなぐ
plt.plot(df['Longitude (°)'], df['Latitude (°)'], '-o', markersize=2)

plt.xlabel('Longitude (°)')
plt.ylabel('Latitude (°)')
plt.title('Route')
plt.grid(True)
plt.axis('equal')  # 縦横比を揃えて歪みを減らす
plt.tight_layout()

plt.show()
