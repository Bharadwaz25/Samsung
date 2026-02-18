from flask import Flask, render_template, request, jsonify, Response
import sqlite3
from datetime import datetime, timedelta
import pickle
import cv2
import face_recognition
from rfid_module import RFIDReader
from face_recognition_module import FaceRecognitionSystem
import threading
import time

app = Flask(__name__)

lms_instance = None
operation_status = {"status": "idle", "message": "System Ready"}

class LibraryManagementSystem:
    def __init__(self):
        self.db_name = 'library_management.db'
        self.rfid_reader = RFIDReader()
        self.face_system = FaceRecognitionSystem()
    
    def get_connection(self):
        return sqlite3.connect(self.db_name)
    
    def register_book(self, title, author, isbn, category):
        global operation_status
        operation_status = {"status": "reading_rfid", "message": "Place book on RFID reader..."}
        
        rfid_tag, _ = self.rfid_reader.read_rfid()
        if not rfid_tag:
            operation_status = {"status": "error", "message": "Failed to read RFID!"}
            return
        
        self.rfid_reader.write_rfid(f"{title}|{author}")
        
        conn = self.get_connection()
        cur = conn.cursor()
        try:
            cur.execute('INSERT INTO books (rfid_tag, title, author, isbn, category) VALUES (?, ?, ?, ?, ?)',
                       (rfid_tag, title, author, isbn, category))
            conn.commit()
            operation_status = {"status": "success", "message": f"Book registered! ID: {cur.lastrowid}"}
        except sqlite3.IntegrityError:
            operation_status = {"status": "error", "message": "RFID already registered!"}
        finally:
            conn.close()
    
    def register_user(self, name, email, phone):
        global operation_status
        try:
            operation_status = {"status": "capturing_face", "message": "Look at camera..."}
            print(f"Registering user: {name}")
            
            time.sleep(2)
            
            # Capture image
            print("Capturing image...")
            frame_array = self.face_system.picam2.capture_array()
            
            # Convert RGB to BGR for face_recognition
            frame_rgb = cv2.cvtColor(frame_array, cv2.COLOR_BGR2RGB)
            
            # Detect faces
            print("Detecting faces...")
            face_locations = face_recognition.face_locations(frame_rgb)
            print(f"Found {len(face_locations)} faces")
            
            if len(face_locations) == 0:
                operation_status = {"status": "error", "message": "No face detected!"}
                print("No face detected!")
                time.sleep(3)
                return
            
            if len(face_locations) > 1:
                operation_status = {"status": "error", "message": "Multiple faces detected!"}
                print("Multiple faces detected!")
                time.sleep(3)
                return
            
            # Get face encoding
            print("Encoding face...")
            face_encodings = face_recognition.face_encodings(frame_rgb, face_locations)
            
            if not face_encodings:
                operation_status = {"status": "error", "message": "Failed to encode face!"}
                print("Failed to encode face!")
                time.sleep(3)
                return
            
            encoding = face_encodings[0]
            print("Face encoded successfully!")
            
            conn = self.get_connection()
            cur = conn.cursor()
            try:
                cur.execute('INSERT INTO users (name, email, phone, face_encoding) VALUES (?, ?, ?, ?)',
                           (name, email, phone, pickle.dumps(encoding)))
                conn.commit()
                operation_status = {"status": "success", "message": f"User {name} registered!"}
                print(f"User {name} registered successfully!")
                time.sleep(3)
            except sqlite3.IntegrityError:
                operation_status = {"status": "error", "message": "Email exists!"}
                print("Email already exists!")
                time.sleep(3)
            finally:
                conn.close()
        except Exception as e:
            operation_status = {"status": "error", "message": f"Error: {str(e)}"}
            print(f"Registration error: {e}")
            time.sleep(3)
    
    def issue_book(self):
        global operation_status
        try:
            operation_status = {"status": "reading_rfid", "message": "Reading RFID..."}
            print("Issue Book: Reading RFID...")
            
            rfid_tag, _ = self.rfid_reader.read_rfid()
            if not rfid_tag:
                operation_status = {"status": "error", "message": "RFID read failed!"}
                return
            
            conn = self.get_connection()
            cur = conn.cursor()
            cur.execute('SELECT book_id, title, status FROM books WHERE rfid_tag=?', (rfid_tag,))
            book = cur.fetchone()
            
            if not book or book[2] != 'available':
                operation_status = {"status": "error", "message": "Book unavailable!"}
                conn.close()
                return
            
            print(f"Book found: {book[1]}")
            
            operation_status = {"status": "identifying", "message": "Look at camera..."}
            print("Identifying user...")
            time.sleep(2)
            
            # Capture and identify
            frame_array = self.face_system.picam2.capture_array()
            frame_rgb = cv2.cvtColor(frame_array, cv2.COLOR_BGR2RGB)
            
            face_locations = face_recognition.face_locations(frame_rgb)
            print(f"Found {len(face_locations)} faces")
            
            if len(face_locations) == 0:
                operation_status = {"status": "error", "message": "No face detected!"}
                print("No face detected!")
                time.sleep(3)
                conn.close()
                return
            
            face_encodings = face_recognition.face_encodings(frame_rgb, face_locations)
            
            if not face_encodings:
                operation_status = {"status": "error", "message": "Failed to encode face!"}
                print("Failed to encode face!")
                time.sleep(3)
                conn.close()
                return
            
            encoding = face_encodings[0]
            
            cur.execute('SELECT user_id, name, face_encoding FROM users WHERE is_active=1')
            users = cur.fetchall()
            
            user_id = None
            user_name = None
            
            print(f"Comparing with {len(users)} users...")
            for uid, uname, enc in users:
                known_encoding = pickle.loads(enc)
                matches = face_recognition.compare_faces([known_encoding], encoding, tolerance=0.6)
                distance = face_recognition.face_distance([known_encoding], encoding)
                print(f"User {uname}: match={matches[0]}, distance={distance[0]}")
                
                if matches[0]:
                    user_id = uid
                    user_name = uname
                    break
            
            if not user_id:
                operation_status = {"status": "error", "message": "User not recognized!"}
                print("User not recognized!")
                time.sleep(3)
                conn.close()
                return
            
            print(f"User recognized: {user_name}")
            operation_status = {"status": "processing", "message": f"Issuing to {user_name}..."}
            
            issue_date = datetime.now()
            due_date = issue_date + timedelta(days=14)
            
            cur.execute('INSERT INTO transactions (book_id, user_id, rfid_tag, issue_date, due_date, status) VALUES (?, ?, ?, ?, ?, ?)',
                       (book[0], user_id, rfid_tag, issue_date.strftime('%Y-%m-%d %H:%M:%S'),
                        due_date.strftime('%Y-%m-%d %H:%M:%S'), 'issued'))
            cur.execute('UPDATE books SET status=? WHERE book_id=?', ('issued', book[0]))
            conn.commit()
            conn.close()
            
            operation_status = {"status": "success", "message": f"Book '{book[1]}' issued to {user_name}!"}
            print(f"Book issued successfully to {user_name}")
            time.sleep(3)
        except Exception as e:
            operation_status = {"status": "error", "message": f"Error: {str(e)}"}
            print(f"Issue error: {e}")
            time.sleep(3)
    
    def return_book(self):
        global operation_status
        try:
            operation_status = {"status": "reading_rfid", "message": "Reading RFID..."}
            print("Return Book: Reading RFID...")
            
            rfid_tag, _ = self.rfid_reader.read_rfid()
            if not rfid_tag:
                operation_status = {"status": "error", "message": "RFID read failed!"}
                return
            
            conn = self.get_connection()
            cur = conn.cursor()
            cur.execute('''SELECT t.transaction_id, t.book_id, b.title, u.name, u.face_encoding 
                          FROM transactions t 
                          JOIN books b ON t.book_id=b.book_id
                          JOIN users u ON t.user_id=u.user_id 
                          WHERE t.rfid_tag=? AND t.status='issued' ''', (rfid_tag,))
            trans = cur.fetchone()
            
            if not trans:
                operation_status = {"status": "error", "message": "No active transaction!"}
                conn.close()
                return
            
            tid, book_id, book_title, user_name, known_enc_bytes = trans
            print(f"Book found: {book_title}, issued to: {user_name}")
            
            operation_status = {"status": "verifying", "message": "Look at camera..."}
            print("Verifying user...")
            time.sleep(2)
            
            # Capture and verify
            frame_array = self.face_system.picam2.capture_array()
            frame_rgb = cv2.cvtColor(frame_array, cv2.COLOR_BGR2RGB)
            
            face_locations = face_recognition.face_locations(frame_rgb)
            print(f"Found {len(face_locations)} faces")
            
            if len(face_locations) == 0:
                operation_status = {"status": "error", "message": "No face detected!"}
                print("No face detected!")
                time.sleep(3)
                conn.close()
                return
            
            face_encodings = face_recognition.face_encodings(frame_rgb, face_locations)
            
            if not face_encodings:
                operation_status = {"status": "error", "message": "Failed to encode face!"}
                print("Failed to encode face!")
                time.sleep(3)
                conn.close()
                return
            
            current_encoding = face_encodings[0]
            known_encoding = pickle.loads(known_enc_bytes)
            
            matches = face_recognition.compare_faces([known_encoding], current_encoding, tolerance=0.6)
            distance = face_recognition.face_distance([known_encoding], current_encoding)
            print(f"Face match: {matches[0]}, distance: {distance[0]}")
            
            if not matches[0]:
                operation_status = {"status": "error", "message": "Invalid user! Face mismatch!"}
                print("Face mismatch!")
                time.sleep(3)
                conn.close()
                return
            
            print(f"User verified: {user_name}")
            operation_status = {"status": "processing", "message": f"Processing return..."}
            
            return_date = datetime.now()
            cur.execute('UPDATE transactions SET return_date=?, status=? WHERE transaction_id=?',
                       (return_date.strftime('%Y-%m-%d %H:%M:%S'), 'returned', tid))
            cur.execute('UPDATE books SET status=? WHERE book_id=?', ('available', book_id))
            conn.commit()
            conn.close()
            
            operation_status = {"status": "success", "message": f"Book '{book_title}' returned by {user_name}!"}
            print(f"Book returned successfully by {user_name}")
            time.sleep(3)
        except Exception as e:
            operation_status = {"status": "error", "message": f"Error: {str(e)}"}
            print(f"Return error: {e}")
            time.sleep(3)
    
    def delete_book(self, book_id):
        conn = self.get_connection()
        cur = conn.cursor()
        cur.execute('SELECT status FROM books WHERE book_id=?', (book_id,))
        book = cur.fetchone()
        if book and book[0] == 'issued':
            conn.close()
            return {"status": "error", "message": "Book is issued!"}
        cur.execute('DELETE FROM books WHERE book_id=?', (book_id,))
        conn.commit()
        conn.close()
        return {"status": "success", "message": "Book deleted!"}
    
    def delete_user(self, user_id):
        conn = self.get_connection()
        cur = conn.cursor()
        cur.execute('SELECT COUNT(*) FROM transactions WHERE user_id=? AND status="issued"', (user_id,))
        if cur.fetchone()[0] > 0:
            conn.close()
            return {"status": "error", "message": "User has active issues!"}
        cur.execute('UPDATE users SET is_active=0 WHERE user_id=?', (user_id,))
        conn.commit()
        conn.close()
        return {"status": "success", "message": "User deleted!"}
    
    def clear_database(self):
        conn = self.get_connection()
        cur = conn.cursor()
        cur.execute('DELETE FROM activity_logs')
        cur.execute('DELETE FROM transactions')
        cur.execute('DELETE FROM books')
        cur.execute('DELETE FROM users')
        conn.commit()
        conn.close()
        return {"status": "success", "message": "All data cleared!"}
    
    def get_all_books(self):
        conn = self.get_connection()
        cur = conn.cursor()
        cur.execute('SELECT book_id, title, author, category, status FROM books')
        books = cur.fetchall()
        conn.close()
        return books
    
    def get_all_users(self):
        conn = self.get_connection()
        cur = conn.cursor()
        cur.execute('SELECT user_id, name, email, phone FROM users WHERE is_active=1')
        users = cur.fetchall()
        conn.close()
        return users
    
    def get_all_transactions(self):
        conn = self.get_connection()
        cur = conn.cursor()
        cur.execute('''SELECT t.transaction_id, b.title, u.name, t.issue_date, t.due_date, t.return_date, t.status
                      FROM transactions t JOIN books b ON t.book_id=b.book_id JOIN users u ON t.user_id=u.user_id
                      ORDER BY t.transaction_id DESC''')
        trans = cur.fetchall()
        conn.close()
        return trans
    
    def get_active_transactions(self):
        conn = self.get_connection()
        cur = conn.cursor()
        cur.execute('''SELECT t.transaction_id, b.title, u.name, t.issue_date, t.due_date
                      FROM transactions t JOIN books b ON t.book_id=b.book_id JOIN users u ON t.user_id=u.user_id
                      WHERE t.status='issued' ''')
        trans = cur.fetchall()
        conn.close()
        return trans

