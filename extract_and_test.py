import requests
import time
import re
import json
from dataclasses import dataclass
from typing import Dict, List, Tuple
from urllib.parse import urlparse

# ===================== 配置项 =====================
GITHUB_RAW_URL = "https://raw.githubusercontent.com/xiaojieonly/Ehviewer_CN_SXJ/refs/heads/BiLi_PC_Gamer/app/src/main/java/com/hippo/ehviewer/client/EhHosts.kt"
TEST_TIMEOUT = 3  # 超时时间（秒）
TEST_COUNT = 2    # 每个IP测试次数
OUTPUT_HOSTS = "./optimized_hosts.txt"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

# ===================== 数据结构 =====================
@dataclass
class IPResult:
    ip: str
    delay: float = float('inf')  # 延迟（毫秒）
    available: bool = False

# ===================== 步骤1：修复版解析逻辑 =====================
def extract_hosts_mapping() -> Dict[str, List[str]]:
    """
    修复版：精准解析EhHosts.kt中跨多行、带缩进的put方法调用
    返回格式：{"e-hentai.org": ["104.20.18.168", ...], ...}
    """
    print(f"📥 拉取文件: {GITHUB_RAW_URL}")
    try:
        headers = {"User-Agent": USER_AGENT}
        response = requests.get(GITHUB_RAW_URL, headers=headers, timeout=10)
        response.raise_for_status()
        content = response.text

        # 第一步：移除所有注释（// 开头的内容）
        content = re.sub(r'//.*?$', '', content, flags=re.MULTILINE)
        # 第二步：将跨多行的put调用合并为单行（关键修复）
        # 匹配put( 开头，直到 ); 结束的整块内容
        put_blocks = re.findall(r'put\(\s*map,\s*[^;]+?\);', content, re.DOTALL)
        
        hosts_mapping = {}
        for block in put_blocks:
            # 清理块内的换行和多余空格
            clean_block = re.sub(r'\s+', ' ', block).strip()
            # 提取域名和IP列表
            # 匹配格式：put( map, "域名", "ip1", "ip2", ... );
            pattern = re.compile(r'put\(\s*map,\s*"([^"]+)"\s*,\s*(.*?)\s*\);')
            match = pattern.search(clean_block)
            if match:
                domain = match.group(1).strip()
                ip_str = match.group(2).strip()
                # 拆分IP列表并清理
                ip_list = [ip.strip().strip('"') for ip in ip_str.split(',') if ip.strip()]
                # 过滤出合法的IPv4
                valid_ips = []
                for ip in ip_list:
                    if re.match(r'^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$', ip):
                        valid_ips.append(ip)
                # 去重并保存
                if valid_ips:
                    hosts_mapping[domain] = list(set(valid_ips))
                    print(f"✅ 提取域名 {domain} - IP列表: {valid_ips}")

        # 调试：打印原始匹配结果（便于排查）
        print(f"\n🔍 调试信息 - 匹配到的put块数量: {len(put_blocks)}")
        if not hosts_mapping:
            # 输出原始内容片段（前2000字符）便于排查
            print(f"❌ 未提取到有效映射，原始内容片段:\n{content[:2000]}")
            raise ValueError("未提取到任何有效域名-IP映射")
        
        print(f"\n📊 共提取 {len(hosts_mapping)} 个域名的IP映射")
        return hosts_mapping

    except Exception as e:
        print(f"❌ 解析失败: {str(e)}")
        raise

# ===================== 步骤2：定向测速 =====================
def test_ip_for_domain(domain: str, ips: List[str]) -> Tuple[str, float]:
    """测试指定域名的所有IP访问速度，返回最优IP和延迟"""
    print(f"\n🔍 测试域名 {domain} 的IP性能:")
    results = []

    for ip in ips:
        ip_result = IPResult(ip=ip)
        delays = []
        
        for _ in range(TEST_COUNT):
            try:
                # 适配不同域名的协议（raw.githubusercontent.com用HTTP）
                scheme = "http" if domain == "raw.githubusercontent.com" else "https"
                url = f"{scheme}://{ip}/"
                headers = {
                    "Host": domain,
                    "User-Agent": USER_AGENT,
                    "Connection": "close",
                    "Accept": "*/*"
                }

                start = time.time()
                # 只请求头，不下载内容
                response = requests.get(
                    url,
                    headers=headers,
                    timeout=TEST_TIMEOUT,
                    allow_redirects=False,
                    verify=False  # 忽略SSL证书错误
                )
                if response.status_code >= 100 and response.status_code < 600:
                    delay = (time.time() - start) * 1000
                    delays.append(delay)
                time.sleep(0.2)

            except Exception as e:
                continue
        
        if delays:
            ip_result.delay = sum(delays) / len(delays)
            ip_result.available = True
            results.append(ip_result)
            print(f"   📶 {ip} - 平均延迟: {ip_result.delay:.2f}ms")
        else:
            print(f"   ❌ {ip} - 不可达")

    # 选择最优IP
    if results:
        best_ip = min(results, key=lambda x: x.delay)
        return best_ip.ip, best_ip.delay
    else:
        print(f"   ⚠️ 所有IP均不可达，使用第一个IP: {ips[0]}")
        return ips[0], 999.99

# ===================== 步骤3：生成hosts文件 =====================
def generate_optimized_hosts(hosts_mapping: Dict[str, List[str]]):
    """生成每个域名对应最优IP的hosts文件"""
    print("\n📝 开始生成优化后的hosts文件...")
    best_mapping = {}

    # 逐个域名测试
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

    # 写入hosts
    for domain in sorted(best_mapping.keys()):
        best_ip, delay = best_mapping[domain]
        hosts_content.append(f"{best_ip:<15} {domain}  # 延迟: {delay:.2f}ms")

    # 保存文件
    with open(OUTPUT_HOSTS, 'w', encoding='utf-8') as f:
        f.write('\n'.join(hosts_content))

    print(f"\n✅ 成功生成hosts文件: {OUTPUT_HOSTS}")
    print("\n📄 Hosts文件内容预览:")
    with open(OUTPUT_HOSTS, 'r', encoding='utf-8') as f:
        print(f.read())

# ===================== 主流程 =====================
if __name__ == "__main__":
    # 禁用requests警告
    requests.packages.urllib3.disable_warnings()
    
    print("🚀 开始提取并优化EhViewer Hosts...")
    try:
        # 1. 解析域名-IP映射
        hosts_mapping = extract_hosts_mapping()
        # 2. 生成优化后的hosts文件
        generate_optimized_hosts(hosts_mapping)
        print("\n🎉 操作完成！可直接使用生成的hosts文件")
    except Exception as e:
        print(f"\n❌ 执行失败: {str(e)}")
        # 非零退出码触发Actions失败
        exit(1)
