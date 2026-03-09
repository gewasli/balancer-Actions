import requests
import time
import re
import socket
from dataclasses import dataclass
from typing import Dict, List, Tuple

# ===================== 核心配置 =====================
# 目标文件地址
GITHUB_RAW_URL = "https://raw.githubusercontent.com/xiaojieonly/Ehviewer_CN_SXJ/refs/heads/BiLi_PC_Gamer/app/src/main/java/com/hippo/ehviewer/client/EhHosts.kt"
# 测速配置
TEST_TIMEOUT = 3  # 超时时间（秒）
TEST_COUNT = 2    # 每个IP测试次数
# 输出配置（根目录）
OUTPUT_HOSTS = "./ehviewer_optimized_hosts.txt"  # 根目录输出
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

# ===================== 数据结构 =====================
@dataclass
class IPResult:
    ip: str
    ip_type: str  # "IPv4" 或 "IPv6"
    delay: float = float('inf')  # 延迟（毫秒）
    available: bool = False

# ===================== 工具函数：IP类型判断 =====================
def get_ip_type(ip: str) -> str:
    """判断IP类型（IPv4/IPv6）"""
    try:
        socket.inet_pton(socket.AF_INET, ip)
        return "IPv4"
    except:
        try:
            socket.inet_pton(socket.AF_INET6, ip)
            return "IPv6"
        except:
            return "Unknown"

# ===================== 步骤1：精准解析域名-IP映射（包含IPv6） =====================
def extract_hosts_mapping() -> Dict[str, List[str]]:
    """
    解析companion object中的put(map)调用，提取所有IPv4/IPv6
    规则：put(map, "域名", "ip1", "ip2"...))
    """
    print("="*60)
    print(f"📥 开始拉取文件: {GITHUB_RAW_URL}")
    print("="*60)
    
    try:
        # 1. 拉取文件内容
        headers = {"User-Agent": USER_AGENT}
        response = requests.get(GITHUB_RAW_URL, headers=headers, timeout=15)
        response.raise_for_status()
        content = response.text
        
        # 2. 核心正则：匹配所有put(map, "域名", ip列表) 块
        # 兼容跨多行、带注释、任意缩进的格式
        pattern = re.compile(r'put\(\s*map,\s*"([^"]+)"\s*,([\s\S]*?)\);', re.MULTILINE)
        hosts_mapping = {}
        
        # 3. 逐个解析put块
        for match in pattern.findall(content):
            domain = match[0].strip()  # 提取域名
            ip_part = match[1].strip() # 提取IP部分
            
            # 4. 提取所有未被注释的IP（IPv4+IPv6）
            ips = []
            for part in ip_part.split(','):
                # 移除行内注释（// 后面的内容）
                clean_part = part.split("//")[0].strip()
                if not clean_part:
                    continue
                
                # 匹配IP（支持IPv4和IPv6）
                # IPv4: "xxx.xxx.xxx.xxx"
                # IPv6: "xxxx:xxxx:xxxx:xxxx::xxx"
                ip_match = re.search(r'"((?:\d{1,3}\.){3}\d{1,3}|(?:[0-9a-fA-F:]+))"', clean_part)
                if ip_match:
                    ip = ip_match.group(1)
                    ip_type = get_ip_type(ip)
                    if ip_type in ["IPv4", "IPv6"]:  # 只保留有效IP类型
                        ips.append(ip)
            
            # 5. 去重并保存
            if ips:
                unique_ips = list(set(ips))
                hosts_mapping[domain] = unique_ips
                # 打印提取结果（区分IPv4/IPv6）
                ip_info = [f"{ip}({get_ip_type(ip)})" for ip in unique_ips]
                print(f"✅ 提取域名: {domain} | IP列表: {ip_info}")
        
        # 6. 解析结果汇总
        print("\n" + "="*60)
        print(f"📊 解析完成！共提取 {len(hosts_mapping)} 个域名:")
        for idx, (domain, ips) in enumerate(hosts_mapping.items(), 1):
            ipv4_count = len([ip for ip in ips if get_ip_type(ip) == "IPv4"])
            ipv6_count = len([ip for ip in ips if get_ip_type(ip) == "IPv6"])
            print(f"   {idx}. {domain:<20} | IPv4: {ipv4_count} | IPv6: {ipv6_count}")
        
        if not hosts_mapping:
            raise ValueError("未提取到任何有效域名-IP映射")
        
        return hosts_mapping
    
    except Exception as e:
        print(f"❌ 解析失败: {str(e)}")
        # 兜底映射（确保脚本不中断）
        fallback = {
            "e-hentai.org": ["104.20.18.168", "172.67.2.238"],
            "exhentai.org": ["178.175.128.251", "178.175.128.254"],
            "ehgt.org": ["109.236.85.28", "2a00:7c80:0:123::3a85"],
            "raw.githubusercontent.com": ["151.101.0.133"]
        }
        print(f"⚠️ 使用兜底映射: {list(fallback.keys())}")
        return fallback

