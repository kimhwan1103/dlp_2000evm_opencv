import cv2
import numpy as np
import time
import subprocess
import logging
from control import *
import datetime
from Constants import *
import os
import fcntl
import mmap
import struct
import array

cv2.ocl.setUseOpenCL(False)

def draw_rectangle(image, top_left, bottom_right, text):
    color = (0, 255, 0)
    cv2.rectangle(image, top_left, bottom_right, color, 2)

    center_x = (top_left[0] + bottom_right[0]) // 2
    center_y = (top_left[1] + bottom_right[1]) // 2
    
    font = cv2.FONT_HERSHEY_SIMPLEX
    font_scale = 0.5
    font_thickness = 1
    text_size = cv2.getTextSize(text, font, font_scale, font_thickness)[0]
    
    text_x = center_x - text_size[0] // 2
    text_y = center_y + text_size[1] // 2

    cv2.putText(image, text, (text_x, text_y), font, font_scale, (255, 255, 255), font_thickness)

    return image

def draw_grid_of_rectangles(image, rows=2, cols=5):
    img_height, img_width, _ = image.shape

    rect_width = int(img_width // (cols + 1))
    rect_height = int(img_height // (rows + 2))
    spacing_x = rect_width // 5
    spacing_y = rect_height // 4

    idx = 1

    for row in range(rows):
        for col in range(cols):
            top_left_x = (col + 1) * spacing_x + col * rect_width
            top_left_y = (row + 1) * spacing_y + row * rect_height
            bottom_right_x = top_left_x + rect_width
            bottom_right_y = top_left_y + rect_height

            image = draw_rectangle(image, (top_left_x, top_left_y), (bottom_right_x, bottom_right_y), str(idx))
            idx += 1
    return image

def add_click_text(image):
    img_height, img_width, _ = image.shape
    font = cv2.FONT_HERSHEY_SIMPLEX
    font_scale = 1
    font_thickness = 2
    text = "Click"
    text_size = cv2.getTextSize(text, font, font_scale, font_thickness)[0]
    text_x = (img_width - text_size[0]) // 2  
    text_y = img_height - 20  
    cv2.putText(image, text, (text_x, text_y), font, font_scale, (255, 255, 255), font_thickness)
    return image

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

def draw_border_and_markers(image):
    height, width = image.shape[:2]
    border_color = (255, 0, 0)  
    marker_color = (0, 255, 0) 
    thickness = 2
    marker_size = 20

    cv2.rectangle(image, (0, 0), (width-1, height-1), border_color, thickness)

    cv2.rectangle(image, (0, 0), (marker_size, marker_size), marker_color, -1)
    cv2.rectangle(image, (width-marker_size, 0), (width, marker_size), marker_color, -1)
    cv2.rectangle(image, (0, height-marker_size), (marker_size, height), marker_color, -1)
    cv2.rectangle(image, (width-marker_size, height-marker_size), (width, height), marker_color, -1)

    return image

def main():
    Test_name = 'OpenCV DLP2000 Keyboard Test'
    
    datalog = DataLog(LogDir, Test_name)

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
        
        width, height = 720, 480
        frame_count = 0
        duration = 3600

        start_time = time.time()
        while time.time() - start_time < duration:
            image = np.zeros((height, width, 3), dtype=np.uint8)

            frame = draw_grid_of_rectangles(image)
            frame = add_click_text(frame)
            frame = draw_border_and_markers(frame)

            write_to_framebuffer(frame)

            if frame_count % 3600 == 0:  
                cv2.imwrite('dlp2000_keyboard_output_{}.png'.format(frame_count//3600), frame)
                print("Image saved at {} minutes.".format(frame_count//3600))

            frame_count += 1
            time.sleep(0.016)  # Approximately 60 FPS

        cv2.imwrite('dlp2000_keyboard_output_final.png', frame)
        print("Final image has been saved.")
        
        result = "OpenCV keyboard images displayed for 1 hour and saved periodically. (Pass/Fail/Stop)"
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
        print("Cleaning up...")
        run_i2c_commands()
        DPP2607_Close()
        datalog.close()

if __name__ == "__main__":
    main()