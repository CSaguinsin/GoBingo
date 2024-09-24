import easyocr
import cv2
import json
import numpy as np

def convert_to_json(result):
    data = []
    for (bbox, text, confidence) in result:
        entry = {
            "coordinates": np.array(bbox).tolist(),  # Convert numpy array to list
            "text": text,
            "confidence": float(confidence)  # Ensure confidence is a float
        }
        data.append(entry)
    return json.dumps(data, indent=4)

# Initialize the EasyOCR reader
reader = easyocr.Reader(['en'])

# Read the image
image_path = '/Users/carlsaginsin/Projects/BingoTelegram/image_folder/DriversLicense_front.jpg'
img = cv2.imread(image_path)

# Check if the image was loaded successfully
if img is None:
    print(f"Error: Unable to load image at {image_path}")
else:
    # Convert the image to grayscale if needed
    img_gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    
    # Proceed with EasyOCR processing
    result = reader.readtext(img_gray)
    
    # Convert the result to JSON
    json_result = convert_to_json(result)
    print(json_result)
