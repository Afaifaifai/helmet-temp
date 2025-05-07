import darknet
import time
import cv2
import threading
import queue
import os
import numpy as np
import datetime
import socket
import struct        # 打包長度用
import mysql.connector            # pip install mysql‑connector‑python
from mysql.connector import pooling

HOST = "0.0.0.0"
LISTEN_PORT = 5000          # 依需求自行修改

EXIT_BY_KEY = False      # 預設不離開

expiry_frames = 50

''' ---以上為新增的--- '''

objIndex = 0
ObjList = []

KNOWN_DISTANCE = 4  # INCHES
B_WIDTH = 16  # INCHES
S_WIDTH = 3.0  # INCHES
C_WIDTH = 16  # INCHES
T_WIDTH = 3.0  # INCHES
MT_WIDTH = 16  # INCHES

class_names = []
with open("classid.txt", "r") as f:
    class_names = [cname.strip() for cname in f.readlines()]


WEIGHT = "/home/st426/darknet/IMGDATA/cfg/weights/yolov4_final.weights"
CFG = "/home/st426/darknet/IMGDATA/cfg/yolov4.cfg"
DATA = "/home/st426/darknet/IMGDATA/cfg/obj.data"
CONFTH = 0.5
(WIDTH, HEIGHT) = (640, 640)  # 解析度 越高越精細速度越慢
RefimageList = ["B.jpg", "S.jpg", "C.jpg", "T.jpg", "MT.jpg"]

network, class_names, class_colors = darknet.load_network(
    CFG,
    DATA,
    WEIGHT,
)

# 影片參數
fps = 10  # 影片的幀率
fourcc = cv2.VideoWriter_fourcc(*'XVID')
video_writer = None


# 寫入影片的函式
def write_video():
    global is_writing, video_writer

    while is_writing:
        frame = frame_queue.get()
        if frame is not None:
            video_writer.write(frame)
    video_writer.release()

# Darknet YOLO辨識主程式
def initial_detection(image, network, class_names, class_colors, thresh):
    darknet_image = darknet.make_image(WIDTH, HEIGHT, 3)
    image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
    image_resized = cv2.resize(image_rgb, (WIDTH, HEIGHT))

    darknet.copy_image_from_bytes(darknet_image, image_resized.tobytes())
    detections = darknet.detect_image(network, class_names, darknet_image, thresh=thresh)
    darknet.free_image(darknet_image)
    image = darknet.draw_boxes(detections, image_resized, class_colors)

    for detection in detections:
        class_name, confidence, (x, y, w, h) = detection
        try:
            width_in_rf = w
        except:
            width_in_rf = 1

    try:
        test = 1/width_in_rf
    except:
        width_in_rf = 1

    return width_in_rf

# Darknet YOLO辨識主程式
def image_detection(image, network, class_names, class_colors, thresh):
    darknet_image = darknet.make_image(WIDTH, HEIGHT, 3)
    image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
    image_resized = cv2.resize(image_rgb, (WIDTH, HEIGHT))

    darknet.copy_image_from_bytes(darknet_image, image_resized.tobytes())
    detections = darknet.detect_image(network, class_names, darknet_image, thresh=thresh)
    darknet.free_image(darknet_image)
    image = darknet.draw_boxes(detections, image_resized, class_colors)
    
    updated_detections = []
    
    for detection in detections:
        class_name, confidence, (x, y, w, h) = detection
        if class_name == 'B':
            distance = distance_finder(focal_B, B_WIDTH, w)
        elif class_name == 'S':
            distance = distance_finder(focal_S, S_WIDTH, w)
        elif class_name == 'C':
            distance = distance_finder(focal_C, C_WIDTH, w)
        elif class_name == 'T':
            distance = distance_finder(focal_T, T_WIDTH, w)
        elif class_name == 'MT':
            distance = distance_finder(focal_MT, MT_WIDTH, w)
        else:
            distance = None
        
        # Add distance to the detection tuple
        updated_detection = (class_name, confidence, (x, y, w, h), distance)
        updated_detections.append(updated_detection)

    return cv2.cvtColor(image, cv2.COLOR_BGR2RGB), updated_detections

def focal_length_finder(measured_distance, real_width, width_in_rf):
    focal_length = (width_in_rf * measured_distance) / real_width
    return focal_length

def distance_finder(focal_length, real_object_width, width_in_frame):
    distance = (real_object_width * focal_length) / width_in_frame
    return distance

def calculate_average_speed(previous_distances, fps):
    if len(previous_distances) < 2:
        return 0
    
    speed_sum = 0
    for i in range(1, len(previous_distances)):
        distance_diff = previous_distances[i] - previous_distances[i-1]
        speed_sum += distance_diff * fps
    
    average_speed = speed_sum / (len(previous_distances) - 1)
    return average_speed

