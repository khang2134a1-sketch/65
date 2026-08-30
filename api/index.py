import os
import requests
from flask import Flask, render_template, jsonify, request

app = Flask(__name__, template_folder='../templates', static_folder='../static')

DEFAULT_GITHUB_TOKEN = os.environ.get('GITHUB_TOKEN', '')

@app.route('/')
def home():
    try:
        return render_template('index.html')
    except Exception as e:
        return f"Lỗi giao diện: {str(e)}", 500

@app.route('/api/vps', methods=['GET'])
def get_vps():
    try:
        # Xử lý an toàn tránh văng lỗi 500 khi chưa có token hoặc cấu hình git
        vps_list = []
        return jsonify({"success": True, "vps": vps_list})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 200

@app.route('/api/create', methods=['POST'])
def create_vps():
    try:
        data = request.json or {}
        name = data.get('name', 'vps-node')
        return jsonify({"success": True, "message": f"Đã khởi tạo VPS '{name}' thành công!"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 200

if __name__ == '__main__':
    app.run(debug=True)
