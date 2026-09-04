import json
import uuid
import base64

def generate_xray_config(inbounds, clients):
    """Generate full xray config JSON"""
    config = {
        "log": {"loglevel": "warning"},
        "routing": {
            "domainStrategy": "AsIs",
            "rules": [
                {
                    "type": "field",
                    "inboundTag": ["api"],
                    "outboundTag": "api"
                }
            ]
        },
        "inbounds": [
            {
                "tag": "api",
                "listen": "127.0.0.1",
                "port": 62789,
                "protocol": "dokodemo-door",
                "settings": {"address": "127.0.0.1"}
            }
        ],
        "outbounds": [
            {"protocol": "freedom", "tag": "direct"},
            {"protocol": "blackhole", "tag": "block"}
        ]
    }

    for inbound in inbounds:
        if not inbound.get("enable", True):
            continue

        xray_in = {
            "tag": inbound["tag"],
            "port": inbound["port"],
            "protocol": inbound["protocol"],
            "settings": {"clients": []},
            "streamSettings": {"network": inbound.get("network", "tcp")}
        }

        # Add clients for this inbound
        for client in clients:
            if client.inbound_tag == inbound["tag"] and client.enable and not client.is_expired:
                client_config = {
                    "id": str(client.uuid),
                    "email": client.email,
                    "flow": client.flow or ""
                }
                # Remove empty flow
                if not client_config["flow"]:
                    del client_config["flow"]
                xray_in["settings"]["clients"].append(client_config)

        # Stream settings based on protocol
        network = inbound.get("network", "tcp")
        if network == "ws":
            xray_in["streamSettings"] = {
                "network": "ws",
                "wsSettings": {
                    "path": f"/{inbound['tag']}"
                }
            }
        elif network == "grpc":
            xray_in["streamSettings"] = {
                "network": "grpc",
                "grpcSettings": {
                    "serviceName": inbound["tag"]
                }
            }
        elif network == "h2":
            xray_in["streamSettings"] = {
                "network": "h2",
                "httpSettings": {
                    "path": f"/{inbound['tag']}"
                }
            }

        # Security
        security = inbound.get("security", "none")
        if security == "tls":
            xray_in["streamSettings"]["security"] = "tls"
            xray_in["streamSettings"]["tlsSettings"] = {
                "certificates": [
                    {
                        "certificateFile": "/etc/letsencrypt/live/domain/fullchain.pem",
                        "keyFile": "/etc/letsencrypt/live/domain/privkey.pem"
                    }
                ]
            }

        config["inbounds"].append(xray_in)

    return config


def generate_config_uri(protocol, server, port, uuid_str, email, network="ws", security="none", sni="", flow="", path=""):
    """Generate connection URI for different protocols"""
    uuid_str = str(uuid_str) if isinstance(uuid_str, uuid.UUID) else uuid_str

    if protocol == "vless":
        params = f"?encryption=none&security={security}&type={network}"
        if network == "ws":
            params += f"&path={path or f'/{email}'}"
        if security == "tls" and sni:
            params += f"&sni={sni}"
        if flow:
            params += f"&flow={flow}"
        return f"vless://{uuid_str}@{server}:{port}{params}#{email}"

    elif protocol == "vmess":
        vmess_config = {
            "v": "2",
            "ps": email,
            "add": server,
            "port": str(port),
            "id": uuid_str,
            "aid": "0",
            "scy": "auto",
            "net": network,
            "type": "none",
            "host": "",
            "path": path or f"/{email}",
            "tls": security
        }
        encoded = base64.b64encode(json.dumps(vmess_config).encode()).decode()
        return f"vmess://{encoded}"

    elif protocol == "trojan":
        params = f"?security={security}&type={network}"
        if network == "ws":
            params += f"&path={path or f'/{email}'}"
        if security == "tls" and sni:
            params += f"&sni={sni}"
        return f"trojan://{uuid_str}@{server}:{port}{params}#{email}"

    elif protocol == "shadowsocks":
        method = "chacha20-ietf-poly1305"
        part = base64.b64encode(f"{method}:{uuid_str}".encode()).decode()
        return f"ss://{part}@{server}:{port}#{email}"

    elif protocol == "hysteria2":
        params = f"?security={security}"
        if security == "tls" and sni:
            params += f"&sni={sni}"
        return f"hysteria2://{uuid_str}@{server}:{port}{params}#{email}"

    return ""


def generate_subscription(clients, server, base_url):
    """Generate subscription link content"""
    links = []
    for client in clients:
        if client.enable and not client.is_expired:
            link = generate_config_uri(
                protocol=client.protocol,
                server=server,
                port=443,
                uuid_str=client.uuid,
                email=client.email,
                flow=client.flow
            )
            if link:
                links.append(link)
    return "\n".join(links)
