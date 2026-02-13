# 删除旧的端口代理规则
netsh interface portproxy delete v4tov4 listenport=8000 listenaddress=0.0.0.0

# 获取 WSL 的 IP 地址
$wslIp = (wsl hostname -I).Trim().Split(" ")[0]

# 添加新的端口代理规则
netsh interface portproxy add v4tov4 listenaddress=0.0.0.0 listenport=8000 connectaddress=$wslIp connectport=8000
