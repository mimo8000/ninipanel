from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
import uuid
import datetime

db = SQLAlchemy()

class User(UserMixin, db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)

class Client(db.Model):
    __tablename__ = 'clients'
    id = db.Column(db.Integer, primary_key=True)
    uuid = db.Column(db.String(36), default=lambda: str(uuid.uuid4()), unique=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    telegram_id = db.Column(db.String(50), nullable=True)
    protocol = db.Column(db.String(20), default='vless')
    inbound_tag = db.Column(db.String(50), default='vless-ws')
    enable = db.Column(db.Boolean, default=True)
    expiry_time = db.Column(db.BigInteger, default=0)  # timestamp
    flow = db.Column(db.String(100), default='')
    limit_ip = db.Column(db.Integer, default=2)
    upload = db.Column(db.BigInteger, default=0)
    download = db.Column(db.BigInteger, default=0)
    total = db.Column(db.BigInteger, default=0)  # total traffic in bytes
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    note = db.Column(db.Text, default='')

    @property
    def is_expired(self):
        if self.expiry_time == 0:
            return False
        return datetime.datetime.utcnow().timestamp() > self.expiry_time

    @property
    def traffic_used(self):
        return self.upload + self.download

    @property
    def traffic_display(self):
        used = self.traffic_used
        if used < 1024**2:
            return f"{used/1024:.1f} KB"
        elif used < 1024**3:
            return f"{used/1024**2:.1f} MB"
        else:
            return f"{used/1024**3:.2f} GB"

    @property
    def total_display(self):
        if self.total == 0:
            return "∞ نامحدود"
        t = self.total
        if t < 1024**3:
            return f"{t/1024**2:.0f} MB"
        return f"{t/1024**3:.1f} GB"

    @property
    def expiry_display(self):
        if self.expiry_time == 0:
            return "∞ نامحدود"
        exp = datetime.datetime.fromtimestamp(self.expiry_time)
        if exp < datetime.datetime.utcnow():
            return "⏰ منقضی شده"
        diff = exp - datetime.datetime.utcnow()
        days = diff.days
        if days > 30:
            return f"{days//30} ماه"
        return f"{days} روز"


class Inbound(db.Model):
    __tablename__ = 'inbounds'
    id = db.Column(db.Integer, primary_key=True)
    tag = db.Column(db.String(50), unique=True, nullable=False)
    protocol = db.Column(db.String(20), nullable=False)
    port = db.Column(db.Integer, nullable=False)
    network = db.Column(db.String(20), default='tcp')
    security = db.Column(db.String(20), default='none')
    enable = db.Column(db.Boolean, default=True)
    settings = db.Column(db.JSON, default=dict)
    stream_settings = db.Column(db.JSON, default=dict)


class ServerConfig(db.Model):
    __tablename__ = 'server_config'
    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(50), unique=True, nullable=False)
    value = db.Column(db.Text, default='')