# 物件追蹤程式
def TrackObj(newCenterList, ObjList1, objIndex, temp_storage, expiry_frames, newDistance):
    ObjListTemp = []
    matched_ids = set()
    
    for i in range(len(newCenterList)):
        newP = (newCenterList[i][0], newCenterList[i][1])
        matched = False
        for obj_id, obj_info in temp_storage.items():
            oldP = obj_info['position']
            distant = ((oldP[0] - newP[0]) ** 2 + (oldP[1] - newP[1]) ** 2) ** 0.5
            if distant < 30 and obj_info['class'] == newCenterList[i][2]:  # 確認類別相同
                temp_storage[obj_id]['position'] = newP
                temp_storage[obj_id]['frame_count'] = 0
                matched = True
                matched_ids.add(obj_id)
                
                # Calculate average speed based on distance changes
                previous_distances = temp_storage[obj_id]['previous_distances']
                average_speed = calculate_average_speed(previous_distances, fps)
                ObjListTemp.append((obj_id, newP[0], newP[1], newDistance[i], average_speed, obj_info['class']))
                
                # Update previous distances
                temp_storage[obj_id]['previous_distances'].append(newDistance[i])
                if len(temp_storage[obj_id]['previous_distances']) > 25:
                    temp_storage[obj_id]['previous_distances'].pop(0)
                
                break

        if not matched:
            objIndex += 1
            temp_storage[objIndex] = {'class': newCenterList[i][2], 'position': newP, 'frame_count': 0, 'previous_distances': [newDistance[i]]}
            average_speed = 0
            ObjListTemp.append((objIndex, newP[0], newP[1], newDistance[i], average_speed, newCenterList[i][2]))
            matched_ids.add(objIndex)

    # 更新暫存區中的物件的幀計數器，並刪除超過過期時間的物件
    expired_ids = []
    for obj_id, obj_info in temp_storage.items():
        if obj_id not in matched_ids:
            temp_storage[obj_id]['frame_count'] += 1
        if temp_storage[obj_id]['frame_count'] > expiry_frames:
            expired_ids.append(obj_id)
    
    for obj_id in expired_ids:
        del temp_storage[obj_id]

    return ObjListTemp, objIndex






