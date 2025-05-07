import time
import math
import threading
import socket
from pyicloud import PyiCloudService
from collections import deque
import os
import hashlib

def haversine(coord1, coord2):
    lat1, lon1 = math.radians(float(coord1[0]))
    lon1 = math.radians(float(coord1[1]))
    lat2 = math.radians(float(coord2[0]))
    lon2 = math.radians(float(coord2[1]))
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = math.sin(dlat / 2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2)**2
    c = 2 * math.asin(math.sqrt(a))
    r = 6371.0
    return c * r

def delete_files_in_folder(folder_path):
    if not os.path.isdir(folder_path):
        print(f"{folder_path} 不是一個有效的資料夾路徑")
        return
    for file_name in os.listdir(folder_path):
        file_path = os.path.join(folder_path, file_name)
        try:
            if os.path.isfile(file_path):
                os.remove(file_path)
                print(f"{file_path} 已刪除")
            elif os.path.isdir(file_path):
                delete_files_in_folder(file_path)
        except Exception as e:
            print(f"刪除 {file_path} 時發生錯誤：{e}")

def start_server1(): # 暫定: 回傳YOLO辨識結果
    ip = "172.20.10.2"
    port = 1234
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind((ip, port))
    server.listen(5)
    while True:
        client, address = server.accept()
        print(f"連接建立 - {address[0]}:{address[1]}")
        with open("//wsl$/Ubuntu-22.04/home/st426/darknet/mes/mes.txt", "r") as f:
            string = f.read()
        client.send(bytes(string, "utf-8"))
        client.close()

def start_server2(): # 回傳GPS
    ip = "172.20.10.2"
    port = 5678
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind((ip, port))
    server.listen(5)
    while True:
        client, address = server.accept()
        with open("C:/Users/st426/Desktop/SAS/orientation.txt", "r") as f: # CALL DB
            string = f.read()
        client.send(bytes(string, "utf-8"))
        client.close()
        time.sleep(5)

def start_server3(folder_path, host='172.20.10.2', port=2345): # 
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.bind((host, port))
    server_socket.listen(1)
    print(f"伺服器已啟動，正在 {host}:{port} 等待連接...")
    number = 0
    while True:
        try:
            client_socket, client_address = server_socket.accept()
            print(f"與 {client_address} 建立連接")
            file_names = os.listdir(folder_path)
            if len(file_names) < 4:
                number += 1
            path = os.path.join(folder_path, f"{number}.jpg")
            with open(path, 'wb') as image_file:
                while True:
                    data = client_socket.recv(1024)
                    if not data:
                        break
                    image_file.write(data)
            print("圖片已接收並儲存為:", path)
            client_socket.close()
        except Exception as e:
            print(f"[Server3 錯誤] {e}")
            continue  # 強制繼續



def calculate_file_hash(file_path):
    hasher = hashlib.sha256()
    with open(file_path, 'rb') as f:
        while True:
            chunk = f.read(8192)
            if not chunk:
                break
            hasher.update(chunk)
    return hasher.hexdigest()

# def start_server4(host='172.20.10.2', port=6789):
#     wav_file_path = "C:/Users/st426/Desktop/SAS/speak.wav"
#     previous_file_hash = None
#     server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
#     server_socket.bind((host, port))
#     server_socket.listen(1)
#     print(f"語音伺服器已啟動，正在 {host}:{port} 等待連接...")

#     while True:
#         try:
#             client_socket, client_address = server_socket.accept()
#             print(f"與 {client_address} 建立連接，檢查 WAV 檔案...")
#             if not os.path.isfile(wav_file_path):
#                 print(f"檔案 {wav_file_path} 不存在")
#                 client_socket.sendall(b"Error: File not found")
#                 client_socket.close()
#                 continue
#             current_file_hash = calculate_file_hash(wav_file_path)
#             if previous_file_hash is not None and current_file_hash == previous_file_hash:
#                 print("WAV 檔案未改變，跳過傳輸")
#                 client_socket.sendall(b"File not changed")
#             else:
#                 with open(wav_file_path, 'rb') as wav_file:
#                     while True:
#                         data = wav_file.read(1024)
#                         if not data:
#                             break
#                         client_socket.sendall(data)
#                 print("WAV 傳輸完成")
#                 previous_file_hash = current_file_hash
#             client_socket.sendall(b"Transmission complete")
#         except Exception as e:
#             print(f"[Server4 錯誤] {e}")
#         finally:
#             client_socket.close()
'''
def update_location():
    api = PyiCloudService('aa9128bb@gmail.com', 'meow9128Mumi')
    device = api.devices[0]
    data_history = []
    
    # 用來儲存最近 5 秒的速度
    speed_history = deque(maxlen=3)
    
    last_update_time = time.time()
    
    while True:
        try:
            # 獲取設備位置
            location = device.location()

            # 提取經緯度並儲存到列表中
            location_coords = [location['latitude'], location['longitude']]
            
            print(f"Current location: {location_coords}")

            coords = str(location['latitude']) + "," + str(location['longitude'])

            with open("C:/Users/st426/Desktop/SAS/coordinate.txt", "w") as f:
                f.write(coords)

            if len(data_history) > 2:
                data_history.pop(0)

            if len(data_history) == 2:
                distance = haversine(data_history[0], data_history[1])
                current_time = time.time()
                elapsed_time = current_time - last_update_time
                
                # 計算速度（公里/小時）
                speed = (distance / elapsed_time) * 3600
                
                # 更新最後更新時間
                last_update_time = current_time
            else:
                speed = 0

            # 將速度加入歷史列表
            speed_history.append(speed)
            
            # 計算最近 3 秒的平均速度
            average_speed = sum(speed_history) / len(speed_history)
            speed_str = f"{average_speed:.2f}"  # 格式化速度顯示
            print(f"最近 3 秒平均速度: {speed_str} 公里/小時")

            with open("//wsl$/Ubuntu-22.04/home/st426/darknet/ownspeed.txt", "w") as f:
                f.write(speed_str)

            print(speed_str)

            # 每隔 1 秒更新一次位置（可以根據需要調整）
            time.sleep(1)
            if len(data_history) < 2:
                data_history.append(location_coords)
                
        except Exception as e:
            print(f"An error occurred: {e}")
            break
'''


if __name__ == "__main__":
    folder_path = '//wsl$/Ubuntu-22.04/home/st426/darknet/Camera1'
    delete_files_in_folder(folder_path)

    #location_thread = threading.Thread(target=update_location)
    server1_thread = threading.Thread(target=start_server1)
    server2_thread = threading.Thread(target=start_server2)
    server3_thread = threading.Thread(target=start_server3, args=(folder_path,))
    # server4_thread = threading.Thread(target=start_server4)

    #location_thread.start()
    server1_thread.start()
    server2_thread.start()
    server3_thread.start()
    # server4_thread.start()

    #location_thread.join()
    server1_thread.join()
    server2_thread.join()
    server3_thread.join()
    # server4_thread.join()
