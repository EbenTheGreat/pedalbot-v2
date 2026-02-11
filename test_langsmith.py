
import os
import socket
import requests
from langsmith import Client
from dotenv import load_dotenv

load_dotenv()

def check_dns():
    hostname = "api.smith.langchain.com"
    print(f"Checking DNS for {hostname}...")
    try:
        ip = socket.gethostbyname(hostname)
        print(f"✅ DNS Resolved: {hostname} -> {ip}")
        return True
    except Exception as e:
        print(f"❌ DNS Failed: {e}")
        return False

def check_http():
    url = "https://api.smith.langchain.com/info"
    print(f"Checking HTTP GET to {url}...")
    try:
        resp = requests.get(url, timeout=5)
        print(f"✅ HTTP Status: {resp.status_code}")
        print(f"Response: {resp.text[:100]}...")
        return True
    except Exception as e:
        print(f"❌ HTTP Failed: {e}")
        return False

def check_langsmith_client():
    print("Checking LangSmith Client...")
    try:
        client = Client()
        # Just listing projects or checking generic connectivity
        projects = list(client.list_projects(limit=1))
        print(f"✅ LangSmith Client Connected. Found {len(projects)} projects.")
        if projects:
            print(f"   Sample Project: {projects[0].name}")
        return True
    except Exception as e:
        print(f"❌ LangSmith Client Failed: {e}")
        return False

if __name__ == "__main__":
    print("--- DIAGNOSTICS START ---")
    dns_ok = check_dns()
    if dns_ok:
        http_ok = check_http()
        if http_ok:
            check_langsmith_client()
    print("--- DIAGNOSTICS END ---")
