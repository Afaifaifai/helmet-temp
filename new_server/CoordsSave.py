#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import socket
import threading
import yaml
import math
import mysql.connector
from contextlib import closing


# ---------- 小工具：計算兩點平均速度（km/h） ----------
def haversine_m(lat1, lon1, lat2, lon2, time_pass: float) -> float:
    """
    lat*, lon* : 兩個座標 (十進位度)
    time_pass  : 時間差 (秒)
    回傳值     : 平均速度 (km/h)
    """
    if time_pass <= 0:
        print("[WARN] time_pass must be > 0")
        return 0.0

    R = 6_371_000.0                                # 地球半徑 (m)
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi       = phi2 - phi1
    dlambda    = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    dist_m     = 2 * R * math.asin(math.sqrt(a))   # 路徑長度 (公尺)

    speed_mps  = dist_m / time_pass                # m/s
    return speed_mps * 3.6                         # 轉 km/h


class CoordsSave:
    """接收 (lat,lon) → 計算速度(km/h) → 更新 MySQL。"""

    def __init__(self, listen_host="0.0.0.0", listen_port=5001,
                 db_host="127.0.0.1", db_user="root",
                 db_pass="", db_name="tracking_db", db_table="Info", time_pass=1.0):

        # -------- DB 永續連線 --------
        self._db_conn = mysql.connector.connect(
            host=db_host, user=db_user, password=db_pass,
            database=db_name, autocommit=True
        )
        self._db_lock = threading.Lock()
        print("MySQL connected successfully.")

        self.db_table = db_table
        self.time_pass = time_pass

        # -------- Socket 伺服器 --------
        self.listen_host, self.listen_port = listen_host, listen_port
        self._server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._server.bind((self.listen_host, self.listen_port))
        self._server.listen(5)

        self._stop_evt = threading.Event()
        self._thread   = threading.Thread(target=self._serve, daemon=True)

    # ================== 公開方法 ==================
    def start(self):
        print(f"[GPS] listen on {self.listen_host}:{self.listen_port}")
        self._thread.start()

    def stop(self):
        self._stop_evt.set()
        try:                                           # 假連線跳出 accept
            with closing(socket.socket()) as s:
                s.connect((self.listen_host, self.listen_port))
        except OSError:
            pass
        self._thread.join()
        self._server.close()
        self._db_conn.close()
        print("[GPS] stopped.")

    # ================= 內部 =================
    def _serve(self):
        while not self._stop_evt.is_set():
            try:
                conn, addr = self._server.accept()
            except OSError:
                break
            threading.Thread(target=self._handle_client,
                             args=(conn, addr), daemon=True).start()

    # ---------- 每個客戶端 ----------
    def _handle_client(self, conn: socket.socket, addr):
        with conn:
            try:
                line = self._readline(conn).strip()         # 'lat,lon'
                print(f'[GPS-Received]: {line}')
                L = line.split(",")
                lat, lon = L[0], L[1]
                # lat, lon = map(float, line.split(","))
                speed = self._update_speed_db(lat, lon, record_id=1)
                conn.sendall(f"OK,{speed:.2f}kph\n".encode())
            except Exception as e:
                print(f"[GPS-ERROR] {e}")
                conn.sendall(b"ERROR\n")

    # ---------- 計算並更新資料庫 ----------
    def _update_speed_db(self, lat, lon, record_id=1):
        with self._db_lock:
            cur = self._db_conn.cursor()

            # 1. 取先前座標
            cur.execute(
                "SELECT ST_X(coords), ST_Y(coords) "
                f"FROM {self.db_table} WHERE id=%s", (record_id,)
            )
            row = cur.fetchone()
            if row and None not in row:
                lat_old, lon_old = row[1], row[0]
                speed_kph = haversine_m(lat_old, lon_old, lat, lon, self.time_pass)
            else:
                speed_kph = 0.0                   # 首次無法算速度

            # 2. 更新 pre_coords, coords, speed_kph
            cur.execute(
                "UPDATE %s "
                "SET pre_coords = coords, "
                "coords = ST_GeomFromText(%s), "
                "speed_kph = %s "
                "WHERE id = %s",
                self.db_table, (f"POINT({lon} {lat})", speed_kph, record_id)
            )
            cur.close()
            return speed_kph

    # ---------- 讀到換行 ----------
    @staticmethod
    def _readline(conn) -> str:
        data = bytearray()
        while True:
            ch = conn.recv(1)
            if not ch:
                break
            if ch == b'\n':
                break
            data.extend(ch)
        return data.decode("utf-8")


# ================= 實際啟動 =================
if __name__ == "__main__":
    with open("config.yaml", "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)

    server = CoordsSave(
        listen_host="0.0.0.0",                 # 固定 0.0.0.0
        listen_port=cfg["SAVE_PORT"],           # e.g. 5001
        db_host=cfg["DB_IP"], db_user=cfg["DB_USER"],
        db_pass=cfg["DB_PASSWORD"], db_name=cfg["DB_NAME"], db_table=cfg["DB_TABLE"],
        time_pass=cfg["TIME_PASS"]
    )
    server.start()

    try:
        while True:
            pass               # 或放主程式其它邏輯
    except KeyboardInterrupt:
        server.stop()
