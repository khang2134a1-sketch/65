import os
import json
import base64
import requests
from flask import Flask, render_template, request, jsonify

app = Flask(__name__)

# Token dự phòng hệ thống (bạn có thể thay thế bằng token mới của bạn tại đây)
DEFAULT_GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")

def get_auth_token(req=None):
    if req:
        custom_token = req.headers.get('X-Github-Token')
        if custom_token and custom_token.strip():
            return custom_token.strip()
    return DEFAULT_GITHUB_TOKEN

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/create', methods=['POST'])
def create_vps():
    data = request.json or {}
    vps_name = data.get('name', 'vps-server')
    user_token = data.get('token', '').strip()
    
    token = user_token if user_token else get_auth_token(request)
    if not token:
        return jsonify({"success": False, "error": "Chưa cung cấp GitHub Token hợp lệ!"}), 400

    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json"
    }

    # Lấy thông tin user hiện tại để clone template hoặc tạo repo
    user_res = requests.get("https://api.github.com/user", headers=headers)
    if user_res.status_code != 200:
        return jsonify({"success": False, "error": "Token GitHub không hợp lệ hoặc đã hết hạn!"}), 400
    
    username = user_res.json().get("login")
    repo_name = f"{vps_name.lower().replace(' ', '-')}-{int(os.times()[4]*1000)}"

    # 1. Tạo repository mới từ template hoặc tạo repo trống có sẵn workflow
    create_repo_data = {
        "name": repo_name,
        "description": "VPS Commander Automation Node",
        "private": True,
        "auto_init": True
    }
    
    create_res = requests.post("https://api.github.com/user/repos", headers=headers, json=create_repo_data)
    if create_res.status_code not in [201, 200]:
        return jsonify({"success": False, "error": f"Không thể tạo kho chứa: {create_res.text}"}), 400

    # 2. Tạo file workflow tự động chạy VPS và Cloudflare Tunnel
    workflow_content = f"""name: Start VPS Commander
on: [workflow_dispatch, push]
jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout Code
        uses: actions/checkout@v4
      
      - name: Setup Tmate & Cloudflare
        run: |
          sudo apt-get update
          sudo apt-get install -y tmate curl
          echo "Starting Tmate session..."
          tmate -F &
          sleep 10
          
          # Lấy link tmate hoặc tạo cloudflare tunnel
          TMATE_WEB=$(tmate -S /tmp/tmate.sock display -p '#{tmate_web}inspect')
          echo "Link: $TMATE_WEB"
          
          # Lưu link vào file remote-link.txt để đẩy ngược lại repo
          git config --global user.name "VPS Commander Bot"
          git config --global user.email "bot@vps.local"
          echo "$TMATE_WEB" > remote-link.txt
          git add remote-link.txt
          git commit -m "Update VPS active link [skip ci]" || true
          git push origin HEAD:main || true
          
          # Giữ session sống lâu nhất có thể (tối đa 6 tiếng)
          sleep 21600
"""

    workflow_payload = {
        "message": "Add automated workflow for VPS",
        "content": base64.b64encode(workflow_content.encode()).decode(),
        "branch": "main"
    }
    
    # Tạo thư mục .github/workflows và đẩy file workflow lên
    requests.put(
        f"https://api.github.com/repos/{username}/{repo_name}/contents/.github/workflows/vps.yml",
        headers=headers,
        json=workflow_payload
    )

    # 3. Kích hoạt Workflow Dispatch thủ công để chạy ngay lập tức
    requests.post(
        f"https://api.github.com/repos/{username}/{repo_name}/actions/workflows/vps.yml/dispatches",
        headers=headers,
        json={"ref": "main"}
    )

    return jsonify({
        "success": True, 
        "message": f"Khởi tạo thành công VPS: {repo_name}",
        "repo": repo_name
    })

@app.route('/api/vps', methods=['GET'])
def list_vps():
    token = get_auth_token(request)
    if not token:
        return jsonify({"success": True, "vps": []})

    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json"
    }

    user_res = requests.get("https://api.github.com/user", headers=headers)
    if user_res.status_code != 200:
        return jsonify({"success": True, "vps": []})
    
    username = user_res.json().get("login")
    
    # Lấy danh sách các repo của user
    repos_res = requests.get(f"https://api.github.com/users/{username}/repos?per_page=100", headers=headers)
    if repos_res.status_code != 200:
        return jsonify({"success": True, "vps": []})

    vps_list = []
    for repo in repos_res.json():
        if repo['name'].startswith(('vps-', 'windows-', 'server-')) or 'vps' in repo['name']:
            repo_name = repo['name']
            created_at = repo['created_at']
            
            # Chuyển đổi thời gian tạo sang timestamp
            import datetime
            try:
                dt = datetime.datetime.strptime(created_at, "%Y-%m-%dT%H:%M:%SZ")
                created_timestamp = dt.timestamp()
            except:
                created_timestamp = 0

            # Kiểm tra xem repo có file remote-link.txt chứa link VNC hay không
            link_res = requests.get(f"https://api.github.com/repos/{username}/{repo_name}/contents/remote-link.txt", headers=headers)
            vnc_link = ""
            if link_res.status_code == 200:
                try:
                    file_data = link_res.json()
                    decoded_content = base64.b64decode(file_data['content']).decode('utf-8').strip()
                    if decoded_content.startswith("http"):
                        vnc_link = decoded_content
                except:
                    pass

            vps_list.append({
                "name": repo_name,
                "url": repo['html_url'],
                "link": vnc_link,
                "created_at": created_timestamp
            })

    return jsonify({"success": True, "vps": vps_list})

if __name__ == '__main__':
    app.run(debug=True)