def init_lms():
    global lms_instance
    if not lms_instance:
        lms_instance = LibraryManagementSystem()
    return lms_instance

def generate_frames():
    lms = init_lms()
    while True:
        try:
            frame = lms.face_system.picam2.capture_array()
            frame_bgr = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
            _, buffer = cv2.imencode('.jpg', frame_bgr)
            yield (b'--frame\r\nContent-Type: image/jpeg\r\n\r\n' + buffer.tobytes() + b'\r\n')
        except:
            time.sleep(0.1)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/video_feed')
def video_feed():
    return Response(generate_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/status')
def status():
    return jsonify(operation_status)

@app.route('/register_book', methods=['POST'])
def register_book():
    data = request.json
    threading.Thread(target=init_lms().register_book,
                    args=(data['title'], data['author'], data['isbn'], data['category'])).start()
    return jsonify({"status": "started"})

@app.route('/register_user', methods=['POST'])
def register_user():
    data = request.json
    threading.Thread(target=init_lms().register_user,
                    args=(data['name'], data['email'], data['phone'])).start()
    return jsonify({"status": "started"})

@app.route('/issue_book', methods=['POST'])
def issue_book():
    threading.Thread(target=init_lms().issue_book).start()
    return jsonify({"status": "started"})

@app.route('/return_book', methods=['POST'])
def return_book():
    threading.Thread(target=init_lms().return_book).start()
    return jsonify({"status": "started"})

@app.route('/delete_book/<int:book_id>', methods=['DELETE'])
def delete_book(book_id):
    return jsonify(init_lms().delete_book(book_id))

@app.route('/delete_user/<int:user_id>', methods=['DELETE'])
def delete_user(user_id):
    return jsonify(init_lms().delete_user(user_id))

@app.route('/clear_database', methods=['POST'])
def clear_database():
    return jsonify(init_lms().clear_database())

@app.route('/books')
def get_books():
    return jsonify([{"id": b[0], "title": b[1], "author": b[2], "category": b[3], "status": b[4]}
                   for b in init_lms().get_all_books()])

@app.route('/users')
def get_users():
    return jsonify([{"id": u[0], "name": u[1], "email": u[2], "phone": u[3]}
                   for u in init_lms().get_all_users()])

@app.route('/transactions')
def get_transactions():
    return jsonify([{"id": t[0], "book": t[1], "user": t[2], "issue_date": t[3],
                    "due_date": t[4], "return_date": t[5] or "N/A", "status": t[6]}
                   for t in init_lms().get_all_transactions()])

@app.route('/transactions/active')
def get_active_transactions():
    return jsonify([{"id": t[0], "book": t[1], "user": t[2], "issue_date": t[3], "due_date": t[4]}
                   for t in init_lms().get_active_transactions()])

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True, threaded=True)
