#!/usr/bin/env python3
"""
网络连接测试脚本
测试笔电能否连接到后端和前端服务
"""

import socket
import requests
import time


def test_port(host, port, service_name):
    """测试端口连接"""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5)
        result = sock.connect_ex((host, port))
        sock.close()

        if result == 0:
            print(f"✅ {service_name} ({host}:{port}) - 连接成功")
            return True
        else:
            print(f"❌ {service_name} ({host}:{port}) - 连接失败 (错误码: {result})")
            return False
    except Exception as e:
        print(f"❌ {service_name} ({host}:{port}) - 连接异常: {e}")
        return False


def test_http_service(url, service_name):
    """测试HTTP服务"""
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            print(f"✅ {service_name} ({url}) - HTTP响应正常")
            return True
        else:
            print(f"⚠️  {service_name} ({url}) - HTTP状态码: {response.status_code}")
            return False
    except requests.exceptions.ConnectionError:
        print(f"❌ {service_name} ({url}) - 连接被拒绝")
        return False
    except requests.exceptions.Timeout:
        print(f"❌ {service_name} ({url}) - 连接超时")
        return False
    except Exception as e:
        print(f"❌ {service_name} ({url}) - 请求异常: {e}")
        return False


def main():
    """主测试函数"""
    print("🌐 网络连接测试开始...")
    print("=" * 60)

    # 测试目标
    targets = [
        ("192.168.7.75", 8000, "后端服务"),
        ("192.168.7.75", 8080, "前端服务"),
        ("localhost", 8000, "本地后端"),
        ("localhost", 8080, "本地前端"),
    ]

    # 端口连接测试
    print("🔌 端口连接测试:")
    port_results = []
    for host, port, service in targets:
        result = test_port(host, port, service)
        port_results.append(result)

    print("\n🌐 HTTP服务测试:")
    # HTTP服务测试
    http_results = []
    http_targets = [
        ("http://192.168.7.75:8000/health", "后端健康检查"),
        ("http://192.168.7.75:8080/frontend_glass.html", "前端页面"),
        ("http://localhost:8000/health", "本地后端健康检查"),
        ("http://localhost:8080/frontend_glass.html", "本地前端页面"),
    ]

    for url, service in http_targets:
        result = test_http_service(url, service)
        http_results.append(result)

    print("\n📊 测试结果总结:")
    print("=" * 60)

    # 分析结果
    port_success = sum(port_results)
    http_success = sum(http_results)

    print(f"端口连接: {port_success}/{len(port_results)} 成功")
    print(f"HTTP服务: {http_success}/{len(http_results)} 成功")

    if port_success == len(port_results):
        print("🎉 所有端口连接正常！")
    else:
        print("⚠️  部分端口连接失败，请检查防火墙设置")

    if http_success == len(http_results):
        print("🎉 所有HTTP服务正常！")
    else:
        print("⚠️  部分HTTP服务异常，请检查服务状态")

    print("\n💡 笔电访问建议:")
    print(f"前端地址: http://192.168.7.75:8080/frontend_glass.html")
    print(f"后端API: http://192.168.7.75:8000")

    if port_success >= 2 and http_success >= 2:
        print("✅ 网络配置正常，笔电应该能够访问")
    else:
        print("❌ 网络配置异常，请检查防火墙和网络设置")


if __name__ == "__main__":
    main()
