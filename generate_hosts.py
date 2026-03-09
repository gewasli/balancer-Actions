import requests
import time
import re
import os
import sys
from ping3 import ping
from dataclasses import dataclass
from typing import List, Dict

# 配置项
GITHUB_RAW_URL = "https://raw.githubusercontent.com/xiaojieonly/Ehviewer_CN_SXJ/refs/heads/BiLi_PC_Gamer/app/src/main/java/com/hippo/ehviewer/client/EhHosts.kt"
TARGET_DOMAINS = ["e-hentai.org", "exhentai.org", "ehgt.org", "api.e-hentai.org"]
OUTPUT_HOSTS_PATH = "./generated_hosts"  # 输出路径（Action工作目录）
PING_TIMEOUT = 2
PING_COUNT = 3

@dataclass
class ProxyIP:
    ip: str
    delay: float = float('inf')
    available: bool = False

def fetch_ip_list_from_github() -> List[str]:
    """从GitHub拉取IP列表"""
    try:
        print(f"正在拉取文件: {GITHUB_RAW_URL}")
        response = requests.get(GITHUB_RAW_URL, timeout=15)
        response.raise_for_status()
        content = response.text
        
        # 增强版IP解析规则，适配EhHosts.kt常见格式
        ip_pattern = re.compile(r'"(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})"')
        ip_list = list(set(ip_pattern.findall(content)))  # 去重
        
        if not ip_list:
            raise ValueError("未提取到任何IP地址")
        print(f"成功提取 {len(ip_list)} 个IP: {ip_list}")
        return ip_list
    except Exception as e:
        print(f"拉取IP失败: {str(e)}", file=sys.stderr)
        sys.exit(1)

def test_ip_performance(ip_list: List[str]) -> List[ProxyIP]:
    """测试IP延迟和可用性"""
    proxy_ips = []
    print("\n开始测试IP性能...")
    for ip in ip_list:
        proxy_ip = ProxyIP(ip=ip)
        delays = []
        try:
            for _ in range(PING_COUNT):
                delay = ping(ip, timeout=PING_TIMEOUT, unit='ms')
                if delay and delay < PING_TIMEOUT * 1000:
                    delays.append(delay)
                time.sleep(0.1)
            
            if delays:
                proxy_ip.delay = round(sum(delays) / len(delays), 2)
                proxy_ip.available = True
                print(f"IP {ip} - 可用，平均延迟: {proxy_ip.delay}ms")
            else:
                print(f"IP {ip} - 不可达")
        except Exception as e:
            print(f"IP {ip} - 测试失败: {str(e)}")
        proxy_ips.append(proxy_ip)
    
    # 过滤可用IP并按延迟排序
    available_ips = [p for p in proxy_ips if p.available]
    if not available_ips:
        print("所有IP均不可用！", file=sys.stderr)
        sys.exit(1)
    
    available_ips.sort(key=lambda x: x.delay)
    return available_ips

def generate_hosts_file(best_ips: List[ProxyIP]):
    """生成hosts文件"""
    best_ip = best_ips[0].ip
    print(f"\n选中最优IP: {best_ip} (延迟: {best_ips[0].delay}ms)")
    
    # 构建hosts内容
    hosts_content = [
        "# 自动生成的EhViewer Hosts配置",
        f"# 更新时间: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime())}",
        f"# 最优IP: {best_ip} (延迟: {best_ips[0].delay}ms)",
        "# ===================================",
        ""
    ]
    
    # 添加域名映射
    for domain in TARGET_DOMAINS:
        hosts_content.append(f"{best_ip}    {domain}")
    
    # 写入文件
    with open(OUTPUT_HOSTS_PATH, 'w', encoding='utf-8') as f:
        f.write('\n'.join(hosts_content))
    
    print(f"成功生成hosts文件: {OUTPUT_HOSTS_PATH}")
    # 打印文件内容便于调试
    with open(OUTPUT_HOSTS_PATH, 'r', encoding='utf-8') as f:
        print("\nHosts文件内容:")
        print(f.read())

if __name__ == "__main__":
    # 主流程
    ip_list = fetch_ip_list_from_github()
    best_ips = test_ip_performance(ip_list)
    generate_hosts_file(best_ips)
