#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import socket
import threading
import yaml
import mysql.connector
from contextlib import closing


class CoordsGet:
    """接收任意連線 → 查詢 id=1 的 coords → 回傳 'lat,lon\\n'"""

    def __init__(self, listen_host="0.0.0.0", listen_port=5002,
                 db_host="127.0.0.1", db_user="root",
                 db_pass="", db_name="tracking_db", db_table="Info"):
        # ── DB 永續連線 ──
        self._conn = mysql.connector.connect(
            host=db_host, user=db_user, password=db_pass,
            database=db_name, autocommit=True
        )
        self._lock = threading.Lock()
        self.db_table = db_table

        # ── TCP 伺服器 ──
        self.listen_host, self.listen_port = listen_host, listen_port
        self._server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._server.bind((self.listen_host, self.listen_port))
        self._server.listen(5)

        self._stop_evt = threading.Event()
        self._thread = threading.Thread(target=self._serve, daemon=True)

    # ---------- 公開 ----------
    def start(self):
        print(f"[Query] listen on {self.listen_host}:{self.listen_port}")
        self._thread.start()

    def stop(self):
        self._stop_evt.set()
        try:                              # 假連線喚醒 accept
            with closing(socket.socket()) as s:
                s.connect((self.listen_host, self.listen_port))
        except OSError:
            pass
        self._thread.join()
        self._server.close()
        self._conn.close()
        print("[Query] stopped.")

    # ---------- 內部 ----------
    def _serve(self):
        while not self._stop_evt.is_set():
            try:
                conn, addr = self._server.accept()
            except OSError:
                break
            threading.Thread(target=self._handle, args=(conn,), daemon=True).start()

    def _handle(self, conn: socket.socket):
        with conn:
            try:
                lat, lon = self._fetch_coords(record_id=1)
                if lat is None:                     # 未找到紀錄
                    conn.sendall(b"NA\n")
                else:
                    conn.sendall(f"{lat},{lon}\n".encode())
            except Exception as e:
                print(f"[Query-ERROR] {e}")
                conn.sendall(b"ERROR\n")

    def _fetch_coords(self, record_id=1):
        with self._lock:
            cur = self._conn.cursor()
            cur.execute(
                f"SELECT ST_Y(coords), ST_X(coords) "
                f"FROM {self.db_table} WHERE id=%s",
                (record_id,)
            )
            row = cur.fetchone()
            cur.close()
        return (row[0], row[1]) if row else (None, None)


# ============= 啟動腳本 =============
if __name__ == "__main__":
    with open("config.yaml", "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)

    query_srv = CoordsGet(
        listen_host="0.0.0.0",
        listen_port=cfg["GET_PORT"],       # 例如 5002
        db_host=cfg["DB_IP"], db_user=cfg["DB_USER"],
        db_pass=cfg["DB_PASSWORD"], db_name=cfg["DB_NAME"],
        db_table=cfg["DB_TABLE"]
    )
    query_srv.start()

    try:
        while True:
            pass              # 或插入其他背景工作
    except KeyboardInterrupt:
        query_srv.stop()