# ===================== 步骤2：IPv4/IPv6 测速（兼容测试） =====================
def test_ip_performance(domain: str, ip: str) -> IPResult:
    """测试单个IP（IPv4/IPv6）的访问性能"""
    ip_result = IPResult(ip=ip, ip_type=get_ip_type(ip))
    delays = []
    
    for _ in range(TEST_COUNT):
        try:
            # 适配协议（raw.githubusercontent.com用HTTP）
            scheme = "http" if "github" in domain else "https"
            url = f"{scheme}://{ip}/"
            headers = {
                "Host": domain,
                "User-Agent": USER_AGENT,
                "Connection": "close",
                "Accept": "*/*"
            }
            
            start = time.time()
            # 发送请求（只请求头，不下载内容）
            response = requests.get(
                url,
                headers=headers,
                timeout=TEST_TIMEOUT,
                allow_redirects=False,
                verify=False,  # 忽略SSL证书错误
                # 强制使用对应IP协议
                proxies={"http": None, "https": None}  # 禁用代理，确保直连测试
            )
            
            # 只要返回状态码就认为可用
            if 100 <= response.status_code < 600:
                delay = (time.time() - start) * 1000
                delays.append(delay)
            
            time.sleep(0.2)  # 避免请求过快
        
        except Exception as e:
            # IPv6测试失败是常见情况，友好提示
            if ip_result.ip_type == "IPv6":
                print(f"   ⚠️ IPv6 {ip} 测试失败: {str(e)[:50]}")
            continue
    
    # 计算平均延迟
    if delays:
        ip_result.delay = round(sum(delays) / len(delays), 2)
        ip_result.available = True
    
    return ip_result

