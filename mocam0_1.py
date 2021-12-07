#!/usr/bin/python
import mysql.connector as mariadb
import RPi.GPIO as GPIO
import time
import picamera
from datetime import datetime
import os


mariadb_connection = mariadb.connect(user='wordpress', password='hammer99', database='wordpress')
cursor = mariadb_connection.cursor()


#prints into a logfile
def logEntry(msg):
    stamp = str(datetime.now)
    logfile = open('logfile.txt', 'a')
    logfile.write("{} : {}\n".format(stamp,msg))
    logfile.close()

    #video length
vid_len = 6

#setup pin
GPIO.setmode(GPIO.BCM)
pir = 4
GPIO.setup(pir, GPIO.IN)


res_width = 1920
res_height = 1080

#from signal import pause
while True:
    if GPIO.input(pir):
        
        #get timestamp
        t_start = datetime.now()
        print("Motion! {}".format(t_start))
        logEntry("Motion! {}".format(t_start))
        #make vid_name
        vid_name = 'vid-%04d-%02d-%02d-%02d:%02d%02d.h264' % (t_start.year, t_start.month, t_start.day, t_start.hour, t_start.minute, t_start.second)
        img_name = 'img-%04d-%02d-%02d-%02d:%02d%02d.jpg' % (t_start.year, t_start.month, t_start.day, t_start.hour, t_start.minute, t_start.second)
        
#setup camera
        camera = picamera.PiCamera()
        camera.resolution = (res_width, res_height)
        time.sleep(0.1)
        
        #record camera
        try:
            camera.capture(img_name)
            camera.start_recording(vid_name)
            camera.wait_recording(vid_len)
            #keeps recording open while
            while GPIO.input(pir):
                camera.wait_recording(vid_len)
            
            camera.stop_recording()
            t_end = datetime.now()
            print("recording stopped.")
            logEntry("recording stopped.")
            camera.close()
            print("camera off")
            
            #get saved h264 file size
            vid_size = os.path.getsize(vid_name)
            
        except picamera.PiCameraError as error:
            print('PiCameraError: {}'.format(error))
            logEntry('PiCameraError: {}'.format(error))
        except ValueError as error:
            print("ValueError: {}".format(error))
            logEntry("ValueError: {}".format(error))
        
        duration = (t_end - t_start).total_seconds()
        upload_date = datetime.now()

        try:
            cursor.execute("INSERT INTO wordpress (res_width, res_height, img_name, vid_name, t_start, t_end, upload_date, duration, vid_size) VALUES(%s, %s, %s, %s, %s, %s, %s, %s, %s)", (res_width, res_height, 
            img_name, vid_name, t_start, t_end, upload_date, duration, vid_size))
            mariadb_connection.commit()
            print("Data inserted at {} for {}-second video. ".format(t_start, duration))
            logEntry("Data inserted at {} for {}-second video. ".format(t_start, duration))
        except mariadb.Error as error:
            print("DB error: {}".format(error))
            logEntry("DB error: {}".format(error))
    time.sleep(1)

