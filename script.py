import json
import requests
import git
import os
from flask import Flask, request, jsonify
import urllib3
import urllib

# Disable SSL warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

app = Flask(__name__)
BITBUCKET_USERNAME = os.getenv("BITBUCKET_USERNAME")
BITBUCKET_TOKEN = os.getenv("BITBUCKET_TOKEN")
WORKSPACE = "NNAA"
REPO_SOURCE = "Applications"
BRANCHE_APP = "feature/applications"
FILE_NAME = "listApplications"
REPO_JOB = "nnap-jjd"
REPO_OWNER_JOB = "NNAP"
BRANCHE_JOB = "feature/ITNP-125794"
FILE_PATH_1 = "configurations/jobs/standardAppTerraformPipelineJob.json"
FILE_PATH_2 = "configurations/jobs/standardMultibranchPipelineJob.json"
LOCAL_REPO_PATH = "/tmp/nnap-jjd" 
def setup_git_credentials():
    """Create a .netrc file to store Git credentials dynamically"""
    home = os.path.expanduser("~")
    netrc_path = os.path.join(home, ".netrc")

    with open(netrc_path, "w") as f:
        f.write(f"machine dsu-bitbucket.nestle.biz\n")
        f.write(f"login {BITBUCKET_USERNAME}\n")
        f.write(f"password {BITBUCKET_TOKEN}\n")

    os.chmod(netrc_path, 0o600)  # Restrict file permissions
    print("✅ Git credentials configured.")

setup_git_credentials()

def clone_or_pull_repo():
    """ Clone the repository if it does not exist, otherwise update it """
    setup_git_credentials()
    if os.path.exists(LOCAL_REPO_PATH):
        print("Updating local repository...")
        repo = git.Repo(LOCAL_REPO_PATH)
        repo.git.fetch("origin")
        repo.git.checkout(BRANCHE_JOB)
        repo.git.pull("origin", BRANCHE_JOB)
    else:
        print("Cloning the repository...")
        url = f"https://dsu-bitbucket.nestle.biz/scm/{REPO_OWNER_JOB}/{REPO_JOB}.git"

        # 🔥 Fix encoding for special characters
        url = urllib.parse.quote(url, safe=":/@")

        print("Using URL:", url)  # Debugging
        git.Repo.clone_from(url, LOCAL_REPO_PATH)
        repo = git.Repo(LOCAL_REPO_PATH)
        repo.git.checkout(BRANCHE_JOB)

def update_file(file_path, new_content):
    """ Update a JSON file in the local repository """
    file_full_path = os.path.join(LOCAL_REPO_PATH, file_path)
    if not os.path.exists(file_full_path):
        print(f"⚠️ File {file_path} does not exist.")
        return False
    
    with open(file_full_path, "w") as f:
        json.dump(new_content, f, indent=4)
    
    print(f"✅ File {file_path} updated locally.")
    return True

def commit_and_push_changes():
    """Commit and push changes to Bitbucket"""
    try:
        repo = git.Repo(LOCAL_REPO_PATH)
        # Set Git user identity locally for this repository
        repo.git.config("user.name", "najeh")
        repo.git.config("user.email", BITBUCKET_USERNAME)
        
        repo.git.add(".")
        repo.git.commit("-m", "Updated JSON files via script")
        repo.git.push("origin", BRANCHE_JOB)
        print("🚀 Changes pushed to Bitbucket!")
    except Exception as e:
        print("❌ Error committing and pushing changes:", str(e))
        raise



