import requests
import time
import re
from dataclasses import dataclass
from typing import Dict, List, Tuple

# ===================== 配置项 =====================
GITHUB_RAW_URL = "https://raw.githubusercontent.com/xiaojieonly/Ehviewer_CN_SXJ/refs/heads/BiLi_PC_Gamer/app/src/main/java/com/hippo/ehviewer/client/EhHosts.kt"
TEST_TIMEOUT = 3
TEST_COUNT = 2
OUTPUT_HOSTS = "./optimized_hosts.txt"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

# ===================== 数据结构 =====================
@dataclass
class IPResult:
    ip: str
    delay: float = float('inf')
    available: bool = False

# ===================== 步骤1：精准解析companion object中的map =====================
def extract_hosts_mapping() -> Dict[str, List[str]]:
    """
    精准解析companion object中的put(map, "域名", "ip1", "ip2"...))
    步骤：
    1. 定位companion object代码块
    2. 逐行匹配put(map开头的行，提取域名
    3. 读取后续行的所有IP，直到下一个put/代码结束
    """
    print(f"📥 拉取文件: {GITHUB_RAW_URL}")
    try:
        # 1. 拉取文件并按行分割
        headers = {"User-Agent": USER_AGENT}
        response = requests.get(GITHUB_RAW_URL, headers=headers, timeout=10)
        response.raise_for_status()
        lines = response.text.split('\n')
        
        # 2. 定位companion object代码块（只解析这个区域）
        obj_start = -1
        obj_end = -1
        for i, line in enumerate(lines):
            clean_line = line.strip()
            if clean_line.startswith("companion object {"):
                obj_start = i
            elif obj_start != -1 and clean_line == "}":
                obj_end = i
                break
        
        if obj_start == -1 or obj_end == -1:
            raise ValueError("未找到companion object代码块")
        
        # 3. 解析companion object内的put方法
        hosts_mapping = {}
        current_domain = ""
        current_ips = []
        
        for i in range(obj_start, obj_end):
            line = lines[i].strip()
            # 移除行内注释
            line = line.split("//")[0].strip()
            
            # 匹配put(map, "域名", 开头的行（新域名开始）
            put_match = re.match(r'put\(\s*map,\s*"([^"]+)"\s*,', line)
            if put_match:
                # 先保存上一个域名的IP（如果有）
                if current_domain and current_ips:
                    hosts_mapping[current_domain] = list(set(current_ips))
                    print(f"✅ 提取域名 {current_domain} - IP列表: {current_ips}")
                
                # 初始化新域名
                current_domain = put_match.group(1)
                current_ips = []
                
                # 提取当前行的IP
                ip_matches = re.findall(r'"(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})"', line)
                current_ips.extend(ip_matches)
            elif current_domain and line:  # 继续提取当前域名的IP（后续行）
                ip_matches = re.findall(r'"(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})"', line)
                current_ips.extend(ip_matches)
        
        # 保存最后一个域名
        if current_domain and current_ips:
            hosts_mapping[current_domain] = list(set(current_ips))
            print(f"✅ 提取域名 {current_domain} - IP列表: {current_ips}")
        
        # 校验结果
        if not hosts_mapping:
            raise ValueError("未提取到任何有效域名-IP映射")
        
        print(f"\n📊 共提取 {len(hosts_mapping)} 个域名的IP映射")
        return hosts_mapping

    except Exception as e:
        print(f"❌ 解析失败: {str(e)}")
        # 兜底映射（防止解析失败）
        fallback = {
            "e-hentai.org": ["104.20.18.168", "104.20.19.168", "172.67.2.238"],
            "exhentai.org": ["178.175.128.251", "178.175.128.254"],
            "raw.githubusercontent.com": ["151.101.0.133", "151.101.64.133"]
        }
        print(f"⚠️ 使用兜底IP映射: {fallback}")
        return fallback

# ===================== 步骤2：定向测速 =====================
def test_ip_for_domain(domain: str, ips: List[str]) -> Tuple[str, float]:
    print(f"\n🔍 测试域名 {domain} 的IP性能:")
    results = []

    for ip in ips:
        ip_result = IPResult(ip=ip)
        delays = []
        
        for _ in range(TEST_COUNT):
            try:
                scheme = "http" if domain == "raw.githubusercontent.com" else "https"
                url = f"{scheme}://{ip}/"
                headers = {
                    "Host": domain,
                    "User-Agent": USER_AGENT,
                    "Connection": "close"
                }

                start = time.time()
                response = requests.get(
                    url, headers=headers, timeout=TEST_TIMEOUT,
                    allow_redirects=False, verify=False
                )
                if 100 <= response.status_code < 600:
                    delays.append((time.time() - start) * 1000)
                time.sleep(0.2)

            except:
                continue
        
        if delays:
            ip_result.delay = sum(delays) / len(delays)
            ip_result.available = True
            results.append(ip_result)
            print(f"   📶 {ip} - 平均延迟: {ip_result.delay:.2f}ms")
        else:
            print(f"   ❌ {ip} - 不可达")

    if results:
        best_ip = min(results, key=lambda x: x.delay)
        return best_ip.ip, best_ip.delay
    else:
        print(f"   ⚠️ 所有IP不可达，使用第一个IP: {ips[0]}")
        return ips[0], 999.99

# ===================== 步骤3：生成hosts文件 =====================
def generate_optimized_hosts(hosts_mapping: Dict[str, List[str]]):
    print("\n📝 生成优化后的hosts文件...")
    best_mapping = {}

    for domain, ips in hosts_mapping.items():
        best_ip, delay = test_ip_for_domain(domain, ips)
        best_mapping[domain] = (best_ip, delay)

    # 构建hosts内容
    hosts_content = [
        "# 自动生成的EhViewer优化Hosts文件",
        f"# 更新时间: {time.strftime('%Y-%m-%d %H:%M:%S')}",
        "# 规则: 每个域名选择访问速度最快的IP",
        "================================================",
        ""
    ]

    for domain in sorted(best_mapping.keys()):
        best_ip, delay = best_mapping[domain]
        hosts_content.append(f"{best_ip:<15} {domain}  # 延迟: {delay:.2f}ms")

    # 写入文件
    with open(OUTPUT_HOSTS, 'w', encoding='utf-8') as f:
        f.write('\n'.join(hosts_content))

    print(f"\n✅ 成功生成: {OUTPUT_HOSTS}")
    print("\n📄 内容预览:")
    with open(OUTPUT_HOSTS, 'r', encoding='utf-8') as f:
        print(f.read())

# ===================== 主流程 =====================
if __name__ == "__main__":
    requests.packages.urllib3.disable_warnings()
    print("🚀 开始提取并优化EhViewer Hosts...")
    
    # 1. 精准解析域名-IP映射
    hosts_mapping = extract_hosts_mapping()
    # 2. 生成优化hosts
    generate_optimized_hosts(hosts_mapping)
    
    print("\n🎉 操作完成！")