def riskrule(ObjList,speed):
    risk_temp = []
    rihgt_risk_temp = []
    middle_risk_temp = []
    left_risk_temp = []
    for i in range(len(ObjList)):
        #類型為B
        if ObjList[i][5] == 'B':
            #自身速度
            if speed <= 40:
                #相對速度
                if ObjList[i][4] <= 3:
                    #相對距離
                    if ObjList[i][3] <= 3.5:
                        if ObjList[i][1] <= 220:
                            rihgt_risk_temp.append(1)
                        elif ObjList[i][1] >= 420:
                            left_risk_temp.append(1)
                        else :
                            middle_risk_temp.append(1)
                    #相對距離
                    else:
                        if ObjList[i][1] <= 220:
                            rihgt_risk_temp.append(0)
                        elif ObjList[i][1] >= 420:
                            left_risk_temp.append(0)
                        else :
                            middle_risk_temp.append(0)  
                #相對速度           
                else:
                    #相對距離
                    if ObjList[i][3] <= 3.5:
                        if ObjList[i][1] <= 220:
                            rihgt_risk_temp.append(2)
                        elif ObjList[i][1] >= 420:
                            left_risk_temp.append(2)
                        else :
                            middle_risk_temp.append(2)   
                    #相對距離  
                    if ObjList[i][3] >= 6:  
                        if ObjList[i][1] <= 220:
                            rihgt_risk_temp.append(0)
                        elif ObjList[i][1] >= 420:
                            left_risk_temp.append(0)
                        else :
                            middle_risk_temp.append(0)  
                    #相對距離       
                    else:  
                        if ObjList[i][3] <= 3.5:
                            if ObjList[i][1] <= 220:
                                rihgt_risk_temp.append(1)
                            elif ObjList[i][1] >= 420:
                                left_risk_temp.append(1)
                            else :
                                middle_risk_temp.append(1)  
            #自身速度
            else:                                                                        
                #相對距離
                if ObjList[i][3] <= 3.5:
                        if ObjList[i][1] <= 220:
                            rihgt_risk_temp.append(1)
                        elif ObjList[i][1] >= 420:
                            left_risk_temp.append(1)
                        else :
                            middle_risk_temp.append(1) 
                #相對距離
                else:
                        if ObjList[i][1] <= 220:
                            rihgt_risk_temp.append(0)
                        elif ObjList[i][1] >= 420:
                            left_risk_temp.append(0)
                        else :
                            middle_risk_temp.append(0) 



        #類型為'S'
        if ObjList[i][5] == 'S':
            #自身速度
            if speed <= 40:
                #相對速度
                if ObjList[i][4] <= 9:
                    #相對距離
                    if ObjList[i][3] <= 3:                  
                        if ObjList[i][1] <= 220:
                            rihgt_risk_temp.append(2)
                        elif ObjList[i][1] >= 420:
                            left_risk_temp.append(2)
                        else :
                            middle_risk_temp.append(2) 
                    #相對距離  
                    elif ObjList[i][3] >= 6:                  
                        if ObjList[i][1] <= 220:
                            rihgt_risk_temp.append(0)
                        elif ObjList[i][1] >= 420:
                            left_risk_temp.append(0)
                        else :
                            middle_risk_temp.append(0)  
                    #相對距離  
                    else:                  
                        if ObjList[i][1] <= 220:
                            rihgt_risk_temp.append(1)
                        elif ObjList[i][1] >= 420:
                            left_risk_temp.append(1)
                        else :
                            middle_risk_temp.append(1)  
                #相對速度
                elif 15 >= ObjList[i][4] > 9 :
                    #相對距離
                    if ObjList[i][3] <= 6:                  
                        if ObjList[i][1] <= 220:
                            rihgt_risk_temp.append(2)
                        elif ObjList[i][1] >= 420:
                            left_risk_temp.append(2)
                        else :
                            middle_risk_temp.append(2) 
                    #相對距離  
                    elif ObjList[i][3] >= 10:                  
                        if ObjList[i][1] <= 220:
                            rihgt_risk_temp.append(0)
                        elif ObjList[i][1] >= 420:
                            left_risk_temp.append(0)
                        else :
                            middle_risk_temp.append(0)  
                    #相對距離  
                    else:                  
                        if ObjList[i][1] <= 220:
                            rihgt_risk_temp.append(1)
                        elif ObjList[i][1] >= 420:
                            left_risk_temp.append(1)
                        else :
                            middle_risk_temp.append(1) 
                #相對速度
                else:
                    #相對距離
                    if ObjList[i][3] <= 10:                  
                        if ObjList[i][1] <= 220:
                            rihgt_risk_temp.append(2)
                        elif ObjList[i][1] >= 420:
                            left_risk_temp.append(2)
                        else :
                            middle_risk_temp.append(2) 
                    #相對距離  
                    elif ObjList[i][3] >= 18:                  
                        if ObjList[i][1] <= 220:
                            rihgt_risk_temp.append(0)
                        elif ObjList[i][1] >= 420:
                            left_risk_temp.append(0)
                        else :
                            middle_risk_temp.append(0)  
                    #相對距離  
                    else:                  
                        if ObjList[i][1] <= 220:
                            rihgt_risk_temp.append(1)
                        elif ObjList[i][1] >= 420:
                            left_risk_temp.append(1)
                        else :
                            middle_risk_temp.append(1)
            #自身速度
            if 60 >= speed > 40:
                #相對速度
                if ObjList[i][4] <= 3:
                    #相對距離
                    if ObjList[i][3] <= 2:                  
                        if ObjList[i][1] <= 220:
                            rihgt_risk_temp.append(2)
                        elif ObjList[i][1] >= 420:
                            left_risk_temp.append(2)
                        else :
                            middle_risk_temp.append(2) 
                    #相對距離  
                    elif ObjList[i][3] >= 3.5:                  
                        if ObjList[i][1] <= 220:
                            rihgt_risk_temp.append(0)
                        elif ObjList[i][1] >= 420:
                            left_risk_temp.append(0)
                        else :
                            middle_risk_temp.append(0)  
                    #相對距離  
                    else:                  
                        if ObjList[i][1] <= 220:
                            rihgt_risk_temp.append(1)
                        elif ObjList[i][1] >= 420:
                            left_risk_temp.append(1)
                        else :
                            middle_risk_temp.append(1)  
                #相對速度
                elif 9 >= ObjList[i][4] > 3 :
                    #相對距離
                    if ObjList[i][3] <= 3.5:                  
                        if ObjList[i][1] <= 220:
                            rihgt_risk_temp.append(2)
                        elif ObjList[i][1] >= 420:
                            left_risk_temp.append(2)
                        else :
                            middle_risk_temp.append(2) 
                    #相對距離  
                    elif ObjList[i][3] >= 6:                  
                        if ObjList[i][1] <= 220:
                            rihgt_risk_temp.append(0)
                        elif ObjList[i][1] >= 420:
                            left_risk_temp.append(0)
                        else :
                            middle_risk_temp.append(0)  
                    #相對距離  
                    else:                  
                        if ObjList[i][1] <= 220:
                            rihgt_risk_temp.append(1)
                        elif ObjList[i][1] >= 420:
                            left_risk_temp.append(1)
                        else :
                            middle_risk_temp.append(1) 
                #相對速度
                else:
                    #相對距離
                    if ObjList[i][3] <= 6:                  
                        if ObjList[i][1] <= 220:
                            rihgt_risk_temp.append(2)
                        elif ObjList[i][1] >= 420:
                            left_risk_temp.append(2)
                        else :
                            middle_risk_temp.append(2) 
                    #相對距離  
                    elif ObjList[i][3] >= 10:                  
                        if ObjList[i][1] <= 220:
                            rihgt_risk_temp.append(0)
                        elif ObjList[i][1] >= 420:
                            left_risk_temp.append(0)
                        else :
                            middle_risk_temp.append(0)  
                    #相對距離  
                    else:                  
                        if ObjList[i][1] <= 220:
                            rihgt_risk_temp.append(1)
                        elif ObjList[i][1] >= 420:
                            left_risk_temp.append(1)
                        else :
                            middle_risk_temp.append(1)
            #自身速度
            else:
                #相對速度
                if ObjList[i][4] <= 3:
                    #相對距離
                    if ObjList[i][3] <= 2:                  
                        if ObjList[i][1] <= 220:
                            rihgt_risk_temp.append(2)
                        elif ObjList[i][1] >= 420:
                            left_risk_temp.append(2)
                        else :
                            middle_risk_temp.append(2) 
                    #相對距離  
                    elif ObjList[i][3] >= 3.5:                  
                        if ObjList[i][1] <= 220:
                            rihgt_risk_temp.append(0)
                        elif ObjList[i][1] >= 420:
                            left_risk_temp.append(0)
                        else :
                            middle_risk_temp.append(0)  
                    #相對距離  
                    else:                  
                        if ObjList[i][1] <= 220:
                            rihgt_risk_temp.append(1)
                        elif ObjList[i][1] >= 420:
                            left_risk_temp.append(1)
                        else :
                            middle_risk_temp.append(1)  
                #相對速度
                else:
                    #相對距離
                    if ObjList[i][3] <= 5:                  
                        if ObjList[i][1] <= 220:
                            rihgt_risk_temp.append(2)
                        elif ObjList[i][1] >= 420:
                            left_risk_temp.append(2)
                        else :
                            middle_risk_temp.append(2) 
                    #相對距離  
                    elif ObjList[i][3] >= 8:                  
                        if ObjList[i][1] <= 220:
                            rihgt_risk_temp.append(0)
                        elif ObjList[i][1] >= 420:
                            left_risk_temp.append(0)
                        else :
                            middle_risk_temp.append(0)  
                    #相對距離  
                    else:                  
                        if ObjList[i][1] <= 220:
                            rihgt_risk_temp.append(1)
                        elif ObjList[i][1] >= 420:
                            left_risk_temp.append(1)
                        else :
                            middle_risk_temp.append(1) 


        if ObjList[i][5] == 'C':
            #自身速度
            if speed <= 60:
                #相對速度
                if ObjList[i][4] <= 3:
                    #相對距離
                    if ObjList[i][3] <= 3:                  
                        if ObjList[i][1] <= 220:
                            rihgt_risk_temp.append(2)
                        elif ObjList[i][1] >= 420:
                            left_risk_temp.append(2)
                        else :
                            middle_risk_temp.append(2) 
                    #相對距離  
                    elif ObjList[i][3] >= 5:                  
                        if ObjList[i][1] <= 220:
                            rihgt_risk_temp.append(0)
                        elif ObjList[i][1] >= 420:
                            left_risk_temp.append(0)
                        else :
                            middle_risk_temp.append(0)  
                    #相對距離  
                    else:                  
                        if ObjList[i][1] <= 220:
                            rihgt_risk_temp.append(1)
                        elif ObjList[i][1] >= 420:
                            left_risk_temp.append(1)
                        else :
                            middle_risk_temp.append(1)
                #相對速度
                elif 9 >= ObjList[i][4] > 3 :
                    #相對距離
                    if ObjList[i][3] <= 5:                  
                        if ObjList[i][1] <= 220:
                            rihgt_risk_temp.append(2)
                        elif ObjList[i][1] >= 420:
                            left_risk_temp.append(2)
                        else :
                            middle_risk_temp.append(2) 
                    #相對距離  
                    elif ObjList[i][3] >= 8:                  
                        if ObjList[i][1] <= 220:
                            rihgt_risk_temp.append(0)
                        elif ObjList[i][1] >= 420:
                            left_risk_temp.append(0)
                        else :
                            middle_risk_temp.append(0)  
                    #相對距離  
                    else:                  
                        if ObjList[i][1] <= 220:
                            rihgt_risk_temp.append(1)
                        elif ObjList[i][1] >= 420:
                            left_risk_temp.append(1)
                        else :
                            middle_risk_temp.append(1)   
                #相對速度
                elif 15 >= ObjList[i][4] > 9 :
                    #相對距離
                    if ObjList[i][3] <= 8:                  
                        if ObjList[i][1] <= 220:
                            rihgt_risk_temp.append(2)
                        elif ObjList[i][1] >= 420:
                            left_risk_temp.append(2)
                        else :
                            middle_risk_temp.append(2) 
                    #相對距離  
                    elif ObjList[i][3] >= 12:                  
                        if ObjList[i][1] <= 220:
                            rihgt_risk_temp.append(0)
                        elif ObjList[i][1] >= 420:
                            left_risk_temp.append(0)
                        else :
                            middle_risk_temp.append(0)  
                    #相對距離  
                    else:                  
                        if ObjList[i][1] <= 220:
                            rihgt_risk_temp.append(1)
                        elif ObjList[i][1] >= 420:
                            left_risk_temp.append(1)
                        else :
                            middle_risk_temp.append(1) 
                #相對速度
                else:
                    #相對距離
                    if ObjList[i][3] <= 15:                  
                        if ObjList[i][1] <= 220:
                            rihgt_risk_temp.append(2)
                        elif ObjList[i][1] >= 420:
                            left_risk_temp.append(2)
                        else :
                            middle_risk_temp.append(2) 
                    #相對距離  
                    elif ObjList[i][3] >= 25:                  
                        if ObjList[i][1] <= 220:
                            rihgt_risk_temp.append(0)
                        elif ObjList[i][1] >= 420:
                            left_risk_temp.append(0)
                        else :
                            middle_risk_temp.append(0)  
                    #相對距離  
                    else:                  
                        if ObjList[i][1] <= 220:
                            rihgt_risk_temp.append(1)
                        elif ObjList[i][1] >= 420:
                            left_risk_temp.append(1)
                        else :
                            middle_risk_temp.append(1)
            #自身速度
            else:
                #相對速度
                if ObjList[i][4] <= 3:
                    #相對距離
                    if ObjList[i][3] <= 5:                  
                        if ObjList[i][1] <= 220:
                            rihgt_risk_temp.append(2)
                        elif ObjList[i][1] >= 420:
                            left_risk_temp.append(2)
                        else :
                            middle_risk_temp.append(2) 
                    #相對距離  
                    elif ObjList[i][3] >= 8:                  
                        if ObjList[i][1] <= 220:
                            rihgt_risk_temp.append(0)
                        elif ObjList[i][1] >= 420:
                            left_risk_temp.append(0)
                        else :
                            middle_risk_temp.append(0)  
                    #相對距離  
                    else:                  
                        if ObjList[i][1] <= 220:
                            rihgt_risk_temp.append(1)
                        elif ObjList[i][1] >= 420:
                            left_risk_temp.append(1)
                        else :
                            middle_risk_temp.append(1)  
                #相對速度
                else:
                    #相對距離
                    if ObjList[i][3] <= 6:                  
                        if ObjList[i][1] <= 220:
                            rihgt_risk_temp.append(2)
                        elif ObjList[i][1] >= 420:
                            left_risk_temp.append(2)
                        else :
                            middle_risk_temp.append(2) 
                    #相對距離  
                    elif ObjList[i][3] >= 10:                  
                        if ObjList[i][1] <= 220:
                            rihgt_risk_temp.append(0)
                        elif ObjList[i][1] >= 420:
                            left_risk_temp.append(0)
                        else :
                            middle_risk_temp.append(0)  
                    #相對距離  
                    else:                  
                        if ObjList[i][1] <= 220:
                            rihgt_risk_temp.append(1)
                        elif ObjList[i][1] >= 420:
                            left_risk_temp.append(1)
                        else :
                            middle_risk_temp.append(1) 
                



        if ObjList[i][5] == 'T':
            #相對速度
            if ObjList[i][4] <= 3:
                #相對距離
                if ObjList[i][3] <= 4:                  
                    if ObjList[i][1] <= 220:
                        rihgt_risk_temp.append(2)
                    elif ObjList[i][1] >= 420:
                        left_risk_temp.append(2)
                    else :
                        middle_risk_temp.append(2) 
                #相對距離  
                elif ObjList[i][3] >= 6:                  
                    if ObjList[i][1] <= 220:
                        rihgt_risk_temp.append(0)
                    elif ObjList[i][1] >= 420:
                        left_risk_temp.append(0)
                    else :
                        middle_risk_temp.append(0)  
                #相對距離  
                else:                  
                    if ObjList[i][1] <= 220:
                        rihgt_risk_temp.append(1)
                    elif ObjList[i][1] >= 420:
                        left_risk_temp.append(1)
                    else :
                        middle_risk_temp.append(1)
            #相對速度
            elif 9 >= ObjList[i][4] > 3 :
                #相對距離
                if ObjList[i][3] <= 6:                  
                    if ObjList[i][1] <= 220:
                        rihgt_risk_temp.append(2)
                    elif ObjList[i][1] >= 420:
                        left_risk_temp.append(2)
                    else :
                        middle_risk_temp.append(2) 
                #相對距離  
                elif ObjList[i][3] >= 10:                  
                    if ObjList[i][1] <= 220:
                        rihgt_risk_temp.append(0)
                    elif ObjList[i][1] >= 420:
                        left_risk_temp.append(0)
                    else :
                        middle_risk_temp.append(0)  
                #相對距離  
                else:                  
                    if ObjList[i][1] <= 220:
                        rihgt_risk_temp.append(1)
                    elif ObjList[i][1] >= 420:
                        left_risk_temp.append(1)
                    else :
                        middle_risk_temp.append(1)   
            #相對速度
            elif 15 >= ObjList[i][4] > 9 :
                #相對距離
                if ObjList[i][3] <= 10:                  
                    if ObjList[i][1] <= 220:
                        rihgt_risk_temp.append(2)
                    elif ObjList[i][1] >= 420:
                        left_risk_temp.append(2)
                    else :
                        middle_risk_temp.append(2) 
                #相對距離  
                elif ObjList[i][3] >= 15:                  
                    if ObjList[i][1] <= 220:
                        rihgt_risk_temp.append(0)
                    elif ObjList[i][1] >= 420:
                        left_risk_temp.append(0)
                    else :
                        middle_risk_temp.append(0)  
                #相對距離  
                else:                  
                    if ObjList[i][1] <= 220:
                        rihgt_risk_temp.append(1)
                    elif ObjList[i][1] >= 420:
                        left_risk_temp.append(1)
                    else :
                        middle_risk_temp.append(1) 
            #相對速度
            else:
                #相對距離
                if ObjList[i][3] <= 15:                  
                    if ObjList[i][1] <= 220:
                        rihgt_risk_temp.append(2)
                    elif ObjList[i][1] >= 420:
                        left_risk_temp.append(2)
                    else :
                        middle_risk_temp.append(2) 
                #相對距離  
                elif ObjList[i][3] >= 25:                  
                    if ObjList[i][1] <= 220:
                        rihgt_risk_temp.append(0)
                    elif ObjList[i][1] >= 420:
                        left_risk_temp.append(0)
                    else :
                        middle_risk_temp.append(0)  
                #相對距離  
                else:                  
                    if ObjList[i][1] <= 220:
                        rihgt_risk_temp.append(1)
                    elif ObjList[i][1] >= 420:
                        left_risk_temp.append(1)
                    else :
                        middle_risk_temp.append(1)



        if ObjList[i][5] == 'MT':
            #相對速度
            if ObjList[i][4] <= 3:
                #相對距離
                if ObjList[i][3] <= 5:                  
                    if ObjList[i][1] <= 220:
                        rihgt_risk_temp.append(2)
                    elif ObjList[i][1] >= 420:
                        left_risk_temp.append(2)
                    else :
                        middle_risk_temp.append(2) 
                #相對距離  
                elif ObjList[i][3] >= 7:                  
                    if ObjList[i][1] <= 220:
                        rihgt_risk_temp.append(0)
                    elif ObjList[i][1] >= 420:
                        left_risk_temp.append(0)
                    else :
                        middle_risk_temp.append(0)  
                #相對距離  
                else:                  
                    if ObjList[i][1] <= 220:
                        rihgt_risk_temp.append(1)
                    elif ObjList[i][1] >= 420:
                        left_risk_temp.append(1)
                    else :
                        middle_risk_temp.append(1)
            #相對速度
            elif 9 >= ObjList[i][4] > 3 :
                #相對距離
                if ObjList[i][3] <= 7:                  
                    if ObjList[i][1] <= 220:
                        rihgt_risk_temp.append(2)
                    elif ObjList[i][1] >= 420:
                        left_risk_temp.append(2)
                    else :
                        middle_risk_temp.append(2) 
                #相對距離  
                elif ObjList[i][3] >= 10:                  
                    if ObjList[i][1] <= 220:
                        rihgt_risk_temp.append(0)
                    elif ObjList[i][1] >= 420:
                        left_risk_temp.append(0)
                    else :
                        middle_risk_temp.append(0)  
                #相對距離  
                else:                  
                    if ObjList[i][1] <= 220:
                        rihgt_risk_temp.append(1)
                    elif ObjList[i][1] >= 420:
                        left_risk_temp.append(1)
                    else :
                        middle_risk_temp.append(1)   
            #相對速度
            elif 15 >= ObjList[i][4] > 9 :
                #相對距離
                if ObjList[i][3] <= 10:                  
                    if ObjList[i][1] <= 220:
                        rihgt_risk_temp.append(2)
                    elif ObjList[i][1] >= 420:
                        left_risk_temp.append(2)
                    else :
                        middle_risk_temp.append(2) 
                #相對距離  
                elif ObjList[i][3] >= 16:                  
                    if ObjList[i][1] <= 220:
                        rihgt_risk_temp.append(0)
                    elif ObjList[i][1] >= 420:
                        left_risk_temp.append(0)
                    else :
                        middle_risk_temp.append(0)  
                #相對距離  
                else:                  
                    if ObjList[i][1] <= 220:
                        rihgt_risk_temp.append(1)
                    elif ObjList[i][1] >= 420:
                        left_risk_temp.append(1)
                    else :
                        middle_risk_temp.append(1) 
            #相對速度
            else:
                #相對距離
                if ObjList[i][3] <= 18:                  
                    if ObjList[i][1] <= 220:
                        rihgt_risk_temp.append(2)
                    elif ObjList[i][1] >= 420:
                        left_risk_temp.append(2)
                    else :
                        middle_risk_temp.append(2) 
                #相對距離  
                elif ObjList[i][3] >= 30:                  
                    if ObjList[i][1] <= 220:
                        rihgt_risk_temp.append(0)
                    elif ObjList[i][1] >= 420:
                        left_risk_temp.append(0)
                    else :
                        middle_risk_temp.append(0)  
                #相對距離  
                else:                  
                    if ObjList[i][1] <= 220:
                        rihgt_risk_temp.append(1)
                    elif ObjList[i][1] >= 420:
                        left_risk_temp.append(1)
                    else :
                        middle_risk_temp.append(1)


    if len(rihgt_risk_temp) == 0:
        rihgt_risk_temp = [0]
    if len(left_risk_temp) == 0:
        left_risk_temp = [0]
    if len(middle_risk_temp) == 0:
        middle_risk_temp = [0]

    risk_temp = [max(rihgt_risk_temp),max(middle_risk_temp),max(left_risk_temp)]

    return(risk_temp)

