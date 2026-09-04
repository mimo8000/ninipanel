import os

SECRET_KEY = os.getenv("SECRET_KEY", "ninipanel-secret-key-change-me")
SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL", "sqlite:///ninipanel.db")
SQLALCHEMY_TRACK_MODIFICATIONS = False

# Panel Settings
PANEL_NAME = "NiniPanel"
PANEL_VERSION = "1.0.0"

# Telegram Bot
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_ADMIN_ID = os.getenv("TELEGRAM_ADMIN_ID", "")

# Xray Core
XRAY_CORE_PATH = os.getenv("XRAY_CORE_PATH", "/usr/local/bin/xray")
XRAY_CONFIG_PATH = os.getenv("XRAY_CONFIG_PATH", "/usr/local/etc/xray/config.json")

# Subscription
SUB_BASE_URL = os.getenv("SUB_BASE_URL", "http://localhost:5000")

# Inbounds (default)
DEFAULT_INBOUNDS = [
    {"tag": "vless-ws", "protocol": "vless", "port": 443, "network": "ws"},
    {"tag": "vmess-ws", "protocol": "vmess", "port": 444, "network": "ws"},
    {"tag": "trojan-ws", "protocol": "trojan", "port": 445, "network": "ws"},
    {"tag": "hysteria2", "protocol": "hysteria2", "port": 8443, "network": "udp"},
]
