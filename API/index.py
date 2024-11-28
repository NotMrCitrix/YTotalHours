from flask import Flask, request, jsonify, render_template
import json
import requests
from io import StringIO
from tqdm import tqdm

app = Flask(__name__)

# Function to process the uploaded JSON file
def process_json_file(json_file):
    total_seconds = 0
    total_minutes = 0

    # Read the JSON file
    data = json.load(json_file)
    
    # Loop through each URL in the JSON file
    urls = []
    if isinstance(data, dict):
        # Extract URLs from a dictionary-like structure
        urls = [value for value in data.values() if isinstance(value, str) and value.startswith("http")]
    elif isinstance(data, list):
        # If it's a list, extract all URLs
        for item in data:
            if isinstance(item, str) and item.startswith("http"):
                urls.append(item)

    # Calculate the duration of each URL
    for url in tqdm(urls, desc="Processing URLs", ncols=100):
        try:
            response = requests.head(url)
            length = int(response.headers.get('Content-Length', 0))
            if length > 0:
                # Convert bytes to seconds (assuming 1 byte is 1 second for simplicity)
                seconds = length // 1024  # Convert to kilobytes then to seconds (rough estimate)
                total_seconds += seconds
        except requests.exceptions.RequestException:
            continue  # Skip URLs that result in errors

    total_minutes = total_seconds // 60
    remaining_seconds = total_seconds % 60

    return total_minutes, remaining_seconds


@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        # Check if a file is uploaded
        if "file" not in request.files:
            return jsonify({"error": "No file part"}), 400
        
        file = request.files["file"]
        
        if file.filename == "":
            return jsonify({"error": "No selected file"}), 400

        # Process the uploaded file
        if file and file.filename.endswith(".json"):
            total_minutes, remaining_seconds = process_json_file(file)
            return render_template("index.html", minutes=total_minutes, seconds=remaining_seconds)
        else:
            return jsonify({"error": "Invalid file format. Please upload a JSON file."}), 400
    return render_template("index.html")


if __name__ == "__main__":
    app.run(debug=True)
