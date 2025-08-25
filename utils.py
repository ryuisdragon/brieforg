#!/usr/bin/env python3
"""
工具函數模組
提供重試機制、快取、錯誤處理和效能監控等功能
"""

import time
import logging
import functools
from typing import Any, Callable, Dict, Optional
import requests
from config import MAX_RETRIES, RETRY_DELAY, LOG_LEVEL, LOG_FORMAT

# 設定日誌
logging.basicConfig(level=getattr(logging, LOG_LEVEL), format=LOG_FORMAT)
logger = logging.getLogger(__name__)

# 簡單的記憶體快取
_cache: Dict[str, Any] = {}

def retry_on_failure(max_retries: int = MAX_RETRIES, delay: float = RETRY_DELAY):
    """
    重試裝飾器
    在函數失敗時自動重試
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    if attempt < max_retries:
                        logger.warning(f"嘗試 {attempt + 1}/{max_retries + 1} 失敗: {e}")
                        time.sleep(delay)
                    else:
                        logger.error(f"所有重試都失敗了: {e}")
            
            raise last_exception
        return wrapper
    return decorator

def cache_result(ttl: int = 300):
    """
    快取裝飾器
    快取函數結果，避免重複計算
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # 生成快取鍵
            cache_key = f"{func.__name__}:{hash(str(args) + str(sorted(kwargs.items())))}"
            
            # 檢查快取
            if cache_key in _cache:
                cached_result, timestamp = _cache[cache_key]
                if time.time() - timestamp < ttl:
                    logger.debug(f"從快取返回 {func.__name__} 的結果")
                    return cached_result
            
            # 執行函數並快取結果
            result = func(*args, **kwargs)
            _cache[cache_key] = (result, time.time())
            logger.debug(f"快取 {func.__name__} 的結果")
            
            return result
        return wrapper
    return decorator

def monitor_performance(func: Callable) -> Callable:
    """
    效能監控裝飾器
    記錄函數執行時間
    """
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        start_time = time.time()
        try:
            result = func(*args, **kwargs)
            execution_time = time.time() - start_time
            logger.info(f"{func.__name__} 執行時間: {execution_time:.3f}秒")
            return result
        except Exception as e:
            execution_time = time.time() - start_time
            logger.error(f"{func.__name__} 執行失敗 (耗時: {execution_time:.3f}秒): {e}")
            raise
    return wrapper

@retry_on_failure()
def make_http_request(url: str, method: str = "GET", **kwargs) -> requests.Response:
    """
    發送 HTTP 請求，帶重試機制
    """
    response = requests.request(method, url, **kwargs)
    response.raise_for_status()
    return response

def clear_cache():
    """清除所有快取"""
    global _cache
    _cache.clear()
    logger.info("快取已清除")

def get_cache_info() -> Dict[str, Any]:
    """獲取快取資訊"""
    return {
        "cache_size": len(_cache),
        "cache_keys": list(_cache.keys())
    }

def handle_ollama_error(error: Exception) -> str:
    """
    處理 Ollama 相關錯誤
    返回用戶友好的錯誤訊息
    """
    error_msg = str(error)
    
    if "Connection refused" in error_msg:
        return "無法連接到 Ollama 服務，請確認 Ollama 是否正在運行"
    elif "timeout" in error_msg.lower():
        return "請求超時，請稍後再試"
    elif "model not found" in error_msg.lower():
        return "指定的模型不存在，請檢查模型名稱"
    elif "out of memory" in error_msg.lower():
        return "記憶體不足，請嘗試使用較小的模型"
    else:
        return f"Ollama 服務錯誤: {error_msg}"

def validate_json_response(response_text: str) -> bool:
    """
    驗證回應是否為有效的 JSON
    """
    import json
    try:
        json.loads(response_text)
        return True
    except json.JSONDecodeError:
        return False

def clean_json_response(response_text: str) -> str:
    """
    清理 JSON 回應，移除 markdown 標記和說明文字，只保留 JSON 部分
    """
    import re
    
    # 移除 markdown 程式碼區塊標記
    cleaned = re.sub(r'```json\s*', '', response_text)
    cleaned = re.sub(r'```\s*$', '', cleaned)
    
    # 尋找 JSON 開始的位置（第一個 { 或 [）
    json_start = -1
    for i, char in enumerate(cleaned):
        if char in '{[':
            json_start = i
            break
    
    if json_start == -1:
        # 如果沒有找到 JSON 開始標記，返回原始內容
        return cleaned.strip()
    
    # 從 JSON 開始位置提取到結尾
    json_part = cleaned[json_start:]
    
    # 嘗試找到 JSON 的結束位置
    brace_count = 0
    bracket_count = 0
    in_string = False
    escape_next = False
    
    for i, char in enumerate(json_part):
        if escape_next:
            escape_next = False
            continue
            
        if char == '\\':
            escape_next = True
            continue
            
        if char == '"' and not escape_next:
            in_string = not in_string
            continue
            
        if not in_string:
            if char == '{':
                brace_count += 1
            elif char == '}':
                brace_count -= 1
            elif char == '[':
                bracket_count += 1
            elif char == ']':
                bracket_count -= 1
                
            # 如果所有括號都匹配了，這就是 JSON 的結束
            if brace_count == 0 and bracket_count == 0:
                json_part = json_part[:i+1]
                break
    
    return json_part.strip() 