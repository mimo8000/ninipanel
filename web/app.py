from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, Response
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from core.models import db, User, Client, Inbound, ServerConfig
from core.config import *
from core.xray_config import generate_xray_config, generate_config_uri, generate_subscription
import bcrypt
import datetime
import json

app = Flask(__name__)
app.config['SECRET_KEY'] = SECRET_KEY
app.config['SQLALCHEMY_DATABASE_URI'] = SQLALCHEMY_DATABASE_URI
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# ═══════════════════════════════════════
#  AUTH
# ═══════════════════════════════════════

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter_by(username=username).first()
        if user and bcrypt.checkpw(password.encode(), user.password_hash.encode()):
            login_user(user)
            return redirect(url_for('dashboard'))
        flash('نام کاربری یا رمز عبور اشتباه است', 'error')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

# ═══════════════════════════════════════
#  DASHBOARD
# ═══════════════════════════════════════

@app.route('/')
@login_required
def dashboard():
    clients = Client.query.all()
    inbounds = Inbound.query.all()
    total_clients = len(clients)
    active_clients = len([c for c in clients if c.enable and not c.is_expired])
    total_upload = sum(c.upload for c in clients)
    total_download = sum(c.download for c in clients)

    def fmt_bytes(b):
        if b < 1024**2:
            return f"{b/1024:.1f} KB"
        elif b < 1024**3:
            return f"{b/1024**2:.1f} MB"
        return f"{b/1024**3:.2f} GB"

    return render_template('dashboard.html',
        total_clients=total_clients,
        active_clients=active_clients,
        total_upload=fmt_bytes(total_upload),
        total_download=fmt_bytes(total_download),
        inbounds=inbounds,
        panel_name=PANEL_NAME,
    )

# ═══════════════════════════════════════
#  CLIENTS
# ═══════════════════════════════════════

@app.route('/clients')
@login_required
def clients_list():
    clients = Client.query.all()
    return render_template('clients.html', clients=clients, panel_name=PANEL_NAME)

@app.route('/clients/add', methods=['GET', 'POST'])
@login_required
def client_add():
    if request.method == 'POST':
        email = request.form.get('email')
        protocol = request.form.get('protocol', 'vless')
        inbound_tag = request.form.get('inbound_tag', 'vless-ws')
        limit_ip = int(request.form.get('limit_ip', 2))
        total_gb = int(request.form.get('total', 0)) * 1024**3
        expiry_days = int(request.form.get('expiry', 0))
        note = request.form.get('note', '')

        expiry_time = 0
        if expiry_days > 0:
            expiry_time = int((datetime.datetime.utcnow() + datetime.timedelta(days=expiry_days)).timestamp())

        client = Client(
            email=email,
            protocol=protocol,
            inbound_tag=inbound_tag,
            limit_ip=limit_ip,
            total=total_gb,
            expiry_time=expiry_time,
            note=note,
        )
        db.session.add(client)
        db.session.commit()
        flash(f'کاربر {email} اضافه شد ✅', 'success')
        return redirect(url_for('clients_list'))

    inbounds = Inbound.query.all()
    return render_template('client_add.html', inbounds=inbounds, panel_name=PANEL_NAME)

@app.route('/clients/<int:id>/delete', methods=['POST'])
@login_required
def client_delete(id):
    client = Client.query.get_or_404(id)
    db.session.delete(client)
    db.session.commit()
    flash(f'کاربر {client.email} حذف شد', 'success')
    return redirect(url_for('clients_list'))

@app.route('/clients/<int:id>/toggle', methods=['POST'])
@login_required
def client_toggle(id):
    client = Client.query.get_or_404(id)
    client.enable = not client.enable
    db.session.commit()
    status = "فعال" if client.enable else "غیرفعال"
    flash(f'کاربر {client.email} {status} شد', 'success')
    return redirect(url_for('clients_list'))

@app.route('/clients/<int:id>/config')
@login_required
def client_config(id):
    client = Client.query.get_or_404(id)
    link = generate_config_uri(
        protocol=client.protocol,
        server=request.host.split(':')[0],
        port=443,
        uuid_str=client.uuid,
        email=client.email,
        flow=client.flow,
    )
    return render_template('client_config.html', client=client, link=link, panel_name=PANEL_NAME)