def calculate_max_risks(risk_history):
    max_right = max([risk[0] for risk in risk_history])
    max_middle = max([risk[1] for risk in risk_history])
    max_left = max([risk[2] for risk in risk_history])
    return (max_right, max_middle, max_left)



def pre_trained():
    global is_writing, frame_queue, focal_B, focal_S, focal_C, focal_T, focal_MT

    width_in_rf_list = []
    TARGET_folder = "REFimg"
    TARGET = TARGET_folder + "/" + RefimageList[0]

    cap = cv2.VideoCapture(TARGET)
    frame_queue = queue.Queue()
    REFtimes = 0
    is_writing = False

    while cap.isOpened():
        ret, frame = cap.read()  # ret=retval,frame=image
        if not ret:
            break
        
        # 影像偵測
        width_in_rf = initial_detection(frame, network, class_names, class_colors, CONFTH)
        width_in_rf_list.append(width_in_rf)
        
        REFtimes += 1
        try:
            TARGET = TARGET_folder + "/" + RefimageList[REFtimes]
        except:
            break
        
        cap = cv2.VideoCapture(TARGET)
        if REFtimes >= len(RefimageList):
            break

    B_width_in_rf = float(width_in_rf_list[0])
    S_width_in_rf = float(width_in_rf_list[1])
    C_width_in_rf = float(width_in_rf_list[2])
    T_width_in_rf = float(width_in_rf_list[3])
    MT_width_in_rf = float(width_in_rf_list[4])

    focal_B = focal_length_finder(KNOWN_DISTANCE, B_WIDTH, B_width_in_rf)
    focal_S = focal_length_finder(KNOWN_DISTANCE, S_WIDTH, S_width_in_rf)
    focal_C = focal_length_finder(KNOWN_DISTANCE, C_WIDTH, C_width_in_rf)
    focal_T = focal_length_finder(KNOWN_DISTANCE, T_WIDTH, T_width_in_rf)
    focal_MT = focal_length_finder(KNOWN_DISTANCE, MT_WIDTH, MT_width_in_rf)

    cap.release()
    frame_queue.put(None)  # 停止寫入影片的執行緒

