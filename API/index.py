import json
import requests
import re
import time
from flask import Flask, request, render_template_string, jsonify
from concurrent.futures import ThreadPoolExecutor, as_completed
import signal
from tqdm import tqdm

# Flask app setup
app = Flask(__name__)

# Regular expression to identify URLs
URL_REGEX = re.compile(
    r"https?://(?:www\.)?[a-zA-Z0-9\-_]+\.[a-zA-Z]{2,}(?:/[^ \n]*)?"
)

# Graceful exit on interrupt
def handle_interrupt(signal_received, frame):
    print("\nProcess interrupted! Exiting safely...")
    exit(0)

signal.signal(signal.SIGINT, handle_interrupt)

# Function to recursively find all URLs in a JSON object
def find_urls(data):
    urls = []
    if isinstance(data, dict):
        for key, value in data.items():
            urls.extend(find_urls(value))
    elif isinstance(data, list):
        for item in data:
            urls.extend(find_urls(item))
    elif isinstance(data, str) and URL_REGEX.match(data):
        urls.append(data)
    return urls

# Function to calculate size/time using HEAD requests (faster, less accurate)
def head_request(url, session):
    try:
        start_time = time.time()
        with session.head(url, timeout=10) as response:
            total_bytes = int(response.headers.get("Content-Length", 0))
        elapsed_time = time.time() - start_time
        return url, total_bytes, elapsed_time
    except requests.RequestException:
        return url, 0, 0

# Function to download and measure size/time (slower, more accurate)
def download_request(url, session):
    try:
        start_time = time.time()
        with session.get(url, stream=True, timeout=10) as response:
            total_bytes = sum(len(chunk) for chunk in response.iter_content(chunk_size=8192))
        elapsed_time = time.time() - start_time
        return url, total_bytes, elapsed_time
    except requests.RequestException:
        return url, 0, 0

# Function to format seconds into minutes and seconds
def format_time(total_seconds):
    minutes = total_seconds // 60
    seconds = total_seconds % 60
    return f"{minutes} minutes and {seconds} seconds"

# Process URLs and calculate sizes/time
def process_urls(urls, max_threads=10, accurate=False):
    # Initialize session for connection pooling
    session = requests.Session()
    function_to_use = download_request if accurate else head_request

    # Process URLs with threading
    total_size = 0
    total_time = 0
    video_details = []

    with ThreadPoolExecutor(max_threads) as executor:
        future_to_url = {executor.submit(function_to_use, url, session): url for url in urls}
        for future in tqdm(as_completed(future_to_url), total=len(urls), desc="Processing URLs"):
            url, size, elapsed = future.result()
            total_size += size
            total_time += elapsed
            video_details.append({
                'url': url,
                'size': size / 1024,  # Size in KB
                'time': elapsed,  # Time in seconds
                'formatted_time': format_time(elapsed),
                'formatted_size': f"{size / 1024:.2f} KB"
            })

    # Calculate total time in minutes and seconds
    total_minutes = total_time // 60
    total_remaining_seconds = total_time % 60
    total_time_str = f"{total_minutes}m {total_remaining_seconds}s"

    return {
        "total_size": total_size / (1024 * 1024),  # Size in MB
        "total_time": total_time_str,
        "video_details": video_details
    }

# HTML for file upload form
UPLOAD_FORM_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Upload JSON File</title>
</head>
<body>
    <h1>Upload Your JSON File with YouTube URLs</h1>
    <form action="/upload" method="POST" enctype="multipart/form-data">
        <label for="file">Choose a JSON file:</label>
        <input type="file" name="file" id="file" required>
        <button type="submit">Upload</button>
    </form>
</body>
</html>
"""

# Main route to display the upload form
@app.route('/', methods=['GET'])
def index():
    return render_template_string(UPLOAD_FORM_HTML)

# Handle uploaded JSON file and process URLs
@app.route('/upload', methods=['POST'])
def upload():
    if 'file' not in request.files:
        return jsonify({"error": "No file part"}), 400
    
    file = request.files['file']
    
    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400
    
    try:
        data = json.load(file)  # Load JSON data from the uploaded file
        if not isinstance(data, list):
            return jsonify({"error": "Invalid JSON structure. Should be a list of URLs."}), 400
        
        urls = find_urls(data)
        if not urls:
            return jsonify({"error": "No valid URLs found in the JSON file."}), 400
        
        # Choose accuracy mode (fast vs accurate)
        accurate = False
        mode = request.form.get("mode", "1")  # Use form to decide mode
        if mode == "2":
            accurate = True
        
        results = process_urls(urls, max_threads=10, accurate=accurate)

        # Display total results on the webpage
        return render_template_string("""
        <h1>Processing Results</h1>
        <p><strong>Total URLs processed:</strong> {{ len(results['video_details']) }}</p>
        <p><strong>Total size:</strong> {{ results['total_size'] }} MB</p>
        <p><strong>Total time:</strong> {{ results['total_time'] }}</p>
        <ul>
            {% for video in results['video_details'] %}
            <li>
                URL: {{ video['url'] }}<br>
                Size: {{ video['formatted_size'] }}<br>
                Time: {{ video['formatted_time'] }}
            </li>
            {% endfor %}
        </ul>
        <a href="/">Upload another file</a>
        """, results=results)

    except json.JSONDecodeError:
        return jsonify({"error": "Invalid JSON file."}), 400

# Run the Flask app
if __name__ == '__main__':
    app.run(debug=True)
