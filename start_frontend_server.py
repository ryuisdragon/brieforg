#!/usr/bin/env python3
"""
簡單的HTTP服務器來托管前端網站
支持跨域訪問，讓筆電可以連接到後端
"""

import http.server
import socketserver
import os
import webbrowser
from pathlib import Path

# 配置
PORT = 8080
HOST = "0.0.0.0"  # 监听所有网络接口
FRONTEND_FILE = "frontend_glass.html"


class CORSHTTPRequestHandler(http.server.SimpleHTTPRequestHandler):
    """支持CORS的HTTP請求處理器"""

    def end_headers(self):
        # 添加CORS頭
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header(
            "Access-Control-Allow-Methods", "GET, POST, OPTIONS, PUT, DELETE"
        )
        self.send_header("Access-Control-Allow-Headers", "Content-Type, X-Session-Id")
        self.send_header("Access-Control-Max-Age", "86400")
        super().end_headers()

    def do_OPTIONS(self):
        # 處理預檢請求
        self.send_response(200)
        self.end_headers()

    def log_message(self, format, *args):
        # 自定義日誌格式
        print(f"[HTTP Server] {format % args}")


def main():
    """主函數"""
    # 檢查前端文件是否存在
    if not Path(FRONTEND_FILE).exists():
        print(f"❌ 錯誤：找不到前端文件 {FRONTEND_FILE}")
        print("請確保文件存在於當前目錄中")
        return

    # 切換到包含前端文件的目錄
    os.chdir(Path(__file__).parent)

    # 創建服務器
    with socketserver.TCPServer((HOST, PORT), CORSHTTPRequestHandler) as httpd:
        print(f"🚀 前端服務器已啟動！")
        print(f"📍 地址: http://0.0.0.0:{PORT}")
        print(f"🌐 本地訪問: http://localhost:{PORT}")
        print(f"💻 筆電訪問: http://192.168.7.75:{PORT}")
        print(f"📁 前端文件: {FRONTEND_FILE}")
        print(f"🔗 直接訪問: http://192.168.7.75:{PORT}/{FRONTEND_FILE}")
        print(f"⏹️  按 Ctrl+C 停止服務器")
        print("-" * 60)

        # 自動打開瀏覽器
        try:
            webbrowser.open(f"http://localhost:{PORT}/{FRONTEND_FILE}")
            print("🌐 已自動打開瀏覽器")
        except Exception as e:
            print(f"⚠️  無法自動打開瀏覽器: {e}")
            print(f"請手動訪問: http://localhost:{PORT}/{FRONTEND_FILE}")

        print("-" * 60)
        print("💡 使用說明：")
        print("1. 在筆電瀏覽器中訪問: http://192.168.7.75:8080/frontend_glass.html")
        print("2. 確保API地址設置為: http://192.168.7.75:8000")
        print("3. 點擊「測試連線」確認後端連接正常")
        print("-" * 60)

        try:
            # 啟動服務器
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n🛑 服務器已停止")
        except Exception as e:
            print(f"❌ 服務器錯誤: {e}")


if __name__ == "__main__":
    main()
