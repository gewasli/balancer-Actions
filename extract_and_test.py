import requests
import time
import re
import json
from dataclasses import dataclass
from typing import Dict, List, Tuple
from urllib.parse import urlparse

# ===================== 配置项 =====================
# 目标文件地址
GITHUB_RAW_URL = "https://raw.githubusercontent.com/xiaojieonly/Ehviewer_CN_SXJ/refs/heads/BiLi_PC_Gamer/app/src/main/java/com/hippo/ehviewer/client/EhHosts.kt"
# 测速配置
TEST_TIMEOUT = 3  # 超时时间（秒）
TEST_COUNT = 2    # 每个IP测试次数
# 输出文件
OUTPUT_HOSTS = "./optimized_hosts.txt"
# User-Agent（模拟浏览器访问）
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

# ===================== 数据结构 =====================
@dataclass
class IPResult:
    ip: str
    delay: float = float('inf')  # 延迟（毫秒）
    available: bool = False

# ===================== 步骤1：解析EhHosts.kt，提取域名-IP映射 =====================
def extract_hosts_mapping() -> Dict[str, List[str]]:
    """
    从EhHosts.kt中提取builtInHosts的域名-IP映射
    返回格式：{"e-hentai.org": ["104.20.18.168", ...], ...}
    """
    print(f"📥 拉取文件: {GITHUB_RAW_URL}")
    try:
        headers = {"User-Agent": USER_AGENT}
        response = requests.get(GITHUB_RAW_URL, headers=headers, timeout=10)
        response.raise_for_status()
        content = response.text

        # 1. 提取builtInHosts中的put方法调用（核心正则）
        # 匹配格式：put(map, "域名", "ip1", "ip2", ...)
        put_pattern = re.compile(
            r'put\(\s*map,\s*"([^"]+)"\s*,\s*(["\d\.\:,]+?)\s*\)',
            re.DOTALL | re.MULTILINE
        )
        matches = put_pattern.findall(content)

        hosts_mapping = {}
        for match in matches:
            domain = match[0].strip()
            ip_parts = match[1].split(',')
            
            # 提取合法IPv4（过滤注释、IPv6、空值）
            ips = []
            for part in ip_parts:
                # 清理字符串（移除引号、空格、注释）
                clean_part = part.strip().strip('"').split("//")[0].strip()
                # 校验IPv4格式
                if re.match(r'^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$', clean_part):
                    ips.append(clean_part)
            
            # 去重并保存
            if ips:
                hosts_mapping[domain] = list(set(ips))
                print(f"✅ 提取域名 {domain} - IP列表: {ips}")

        if not hosts_mapping:
            raise ValueError("未提取到任何有效域名-IP映射")
        print(f"\n📊 共提取 {len(hosts_mapping)} 个域名的IP映射")
        return hosts_mapping

    except Exception as e:
        print(f"❌ 解析失败: {str(e)}")
        raise

# ===================== 步骤2：定向测速（针对每个域名的IP） =====================
def test_ip_for_domain(domain: str, ips: List[str]) -> Tuple[str, float]:
    """
    测试指定域名的所有IP访问速度，返回最优IP和延迟
    :param domain: 目标域名（如e-hentai.org）
    :param ips: 该域名对应的IP列表
    :return: (最优IP, 平均延迟)
    """
    print(f"\n🔍 测试域名 {domain} 的IP性能:")
    results = []

    for ip in ips:
        ip_result = IPResult(ip=ip)
        delays = []
        
        for _ in range(TEST_COUNT):
            try:
                # 构造请求：直接访问IP + Host头（模拟域名解析）
                url = f"https://{ip}/" if domain != "raw.githubusercontent.com" else f"http://{ip}/"
                headers = {
                    "Host": domain,
                    "User-Agent": USER_AGENT,
                    "Connection": "close",
                    "Accept": "*/*"
                }

                start = time.time()
                # 只请求头，不下载内容（提升测速效率）
                response = requests.get(
                    url,
                    headers=headers,
                    timeout=TEST_TIMEOUT,
                    allow_redirects=False,
                    verify=False  # 忽略SSL证书错误
                )
                # 只要能建立连接并返回状态码，就算可用
                if response.status_code >= 100 and response.status_code < 600:
                    delay = (time.time() - start) * 1000  # 转换为毫秒
                    delays.append(delay)
                time.sleep(0.2)  # 避免请求过快被限流

            except Exception as e:
                # 失败则跳过
                continue
        
        # 计算平均延迟
        if delays:
            ip_result.delay = sum(delays) / len(delays)
            ip_result.available = True
            results.append(ip_result)
            print(f"   📶 {ip} - 平均延迟: {ip_result.delay:.2f}ms")
        else:
            print(f"   ❌ {ip} - 不可达")

    # 选择最优IP（延迟最低）
    if results:
        best_ip = min(results, key=lambda x: x.delay)
        return best_ip.ip, best_ip.delay
    else:
        # 所有IP都不可达时，返回第一个IP（降级策略）
        print(f"   ⚠️ 所有IP均不可达，使用第一个IP: {ips[0]}")
        return ips[0], 999.99

# ===================== 步骤3：生成优化后的hosts文件 =====================
def generate_optimized_hosts(hosts_mapping: Dict[str, List[str]]):
    """生成每个域名对应最优IP的hosts文件"""
    print("\n📝 开始生成优化后的hosts文件...")
    best_mapping = {}  # 存储每个域名的最优IP

    # 逐个域名测试并选择最优IP
    for domain, ips in hosts_mapping.items():
        best_ip, delay = test_ip_for_domain(domain, ips)
        best_mapping[domain] = (best_ip, delay)

    # 构建hosts内容
    hosts_content = [
        "# ==============================================",
        "# 自动生成的EhViewer优化Hosts文件",
        f"# 更新时间: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime())}",
        "# 生成规则: 每个域名选择访问速度最快的IP",
        "# ==============================================",
        ""
    ]

    # 按域名排序，写入hosts
    for domain in sorted(best_mapping.keys()):
        best_ip, delay = best_mapping[domain]
        hosts_content.append(f"{best_ip:<15} {domain}  # 延迟: {delay:.2f}ms")

    # 写入文件
    with open(OUTPUT_HOSTS, 'w', encoding='utf-8') as f:
        f.write('\n'.join(hosts_content))

    print(f"\n✅ 成功生成hosts文件: {OUTPUT_HOSTS}")
    print("\n📄 Hosts文件内容预览:")
    with open(OUTPUT_HOSTS, 'r', encoding='utf-8') as f:
        print(f.read())

# ===================== 主流程 =====================
if __name__ == "__main__":
    # 禁用requests警告（忽略SSL证书错误）
    requests.packages.urllib3.disable_warnings()
    
    print("🚀 开始提取并优化EhViewer Hosts...")
    # 1. 解析域名-IP映射
    hosts_mapping = extract_hosts_mapping()
    # 2. 生成优化后的hosts文件
    generate_optimized_hosts(hosts_mapping)
    print("\n🎉 操作完成！可直接使用生成的hosts文件")
