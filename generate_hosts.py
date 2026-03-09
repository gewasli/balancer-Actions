import requests
import time
import random
import os
import re
from typing import List, Dict, Tuple
from dataclasses import dataclass
from urllib.parse import urlparse

# ===================== 配置项 =====================
# 新的GitHub原始文件地址
GITHUB_RAW_URL = "https://raw.githubusercontent.com/xiaojieonly/Ehviewer_CN_SXJ/refs/heads/BiLi_PC_Gamer/app/src/main/java/com/hippo/ehviewer/client/EhHosts.kt"
# 目标域名（从EhHosts.kt中提取的核心域名）
TARGET_DOMAINS = [
    "e-hentai.org", "repo.e-hentai.org", "forums.e-hentai.org", "upld.e-hentai.org",
    "ehgt.org", "raw.githubusercontent.com", "exhentai.org", "upld.exhentai.org", "s.exhentai.org"
]
# 本地hosts文件路径（Windows/Linux/Mac适配）
HOSTS_PATH = "C:\\Windows\\System32\\drivers\\etc\\hosts" if os.name == "nt" else "/etc/hosts"
# HTTP测速超时时间（秒）
HTTP_TIMEOUT = 3
# 每个IP测速次数（取平均值）
TEST_COUNT = 2
# ===================== 数据结构 =====================
@dataclass
class ProxyIP:
    ip: str
    delay: float = float('inf')  # 延迟（越小越好）
    available: bool = False      # 是否可用

# ===================== 步骤1：拉取GitHub中的IP列表（过滤IPv6） =====================
def fetch_ip_list_from_github() -> List[str]:
    """从GitHub的EhHosts.kt文件中提取IPv4列表（过滤IPv6和注释）"""
    try:
        # 添加请求头避免403
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        response = requests.get(GITHUB_RAW_URL, headers=headers, timeout=10)
        response.raise_for_status()
        content = response.text

        # 1. 移除注释内容
        content = re.sub(r'//.*?$', '', content, flags=re.MULTILINE)
        # 2. 匹配IPv4（过滤IPv6）
        ip_pattern = re.compile(r'"(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})"')
        ip_list = ip_pattern.findall(content)
        
        # 去重 + 过滤无效IP
        ip_list = list(set(ip_list))
        valid_ips = []
        for ip in ip_list:
            parts = ip.split('.')
            if len(parts) == 4 and all(0 <= int(part) <= 255 for part in parts):
                valid_ips.append(ip)
        
        if not valid_ips:
            raise ValueError("未从EhHosts.kt中提取到有效IPv4")
        print(f"成功提取IP列表（去重后）：{valid_ips}")
        print(f"共提取 {len(valid_ips)} 个有效IPv4")
        return valid_ips
    except Exception as e:
        print(f"拉取IP失败：{str(e)}")
        return []

# ===================== 步骤2：HTTP测速（替代ping，无需root权限） =====================
def http_ping(ip: str, test_domain: str = "e-hentai.org") -> float:
    """
    HTTP测速（替代ICMP ping）
    :param ip: 要测试的IP
    :param test_domain: 目标域名（用于构造请求）
    :return: 延迟（毫秒），失败返回inf
    """
    try:
        # 构造请求：直接访问IP + Host头（模拟域名解析）
        url = f"http://{ip}/"
        headers = {
            "Host": test_domain,
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Connection": "close"
        }
        start = time.time()
        # 只请求头，不下载内容
        response = requests.get(
            url,
            headers=headers,
            timeout=HTTP_TIMEOUT,
            allow_redirects=False,
            verify=False  # 忽略SSL证书错误
        )
        delay = (time.time() - start) * 1000  # 转换为毫秒
        # 只要返回状态码（无论200/403/500都算可达）
        if response.status_code >= 100 and response.status_code < 600:
            return delay
    except:
        # 尝试HTTPS测速（备用）
        try:
            url = f"https://{ip}/"
            start = time.time()
            response = requests.get(
                url,
                headers=headers,
                timeout=HTTP_TIMEOUT,
                allow_redirects=False,
                verify=False
            )
            delay = (time.time() - start) * 1000
            if response.status_code >= 100 and response.status_code < 600:
                return delay
        except:
            pass
    return float('inf')

