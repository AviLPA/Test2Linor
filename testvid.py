from flask import Flask, request, jsonify
import os
import cv2
from PIL import Image
import hashlib
import requests
from blockfrost import BlockFrostApi

app = Flask(__name__)
API_URL = "https://cardano-mainnet.blockfrost.io/api/v0"
API_KEY = "mainnetFBbCwStELF11HELdNM1K9YAKmcs1GUdl"
api = BlockFrostApi(project_id=API_KEY)

def image_to_binary(image, num_colors=8):
    quantized_image = image.convert("L").quantize(colors=num_colors)
    width, height = quantized_image.size
    binary_code = ""
    palette = quantized_image.getpalette()
    color_to_binary = {}
    bits_needed = len(bin(num_colors - 1)[2:])
    for i in range(num_colors):
        binary_value = format(i, f'0{bits_needed}b')
        color_to_binary[i] = binary_value
    for y in range(height):
        for x in range(width):
            pixel = quantized_image.getpixel((x, y))
            binary_code += color_to_binary[pixel]
    return binary_code

def video_to_binary(video_path, num_colors=8, target_resolution=(640, 480)):
    cap = cv2.VideoCapture(video_path)
    binary_code = ""
    frame_count = 0
    if not cap.isOpened():
        return ""
    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break
        frame = cv2.resize(frame, target_resolution)
        frame = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        frame_image = Image.fromarray(frame)
        frame_binary = image_to_binary(frame_image, num_colors)
        binary_code += frame_binary
        frame_count += 1
    cap.release()
    return binary_code

def hash_binary_data(binary_data):
    sha256_hash = hashlib.sha256()
    sha256_hash.update(binary_data.encode('utf-8'))
    return sha256_hash.hexdigest()

def search_metadata_for_hash(wallet_address, hash_value):
    headers = {'project_id': API_KEY}
    page = 1
    while True:
        try:
            response = requests.get(f"{API_URL}/addresses/{wallet_address}/transactions?page={page}", headers=headers)
            response.raise_for_status()
            transactions = response.json()
            if not transactions:
                break
            for tx in transactions:
                tx_hash = tx['tx_hash']
                metadata_response = requests.get(f"{API_URL}/txs/{tx_hash}/metadata", headers=headers)
                metadata_response.raise_for_status()
                metadata = metadata_response.json()
                for entry in metadata:
                    if 'json_metadata' in entry:
                        for key, value in entry['json_metadata'].items():
                            if isinstance(value, list) and hash_value in value:
                                return tx_hash, entry
                            elif value == hash_value:
                                return tx_hash, entry
            page += 1
        except requests.exceptions.RequestException as e:
            break
    return None

@app.route('/upload', methods=['POST'])
def upload_video():
    video = request.files['video']
    if video:
        video_path = os.path.join('uploads', video.filename)
        video.save(video_path)
        wallet_address = "addr1qyqmdurljd7v07rketnnc3udc9w547pya7v8jnh6zalrymyn84lfn88ypr4p6lvkaqwq46h2g67whtnenlpv2w9jvads3d458l"
        binary_code = video_to_binary(video_path)
        if binary_code:
            hash_result = hash_binary_data(binary_code)
            tx = search_metadata_for_hash(wallet_address, hash_result)
            if tx:
                return jsonify({'message': 'Transaction found with this hash.'})
            else:
                return jsonify({'message': 'No transaction found with this hash.'})
        else:
            return jsonify({'message': 'Failed to process video.'})
    return jsonify({'message': 'No video uploaded.'})

if __name__ == '__main__':
    if not os.path.exists('uploads'):
        os.makedirs('uploads')
    app.run(host='0.0.0.0', port=5003)