# Camera1_Number = 1
# TARGET_folder = "Camera1"
# TARGET = TARGET_folder + "/" + str(Camera1_Number) + '.jpg'

# cap = cv2.VideoCapture(TARGET)
# frame_queue = queue.Queue()
# write_thread = threading.Thread(target=write_video)


# risk_history = []
# ObjList = []
# temp_storage = {}
# expiry_frames = 50
# speed = 0

# while cap.isOpened():
#     ret, frame = cap.read()  # ret=retval,frame=image
#     if not ret:
#         break

#     # 影像偵測
#     frame, detections = image_detection(frame, network, class_names, class_colors, CONFTH)
    
#     # Print detections without the distance value
#     print_detections = [(detection[0], detection[1], detection[2]) for detection in detections]
#     darknet.print_detections(print_detections)
        
#     PredDict = {'B': 0, 'S': 0, 'C': 0, 'T': 0, 'MT': 0}
#     newCenterList = []
#     newDistance = []
#     for detection in detections:
#         class_name, confidence, (x, y, w, h), distance = detection
#         if class_name in PredDict.keys():
#             PredDict[class_name] += 1
#             newCenterList.append((int(x), int(y), class_name))
#             cv2.circle(frame, (int(x), int(y)), 3, (255, 255, 0), 3)
#             newDistance.append(distance)