def update_pipeline_files(app_name):
    """ Modify and push JSON files with new information """
    clone_or_pull_repo()
    
    # Load and modify JSON files
    file_1_path = os.path.join(LOCAL_REPO_PATH, FILE_PATH_1)
    file_2_path = os.path.join(LOCAL_REPO_PATH, FILE_PATH_2)
    
    with open(file_1_path, "r") as f1, open(file_2_path, "r") as f2:
        file_1_content = json.load(f1)
        file_2_content = json.load(f2)
    
    new_entry_1 = {
        "repoName": app_name,
        "jobName": f"nnap-app/{app_name}",
        "repoOwner": "NNAP",
        "repository": "nnap-pipelines",
        "scriptPath": "pipelines/terraform/terraformAppPlanApply.groovy",
        "branch": "master"
    }
    file_1_content.get("jobs", []).append(new_entry_1)
    
    new_entries_2 = [
    {"jobName": f"dyn-selection/{app_name}", "repoOwner": "NNAA", "repository": f"{app_name}-config", "scriptPath": "Jenkinsfile"},
    {"jobName": f"nnap-gitops/{app_name}-config", "repoOwner": "NNAA", "repository": f"{app_name}-config", "scriptPath": "Jenkinsfile.auto"},
    {"jobName": f"nnap-gitops/{app_name}", "repoOwner": "NNAA", "repository": app_name, "scriptPath": "Jenkinsfile.auto"}
    ]
    
    file_2_content.get("jobs", []).extend(new_entries_2)
    
    if update_file(FILE_PATH_1, file_1_content) and update_file(FILE_PATH_2, file_2_content):
        commit_and_push_changes()

def get_apps_json():
    """ Retrieve the apps.json file from Bitbucket """
    url = f"https://dsu-bitbucket.nestle.biz/rest/api/1.0/projects/{WORKSPACE}/repos/{REPO_SOURCE}/raw/{FILE_NAME}.json?at={BRANCHE_APP}"
    auth = (BITBUCKET_USERNAME, BITBUCKET_TOKEN)
    response = requests.get(url, auth=auth, verify=False)
    
    if response.status_code == 200:
        print("✅ apps.json successfully retrieved!")
        return response.json()
    else:
        print(f"❌ Error retrieving listApplications.json ({response.status_code}): {response.text}")
        return None

def create_repo(app_name):
    """ Create a new repository in Bitbucket """
    url = f"https://dsu-bitbucket.nestle.biz/rest/api/1.0/projects/{WORKSPACE}/repos"
    headers = {"Content-Type": "application/json"}
    auth = (BITBUCKET_USERNAME, BITBUCKET_TOKEN)
    data = json.dumps({"name": app_name, "scmId": "git", "forkable": True})

    response = requests.post(url, headers=headers, auth=auth, data=data, verify=False)

    if response.status_code == 201:
        print(f"✅ Repository '{app_name}' successfully created!")
        return True
    elif response.status_code == 409:  # Error 409 = Repository already exists
        print(f"⚠️ Repository '{app_name}' already exists.")
        return False
    else:
        print(f"❌ Error creating repository '{app_name}' ({response.status_code}): {response.text}")
        return False

def create_repo_if_not_exists(app_name):
    """ Create a repository if it does not already exist """
    url = f"https://dsu-bitbucket.nestle.biz/rest/api/1.0/projects/{WORKSPACE}/repos/{app_name}"
    auth = (BITBUCKET_USERNAME, BITBUCKET_TOKEN)

    response = requests.get(url, auth=auth, verify=False)

    if response.status_code == 200:
        print(f"⚠️ Repository '{app_name}' already exists.")
        return False  # The repository already exists, do not create it again
    elif response.status_code == 404:
        # Repository does not exist, so create a new one
        return create_repo(app_name)
    else:
        print(f"❌ Error checking existence of repository '{app_name}' ({response.status_code}): {response.text}")
        return False

@app.route("/", methods=["GET"])
def home():
    return "Welcome to the webhook API!"

@app.route("/webhook", methods=["POST"])
def webhook():
    print("📩 Webhook received!")
    apps_data = get_apps_json()
    
    if apps_data:
        apps = apps_data.get("listApplications", [])
        print(f"🔍 {len(apps)} applications found in listApplications.json.")
        
        for app in apps: 
            appconfig = f"{app}-config"
            create_repo_if_not_exists(appconfig)
            repo_created = create_repo_if_not_exists(app)
            if repo_created:
                update_pipeline_files(app)
    
    return jsonify({"message": "Webhook received and processed!"}), 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
