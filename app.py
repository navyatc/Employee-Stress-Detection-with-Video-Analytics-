import os
import cv2
import base64
import random
import sqlite3
from flask import Flask, render_template, request, redirect, url_for, session, jsonify, g, Response
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
import time
import cv2
import cv2
import numpy as np
from keras.models import model_from_json
import csv
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from datetime import datetime
import os

emotion_dict = {0: "Angry", 1: "Disgusted", 2: "Fearful", 3: "Happy", 4: "Neutral", 5: "Sad", 6: "Surprised"}

# load json and create model
json_file = open('model/emotion_model.json', 'r')
loaded_model_json = json_file.read()
json_file.close()
emotion_model = model_from_json(loaded_model_json)

# load weights into new model
emotion_model.load_weights("model/emotion_model.h5")
print("Loaded model from disk")
feed = True

def gen_frames():  # generate frame by frame from camera
    global feed
    camera = cv2.VideoCapture(0)
    with open('emotions.csv', mode='w', newline='') as file:
        writer = csv.writer(file)
        writer.writerow(['emotion'])
    file.close()

    while True:
        # Capture frame-by-frame
        success, frame = camera.read()  # read the camera frame
        if not success:
            camera.release()
            break
        if not feed:
            camera.release()
            break
        else:
            face_detector = cv2.CascadeClassifier('haarcascades/haarcascade_frontalface_default.xml')
            gray_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

            # detect faces available on camera
            num_faces = face_detector.detectMultiScale(gray_frame, scaleFactor=1.3, minNeighbors=5)

            # take each face available on the camera and Preprocess it
            for (x, y, w, h) in num_faces:
                cv2.rectangle(frame, (x, y-50), (x+w, y+h+10), (0, 255, 0), 4)
                roi_gray_frame = gray_frame[y:y + h, x:x + w]
                cropped_img = np.expand_dims(np.expand_dims(cv2.resize(roi_gray_frame, (48, 48)), -1), 0)

                # predict the emotions
                emotion_prediction = emotion_model.predict(cropped_img)
                maxindex = int(np.argmax(emotion_prediction))
                cv2.putText(frame, emotion_dict[maxindex], (x+5, y-20), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 0, 0), 2, cv2.LINE_AA)
                with open('emotions.csv', mode='a', newline='') as file:
                    writer = csv.writer(file)
                    writer.writerow([emotion_dict[maxindex]])
                    file.close()

            ret, buffer = cv2.imencode('.jpg', frame)
            frame = buffer.tobytes()
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')  # concat frame one by one and show result


app = Flask(__name__)
app.secret_key = 'your-secret-key-here'  # Change this in production

# Database configuration
DATABASE = 'data/employee.db'
EXAM_DURATION = 300  # 5 minutes in seconds

# Default admin credentials
ADMIN_USERNAME = 'admin'

def get_db():
    """Get database connection"""
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE)
        db.row_factory = sqlite3.Row
    return db

@app.teardown_appcontext
def close_connection(exception):
    """Close database connection at the end of request"""
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/adminlogout')
def adminlogout():
    session.clear()
    return render_template('index.html')

@app.route('/auth')
def auth():
    return render_template('auth.html')

@app.route('/signin', methods=['POST'])
def signin():
    username = request.form.get('username')
    password = request.form.get('password')
    
    db = get_db()
    cursor = db.execute('SELECT * FROM employees WHERE username = ?', (username,))
    user = cursor.fetchone()
    
    if user and check_password_hash(user['password_hash'], password):
        session['user_id'] = user['id']
        session['username'] = user['username']
        session['is_admin'] = False
        
        if session['is_admin']:
            return redirect(url_for('admin'))
        else:
            return redirect(url_for('employee'))
    else:
        return render_template('auth.html', error='Invalid username or password', is_login=True)

@app.route('/signup', methods=['POST'])
def signup():
    username = request.form.get('username')
    password = request.form.get('password')
    email = request.form.get('email', '')
    
    db = get_db()
    
    try:
        hashed_password = generate_password_hash(password)
        db.execute(
            'INSERT INTO employees (username, email, password_hash) VALUES (?, ?, ?)',
            (username, email, hashed_password)
        )
        db.commit()
        
        # Get the new user ID
        cursor = db.execute('SELECT id FROM employees WHERE username = ?', (username,))
        user = cursor.fetchone()
        
        session['user_id'] = user['id']
        session['username'] = username
        session['is_admin'] = False
        return redirect(url_for('employee'))
    except sqlite3.IntegrityError:
        return render_template('auth.html', error='Username or email already exists', is_login=False)

