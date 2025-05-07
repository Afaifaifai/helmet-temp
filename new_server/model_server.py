import socket
import struct
import threading
from contextlib import closing
import yaml 
import mysql.connector           # 連線 MySQL


class GatewayServer:
    """
    將『接收影像 → 轉送 YOLO 伺服器 → 回傳 mes』封裝成物件。
    ---------
    listen_host / listen_port : 提供相機端連線
    model_host  / model_port  : YOLO 推論伺服器位置
    """

    def __init__(self, listen_host="0.0.0.0", listen_port=2345,
                 model_host="127.0.0.1",  model_port=5000,
                 db_host="127.0.0.1",     db_user="root",
                 db_pass="0000",          db_name="tracking_db",    db_table='Info'):
        
        self.db_host = db_host; self.db_user = db_user
        self.db_pass = db_pass; self.db_name = db_name
        self.db_table = db_table

        # 建立一條持久連線；autocommit=True 免 transaction
        self._db_conn = mysql.connector.connect(
            host=db_host, user=db_user, password=db_pass,
            database=db_name, autocommit=True
        )
        self._db_lock = threading.Lock()    # 多執行緒時保護 cursor

        self.listen_host = listen_host
        self.listen_port = listen_port
        self.model_host  = model_host
        self.model_port  = model_port

        self._server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._server_sock.bind((self.listen_host, self.listen_port))
        self._server_sock.listen(5)

        self._stop_event = threading.Event()
        self._thread     = threading.Thread(target=self._serve, daemon=True)

    # --------------------- 公開方法 ---------------------

    def start(self):
        """於背景執行 Gateway 伺服器。"""
        print(f"[Gateway] listen on {self.listen_host}:{self.listen_port}")
        self._thread.start()

    def stop(self):
        """優雅關閉伺服器。"""
        self._stop_event.set()
        # 建立一次假連線以跳出 accept()
        with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as s:
            s.connect((self.listen_host, self.listen_port))
        self._thread.join()
        self._server_sock.close()

        self._db_conn.close() # Close DB connection

        print("[Gateway] stopped.")

    # --------------------- 內部私有 ---------------------

    def _serve(self):
        while not self._stop_event.is_set():
            try:
                client, addr = self._server_sock.accept()
            except OSError:
                break                                  # socket 被關閉
            threading.Thread(target=self._handle_client,
                             args=(client, addr),
                             daemon=True).start()

    def _handle_client(self, cam_conn: socket.socket, cam_addr):
        print(f"[Gateway] Camera connected: {cam_addr}")
        with cam_conn:
            try:
                image_bytes = self._recv_until_eof(cam_conn)
                mes = self._forward_to_model(image_bytes)
                cam_conn.sendall(mes.encode())
                print(f"[Gateway] mes='{mes}' sent back to camera")
            except Exception as e:
                print(f"[Gateway-ERROR] {e}")

    # -------- 與模型伺服器溝通 --------

    def _forward_to_model(self, img_bytes: bytes, id=1) -> str:
        speed = self._get_speed(id)
        with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as s:
            s.connect((self.model_host, self.model_port))
            payload = struct.pack("!I", len(img_bytes)) + img_bytes # image_length(4 byte) + image
            payload += struct.pack("!f", speed) # speed(4 byte)
            s.sendall(payload)

            mes_len = struct.unpack("!I", self._recvn(s, 4))[0]
            mes     = self._recvn(s, mes_len).decode()
            return mes
        
    def _get_speed(self, record_id: int = 1) -> float:
        try:
            with self._db_lock:                       # 保證 thread‑safe
                cursor = self._db_conn.cursor()
                query = f"SELECT speed_kph FROM {self.table_name} WHERE id=%s"
                cursor.execute(query, (record_id,))
                row = cursor.fetchone()
                cursor.close()
            return float(row[0]) if row else 0.0

        except mysql.connector.errors.InterfaceError:
            # 連線掉線 ⇒ 重連一次後遞迴呼叫
            self._db_conn.reconnect(attempts=3, delay=1)
            return self._get_speed(record_id)

        except Exception as e:
            print(f"[Gateway-DB] {e}")
            return 0.0

    # -------- socket 輔助函式 --------

    @staticmethod
    def _recvn(sock: socket.socket, n: int) -> bytes:
        data = bytearray()
        while len(data) < n:
            chunk = sock.recv(n - len(data))
            if not chunk:
                raise RuntimeError("socket closed while receiving")
            data.extend(chunk)
        return bytes(data)

    @staticmethod
    def _recv_until_eof(sock: socket.socket, bufsize: int = 4096) -> bytes:
        data = bytearray()
        while True:
            chunk = sock.recv(bufsize)
            if not chunk:
                break
            data.extend(chunk)
        if not data:
            raise RuntimeError("empty image received")
        return bytes(data)


# ========== 範例用法 ==========
if __name__ == "__main__":
    with open("config.yaml", "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)     # ctr 會是一個 dict

    gateway = GatewayServer(
        listen_host='0.0.0.0', listen_port=cfg['CLUSTER_PORT'],
        model_host=cfg['MODEL_IP'], model_port=cfg['MODEL_LISTEN_PORT'],
        db_host=cfg['DB_IP'], db_user=cfg['DB_USER'],
        db_pass=cfg['DB_PASSWORD'], db_name=cfg['DB_NAME']
    )
    gateway.start()
    
    try:
        while True:
            pass                              # 或放你的主程式邏輯
    except KeyboardInterrupt:
        gateway.stop()
