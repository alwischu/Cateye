import io
import time
import os
import picamera
import logging
import socketserver
from threading import Condition, Thread
from http import server
import RPi.GPIO as GPIO
from datetime import datetime
import mysql.connector as mariadb

#db
mariadb_connection = mariadb.connect(user='admin', password='hammer99', database='cateye')
cursor = mariadb_connection.cursor()

#folder save path
save_path_img = '/home/pi/mocam/images/'
save_path_vid = '/home/pi/mocam/videos/'

    #video length
vid_len = 6

#setup pin
GPIO.setmode(GPIO.BCM)
pir = 4
GPIO.setup(pir, GPIO.IN)

res_width = 1296
res_height = 730

PAGE="""\
<html>
<body style="background-color:rgb(50,50,50);">
<head>
<title>CatEye</title>
</head>
<body>
<h1 style="color:white;">CatEye</h1>
<h3 style ="color:rgb(225,225,225);">Watch cats poop and get away with shit.</h3>
<img src="stream.mjpg" width="640" height="480" />
</body>
</html>
"""

class StreamingOutput(object):
    def __init__(self):
        self.frame = None
        self.buffer = io.BytesIO()
        self.condition = Condition()

    def write(self, buf):
        if buf.startswith(b'\xff\xd8'):
            # New frame, copy the existing buffer's content and notify all
            # clients it's available
            self.buffer.truncate()
            with self.condition:
                self.frame = self.buffer.getvalue()
                self.condition.notify_all()
            self.buffer.seek(0)
        return self.buffer.write(buf)

class StreamingHandler(server.BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/':
            self.send_response(301)
            self.send_header('Location', '/index.html')
            self.end_headers()
        elif self.path == '/index.html':
            content = PAGE.encode('utf-8')
            self.send_response(200)
            self.send_header('Content-Type', 'text/html')
            self.send_header('Content-Length', len(content))
            self.end_headers()
            self.wfile.write(content)
        elif self.path == '/stream.mjpg':
            self.send_response(200)
            self.send_header('Age', 0)
            self.send_header('Cache-Control', 'no-cache, private')
            self.send_header('Pragma', 'no-cache')
            self.send_header('Content-Type', 'multipart/x-mixed-replace; boundary=FRAME')
            self.end_headers()
            try:
                while True:
                    with output.condition:
                        output.condition.wait()
                        frame = output.frame
                    self.wfile.write(b'--FRAME\r\n')
                    self.send_header('Content-Type', 'image/jpeg')
                    self.send_header('Content-Length', len(frame))
                    self.end_headers()
                    self.wfile.write(frame)
                    self.wfile.write(b'\r\n')
            except Exception as e:
                logging.warning(
                    'Removed streaming client %s: %s',
                    self.client_address, str(e))
        else:
            self.send_error(404)
            self.end_headers()

class StreamingServer(socketserver.ThreadingMixIn, server.HTTPServer):
    allow_reuse_address = True
    daemon_threads = True

#prints into a logfile
def logEntry(msg):
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    logfile = open('logfile.txt', 'a')
    print("{} : {}\n".format(stamp,msg))
    logfile.write("{} : {}\n".format(stamp,msg))
    logfile.close()
    

    #output = StreamingOutput()
   # camera.start_recording(output, format='mjpeg')
try:
    address = ('0.0.0.0', 8000)
    server = StreamingServer(address, StreamingHandler)
    server_thread = Thread(target=server.serve_forever)
    output = StreamingOutput()
    camera = picamera.PiCamera(resolution='640x480', framerate=24)
    time.sleep(0.1)
    camera.start_recording(output, splitter_port=1, format='mjpeg')
    logEntry("Stream started")
    server_thread.start()
    logEntry("Recording started")
    while True:
        record_true = False
        img_true = False
        if GPIO.input(pir):
                #get timestamp
            t_start = datetime.now()
            t_name = '%04d-%02d-%02d-%02d:%02d%02d' % (t_start.year, t_start.month, t_start.day, t_start.hour, t_start.minute, t_start.second)
            logEntry("Motion! {}".format(t_start))
                #make vid_name
            vid_name = '{}vid-{}.h264'.format(save_path_vid,t_name)
            img_name = '{}img-{}.jpg'.format(save_path_img,t_name)
            camera.capture(img_name, splitter_port=3)
            img_true = True
            camera.start_recording(vid_name, splitter_port=2, resize=(res_width, res_height))
            camera.wait_recording(vid_len)
                
            while GPIO.input(pir):
                camera.wait_recording(vid_len)
            
            camera.stop_recording(splitter_port=2)
            t_end = datetime.now()
            logEntry("recording stopped.")
            logEntry("camera off")
            record_true = True
            
                    #get saved h264 file size
            vid_size = os.path.getsize(vid_name)
            duration = (t_end - t_start).total_seconds()
            upload_date = datetime.now()
            err_found = False
            
            cursor.execute("INSERT INTO catdb (res_width, res_height, record_true, t_start, t_name, t_end, vid_size, duration, upload_date, err_found) VALUES(%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                           (res_width, res_height, record_true, t_start, t_name, t_end, vid_size, duration, upload_date, err_found))
            mariadb_connection.commit()
            logEntry("Data inserted at {} for {}-second video. ".format(t_start, duration))
    #erro handling            
except picamera.PiCameraError as error:
    logEntry('PiCameraError: {}'.format(error))
    err_found = True
except ValueError as error:
    logEntry("ValueError: {}".format(error))
    err_found = True
except mariadb.Error as error:
    logEntry("DB error: {}".format(error))
    mariadb_connection.rollback()
            
    #server.serve_forever()
finally:
    logEntry("stream stopped")
    camera.stop_recording()
    camera.close()
    mariadb_connection.close()