def test_all_domains(hosts_mapping: Dict[str, List[str]]) -> Dict[str, Tuple[str, float, str]]:
    """测试所有域名的所有IP（IPv4/IPv6），返回最优IP"""
    print("\n" + "="*60)
    print("🚀 开始测试所有IP性能（IPv4+IPv6）")
    print("="*60)
    
    best_mapping = {}  # {域名: (最优IP, 延迟, IP类型)}
    
    # 遍历所有域名
    for idx, (domain, ips) in enumerate(hosts_mapping.items(), 1):
        print(f"\n[{idx}/{len(hosts_mapping)}] 测试域名: {domain}")
        print(f"   📋 IP列表: {[f'{ip}({get_ip_type(ip)})' for ip in ips]}")
        
        # 测试当前域名的所有IP
        ip_results = []
        for ip in ips:
            result = test_ip_performance(domain, ip)
            ip_results.append(result)
            
            if result.available:
                print(f"   📶 {result.ip_type} {result.ip:<30} - 延迟: {result.delay}ms")
            else:
                print(f"   ❌ {result.ip_type} {result.ip:<30} - 不可达")
        
        # 选择最优IP（优先选可用的，延迟最低的）
        available_results = [r for r in ip_results if r.available]
        if available_results:
            # 优先选IPv4（兼容性更好），再选延迟最低的
            ipv4_results = [r for r in available_results if r.ip_type == "IPv4"]
            if ipv4_results:
                best_ip = min(ipv4_results, key=lambda x: x.delay)
            else:
                best_ip = min(available_results, key=lambda x: x.delay)
            
            best_mapping[domain] = (best_ip.ip, best_ip.delay, best_ip.ip_type)
            print(f"   ✨ 最优IP: {best_ip.ip_type} {best_ip.ip} (延迟: {best_ip.delay}ms)")
        else:
            # 所有IP都不可达，选第一个IP兜底
            fallback_ip = ips[0]
            fallback_type = get_ip_type(fallback_ip)
            best_mapping[domain] = (fallback_ip, 999.99, fallback_type)
            print(f"   ⚠️ 所有IP不可达，使用兜底IP: {fallback_type} {fallback_ip}")
    
    # 测试结果汇总
    print("\n" + "="*60)
    print("📊 所有域名测试完成！最优IP汇总:")
    for domain, (ip, delay, ip_type) in best_mapping.items():
        print(f"   {domain:<20} → {ip_type} {ip:<30} (延迟: {delay}ms)")
    
    return best_mapping

# ===================== 步骤3：生成根目录hosts文件 =====================
def generate_hosts_file(best_mapping: Dict[str, Tuple[str, float, str]]):
    """生成优化后的hosts文件，输出到根目录"""
    print("\n" + "="*60)
    print(f"📝 生成hosts文件（根目录）: {OUTPUT_HOSTS}")
    print("="*60)
    
    # 构建hosts内容
    hosts_content = [
        "# ==============================================",
        "# EhViewer 优化Hosts文件（支持IPv4/IPv6）",
        f"# 生成时间: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime())}",
        f"# 共包含 {len(best_mapping)} 个域名",
        "# 规则: 优先选择延迟最低的IPv4，无可用IPv4则选IPv6",
        "# ==============================================",
        ""
    ]
    
    # 按域名排序，写入所有映射
    for domain in sorted(best_mapping.keys()):
        ip, delay, ip_type = best_mapping[domain]
        # 格式化输出（IP占40字符，适配IPv6长度）
        hosts_line = f"{ip:<40} {domain}  # {ip_type} | 延迟: {delay}ms"
        hosts_content.append(hosts_line)
    
    # 写入根目录文件
    with open(OUTPUT_HOSTS, 'w', encoding='utf-8') as f:
        f.write('\n'.join(hosts_content))
    
    # 验证文件
    file_size = len(open(OUTPUT_HOSTS, 'r', encoding='utf-8').readlines())
    print(f"✅ 成功生成hosts文件！")
    print(f"   📂 文件路径: {OUTPUT_HOSTS}")
    print(f"   📏 文件行数: {file_size}")
    
    # 预览文件内容
    print("\n📄 Hosts文件内容预览:")
    print("-"*60)
    with open(OUTPUT_HOSTS, 'r', encoding='utf-8') as f:
        print(f.read())
    print("-"*60)

# ===================== 主流程 =====================
if __name__ == "__main__":
    # 禁用SSL警告
    requests.packages.urllib3.disable_warnings()
    
    print("="*70)
    print("🎯 EhViewer Hosts 生成工具（支持IPv4/IPv6）")
    print("="*70)
    
    try:
        # 步骤1：解析域名-IP映射
        hosts_mapping = extract_hosts_mapping()
        
        # 步骤2：测试所有IP性能
        best_mapping = test_all_domains(hosts_mapping)
        
        # 步骤3：生成根目录hosts文件
        generate_hosts_file(best_mapping)
        
        print("\n" + "="*70)
        print("🎉 所有操作完成！Hosts文件已保存到仓库根目录")
        print("="*70)
        
    except Exception as e:
        print(f"\n❌ 执行失败: {str(e)}")
        exit(1)
