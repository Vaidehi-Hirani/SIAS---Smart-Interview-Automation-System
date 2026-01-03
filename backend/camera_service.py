import cv2
import threading
import time
import datetime

class CameraMonitor:
    def __init__(self, callback_on_motion, camera_id=0):
        self.camera_id = camera_id
        self.callback = callback_on_motion
        self.running = False
        self.thread = None
        self.cap = None
        self.last_motion_time = 0

    def start(self):
        if self.running:
            return
        self.running = True
        self.thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.thread.start()

    def stop(self):
        self.running = False
        if self.thread:
            self.thread.join()
    
    def set_camera_id(self, new_id):
        self.stop()
        try:
            self.camera_id = int(new_id)
        except ValueError:
            pass
        self.start()

    def _monitor_loop(self):
        # Open camera
        self.cap = cv2.VideoCapture(self.camera_id)
        if not self.cap.isOpened():
            print(f"Error: Could not open camera {self.camera_id}. Retrying in 5s...")
            time.sleep(5)
            # Simple retry loop logic or just exit
            if self.running:
                self._monitor_loop()
            return

        print(f"Camera {self.camera_id} started for presence detection.")
        
        # Read first frame
        ret, frame1 = self.cap.read()
        ret, frame2 = self.cap.read()
        
        while self.running and self.cap.isOpened():
            # Basic Motion Detection using Frame Differencing
            diff = cv2.absdiff(frame1, frame2)
            gray = cv2.cvtColor(diff, cv2.COLOR_BGR2GRAY)
            blur = cv2.GaussianBlur(gray, (5, 5), 0)
            _, thresh = cv2.threshold(blur, 20, 255, cv2.THRESH_BINARY)
            dilated = cv2.dilate(thresh, None, iterations=3)
            contours, _ = cv2.findContours(dilated, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
            
            motion_detected = False
            for contour in contours:
                if cv2.contourArea(contour) < 900: # Sensitivity threshold
                    continue
                motion_detected = True
                break
            
            if motion_detected:
                # Debounce: limit updates to once every few seconds
                now = time.time()
                if now - self.last_motion_time > 2:
                    self.callback()
                    self.last_motion_time = now
            
            frame1 = frame2
            ret, frame2 = self.cap.read()
            
            if not ret:
                break
                
            time.sleep(0.1) # limit FPS to save CPU
            
        self.cap.release()
        print("Camera monitor stopped.")
