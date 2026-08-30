import os
import requests
from flask import Flask, render_template, jsonify, request

app = Flask(__name__, template_folder='../templates', static_folder='../static')

# Cấu hình thông tin Repository GitHub của bạn ở đây
GITHUB_OWNER = os.environ.get('GITHUB_OWNER', 'khang2134a1-sketch') 
GITHUB_REPO = os.environ.get('GITHUB_REPO', 'quanlikhangkk')
WORKFLOW_FILE = os.environ.get('WORKFLOW_FILE', 'main.yml')

@app.route('/')
def home():
    try:
        return render_template('index.html')
    except Exception as e:
        return f"Lỗi giao diện: {str(e)}", 500

@app.route('/api/vps', methods=['GET'])
def get_vps():
    try:
        token = request.headers.get('X-Github-Token') or os.environ.get('GITHUB_TOKEN', '')
        if not token:
            return jsonify({"success": True, "vps": []})

        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json"
        }
        
        # Lấy danh sách workflow runs gần đây để hiển thị trạng thái VPS
        url = f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/actions/runs"
        response = requests.get(url, headers=headers, timeout=5)
        
        vps_list = []
        if response.status_code == 200:
            runs = response.json().get('workflow_runs', [])
            for run in runs[:6]: # Lấy 6 bản chạy gần nhất
                vps_list.append({
                    "name": run.get('display_title', 'VPS Node'),
                    "status": run.get('status'),
                    "conclusion": run.get('conclusion'),
                    "url": run.get('html_url'),
                    "created_at": run.get('created_at'),
                    "link": None # Sẽ tự động nhận diện nếu có Cloudflare tunnel output
                })
                
        return jsonify({"success": True, "vps": vps_list})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 200

@app.route('/api/create', methods=['POST'])
def create_vps():
    try:
        data = request.json or {}
        name = data.get('name', 'vps-node')
        token = data.get('token') or os.environ.get('GITHUB_TOKEN', '')

        if not token:
            return jsonify({"success": False, "error": "Thiếu GitHub Token xác thực!"}), 200

        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json"
        }
        
        # Gửi tín hiệu kích hoạt GitHub Actions (Workflow Dispatch)
        url = f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/actions/workflows/{WORKFLOW_FILE}/dispatches"
        payload = {
            "ref": "main",
            "inputs": {"vps_name": name}
        }
        
        response = requests.post(url, headers=headers, json=payload, timeout=10)
        
        if response.status_code in [204, 201, 200]:
            return jsonify({"success": True, "message": f"Đã gửi lệnh khởi tạo VPS '{name}' lên GitHub thành công!"})
        else:
            return jsonify({"success": False, "error": f"GitHub từ chối: {response.text}"}), 200

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 200

if __name__ == '__main__':
    app.run(debug=True)
