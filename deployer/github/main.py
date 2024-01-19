import io
import json
import os
import zipfile
from time import sleep

import requests
from celery import Celery
from decouple import config
from flask import Flask, abort, request
from prometheus_client import generate_latest

import observability
from metrics import define_metrics

# Configuration
GITHUB_TOKEN = config('GITHUB_TOKEN')
RESPONDER_HOST = config('RESPONDER_HOST')
CELERY_BACKEND = config('CELERY_BACKEND')
CELERY_BROKER = config('CELERY_BROKER')

# Constants
MAX_POLL_ATTEMPTS = 10

# Flask App
app = Flask(__name__)
trace = observability.setup(flask_app=app, requests_enabled=True)

# Celery
tasks = Celery("tasks", backend=CELERY_BACKEND, broker=CELERY_BROKER)
define_metrics(tasks)

# Helper Function to Handle HTTP Requests
def perform_request(url, method='GET', json_data=None):
    headers = {
        "Accept": "application/vnd.github.v3+json",
        "Authorization": f"Token {GITHUB_TOKEN}",
    }
    if json_data:
        headers["Content-Type"] = "application/json"

    response = requests.request(method, url, headers=headers, json=json_data)
    response.raise_for_status()
    return response

# Class for Deployment
class Deployer:
    def __init__(self, request_data):
        request_data = request_data.get_json()
        required_fields = ["platform", "channel", "thread_ts", "user", "repository", "workflow", "ref", "completion_message", "artifacts_to_read"]
        for field in required_fields:
            if field not in request_data:
                abort(400, f"Missing required field: {field}")
        
        self.__dict__.update(request_data)

    def last_workflow_run(self):
        url = f"https://api.github.com/repos/{self.repository}/actions/runs?per_page=1"
        return perform_request(url).json()

    def deploy(self):
        last_run = self.last_workflow_run()
        last_run_number = last_run["workflow_runs"][0]["run_number"] if last_run["workflow_runs"] else 0

        dispatch_url = f"https://api.github.com/repos/{self.repository}/actions/workflows/{self.workflow}/dispatches"
        perform_request(dispatch_url, method='POST', json={"ref": self.ref})

        found_run_id = False
        for _ in range(MAX_POLL_ATTEMPTS, 0, -1):
            last_run = self.last_workflow_run()
            if last_run["workflow_runs"] and last_run["workflow_runs"][0]["run_number"] > last_run_number:
                found_run_id = True
                self.poll_for_conclusion(last_run["workflow_runs"][0]["id"])
                break
            sleep(0.25)

        if not found_run_id:
            abort(500)

    def poll_for_conclusion(self, run_id):
        run_url = f"https://api.github.com/repos/{self.repository}/actions/runs/{run_id}"
        run_json = perform_request(run_url).json()

        if run_json["conclusion"] is None:
            raise RuntimeError(f"Workflow run {run_id} is still running")

        # ... (rest of the existing code)

# Routes
@app.route("/v1/deploy", methods=["POST"])
def deploy():
    deployer = Deployer(request)
    deployer.deploy()
    return ""

@app.route("/", methods=["GET"])
def health():
    return ""

@app.route("/metrics")
def metrics():
    return generate_latest()
