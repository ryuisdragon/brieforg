#!/usr/bin/env python3
"""
統一的LLM客戶端
整合Ollama服務，提供統一的AI模型調用介面
"""

import json
import logging
import asyncio
from typing import Any, Dict, List
import aiohttp
import requests

from config import OLLAMA_HOST, OLLAMA_PORT, OLLAMA_DEFAULT_MODEL, OLLAMA_TIMEOUT

logger = logging.getLogger(__name__)


class LLMClient:
    """統一的LLM客戶端"""

    def __init__(self, host: str = None, port: int = None, model: str = None):
        """初始化LLM客戶端"""
        self.host = host or OLLAMA_HOST
        self.port = port or OLLAMA_PORT
        self.model = model or OLLAMA_DEFAULT_MODEL
        self.base_url = f"http://{self.host}:{self.port}"
        self.timeout = OLLAMA_TIMEOUT

        # 健康狀態
        self.healthy = False

        # 檢查服務可用性
        self.healthy = self._check_service_availability()

    def _check_service_availability(self) -> bool:
        """檢查Ollama服務可用性"""
        try:
            response = requests.get(f"{self.base_url}/api/tags", timeout=5)
            if response.status_code == 200:
                logger.info("Ollama服務連接正常")
                return True
            else:
                logger.warning(f"Ollama服務回應異常: {response.status_code}")
                return False
        except Exception as e:
            logger.error(f"無法連接到Ollama服務: {e}")
            return False

    async def generate_response(
        self,
        prompt: str,
        model: str = None,
        temperature: float = 0.7,
        max_tokens: int = 2000,
        system_prompt: str = None,
    ) -> str:
        """生成AI回應"""
        try:
            # 構建請求數據
            request_data = {
                "model": model or self.model,
                "prompt": prompt,
                "stream": False,
                "options": {"temperature": temperature, "num_predict": max_tokens},
            }

            # 如果有系統提示詞，添加到選項中
            if system_prompt:
                request_data["system"] = system_prompt

            # 發送請求
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.base_url}/api/generate",
                    json=request_data,
                    timeout=aiohttp.ClientTimeout(total=self.timeout),
                ) as response:
                    if response.status == 200:
                        result = await response.json()
                        return result.get("response", "")
                    else:
                        error_msg = f"LLM請求失敗: {response.status}"
                        logger.error(error_msg)
                        return f"抱歉，AI服務暫時無法回應。錯誤：{error_msg}"

        except asyncio.TimeoutError:
            error_msg = "LLM請求超時"
            logger.error(error_msg)
            return f"抱歉，AI回應超時，請稍後再試。"
        except Exception as e:
            error_msg = f"LLM請求異常: {str(e)}"
            logger.error(error_msg)
            return f"抱歉，AI服務出現異常：{str(e)}"

    async def generate_structured_response(
        self,
        prompt: str,
        expected_format: str = "JSON",
        model: str = None,
        temperature: float = 0.3,
    ) -> Dict[str, Any]:
        """生成結構化回應"""
        try:
            # 添加格式要求到提示詞
            formatted_prompt = f"""
{prompt}

請以{expected_format}格式回應，確保回應格式正確且可解析。
"""

            # 生成回應
            response = await self.generate_response(
                formatted_prompt, model=model, temperature=temperature
            )

            # 嘗試解析結構化回應
            if expected_format.upper() == "JSON":
                return self._parse_json_response(response)
            else:
                return {"raw_response": response, "format": expected_format}

        except Exception as e:
            logger.error(f"生成結構化回應失敗: {e}")
            return {"error": str(e), "raw_response": ""}

    def _parse_json_response(self, response: str) -> Dict[str, Any]:
        """解析JSON回應"""
        try:
            # 嘗試找到JSON部分
            if "{" in response and "}" in response:
                start = response.find("{")
                end = response.rfind("}") + 1
                json_str = response[start:end]

                # 清理可能的格式問題
                json_str = json_str.strip()
                if json_str.startswith("```json"):
                    json_str = json_str[7:]
                if json_str.endswith("```"):
                    json_str = json_str[:-3]

                return json.loads(json_str)
            else:
                return {"raw_response": response, "error": "未找到JSON格式"}

        except json.JSONDecodeError as e:
            logger.warning(f"JSON解析失敗: {e}")
            return {"raw_response": response, "error": f"JSON解析失敗: {str(e)}"}
        except Exception as e:
            logger.error(f"解析回應失敗: {e}")
            return {"raw_response": response, "error": f"解析失敗: {str(e)}"}

    async def chat_completion(
        self,
        messages: List[Dict[str, str]],
        model: str = None,
        temperature: float = 0.7,
    ) -> str:
        """聊天完成"""
        try:
            # 構建聊天提示詞
            chat_prompt = ""
            for message in messages:
                role = message.get("role", "user")
                content = message.get("content", "")
                if role == "system":
                    chat_prompt += f"系統: {content}\n\n"
                elif role == "user":
                    chat_prompt += f"用戶: {content}\n\n"
                elif role == "assistant":
                    chat_prompt += f"助手: {content}\n\n"

            # 生成回應
            response = await self.generate_response(
                chat_prompt, model=model, temperature=temperature
            )

            return response

        except Exception as e:
            logger.error(f"聊天完成失敗: {e}")
            return f"抱歉，聊天服務出現異常：{str(e)}"

    async def extract_entities(
        self, text: str, entity_types: List[str], model: str = None
    ) -> Dict[str, Any]:
        """提取實體"""
        try:
            # 構建實體提取提示詞
            entity_list = "、".join(entity_types)
            prompt = f"""
請從以下文本中提取{entity_list}：

文本：{text}

請以JSON格式回傳提取結果，格式如下：
{{
    "entities": {{
        "entity_type": ["value1", "value2"]
    }}
}}
"""

            # 生成結構化回應
            result = await self.generate_structured_response(
                prompt, "JSON", model=model, temperature=0.1
            )

            return result

        except Exception as e:
            logger.error(f"實體提取失敗: {e}")
            return {"error": str(e), "entities": {}}

    async def classify_text(
        self, text: str, categories: List[str], model: str = None
    ) -> Dict[str, Any]:
        """文本分類"""
        try:
            # 構建分類提示詞
            category_list = "、".join(categories)
            prompt = f"""
請將以下文本分類到以下類別之一：{category_list}

文本：{text}

請以JSON格式回傳分類結果，格式如下：
{{
    "category": "selected_category",
    "confidence": 0.95,
    "reasoning": "分類理由"
}}
"""

            # 生成結構化回應
            result = await self.generate_structured_response(
                prompt, "JSON", model=model, temperature=0.3
            )

            return result

        except Exception as e:
            logger.error(f"文本分類失敗: {e}")
            return {"error": str(e), "category": "unknown"}

    async def summarize_text(
        self, text: str, max_length: int = 200, model: str = None
    ) -> str:
        """文本摘要"""
        try:
            # 構建摘要提示詞
            prompt = f"""
請為以下文本生成摘要，摘要長度不超過{max_length}字：

{text}

請直接回傳摘要內容，不要包含其他格式。
"""

            # 生成回應
            response = await self.generate_response(
                prompt, model=model, temperature=0.5, max_tokens=max_length * 2
            )

            return response.strip()

        except Exception as e:
            logger.error(f"文本摘要失敗: {e}")
            return f"摘要生成失敗：{str(e)}"

    def get_available_models(self) -> List[Dict[str, Any]]:
        """獲取可用模型列表"""
        try:
            response = requests.get(f"{self.base_url}/api/tags", timeout=5)
            if response.status_code == 200:
                data = response.json()
                return data.get("models", [])
            else:
                logger.warning(f"獲取模型列表失敗: {response.status_code}")
                return []
        except Exception as e:
            logger.error(f"獲取模型列表異常: {e}")
            return []

    def get_model_info(self, model_name: str = None) -> Dict[str, Any]:
        """獲取模型資訊"""
        try:
            model = model_name or self.model
            response = requests.get(
                f"{self.base_url}/api/show", json={"name": model}, timeout=5
            )
            if response.status_code == 200:
                return response.json()
            else:
                logger.warning(f"獲取模型資訊失敗: {response.status_code}")
                return {}
        except Exception as e:
            logger.error(f"獲取模型資訊異常: {e}")
            return {}

    async def health_check(self) -> Dict[str, Any]:
        """健康檢查"""
        try:
            # 檢查服務連接
            service_ok = self._check_service_availability()

            # 檢查模型可用性
            models = self.get_available_models()
            model_ok = len(models) > 0

            # 測試簡單生成
            test_response = await self.generate_response(
                "測試", temperature=0.1, max_tokens=10
            )
            generation_ok = len(test_response) > 0

            return {
                "service_status": "healthy" if service_ok else "unhealthy",
                "model_status": "healthy" if model_ok else "unhealthy",
                "generation_status": "healthy" if generation_ok else "unhealthy",
                "available_models": [m["name"] for m in models],
                "current_model": self.model,
                "timestamp": asyncio.get_event_loop().time(),
            }

        except Exception as e:
            logger.error(f"健康檢查失敗: {e}")
            return {
                "service_status": "error",
                "error": str(e),
                "timestamp": asyncio.get_event_loop().time(),
            }
