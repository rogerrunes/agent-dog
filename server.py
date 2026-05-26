#!/usr/bin/env python3
"""
Agent DOG — API server
Serves live agent state to the React dashboard.
Run with: python server.py
"""

import json
import os
from flask import Flask, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

STATE_FILE = "/tmp/agent_dog_state.json"

@app.route("/api/state")
def state():
    try:
        with open(STATE_FILE) as f:
            return jsonify(json.load(f))
    except FileNotFoundError:
        return jsonify({"error": "Agent not running yet. Start agent.py first."})
    except Exception as e:
        return jsonify({"error": str(e)})

@app.route("/api/health")
def health():
    return jsonify({"status": "ok", "state_file": os.path.exists(STATE_FILE)})

if __name__ == "__main__":
    print("🌐 Agent DOG API server running on http://localhost:3001")
    app.run(port=3001, debug=False)
