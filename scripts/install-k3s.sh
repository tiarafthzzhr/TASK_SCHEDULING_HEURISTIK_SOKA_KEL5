#!/usr/bin/env bash
# Run in Ubuntu WSL only after mirrored networking TCP/UDP checks pass both ways.
set -euo pipefail
role=${1:?"Usage: install-k3s.sh server|agent NODE_WIFI_IP [SERVER_WIFI_IP]"}
node_ip=${2:?"Provide this laptop's mirrored Wi-Fi IPv4 address"}
server_ip=${3:-}
[[ "$role" == server || "$role" == agent ]] || { echo 'Role must be server or agent'; exit 1; }
[[ $EUID == 0 ]] || { echo 'Run using sudo bash scripts/install-k3s.sh ...'; exit 1; }
[[ $(cat /proc/1/comm) == systemd ]] || { echo 'Enable systemd in WSL first'; exit 1; }
if [[ -e /etc/systemd/system/k3s.service || -e /etc/systemd/system/k3s-agent.service ]]; then
    echo 'Existing K3s service found. Inspect it manually; this script will not overwrite it.'
    exit 1
fi
node_iface=$(ip -j addr | python3 -c 'import sys,json; ip=sys.argv[1]; matches=[x["ifname"] for x in json.load(sys.stdin) if any(a.get("local")==ip for a in x.get("addr_info",[]))]; assert len(matches)==1,"IP not present inside WSL; fix mirrored networking"; print(matches[0])' "$node_ip")
docker_os=$(docker info --format '{{.OperatingSystem}}')
[[ "$docker_os" != *'Docker Desktop'* ]] || { echo 'Use native Docker Engine inside this WSL distro, not the Docker Desktop shared engine.'; exit 1; }
if [[ "$role" == agent && ( -z "$server_ip" || -z "${INSTALL_K3S_VERSION:-}" ) ]]; then
    echo 'Agent requires server IP and INSTALL_K3S_VERSION matching the server.'
    exit 1
fi
installer=$(mktemp)
trap 'rm -f "$installer"' EXIT
curl -fsSL https://get.k3s.io -o "$installer"
if [[ "$role" == server ]]; then
    INSTALL_K3S_CHANNEL=stable sh "$installer" server --docker \
        --node-name soka-master --node-ip "$node_ip" --node-external-ip "$node_ip" \
        --advertise-address "$node_ip" --tls-san "$node_ip" \
        --flannel-iface "$node_iface" --node-label soka.lab/host=host1 \
        --disable traefik --disable servicelb
else
    read -rsp 'Paste server node-token (hidden): ' K3S_TOKEN
    echo
    export K3S_TOKEN
    K3S_URL="https://$server_ip:6443" sh "$installer" agent --docker \
        --node-name soka-worker --node-ip "$node_ip" --node-external-ip "$node_ip" \
        --flannel-iface "$node_iface" --node-label soka.lab/host=host2
    unset K3S_TOKEN
fi