#     print(PredDict)
#     #劃出區域
#     cv2.line(frame, (220, 0), (220, 640), (0, 0, 255), 1)
#     cv2.line(frame, (420, 0), (420, 640), (0, 0, 255), 1)
#     # 將新中心點與現有中心點比對
#     ObjList, objIndex = TrackObj(newCenterList, ObjList, objIndex, temp_storage, expiry_frames, newDistance)
    
#     print(ObjList)
#     print(objIndex)


#     #讀取速度
#     with open("ownspeed.txt","r") as f:
#         speed = f.read()
#     try:
#         speed = float(speed)
#     except:
#         speed = 0


#     #判斷危險
#     risk = riskrule(ObjList, speed)
#     risk_history.append(risk)
#     if len(risk_history) > 30:
#         risk_history.pop(0)
    
#     max_risks = calculate_max_risks(risk_history)
#     print(max_risks)
#     #輸出危險判定結果
#     mes = str(max_risks[0]) + str(max_risks[1]) + str(max_risks[2]) 
#     with open("mes/mes.txt","w") as f:
#         f.write(mes)


#     #紀錄資料
#     with open("account.txt","r") as f:
#         account = f.read()

#     current_time = datetime.datetime.now().strftime("%Y%m%d_%H%M%S%f")  # 使用微秒作為唯一標識
#     filename = f"db_buffer/{account}_{current_time}.txt"

