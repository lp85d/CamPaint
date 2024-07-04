import cv2
import mediapipe as mp
import numpy as np
import base64
import io
import socket
import time
from flask import Flask, request, render_template
from flask_socketio import SocketIO, emit
from PIL import Image
import os
from datetime import datetime

app = Flask(__name__, template_folder='templates')
app.config['SECRET_KEY'] = 'secret!'
socketio = SocketIO(app, cors_allowed_origins="*")

mp_hands = mp.solutions.hands
hands = mp_hands.Hands()

video_folder = 'recordings/'
video_writers = {}

def is_local_ip(ip):
    local_ips = socket.gethostbyname_ex(socket.gethostname())[2]
    if ip.startswith('192.168.') or ip.startswith('10.') or ip.startswith('172.') or ip == '127.0.0.1' or ip in local_ips:
        return True
    return False

def create_directory(directory):
    if not os.path.exists(directory):
        os.makedirs(directory)

@app.route('/')
def index():
    return render_template('index.html')

@socketio.on('connect')
def handle_connect():
    client_ip = request.remote_addr
    print(f"Client connected: {client_ip}")

    create_directory(video_folder)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    if is_local_ip(client_ip):
        filename = f'{video_folder}local_{client_ip}_{timestamp}.avi'
        fourcc = cv2.VideoWriter_fourcc(*'XVID')
        video_writers[client_ip] = cv2.VideoWriter(filename, fourcc, 10.0, (640, 480))
        print(f"IP is local, saving video to {filename}")
    else:
        filename = f'{video_folder}external_{client_ip}_{timestamp}.avi'
        fourcc = cv2.VideoWriter_fourcc(*'XVID')
        video_writers[client_ip] = cv2.VideoWriter(filename, fourcc, 5.0, (640, 480))
        print(f"IP is external, saving video to {filename}")

@socketio.on('image')
def handle_image(data_image):
    start_time = time.time()
    sbuf = io.BytesIO()
    sbuf.write(base64.b64decode(data_image))
    pimg = Image.open(sbuf)
    frame = cv2.cvtColor(np.array(pimg), cv2.COLOR_RGB2BGR)

    frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    results = hands.process(frame_rgb)

    if results.multi_hand_landmarks:
        for hand_landmarks in results.multi_hand_landmarks:
            mp.solutions.drawing_utils.draw_landmarks(
                frame, hand_landmarks, mp_hands.HAND_CONNECTIONS)

            # Получение координат указательного пальца (т.н. Landmark #8)
            index_finger_tip = hand_landmarks.landmark[8]
            height, width, _ = frame.shape
            index_finger_tip_x = int(index_finger_tip.x * width)
            index_finger_tip_y = int(index_finger_tip.y * height)

            # Добавление круга на место указательного пальца
            cv2.circle(frame, (index_finger_tip_x, index_finger_tip_y), 10, (0, 255, 0), -1)

            # Отправка координат для управления карандашом
            emit('finger_position', {'x': index_finger_tip_x, 'y': index_finger_tip_y})

    client_ip = request.remote_addr

    if client_ip in video_writers:
        video_writers[client_ip].write(frame)

    _, buffer = cv2.imencode('.jpg', frame, [int(cv2.IMWRITE_JPEG_QUALITY), 50])
    encoded_image = base64.b64encode(buffer).decode('utf-8')

    emit('brush_preview', {'image': 'data:image/jpeg;base64,' + encoded_image})

@socketio.on('disconnect')
def handle_disconnect():
    client_ip = request.remote_addr
    print(f"Client disconnected: {client_ip}")

    if client_ip in video_writers:
        video_writers[client_ip].release()
        del video_writers[client_ip]

if __name__ == '__main__':
    ssl_context = (
        'C:/Certbot/archive/scladchina.ru/fullchain1.pem',
        'C:/Certbot/archive/scladchina.ru/privkey1.pem'
    )
    socketio.run(app, host='0.0.0.0', port=443, ssl_context=ssl_context)
