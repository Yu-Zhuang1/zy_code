from typing import List
from pydantic import BaseModel, Field

# 1. 定义列表中“字典”元素的结构
class ItemObject(BaseModel):
    name: str = Field(..., description="编造的名字")
    age: str = Field(..., description="编造的年龄")

# 2. 定义最外层的结构，包含一个列表
class ResponseFormat(BaseModel):
    # 这是一个包含 ItemObject 的列表
    results: List[ItemObject] = Field(..., description="包含多个字典元素的列表")

class MarkdownResponse(BaseModel):
    content: str = Field(..., description="Markdown 格式的分析内容，必须为纯净的Markdown格式字符串，不要包含多余的字符，可以直接存储进.md文件")    