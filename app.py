# app.py

import os
from datetime import datetime
from flask import Flask, render_template, request
from make_predictions import object_detection
import pytesseract as pt
import cv2
import numpy as np
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(os.getcwd(), 'site.db')
db = SQLAlchemy(app)

class PlateRequest(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    plate_number = db.Column(db.String(20), nullable=False)
    request_time = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
with app.app_context():
    db.create_all()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload():
    if 'file' not in request.files:
        return render_template('index.html', message='No file part')

    file = request.files['file']

    if file.filename == '':
        return render_template('index.html', message='No selected file')

    if file:
        # Save the uploaded image
        file_path = 'static/images/uploaded_image.png'
        file.save(file_path)

        # Perform object detection and OCR
        image, coords = object_detection(file_path)
        print(image,coords)

        # Extract plate number using OCR on the detected region
        xmin, xmax, ymin, ymax = coords[0]
        roi = image[ymin:ymax, xmin:xmax]
        gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
        blur = cv2.GaussianBlur(gray, (5, 5), 0)
        thresh = cv2.threshold(blur, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)[1]

        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
        opening = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, kernel, iterations=1)
        invert = 255 - opening

        # Perform text extraction
        data = pt.image_to_string(invert, config='--oem 3 --psm 6 -c tessedit_char_whitelist=0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ')
        if(data == ""):
            data= pt.image_to_string(blur)
        filter_data = "".join(data.split()).replace(":", "").replace("-", "").replace("’", "").replace("“", "").replace("'", "")

        plate_number_record = PlateRequest(plate_number=filter_data, request_time=datetime.utcnow())
        db.session.add(plate_number_record)
        db.session.commit()
        plate_records = PlateRequest.query.all()
        return render_template('result.html', image_path=file_path, plate_number=filter_data,plate_records=plate_records)

if __name__ == '__main__':

    app.run(debug=True)
