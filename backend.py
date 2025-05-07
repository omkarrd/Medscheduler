from flask import Flask, request, jsonify, send_from_directory
import pytesseract
import cv2
import numpy as np
import os
from PIL import Image
import re
import spacy
import mysql.connector

# Database connectivity
conn = mysql.connector.connect(
    host="localhost",
    user="root",
    password="mysql@123",
    database="medscheduler"
)
cursor = conn.cursor()
print(" Database connected successfully!")

# Load spaCy model 
nlp = spacy.load("en_core_web_sm")

pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

app = Flask(__name__)

# Upload 
UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)


@app.route('/')
def serve_home():
    return send_from_directory('.', 'Home.html')

@app.route('/login')
def serve_login():
    return send_from_directory('.', 'login.html')

@app.route('/upload', methods=['POST'])
def upload_file():
    try:
        if 'file' not in request.files:
            return jsonify({'error': 'No file uploaded!'}), 400

        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': 'No selected file!'}), 400

        # Save the uploaded file
        file_path = os.path.join(UPLOAD_FOLDER, file.filename)
        file.save(file_path)
        print(f" File saved at: {file_path}")

       
        extracted_text = extract_text(file_path)

       
        cleaned_text = clean_text(extracted_text)

        
        medicines = extract_medicine_data(cleaned_text)
        print("🔍 Extracted Medicines:", medicines)

       
        final_medicines = filter_medicine_names(medicines)
        print(" Final Proper Medicines:", final_medicines)

        
        if not final_medicines:
            return jsonify({'error': 'No valid medicines extracted!'}), 400

        
        store_medicines_in_db(final_medicines)

        
        response = {"medicines": final_medicines}
        print(" Sending to frontend:", response)
        return jsonify(response)

    except Exception as e:
        return jsonify({'error': str(e)}), 500


# OCR and medicine extraction functions
def extract_text(image_path):
    image = cv2.imread(image_path, cv2.IMREAD_GRAYSCALE)
    image = cv2.adaptiveThreshold(image, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2)
    pil_image = Image.fromarray(image)
    text = pytesseract.image_to_string(pil_image)
    print(" Extracted OCR Text:\n", text)
    return text

def clean_text(text):
    text = text.replace("\n", " ")
    text = re.sub(r'[^A-Za-z0-9\s\(\)\-\./]', '', text)  
    text = re.sub(r'\s+', ' ', text).strip()
    return text

def extract_medicine_data(text):
   
    pattern = r"([A-Za-z0-9\s]+)\s*(\d+)\s*(tabs|capsules|mg|ml|syrup|pack)?"
    matches = re.findall(pattern, text)

    medicines = []
    for match in matches:
        name = match[0].strip()
        quantity = int(match[1]) if match[1].isdigit() else 1
        medicines.append({"name": name, "quantity": quantity})

    return medicines

def clean_medicine_name(name):
    name = re.sub(r"^\d+\s*", "", name).strip()
    name = re.sub(r"\s*\.$", "", name)
    name = re.sub(r"\b(?:i|ii|iii|iv|v|vi|vii|viii|ix|x)\b", "", name, flags=re.IGNORECASE)  
    blacklist_keywords = ["super", "bazar", "shop", "invoice", "date", "pack of", "pollo", "client", "new delhi", "ri"]
    for keyword in blacklist_keywords:
        if keyword.lower() in name.lower():
            return None
    return name if any(char.isalpha() for char in name) else None

def filter_medicine_names(medicine_list):
    filtered_medicines = []
    for med in medicine_list:
        cleaned_name = clean_medicine_name(med["name"])
        if cleaned_name:
            filtered_medicines.append({"name": cleaned_name, "quantity": med["quantity"]})
    return filtered_medicines

def store_medicines_in_db(medicines):
    try:
        for med in medicines:
            query = "INSERT INTO medicines (name, quantity) VALUES (%s, %s)"
            values = (med["name"], med["quantity"])
            cursor.execute(query, values)
        conn.commit()
        print(" Medicines stored in database!")
    except Exception as e:
        print("❌ Database insertion error:", e)

if __name__ == '__main__':
    app.run(debug=True)