@app.route('/admin_signin', methods=['POST'])
def admin_signin():
    username = request.form.get('username')
    password = request.form.get('password')
    print(username, password)
    if username == 'admin' and password == 'admin123':
        session['is_admin'] = True
        session['user_id'] = True
        return redirect(url_for('admin'))
    else:
        return render_template('auth.html', error='Invalid admin credentials', is_login=True, is_admin_login=True)

@app.route('/admin')
def admin():
    if not session.get('is_admin'):
        return redirect(url_for('auth'))
    
    db = get_db()
    cursor = db.execute('''
        SELECT username FROM employees
    ''')
    rows = cursor.fetchall()
    names = []
    for row in rows:
        names.append(row['username'])
    return render_template('admin.html', names=names)

@app.route('/employee')
def employee():
    if 'user_id' not in session or session.get('is_admin'):
        return redirect(url_for('auth'))
    return render_template('employee.html')

@app.route('/video_feed')
def video_feed():
    return Response(gen_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/logout')
def logout():
    global feed
    feed = False
    username = session['username']
    filename = 'emotions.csv'
    emotion_dict = {0: "Angry", 1: "Disgusted", 2: "Fearful", 3: "Happy", 4: "Neutral", 5: "Sad", 6: "Surprised"}

    # Read the CSV file
    df = pd.read_csv(filename)

    # Count occurrences of each emotion
    emotion_counts = df['emotion'].value_counts().sort_index()

    # Map emotion codes to names and ensure all emotions are represented
    emotion_labels = [emotion_dict.get(i, f"{i}") for i in emotion_counts.index]
    counts = emotion_counts.values

    # Calculate percentages
    total = sum(counts)
    percentages = [count/total * 100 for count in counts]

    # Find the emotion with the highest percentage
    max_percent_index = percentages.index(max(percentages))
    dominant_emotion = emotion_labels[max_percent_index]
    dominant_percent = percentages[max_percent_index]
    dominant_count = counts[max_percent_index]

    print(f"Dominant emotion: {dominant_emotion} ({dominant_percent:.1f}%, {dominant_count} occurrences)")

    # Create a color palette for the pie chart
    colors = ['#ff6b6b', '#4ecdc4', '#45b7d1', '#f9c74f', '#90be6d', '#ff9f1c', '#d291bc']

    # Create the pie chart
    plt.figure(figsize=(10, 8))
    wedges, texts, autotexts = plt.pie(
        counts, 
        labels=emotion_labels, 
        colors=colors, 
        autopct='%1.1f%%',
        startangle=90,
        textprops={'fontsize': 12}
    )

    # Improve autopct text appearance
    for autotext in autotexts:
        autotext.set_color('white')
        autotext.set_fontweight('bold')

    # Add a title
    plt.title(f'Emotion Distribution for {username}', fontsize=16, fontweight='bold', pad=20)

    # Ensure equal aspect ratio to make pie circular
    plt.axis('equal')

    # Add legend
    plt.legend(
        wedges, 
        [f'{label}: {count} ({percent:.1f}%)' for label, count, percent in zip(emotion_labels, counts, percentages)],
        title="Emotions",
        loc="center left",
        bbox_to_anchor=(1, 0, 0.5, 1)
    )

    # Adjust layout to prevent legend cutoff
    plt.tight_layout()

    # Generate filename with username and current date
    current_date = datetime.now().strftime("%Y%m%d")
    image_filename = f"{username}_{current_date}.png"

    # Create directory for saved images if it doesn't exist
    os.makedirs('static/charts', exist_ok=True)

    # Save the chart
    image_path = 'static/charts/'+image_filename
    plt.savefig(image_path, bbox_inches='tight', dpi=100)
    plt.close()

    print(f"Chart saved as {image_path}")
    session.clear()
    if dominant_emotion in ['Angry', 'Disgusted', 'Sad', 'Fearful']:
        return render_template('sad.html', result='Stress')
    else:
        return render_template('happy.html', result='No Stress')

@app.route('/getdetails', methods = ['POST'])
def getdetails():
    if not session.get('is_admin'):
        return redirect(url_for('auth'))
    
    db = get_db()
    cursor = db.execute('''
        SELECT username FROM employees
    ''')
    rows = cursor.fetchall()
    names = []
    for row in rows:
        names.append(row['username'])

    name = request.form['name']
    Date = request.form['Date']
    path = 'http://127.0.0.1:5000/static/charts/'+name+'_'+Date.replace('-','')+'.png'
    print(path)
    return render_template('admin.html', names=names, image=path, Date=Date, name=name)

if __name__ == '__main__':
    # Initialize database if it doesn't exist
    if not os.path.exists(DATABASE):
        import init_db
        init_db.init_database()
    
    app.run(debug=True, use_reloader=False)