@app.route('/clients/<int:id>/reset', methods=['POST'])
@login_required
def client_reset(id):
    client = Client.query.get_or_404(id)
    client.upload = 0
    client.download = 0
    db.session.commit()
    flash(f'ترافیک {client.email} ریست شد', 'success')
    return redirect(url_for('clients_list'))

# ═══════════════════════════════════════
#  SUBSCRIPTION API
# ═══════════════════════════════════════

@app.route('/sub/<token>')
def subscription(token):
    """Subscription link - returns config list"""
    client = Client.query.filter_by(uuid=token).first()
    if not client or not client.enable or client.is_expired:
        return Response("Forbidden", status=403)

    link = generate_config_uri(
        protocol=client.protocol,
        server=request.host.split(':')[0],
        port=443,
        uuid_str=client.uuid,
        email=client.email,
        flow=client.flow,
    )

    return Response(link, mimetype='text/plain', headers={
        'Content-Disposition': f'attachment; filename="{client.email}.txt"',
        'Subscription-Userinfo': f'upload={client.upload};download={client.download};total={client.total};expire={client.expiry_time}',
    })

@app.route('/sub/<token>/info')
def subscription_info(token):
    """Client info JSON"""
    client = Client.query.filter_by(uuid=token).first()
    if not client:
        return jsonify({"error": "not found"}), 404
    return jsonify({
        "email": client.email,
        "protocol": client.protocol,
        "enable": client.enable,
        "expired": client.is_expired,
        "upload": client.upload,
        "download": client.download,
        "total": client.total,
        "expiry_time": client.expiry_time,
    })

# ═══════════════════════════════════════
#  SETTINGS
# ═══════════════════════════════════════

@app.route('/settings')
@login_required
def settings():
    inbounds = Inbound.query.all()
    return render_template('settings.html', inbounds=inbounds, panel_name=PANEL_NAME)

@app.route('/settings/inbound/add', methods=['POST'])
@login_required
def inbound_add():
    tag = request.form.get('tag')
    protocol = request.form.get('protocol')
    port = int(request.form.get('port', 443))
    network = request.form.get('network', 'ws')
    security = request.form.get('security', 'none')

    inbound = Inbound(tag=tag, protocol=protocol, port=port, network=network, security=security)
    db.session.add(inbound)
    db.session.commit()
    flash(f'Inbound {tag} اضافه شد ✅', 'success')
    return redirect(url_for('settings'))

@app.route('/settings/inbound/<int:id>/delete', methods=['POST'])
@login_required
def inbound_delete(id):
    inbound = Inbound.query.get_or_404(id)
    db.session.delete(inbound)
    db.session.commit()
    flash(f'Inbound {inbound.tag} حذف شد', 'success')
    return redirect(url_for('settings'))

@app.route('/api/clients')
@login_required
def api_clients():
    clients = Client.query.all()
    return jsonify([{
        "id": c.id, "email": c.email, "protocol": c.protocol,
        "enable": c.enable, "expired": c.is_expired,
        "upload": c.upload, "download": c.download,
        "total": c.total, "expiry": c.expiry_display,
        "traffic": c.traffic_display,
    } for c in clients])

# ═══════════════════════════════════════
#  INIT
# ═══════════════════════════════════════

def init_db():
    with app.app_context():
        db.create_all()
        if not User.query.first():
            admin = User(
                username='admin',
                password_hash=bcrypt.hashpw('admin'.encode(), bcrypt.gensalt()).decode(),
                is_admin=True
            )
            db.session.add(admin)
            # Default inbounds
            for inf in DEFAULT_INBOUNDS:
                inbound = Inbound(
                    tag=inf["tag"], protocol=inf["protocol"],
                    port=inf["port"], network=inf["network"]
                )
                db.session.add(inbound)
            db.session.commit()
            print("✅ Database initialized with admin/admin")

if __name__ == '__main__':
    init_db()
    app.run(host='0.0.0.0', port=5000, debug=True)
