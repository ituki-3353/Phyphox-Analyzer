# location_gui.py
import os
import math
import subprocess  # もう使っていないが、念のため残しても問題なし
import webbrowser
import pandas as pd
import tkinter as tk

from tkinter import ttk, filedialog

from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk

import folium
from folium import Element


def haversine(lat1, lon1, lat2, lon2):
    R = 6371000
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlambda/2)**2
    return 2*R*math.asin(math.sqrt(a))


def format_hhmmss(sec):
    sec = int(round(sec))
    h = sec // 3600
    m = (sec % 3600) // 60
    s = sec % 60
    return f"{h:02d}:{m:02d}:{s:02d}"


def make_folium_map(merged_df: pd.DataFrame, step: int, out_name: str = None) -> str:
    """
    merged_df: try_merge_and_update で作った self.merged_df 相当
    必須カラム:
      - Time (s), Latitude (°), Longitude (°), Height (m),
        Yaw (°), Pitch (°), Roll (°),
        cumulative_distance_m, speed_km_h
    step     : 間引きステップ
    out_name : 出力 HTML ファイル名（None のときは route_map_step{step}.html）
    戻り値   : 生成した HTML のフルパス
    """
    if out_name is None:
        out_name = f"route_map_step{step}.html"

    route = merged_df[['Latitude (°)', 'Longitude (°)']].values.tolist()
    if not route:
        raise ValueError("ルートデータが空です")

    center = route[len(route) // 2]

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

    # Summary 用統計
    t = merged_df['Time (s)']
    total_time_s = t.iloc[-1] - t.iloc[0]
    total_dist_m = merged_df['cumulative_distance_m'].iloc[-1]
    avg_speed_ms = total_dist_m / total_time_s if total_time_s > 0 else 0
    avg_speed_kmh = avg_speed_ms * 3.6

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

    # 詳細表示用 JS 関数
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

    # JS に渡す点データ
    step = max(1, int(step))
    point_data = []
    for i in range(0, len(merged_df), step):
        row = merged_df.iloc[i]
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

    import json
    js_points = json.dumps(point_data)

    map_name = m.get_name()

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

    out_path = os.path.abspath(out_name)
    m.save(out_path)
    return out_path


class LocationGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Phyphox Location GUI")
        self.root.geometry("1350x750")  # 横広め

        # DataFrame 保持用
        self.loc_df = None
        self.ori_df = None
        self.merged_df = None

        # メインレイアウト
        self.main_frame = ttk.Frame(root)
        self.main_frame.pack(fill="both", expand=True)

        self.main_frame.columnconfigure(0, weight=3)
        self.main_frame.columnconfigure(1, weight=2)
        self.main_frame.rowconfigure(0, weight=1)
        self.main_frame.rowconfigure(1, weight=1)

        # ===== グラフ領域 =====
        # 高度グラフ
        self.fig_alt = Figure(figsize=(5, 3), dpi=100)
        self.ax_alt = self.fig_alt.add_subplot(111)
        self.ax_alt.set_title("Altitude vs Time")
        self.ax_alt.set_xlabel("Time (s)")
        self.ax_alt.set_ylabel("Height (m)")
        self.ax_alt.grid(True)

        self.frame_alt = ttk.Frame(self.main_frame)
        self.frame_alt.grid(row=0, column=0, sticky="nsew")
        self.canvas_alt = FigureCanvasTkAgg(self.fig_alt, master=self.frame_alt)
        self.canvas_alt.draw()
        self.canvas_alt.get_tk_widget().pack(fill="both", expand=True)
        self.toolbar_alt = NavigationToolbar2Tk(self.canvas_alt, self.frame_alt)
        self.toolbar_alt.update()
        self.toolbar_alt.pack(fill="x")

        # 速度グラフ
        self.fig_spd = Figure(figsize=(5, 3), dpi=100)
        self.ax_spd = self.fig_spd.add_subplot(111)
        self.ax_spd.set_title("Speed vs Time")
        self.ax_spd.set_xlabel("Time (s)")
        self.ax_spd.set_ylabel("Speed (km/h)")
        self.ax_spd.grid(True)

        self.frame_spd = ttk.Frame(self.main_frame)
        self.frame_spd.grid(row=1, column=0, sticky="nsew")
        self.canvas_spd = FigureCanvasTkAgg(self.fig_spd, master=self.frame_spd)
        self.canvas_spd.draw()
        self.canvas_spd.get_tk_widget().pack(fill="both", expand=True)
        self.toolbar_spd = NavigationToolbar2Tk(self.canvas_spd, self.frame_spd)
        self.toolbar_spd.update()
        self.toolbar_spd.pack(fill="x")

        # ===== 右側: Summary と Log =====
        right_frame = ttk.Frame(self.main_frame, padding=5)
        right_frame.grid(row=0, column=1, rowspan=2, sticky="nsew")

        right_frame.columnconfigure(0, weight=1)
        right_frame.columnconfigure(1, weight=1)
        right_frame.rowconfigure(0, weight=1)

        self.summary_frame = ttk.Frame(right_frame, padding=5)
        self.summary_frame.grid(row=0, column=0, sticky="nsew")

        self.log_frame = ttk.Frame(right_frame, padding=5)
        self.log_frame.grid(row=0, column=1, sticky="nsew")

        # --- Summary 側 ---
        ttk.Label(self.summary_frame, text="Summary",
                  font=("Meiryo", 14, "bold")).pack(anchor="w", pady=(0, 8))

        self.start_var = tk.StringVar(value="Start: --, --")
        self.end_var = tk.StringVar(value="End:   --, --")
        self.time_var = tk.StringVar(value="Time:  00:00:00  (0.0 s)")
        self.dist_var = tk.StringVar(value="Dist:  0.000 km")
        self.vavg_var = tk.StringVar(value="Vavg:  0.00 km/h")

        ttk.Label(self.summary_frame, textvariable=self.start_var).pack(anchor="w", pady=2)
        ttk.Label(self.summary_frame, textvariable=self.end_var).pack(anchor="w", pady=2)
        ttk.Label(self.summary_frame, textvariable=self.time_var).pack(anchor="w", pady=2)
        ttk.Label(self.summary_frame, textvariable=self.dist_var).pack(anchor="w", pady=2)
        ttk.Label(self.summary_frame, textvariable=self.vavg_var).pack(anchor="w", pady=2)

        # Location ファイル + ボタン
        ttk.Label(self.summary_frame, text="Location.csv:", padding=(0, 10, 0, 0),
                  font=("Meiryo", 10, "bold")).pack(anchor="w")
        self.loc_path_var = tk.StringVar(value="(未選択)")
        ttk.Label(self.summary_frame, textvariable=self.loc_path_var,
                  foreground="gray").pack(anchor="w")

        loc_btn_frame = ttk.Frame(self.summary_frame)
        loc_btn_frame.pack(anchor="w", pady=(2, 5), fill="x")
        ttk.Button(loc_btn_frame, text="Location 読み込み",
                   command=self.load_location).pack(side="left")
        ttk.Button(loc_btn_frame, text="サンプル表示",
                   command=lambda: self.open_sample_window("Location", self.loc_df)
                   ).pack(side="left", padx=4)

        # Orientation ファイル + ボタン
        ttk.Label(self.summary_frame, text="Orientation.csv:", padding=(0, 10, 0, 0),
                  font=("Meiryo", 10, "bold")).pack(anchor="w")
        self.ori_path_var = tk.StringVar(value="(未選択)")
        ttk.Label(self.summary_frame, textvariable=self.ori_path_var,
                  foreground="gray").pack(anchor="w")

        ori_btn_frame = ttk.Frame(self.summary_frame)
        ori_btn_frame.pack(anchor="w", pady=(2, 5), fill="x")
        ttk.Button(ori_btn_frame, text="Orientation 読み込み",
                   command=self.load_orientation).pack(side="left")
        ttk.Button(ori_btn_frame, text="サンプル表示",
                   command=lambda: self.open_sample_window("Orientation", self.ori_df)
                   ).pack(side="left", padx=4)

        # マップ用 step
        ttk.Label(self.summary_frame, text="マップの点間引き(step)",
                  padding=(0, 10, 0, 0)).pack(anchor="w")
        self.step_var = tk.IntVar(value=10)
        self.step_entry = ttk.Entry(self.summary_frame, textvariable=self.step_var, width=8)
        self.step_entry.pack(anchor="w", pady=2)

        self.map_label_var = tk.StringVar(value="まだ生成していません")

        ttk.Button(self.summary_frame, text="マップ生成＆開く",
                   command=self.make_map).pack(anchor="w", pady=(10, 5))
        ttk.Label(self.summary_frame, textvariable=self.map_label_var,
                  foreground="gray").pack(anchor="w", pady=2)

        # --- Log 側 ---
        ttk.Label(self.log_frame, text="実行ログ",
                  padding=(0, 0, 0, 5),
                  font=("Meiryo", 10, "bold")).pack(anchor="w")
        self.log_text = tk.Text(self.log_frame, height=10, width=40)
        self.log_text.pack(fill="both", expand=True)
        self.log_text.configure(state="disabled")
        self.log_text.configure(font=("Consolas", 9))

        self.log_text.tag_config("INFO",  foreground="black")
        self.log_text.tag_config("OK",    foreground="green")
        self.log_text.tag_config("ERROR", foreground="red")

    # ===== ログ =====
    def append_log(self, message: str, level: str = "INFO"):
        if level not in ("INFO", "OK", "ERROR"):
            level = "INFO"
        self.log_text.configure(state="normal")
        self.log_text.insert("end", message + "\n", level)
        self.log_text.see("end")
        self.log_text.configure(state="disabled")

    # ===== CSVサンプル別窓 =====
    def open_sample_window(self, title: str, df: pd.DataFrame):
        if df is None or df.empty:
            self.append_log(f"[ERROR] {title} データがありません。", level="ERROR")
            return

        win = tk.Toplevel(self.root)
        win.title(title + " サンプル")
        win.geometry("800x300")

        tree = ttk.Treeview(win, show="headings")
        tree.pack(fill="both", expand=True)

        cols = list(df.columns)
        tree["columns"] = cols
        for c in cols:
            tree.column(c, width=120, anchor="w")
            tree.heading(c, text=c)

        # 全行表示
        for _, row in df.iterrows():
            values = [row[c] for c in cols]
            tree.insert("", "end", values=values)

    # ===== ファイル読み込み =====
    def load_location(self):
        path = filedialog.askopenfilename(
            title="Location.csv を選択",
            filetypes=[("CSV Files", "*.csv"), ("All Files", "*.*")]
        )
        if not path:
            return
        try:
            df = pd.read_csv(path, encoding="utf-8")
            df = df[['Time (s)', 'Latitude (°)', 'Longitude (°)', 'Height (m)']].dropna()
        except Exception as e:
            self.append_log(f"[ERROR] Location 読み込み失敗: {e}", level="ERROR")
            return

        self.loc_df = df
        self.loc_path_var.set(path)
        self.append_log(f"[OK] Location 読み込み: {path}", level="OK")

        self.try_merge_and_update()

    def load_orientation(self):
        path = filedialog.askopenfilename(
            title="Orientation.csv を選択",
            filetypes=[("CSV Files", "*.csv"), ("All Files", "*.*")]
        )
        if not path:
            return
        try:
            df = pd.read_csv(path, encoding="utf-8")
            df = df[['Time (s)', 'Yaw (°)', 'Pitch (°)', 'Roll (°)']].dropna()
        except Exception as e:
            self.append_log(f"[ERROR] Orientation 読み込み失敗: {e}", level="ERROR")
            return

        self.ori_df = df
        self.ori_path_var.set(path)
        self.append_log(f"[OK] Orientation 読み込み: {path}", level="OK")

        self.try_merge_and_update()

    # ===== マージ + サマリ計算 + グラフ更新 =====
    def try_merge_and_update(self):
        if self.loc_df is None or self.ori_df is None:
            return

        loc = self.loc_df.sort_values('Time (s)')
        ori = self.ori_df.sort_values('Time (s)')

        merged = pd.merge_asof(
            loc,
            ori,
            on='Time (s)',
            direction='nearest',
            suffixes=('', '_ori')
        ).dropna(subset=['Latitude (°)', 'Longitude (°)', 'Yaw (°)'])

        t = merged['Time (s)']

        dists = [0.0]
        for i in range(1, len(merged)):
            d = haversine(
                merged.iloc[i-1]['Latitude (°)'], merged.iloc[i-1]['Longitude (°)'],
                merged.iloc[i]['Latitude (°)'],   merged.iloc[i]['Longitude (°)'],
            )
            dists.append(d)

        merged['segment_distance_m'] = dists
        merged['cumulative_distance_m'] = merged['segment_distance_m'].cumsum()

        dt = t.diff().fillna(0)
        speed_ms = merged['segment_distance_m'] / dt.replace(0, pd.NA)
        merged['speed_m_s'] = speed_ms.fillna(0)
        merged['speed_km_h'] = merged['speed_m_s'] * 3.6

        self.merged_df = merged

        total_time_s = t.iloc[-1] - t.iloc[0]
        total_dist_m = merged['cumulative_distance_m'].iloc[-1]
        avg_speed_ms = total_dist_m / total_time_s if total_time_s > 0 else 0
        avg_speed_kmh = avg_speed_ms * 3.6

        # サマリ更新
        start_lat = merged.iloc[0]['Latitude (°)']
        start_lon = merged.iloc[0]['Longitude (°)']
        end_lat   = merged.iloc[-1]['Latitude (°)']
        end_lon   = merged.iloc[-1]['Longitude (°)']

        self.start_var.set(f"Start: {start_lat:.6f}, {start_lon:.6f}")
        self.end_var.set(f"End:   {end_lat:.6f}, {end_lon:.6f}")
        self.time_var.set(f"Time:  {format_hhmmss(total_time_s)}  ({total_time_s:.1f} s)")
        self.dist_var.set(f"Dist:  {total_dist_m/1000:.3f} km")
        self.vavg_var.set(f"Vavg:  {avg_speed_kmh:.2f} km/h")

        # グラフ更新
        self.ax_alt.clear()
        self.ax_alt.plot(merged['Time (s)'], merged['Height (m)'])
        self.ax_alt.set_title("Altitude vs Time")
        self.ax_alt.set_xlabel("Time (s)")
        self.ax_alt.set_ylabel("Height (m)")
        self.ax_alt.grid(True)
        self.canvas_alt.draw()

        self.ax_spd.clear()
        self.ax_spd.plot(merged['Time (s)'], merged['speed_km_h'])
        self.ax_spd.set_title("Speed vs Time")
        self.ax_spd.set_xlabel("Time (s)")
        self.ax_spd.set_ylabel("Speed (km/h)")
        self.ax_spd.grid(True)
        self.canvas_spd.draw()

        self.append_log("[OK] マージ & グラフ更新 完了", level="OK")

    # ===== マップ生成 =====
    def make_map(self):
        if self.merged_df is None:
            self.append_log("[ERROR] 先に Location と Orientation を読み込んでください。", level="ERROR")
            return

        step = self.step_var.get()
        if step <= 0:
            step = 1
            self.step_var.set(1)

        self.append_log(f"[INFO] マップ生成開始 step={step}", level="INFO")

        try:
            html_path = make_folium_map(self.merged_df, step)
        except Exception as e:
            self.map_label_var.set("マップ生成失敗")
            self.append_log(f"[ERROR] マップ生成中にエラー: {e}", level="ERROR")
            return

        self.map_label_var.set(f"生成: {html_path}")
        self.append_log(f"[OK] {html_path} 生成", level="OK")
        webbrowser.open('file://' + html_path)


if __name__ == "__main__":
    root = tk.Tk()
    app = LocationGUI(root)
    root.mainloop()