def test_ip_performance(ip_list: List[str]) -> List[ProxyIP]:
    """测试IP延迟和可用性（HTTP测速），返回排序后的IP"""
    proxy_ips = []
    for ip in ip_list:
        proxy_ip = ProxyIP(ip=ip)
        try:
            delays = []
            for _ in range(TEST_COUNT):
                delay = http_ping(ip)
                if delay < HTTP_TIMEOUT * 1000:  # 超时判断
                    delays.append(delay)
                time.sleep(0.2)  # 避免请求过快
            
            if delays:
                proxy_ip.delay = sum(delays) / len(delays)
                proxy_ip.available = True
                print(f"IP {ip} 平均延迟：{proxy_ip.delay:.2f}ms")
            else:
                print(f"IP {ip} 不可达（超时）")
        except Exception as e:
            print(f"测试IP {ip} 失败：{str(e)}")
        proxy_ips.append(proxy_ip)
    
    # 过滤可用IP，并按延迟升序排序
    available_ips = [p for p in proxy_ips if p.available]
    available_ips.sort(key=lambda x: x.delay)
    return available_ips

# ===================== 步骤3：生成本地hosts文件 =====================
def backup_hosts_file():
    """备份原有hosts文件"""
    backup_path = f"{HOSTS_PATH}.backup_{int(time.time())}"
    try:
        with open(HOSTS_PATH, 'r', encoding='utf-8') as f:
            original_content = f.read()
        with open(backup_path, 'w', encoding='utf-8') as f:
            f.write(original_content)
        print(f"已备份原有hosts到：{backup_path}")
        return original_content
    except Exception as e:
        print(f"备份hosts失败：{str(e)}")
        return ""

def generate_hosts_file(best_ips: List[ProxyIP], target_domains: List[str]):
    """生成hosts文件（兼容权限提示）"""
    if not best_ips:
        print("无可用IP，跳过hosts生成")
        return
    
    # 选最优IP（延迟最低）
    best_ip = best_ips[0].ip
    print(f"\n选中最优IP：{best_ip}（延迟：{best_ips[0].delay:.2f}ms）")

    # 备份原有hosts
    original_content = backup_hosts_file()

    # 过滤原有目标域名的配置
    new_lines = []
    for line in original_content.split('\n'):
        if not any(domain in line for domain in target_domains):
            new_lines.append(line)
    
    # 新增最优IP的hosts配置
    new_lines.append("\n# === 自动生成的EhViewer代理配置 ===\n")
    for domain in target_domains:
        new_lines.append(f"{best_ip}    {domain}")
    new_lines.append("# === 自动配置结束 ===\n")

    # 写入hosts文件（处理权限提示）
    try:
        with open(HOSTS_PATH, 'w', encoding='utf-8') as f:
            f.write('\n'.join(new_lines))
        print(f"成功生成hosts文件：{HOSTS_PATH}")
    except PermissionError:
        print("\n⚠️ 权限不足！请以管理员/root身份运行脚本：")
        if os.name == "nt":
            print("  Windows：右键CMD/PowerShell → 以管理员身份运行")
        else:
            print("  Linux/Mac：sudo python3 脚本名.py")

# ===================== 主流程 =====================
if __name__ == "__main__":
    print("===== 开始自动获取IP并生成hosts =====")
    print(f"拉取文件：{GITHUB_RAW_URL}\n")
    
    # 1. 拉取IP列表
    ip_list = fetch_ip_list_from_github()
    if not ip_list:
        print("错误：未提取到有效IP")
        exit(1)
    
    # 2. 测试IP性能（HTTP测速，无需root）
    print("\n===== 开始测试IP延迟（HTTP测速） =====")
    best_ips = test_ip_performance(ip_list)
    if not best_ips:
        print("\n警告：所有IP均不可达，将使用第一个提取的IP作为备选")
        # 降级策略：使用第一个提取的IP（不检测可用性）
        best_ips = [ProxyIP(ip=ip_list[0], delay=999.99, available=True)]
    
    # 3. 生成hosts文件
    print("\n===== 开始生成hosts文件 =====")
    generate_hosts_file(best_ips, TARGET_DOMAINS)
    
    print("\n===== 操作完成 =====")
    # 刷新DNS缓存提示
    if os.name == "nt":
        print("建议执行：ipconfig /flushdns（刷新DNS缓存）")
    else:
        print("建议执行：sudo systemd-resolve --flush-caches（Linux）或 dscacheutil -flushcache（Mac）")
