import base64
import os
import time
from flask import Flask, jsonify, render_template, request
from github import Github

app = Flask(
    __name__,
    template_folder="../templates",
    static_folder="../static",
)
DEFAULT_GITHUB_TOKEN = os.environ.get(
    "GITHUB_TOKEN", "token_moi_cua_ban_o_day"
)

def generate_workflow(vps_name: str) -> str:
  return f"""name: Create VPS ({vps_name})

on:
  workflow_dispatch:
  schedule:
    - cron: '0 */5 * * *'

jobs:
  deploy:
    runs-on: windows-latest
    permissions:
      contents: write
      actions: write

    steps:
    - name: Checkout source
      uses: actions/checkout@v4
      with:
        token: ${{{{ secrets.GH_TOKEN }}}}

    - name: Cài đặt và chạy TightVNC, noVNC, Cloudflared
      shell: pwsh
      run: |
        try {{
          Invoke-WebRequest -Uri "https://www.tightvnc.com/download/2.8.63/tightvnc-2.8.63-gpl-setup-64bit.msi" -OutFile "tightvnc-setup.msi"
          Start-Process msiexec.exe -Wait -ArgumentList '/i tightvnc-setup.msi /quiet /norestart ADDLOCAL="Server" SERVER_REGISTER_AS_SERVICE=1 SET_USEVNCAUTHENTICATION=1 VALUE_OF_USEVNCAUTHENTICATION=1 SET_PASSWORD=1 VALUE_OF_PASSWORD=khang2k13 SET_ACCEPTHTTPCONNECTIONS=1 VALUE_OF_ACCEPTHTTPCONNECTIONS=1'
          
          Stop-Process -Name "tvnserver" -Force -ErrorAction SilentlyContinue
          Start-Process -FilePath "C:\\Program Files\\TightVNC\\tvnserver.exe" -ArgumentList "-run -localhost no" -WindowStyle Hidden
          Start-Sleep -Seconds 10
          
          Invoke-WebRequest -Uri "https://github.com/novnc/noVNC/archive/refs/tags/v1.4.0.zip" -OutFile "novnc.zip"
          Expand-Archive -Path "novnc.zip" -DestinationPath "."
          
          python -m pip install --upgrade pip
          pip install websockify==0.13.0
          
          Start-Process -FilePath "python" -ArgumentList "-m", "websockify", "6080", "127.0.0.1:5900", "--web", "$PWD\\noVNC-1.4.0" -WindowStyle Hidden
          Start-Sleep -Seconds 5
          
          Invoke-WebRequest -Uri "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-windows-amd64.exe" -OutFile "cloudflared.exe"
          Start-Process -FilePath "cloudflared.exe" -ArgumentList "tunnel", "--url", "http://localhost:6080", "--no-autoupdate", "--logfile", "cloudflared.log" -WindowStyle Hidden
          Start-Sleep -Seconds 20
          
          $logContent = Get-Content "cloudflared.log" -Raw -ErrorAction SilentlyContinue
          if ($logContent -match 'https://[a-zA-Z0-9-]+\\.trycloudflare\\.com') {{
              $cloudflaredUrl = $matches[0]
              "$cloudflaredUrl/vnc.html" | Out-File -FilePath "remote-link.txt" -Encoding UTF8 -NoNewline
              
              git config --global user.email "41898282+github-actions[bot]@users.noreply.github.com"
              git config --global user.name "github-actions[bot]"
              git add remote-link.txt
              git commit -m "🔗 Update link" --allow-empty
              git push origin main --force-with-lease
          }}
        }} catch {{ }}
        Start-Sleep -Seconds 17500
"""


@app.route("/")
def index():
  return render_template("index.html")


@app.route("/api/vps", methods=["POST"])
def get_vps_list():
  try:
    data = request.json or {}
    token = data.get("token", "").strip() or DEFAULT_GITHUB_TOKEN
    if not token:
      return jsonify({"success": False, "error": "Thiếu GitHub Token"})

    g = Github(token)
    user = g.get_user()
    vps_list = []

    for repo in user.get_repos():
      if repo.name.startswith("vps-"):
        link = ""
        try:
          file_content = repo.get_contents("remote-link.txt", ref="main")
          link = (
              base64.b64decode(file_content.content).decode("utf-8").strip()
          )
        except Exception:
          pass

        vps_list.append({
            "name": repo.name,
            "url": repo.html_url,
            "link": link,
            "created_at": repo.created_at.timestamp(),
        })

    return jsonify({"success": True, "vps": vps_list})
  except Exception as e:
    return jsonify({"success": False, "error": str(e)})


@app.route("/api/create", methods=["POST"])
def create_vps():
  try:
    data = request.json or {}
    custom_name = data.get("name", "vps").strip().lower()
    token = data.get("token", "").strip() or DEFAULT_GITHUB_TOKEN

    if not token:
      return jsonify(
          {"success": False, "error": "Vui lòng nhập GitHub Token hợp lệ!"}
      )

    safe_name = "".join(
        c if c.isalnum() or c == "-" else "-" for c in custom_name
    )
    repo_name = f"vps-{safe_name}-{int(time.time())}"

    g = Github(token)
    user = g.get_user()

    repo = user.create_repo(
        name=repo_name,
        private=False,
        auto_init=True,
        description=f"VPS Manager: {custom_name}",
    )
    time.sleep(3)

    repo.create_secret("GH_TOKEN", token)
    repo.create_file(
        ".github/workflows/tmate.yml",
        "Add workflow",
        generate_workflow(repo_name),
        branch="main",
    )

    try:
      workflow = repo.get_workflow("tmate.yml")
      workflow.create_dispatch("main")
    except Exception:
      pass

    return jsonify({
        "success": True,
        "message": f"Khởi tạo thành công VPS: {repo_name}",
    })
  except Exception as e:
    return jsonify({"success": False, "error": str(e)})


if __name__ == "__main__":
  app.run()