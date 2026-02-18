# face_recognition_module.py
import face_recognition
import cv2
import numpy as np
import pickle
from picamera2 import Picamera2
from datetime import datetime
import os

class FaceRecognitionSystem:
    def __init__(self):
        """Initialize camera and face recognition system"""
        self.picam2 = Picamera2()
        config = self.picam2.create_preview_configuration(
            main={"size": (640, 480)}
        )
        self.picam2.configure(config)
        self.picam2.start()
        
        # Create directory for face images
        if not os.path.exists('face_images'):
            os.makedirs('face_images')
    
    def capture_image(self, filename=None):
        """Capture image from camera"""
        if filename is None:
            filename = f"face_images/capture_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
        
        # Capture frame
        frame = self.picam2.capture_array()
        
        # Convert from RGB to BGR for OpenCV
        frame_bgr = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
        
        # Save image
        cv2.imwrite(filename, frame_bgr)
        print(f"Image saved: {filename}")
        
        return filename, frame
    
    def detect_and_encode_face(self, image_array):
        """Detect face in image and return encoding"""
        # Convert to RGB if needed
        rgb_image = cv2.cvtColor(image_array, cv2.COLOR_BGR2RGB) if len(image_array.shape) == 3 else image_array
        
        # Detect faces
        face_locations = face_recognition.face_locations(rgb_image)
        
        if len(face_locations) == 0:
            print("No face detected!")
            return None
        
        if len(face_locations) > 1:
            print("Multiple faces detected! Please ensure only one person.")
            return None
        
        # Get face encoding
        face_encodings = face_recognition.face_encodings(rgb_image, face_locations)
        
        if len(face_encodings) > 0:
            print("Face detected and encoded successfully!")
            return face_encodings[0]
        
        return None
    
    def register_new_face(self):
        """Capture and encode face for new user registration"""
        print("Please look at the camera...")
        filename, frame = self.capture_image()
        
        encoding = self.detect_and_encode_face(frame)
        
        if encoding is not None:
            return encoding, filename
        
        return None, None
    
    def compare_faces(self, known_encoding, tolerance=0.6):
        """Capture current face and compare with known encoding"""
        print("Please look at the camera for verification...")
        filename, frame = self.capture_image()
        
        current_encoding = self.detect_and_encode_face(frame)
        
        if current_encoding is None:
            return False, filename
        
        # Compare faces
        matches = face_recognition.compare_faces([known_encoding], current_encoding, tolerance=tolerance)
        
        # Calculate face distance
        face_distance = face_recognition.face_distance([known_encoding], current_encoding)
        
        print(f"Face match: {matches[0]}, Distance: {face_distance[0]:.2f}")
        
        return matches[0], filename
    
    def cleanup(self):
        """Stop camera"""
        self.picam2.stop()
