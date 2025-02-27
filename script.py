from flask import Flask, request, jsonify
import json
import requests

app = Flask(__name__)

BITBUCKET_USERNAME = "ton_username"
BITBUCKET_TOKEN = "ton_token"
WORKSPACE = "ton_workspace"

def create_repo(app_name):
    url = f"https://api.bitbucket.org/2.0/repositories/{WORKSPACE}/{app_name}"
    headers = {"Content-Type": "application/json"}
    auth = (BITBUCKET_USERNAME, BITBUCKET_TOKEN)
    data = json.dumps({"scm": "git", "is_private": True})
    
    response = requests.post(url, headers=headers, auth=auth, data=data)
    return response.status_code

@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.json
    changes = data.get("push", {}).get("changes", [])

    for change in changes:
        for commit in change.get("commits", []):
            modified_files = commit.get("files", [])
            
            for file in modified_files:
                if file["path"] == "apps.json":
                    # Charger le fichier et extraire les nouvelles apps
                    with open("apps.json", "r") as f:
                        apps = json.load(f).get("applications", [])
                    
                    for app in apps:
                        create_repo(app)

    return jsonify({"message": "Webhook reçu !"}), 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