#     with open(filename, "w") as f:
#         db_list = [account,current_time,speed,mes,ObjList,objIndex]
#         f.write(str(db_list))
#     '''
#     frame_queue.put(frame)  # 將幀加入佇列
    
#     if not is_writing:
#         is_writing = True
#         video_writer = cv2.VideoWriter("output.avi", fourcc, fps, (frame.shape[1], frame.shape[0]))
#         write_thread.start()  # 啟動影片寫入執行緒
#     '''
#     cv2.imshow('Inference', frame)
    
#     file_names = os.listdir(TARGET_folder)
#     num_files = len(file_names)
#     if num_files > 2:
#         Camera1_Number += 1
#         os.remove(TARGET)
    
#     TARGET = TARGET_folder + "/" + str(Camera1_Number) + '.jpg'
    
#     try:
#         cap = cv2.VideoCapture(TARGET)
#     except:
#         time.sleep(1)
    
#     key = cv2.waitKey(1)
#     if key == ord('q'):
#         break

# cap.release()
# frame_queue.put(None)  # 停止寫入影片的執行緒
# cv2.destroyAllWindows()
# is_writing = False
# write_thread.join()  # 等待寫入執行緒結束


def detection(img_bgr, speed):
    """
    參數
        img_bgr : numpy.ndarray           # 由 Gateway 送進來的單張影像 (BGR)
    回傳
        mes     : str                     # 三碼風險結果，如 '012'
    備註
        - 使用全域變數: objIndex、risk_history、ObjList、temp_storage
        - 仍會寫入 mes/mes.txt 以相容舊流程
    """
    global objIndex, risk_history, ObjList, temp_storage

    # --------- 影像偵測 ---------
    frame, detections = image_detection(
        img_bgr.copy(), network, class_names, class_colors, CONFTH
    )

    # Print detections without distance
    print_detections = [(d[0], d[1], d[2]) for d in detections]
    darknet.print_detections(print_detections)

    PredDict       = {'B': 0, 'S': 0, 'C': 0, 'T': 0, 'MT': 0}
    newCenterList  = []
    newDistance    = []

    for class_name, confidence, (x, y, w, h), distance in detections:
        if class_name in PredDict:
            PredDict[class_name] += 1
            newCenterList.append((int(x), int(y), class_name))
            cv2.circle(frame, (int(x), int(y)), 3, (255, 255, 0), 3)
            newDistance.append(distance)

    # print(PredDict)

    # 劃出左右區域線
    cv2.line(frame, (220, 0), (220, frame.shape[0]), (0, 0, 255), 1)
    cv2.line(frame, (420, 0), (420, frame.shape[0]), (0, 0, 255), 1)

    # --------- 追蹤 ---------
    ObjList, objIndex = TrackObj(
        newCenterList, ObjList, objIndex, temp_storage,
        expiry_frames, newDistance
    )
    # print(ObjList)
    # print(objIndex)

    # --------- 自車速度 ---------


    # --------- 風險計算 ---------
    risk = riskrule(ObjList, speed)
    risk_history.append(risk)
    if len(risk_history) > 30:
        risk_history.pop(0)

    max_risks = calculate_max_risks(risk_history)
    # print(max_risks)

    # 產生結果字串（右、中、左）
    mes = f"{max_risks[0]}{max_risks[1]}{max_risks[2]}"

    # --------- 輸出 mes.txt ---------
    # os.makedirs("mes", exist_ok=True)
    # with open("mes/mes.txt", "w") as f:
    #     f.write(mes)

    # --------- 紀錄 db_buffer ---------
    # try:
    #     with open("account.txt", "r") as f:
    #         account = f.read().strip()
    # except FileNotFoundError:
    #     account = "unknown"

    # now_str  = datetime.datetime.now().strftime("%Y%m%d_%H%M%S%f")
    # os.makedirs("db_buffer", exist_ok=True)
    # with open(f"db_buffer/{account}_{now_str}.txt", "w") as f:
    #     db_list = [account, now_str, speed, mes, ObjList, objIndex]
    #     f.write(str(db_list))

    # --------- （選擇性）即時顯示 ---------
    # 若伺服器是無螢幕環境，可將下兩行註解
    cv2.imshow('Inference', frame)
    cv2.waitKey(1)          # 不阻塞，僅刷新畫面

    key = cv2.waitKey(1) & 0xFF       # 只取低 8 位
    if key == ord('q'):
        EXIT_BY_KEY = True            # 宣告想離開

    return mes

