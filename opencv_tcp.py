import subprocess
import logging
from control import *
import time
import datetime
from Constants import *
import cv2
import numpy as np
import os
import fcntl
import mmap
import struct
import array
import socket
import threading

cv2.ocl.setUseOpenCL(False)

received_message = ""
message_lock = threading.Lock()

def draw_rectangle(image, top_left, bottom_right, text, is_finger_inside):
    color = (0, 0, 255) if is_finger_inside else (0, 255, 0)  
    cv2.rectangle(image, top_left, bottom_right, color, 2)

    center_x = (top_left[0] + bottom_right[0]) // 2
    center_y = (top_left[1] + bottom_right[1]) // 2
    
    font = cv2.FONT_HERSHEY_SIMPLEX
    font_scale = 1
    font_thickness = 2
    text_size = cv2.getTextSize(text, font, font_scale, font_thickness)[0]
    
    text_x = center_x - text_size[0] // 2
    text_y = center_y + text_size[1] // 2

    cv2.putText(image, text, (text_x, text_y), font, font_scale, (255, 255, 255), font_thickness)

    return image

def draw_grid_of_rectangles(image, rows=2, cols=5):
    img_height, img_width , _= image.shape

    rect_width = int(0.5*img_width // (cols + 1))  
    rect_height = int(0.5*img_height // (rows + 2))  
    spacing_x = rect_width // 5
    spacing_y = rect_height // 4

    idx = 1

    for row in range(rows):
        for col in range(cols):
            # 사각형의 좌측 상단과 우측 하단 좌표 계산
            top_left_x = 300+(col + 1) * spacing_x + col * rect_width
            top_left_y = 500+(row + 1) * spacing_y + row * rect_height
            bottom_right_x = top_left_x + rect_width
            bottom_right_y = top_left_y + rect_height
            

            if finger_pos is not None:
                # 손가락 끝 좌표가 사각형 내부에 있는지 확인
                is_finger_inside = is_finger_in_rectangle(finger_pos, (top_left_x, top_left_y), (bottom_right_x, bottom_right_y))
            else:
                is_finger_inside = False

            # 사각형 그리기 (손가락이 사각형 안에 있으면 색상을 변경)
            image = draw_rectangle(image, (top_left_x, top_left_y), (bottom_right_x, bottom_right_y), str(idx), is_finger_inside)
            idx += 1
    return image

def tcp_server():
    global received_message
    host = '0.0.0.0'  # Server hostname
    port = 12345  # Port number to use

    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.bind((host, port))
    server_socket.listen(1)

    print("Server is waiting on %s:%s..." % (host, port))

    while True:
        client_socket, addr = server_socket.accept()
        print("Client connected from %s" % str(addr))

        data = client_socket.recv(1024).decode()
        print("Message received from client: %s" % data)

        with message_lock:
            received_message = data.decode()

        response = "Response message from server"
        client_socket.send(response)

        client_socket.close()

def run_i2c_commands():
    commands = [
        "i2cset -y 2 0x1b 0x0b 0x00 0x00 0x00 0x00 i",
        "i2cset -y 2 0x1b 0x0c 0x00 0x00 0x00 0x09 i"
    ]
    for cmd in commands:
        try:
            process = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            stdout, stderr = process.communicate()
            if process.returncode == 0:
                print("Successfully executed: {}".format(cmd))
            else:
                print("Error executing command: {}".format(cmd))
                print("Error details: {}".format(stderr))
        except Exception as e:
            print("Exception while executing command: {}".format(cmd))
            print("Exception details: {}".format(str(e)))

def draw_grid_of_rectangles(image, rows=2, cols=5):
    height, width = image.shape[:2]

    rect_width = int(0.5*width // (cols + 1))
    rect_height = int(0.5*height // (rows + 2))
    spacing_x = rect_width // 5
    spacing_y = rect_height // 4

    idx = 1

    for row in range(rows):
        for col in range(cols):
            top_left_x = 300+(col + 1) * spacing_x + col * rect_width
            top_left_y = 500+(row + 1) * spacing_y + row * rect_height
            bottom_right_x = top_left_x + rect_width
            bottom_right_y = top_left_y + rect_height

            cv2.rectangle(image, (top_left_x, top_left_y), (bottom_right_x, bottom_right_y), (0, 255, 0), 2)
            
            font = cv2.FONT_HERSHEY_SIMPLEX
            font_scale = 1
            font_thickness = 2
            text = str(idx)
            text_size = cv2.getTextSize(text, font, font_scale, font_thickness)[0]
            
            text_x = top_left_x + (rect_width - text_size[0]) // 2
            text_y = top_left_y + (rect_height + text_size[1]) // 2

            cv2.putText(image, text, (text_x, text_y), font, font_scale, (255, 255, 255), font_thickness)
            
            idx += 1

    return image

def write_to_framebuffer(image):
    try:
        with open('/dev/fb0', 'r+b') as f:
            # Get variable screen information
            screen_info = array.array('H', [0] * 32)
            fcntl.ioctl(f.fileno(), 0x4600, screen_info)
            xres, yres, xres_virtual, yres_virtual, bits_per_pixel = screen_info[:5]

            # Get fixed screen information
            fix_info = array.array('c', ' ' * 68)
            fcntl.ioctl(f.fileno(), 0x4602, fix_info)
            line_length = struct.unpack('I', fix_info[32:36])[0]

            print("Framebuffer info: xres={}, yres={}, bits_per_pixel={}".format(xres, yres, bits_per_pixel))

            if xres <= 0 or yres <= 0:
                print("Invalid framebuffer resolution. Using default 720x480.")
                xres, yres = 720, 480

            # Ensure the image is in the correct format (RGB565)
            if image.shape[2] == 3:  # If image is BGR
                image = cv2.cvtColor(image, cv2.COLOR_BGR2BGR565)
            
            # Ensure the image is the correct size
            if image.shape[:2] != (yres, xres):
                image = cv2.resize(image, (xres, yres))
            
            # Write the image data to the framebuffer
            f.write(image.tostring())
            f.flush()

    except Exception as e:
        print("Error writing to framebuffer: {}".format(str(e)))

def opencv_display():
    global received_message
    width, height = 720, 480
    frame_count = 0
    duration = 3600
    display_click = False

    start_time = time.time()
    while time.time() - start_time < duration:
        try:
            # Create a black background
            img = np.zeros((height, width, 3), dtype=np.uint8)

            # Draw a moving circle
            center = (int(width/2 + 100*np.sin(frame_count*0.05)), int(height/2))
            cv2.circle(img, center, 50, (0, 0, 255), -1)

            # Draw a rectangle
            cv2.rectangle(img, (100, 100), (200, 200), (0, 255, 0), 3)

            # Draw a triangle
            pts = np.array([[300, 100], [200, 300], [400, 300]], np.int32)
            cv2.fillPoly(img, [pts], (255, 255, 0))

            # Draw some text
            font = cv2.FONT_HERSHEY_SIMPLEX
            cv2.putText(img, 'DLP2000 TCPTest', (10, 30), font, 1, (255, 255, 255), 2, cv2.LINE_AA)

            # Draw grid of rectangles
            img = draw_grid_of_rectangles(img)

            with message_lock:
                if "CLICK" in received_message:
                    display_click = True
                    received_message = ""
                else:
                    display_click = False
                    received_message = ""

            if display_click:
                cv2.putText(img, 'Click', (width//2, height//2), font, 1, (255, 255, 255), 2, cv2.LINE_AA)
                print("Displaying 'Click' on screen")
            else:
                print("Not displaying 'Click' on screen")

            # Write the image to the framebuffer
            write_to_framebuffer(img)

            # Save image every minute
            if frame_count % 3600 == 0:  
                cv2.imwrite('dlp2000_output_{}.png'.format(frame_count//3600), img)
                print("Image saved at {} minutes.".format(frame_count//3600))
                received_message = ""

            frame_count += 1

            # Add a small delay to control frame rate
            time.sleep(0.016)  # Approximately 60 FPS
        except Exception as e:
            print("Error in opencv_display: {}".format(str(e)))
            break

    cv2.imwrite('dlp2000_output_final.png', img)
    print("Final image has been saved.")

    return "OpenCV images displayed for 1 hour and saved periodically. (Pass/Fail/Stop)"

def initialize_display():
    print("Initializing display...")
    run_i2c_commands()
    time.sleep(1)
    DPP2607_Write_SystemReset()
    time.sleep(2)
    DPP2607_Write_VideoSourceSelection(SourceSel.EXTERNAL_VIDEO_PARALLEL_I_F_)
    DPP2607_Write_VideoPixelFormat(RGB888_24_BIT)
    DPP2607_Write_VideoResolution(Resolution.NHD_LANDSCAPE)
    time.sleep(1)
    run_i2c_commands()

def main():
    Test_name = 'OpenCV DLP2000 TCP Test'
    
    # Setup the Test name
    datalog = DataLog(LogDir, Test_name)

    # General setup
    logging.getLogger().setLevel(logging.DEBUG)  
    print("Opening DLP2000...")
    DPP2607_Open()
    print("Setting slave address...")
    DPP2607_SetSlaveAddr(SlaveAddr)
    print("Setting IO debug...")
    DPP2607_SetIODebug(IODebug)

    print("Initializing DLP2000...")
    time.sleep(5) 

    try:
        initialize_display()

        print("Running TCP server...")
        tcp_thread = threading.Thread(target=tcp_server)
        tcp_thread.daemon = True
        tcp_thread.start()
        
        print("Running OpenCV display...")
        result = opencv_display()
        
        print("Display result: {}".format(result))
        
        datalog.add_col('Test name', Test_name)
        datalog.add_col('End Time', ' ' + str(datetime.datetime.now()))
        datalog.add_col('Result', result)
        datalog.add_col('P/F Result', "Pass" if "Pass" in result else "Fail")
        datalog.log()
    except Exception as e:
        print("Test failed Exception: {}".format(str(e)))
        datalogConstants(datalog)
        datalog.add_col('Test name', Test_name)
        datalog.add_col('End Time', ' ' + str(datetime.datetime.now()))
        datalog.add_col('Result', "Test Fail EXCEPTION")        
        datalog.add_col('P/F Result', "Fail")
        datalog.log()
    finally:
        # Cleanup
        print("Cleaning up...")
        run_i2c_commands()  # Run I2C commands one last time
        DPP2607_Close()
        datalog.close()

if __name__ == "__main__":
    main()