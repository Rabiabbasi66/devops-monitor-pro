import argparse
import json
import logging
import os
import time

import requests

from config import settings
from collectors import (
    collect_cpu,
    collect_disk,
    collect_memory,
    collect_network,
    collect_processes,
    collect_system,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger("monitoring-agent")

CONFIG_FILE = "agent_config.json"


def load_config():
    """Load agent configuration from file if exists."""
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r') as f:
                config = json.load(f)
                logger.info("Loaded configuration from agent_config.json")
                return config
        except Exception as e:
            logger.warning(f"Failed to load config file: {e}")
    return None


def save_config(config):
    """Save agent configuration to file."""
    try:
        with open(CONFIG_FILE, 'w') as f:
            json.dump(config, f, indent=2)
        logger.info("Configuration saved to agent_config.json")
    except Exception as e:
        logger.error(f"Failed to save config file: {e}")


def enroll_agent(enrollment_token):
    """Enroll agent using enrollment token."""
    api_url = settings.API_URL.rstrip('/')
    url = f"{api_url}/agents/enroll"
    
    logger.info("Enrolling agent...")
    response = requests.post(url, json={"enrollment_token": enrollment_token}, timeout=30)
    
    if response.status_code == 200:
        data = response.json()
        config = {
            "server_id": data["server_id"],
            "agent_token": data["agent_token"],
            "api_url": data["api_url"],
            "interval_seconds": data.get("interval_seconds", 30)
        }
        save_config(config)
        logger.info("Agent enrolled successfully")
        return config
    else:
        logger.error(f"Enrollment failed: HTTP {response.status_code}")
        raise SystemExit("Agent enrollment failed")


def collect_all() -> dict:
    memory = collect_memory()
    disk = collect_disk()
    network = collect_network()
    system = collect_system()
    return {
        "server_id": settings.SERVER_ID,
        "cpu_usage": collect_cpu(),
        **memory,
        **disk,
        "network_sent": network["network_sent"],
        "network_received": network["network_received"],
        **system,
        "process_count": collect_processes(),
    }


def send_metrics(payload: dict, api_url, agent_token) -> bool:
    url = f"{api_url.rstrip('/')}/monitoring/metrics"
    headers = {"X-Agent-Token": agent_token, "Content-Type": "application/json"}
    response = requests.post(url, json=payload, headers=headers, timeout=15)
    if response.status_code == 200:
        logger.info("Metrics sent successfully")
        return True
    logger.error("Failed to send metrics: %s %s", response.status_code, response.text)
    return False


def main():
    parser = argparse.ArgumentParser(description="DevOps Monitor Pro Agent")
    parser.add_argument("--enroll", help="Enrollment token for automatic agent setup")
    args = parser.parse_args()
    
    # Handle enrollment
    if args.enroll:
        config = enroll_agent(args.enroll)
        # Use enrolled config
        server_id = config["server_id"]
        agent_token = config["agent_token"]
        api_url = config["api_url"]
        interval = config.get("interval_seconds", 30)
    else:
        # Try to load from config file first
        config = load_config()
        if config:
            server_id = config["server_id"]
            agent_token = config["agent_token"]
            api_url = config["api_url"]
            interval = config.get("interval_seconds", 30)
        else:
            # Fall back to environment variables
            if not settings.SERVER_ID or not settings.AGENT_TOKEN:
                raise SystemExit(
                    "SERVER_ID and AGENT_TOKEN must be set in environment, .env, or use --enroll token"
                )
            server_id = settings.SERVER_ID
            agent_token = settings.AGENT_TOKEN
            api_url = settings.API_URL
            interval = settings.INTERVAL_SECONDS
    
    logger.info("Starting monitoring agent for server %s", server_id)
    while True:
        try:
            payload = collect_all()
            payload["server_id"] = server_id
            send_metrics(payload, api_url, agent_token)
        except Exception:
            logger.exception("Agent loop error")
        time.sleep(interval)


if __name__ == "__main__":
    main()