# ------------------------- 客戶端處理 -------------------------
def handle_client(conn, addr):
    try:
        # ❶ 先收 4 byte 影像長度
        # len_buf = conn.recv(4)
        # if len(len_buf) < 4:
        #     return
        # img_len = struct.unpack("!I", len_buf)[0]

        ''' img_len(4 bytes) + img + speed(4 bytes) '''
        len_buf  = recvn(conn, 4)
        img_len  = struct.unpack("!I", len_buf)[0]

        img_bytes = recvn(conn, img_len)          # 影像
        speed_buf = recvn(conn, 4)                # 新增：速度
        speed_kph = struct.unpack("!f", speed_buf)[0]
        print(f"[Model] speed = {speed_kph:.1f} kph")

        # ❷ 持續收直到拿到完整影像
        data = b""
        while len(data) < img_len:
            chunk = conn.recv(img_len - len(data))
            if not chunk:
                break
            data += chunk

        # ❸ 轉成 OpenCV 影像 (如暫不需要可跳過)
        img = None
        if data:
            nparr = np.frombuffer(data, np.uint8)
            img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

        # ❹ 呼叫偵測
        mes = detection(img)
        mes_bytes = mes.encode()

        # ❺ 回傳結果：4 byte 長度 + 資料
        conn.sendall(struct.pack("!I", len(mes_bytes)) + mes_bytes)

    finally:
        conn.close()

def recvn(sock, n):
    buf = bytearray()
    while len(buf) < n:
        chunk = sock.recv(n - len(buf))
        if not chunk:
            raise ConnectionError("socket closed while receiving")
        buf.extend(chunk)
    return bytes(buf)

# ------------------------- 主迴圈 -------------------------
def start_server():
    global is_writing
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server:
        server.bind((HOST, LISTEN_PORT))
        server.listen()
        server.settimeout(0.5)                     # ① 每 0.5 s 醒一次
        print(f"[INFO] Listening on {HOST}:{LISTEN_PORT} ...")

        while True:
            # ② 嘗試 accept；若逾時則檢查退出旗標
            try:
                conn, addr = server.accept()
            except socket.timeout:
                if EXIT_BY_KEY:                    # ③ 已按下 q
                    print("[INFO] Exit requested by 'q'. Shutting down.")
                    break
                continue                           # 繼續等待下一輪
            except OSError:
                break                              # server socket 被關閉

            # ④ 正常取得新連線，開執行緒處理
            threading.Thread(
                target=handle_client, args=(conn, addr), daemon=True
            ).start()
    cv2.destroyAllWindows()
    is_writing = False



if __name__ == '__main__':
    pre_trained()
    start_server()