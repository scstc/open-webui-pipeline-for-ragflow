"""
title: RagFlow Pipeline
author: luyilong2015
date: 2025-01-28
version: 1.0
license: MIT
description: A pipeline for retrieving relevant information from a knowledge base using the RagFlow's Agent Interface.
requirements: datasets>=2.6.1, sentence-transformers>=2.2.0
"""
#智能客服
from typing import List, Union, Generator, Iterator, Optional
from pydantic import BaseModel
import requests
import json

#API_KEY: ragflow apikey
#AGENT_ID: ragflow agentid
#HOST: ragflow host  start with http:// or https:// 
#PORT: ragflow port
class Pipeline:
    class Valves(BaseModel):
        API_KEY: str
        AGENT_ID: str
        HOST: str
        PORT: str

    def __init__(self):
        self.session_id=None
        self.debug=True
        self.sessionKV={}
        self.valves = self.Valves(
            **{
                "API_KEY": "",
                "AGENT_ID": "",
                "HOST":"",
                "PORT":""
            }
        )

    async def on_startup(self):
        pass

    async def on_shutdown(self):
        # This function is called when the server is stopped.
        pass
    async def inlet(self, body: dict, user: Optional[dict] = None) -> dict:
        # This function is called before the OpenAI API request is made. You can modify the form data before it is sent to the OpenAI API.
        print(f"inlet: {__name__}")
        if self.debug:
            chat_id=body['metadata']['chat_id']
            print(f"inlet: {__name__} - chat_id:{chat_id}")
            if self.sessionKV.get(chat_id):
                self.session_id=self.sessionKV.get(chat_id)
                print(f"cache ragflow's session_id is : {self.session_id}")
            else:
                #创建session
                session_url = f"{self.valves.HOST}:{self.valves.PORT}/api/v1/agents/{self.valves.AGENT_ID}/sessions"
                session_headers = {
                    'content-Type': 'application/json',
                    'Authorization': 'Bearer '+self.valves.API_KEY
                }
                session_data={}
                session_response = requests.post(session_url, headers=session_headers, json=session_data)
                json_res=json.loads(session_response.text)
                self.session_id=json_res['data']['id']
                self.sessionKV[chat_id]=self.session_id
                print(f"new ragflow's session_id is : {json_res['data']['id']}")
            #print(f"inlet: {__name__} - body:{body}")
            print(f"inlet: {__name__} - user:")
            print(user)
        return body

    async def outlet(self, body: dict, user: Optional[dict] = None) -> dict:
        # This function is called after the OpenAI API response is completed. You can modify the messages after they are received from the OpenAI API.
        print(f"outlet: {__name__}")
        if self.debug:
            print(f"outlet: {__name__} - body:")
            #print(body)
            print(f"outlet chat_id: {body['chat_id']}")
            print(f"outlet session_id: {body['session_id']}")
            print(f"outlet: {__name__} - user:")
            print(user)
        return body
    def pipe(self, user_message: str, model_id: str, messages: List[dict], body: dict) -> Union[str, Generator]:
        # 构建适配 OpenAI Compatible API 的请求体
        openai_messages = [
            {"role": msg["role"], "content": msg["content"]} for msg in messages
        ]

        # 使用新的 endpoint
        chat_url = f"{self.valves.HOST}:{self.valves.PORT}/api/v1/chats_openai/{self.valves.AGENT_ID}/chat/completions"
        
        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {self.valves.API_KEY}'
        }

        # 构造符合 OpenAI 格式的请求体
        payload = {
            "model": model_id or "model",
            "messages": openai_messages,
            "stream": True
        }

        print(f"Requesting URL: {chat_url}")  # Debug
        print(f"Payload: {payload}")          # Debug

        try:
            response = requests.post(chat_url, headers=headers, json=payload, stream=True)
            response.raise_for_status()

            collected_content = ""
            
            for line in response.iter_lines():
                if not line:
                    continue
                try:
                    line_str = line.decode('utf-8')
                    if line_str.startswith("data: "):
                        data_str = line_str[6:]  # 去掉 "data: " 前缀
                        if data_str == "[DONE]":
                            break
                        chunk = json.loads(data_str)

                        delta = chunk["choices"][0]["delta"]
                        content = delta.get("content", "")

                        if content:
                            collected_content += content
                            yield content  # 流式返回内容

                except json.JSONDecodeError:
                    continue  # 忽略无效行

        except requests.RequestException as e:
            yield f"Workflow request failed: {str(e)}"