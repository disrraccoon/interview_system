#!/usr/bin/env python3
# coding: utf-8
"""
配置文件 - 大学生五育并举访谈智能体
包含 API 配置、系统参数等
"""

import os
from dataclasses import dataclass, field

# ----------------------------
# 路径配置
# ----------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_DIR = os.path.join(BASE_DIR, "logs")
EXPORT_DIR = os.path.join(BASE_DIR, "exports")


# ----------------------------
# 访谈系统配置
# ----------------------------
@dataclass
class InterviewConfig:
    """访谈系统配置"""
    total_questions: int = 6  # 每次访谈的题目数量
    min_answer_length: int = 15  # 触发追问的最小回答长度（降低阈值）
    max_followups_per_question: int = 3  # 每题最大追问次数
    max_depth_score: int = 4  # 回答深度最高分（提高要求）
    
    # 深度评分关键词（更丰富的关键词库）
    depth_keywords: list = field(default_factory=lambda: [
        # 具体经历类
        "例子", "经历", "具体", "当时", "那次", "有一次", "记得",
        # 感受反思类  
        "感受", "感觉", "觉得", "认为", "反思", "思考", "意识到",
        # 影响收获类
        "影响", "收获", "学到", "成长", "改变", "进步", "提升",
        # 细节描述类
        "因为", "所以", "后来", "结果", "过程", "细节",
        # 情感表达类
        "开心", "难过", "紧张", "兴奋", "感动", "印象深刻",
        # 互动关系类
        "帮助", "支持", "合作", "沟通", "交流", "一起"
    ])
    
    # 通用关键词（用于提取回答关键词）
    common_keywords: list = field(default_factory=lambda: [
        "时间", "方法", "计划", "目标", "团队", 
        "互动", "冲突", "经验", "学习", "情绪",
        "家人", "朋友", "老师", "同学", "邻居"
    ])
@dataclass
class LogConfig:
    # 基础配置
    level: str = "INFO"
    console_level: str = "INFO"
    file_level: str = "DEBUG"
    
    # 输出目标
    log_to_console: bool = True
    log_to_file: bool = True
    
    # 文件配置
    max_file_size: int = 10 * 1024 * 1024  # 10MB
    backup_count: int = 10
    rotation_strategy: str = "size"  # "size" 或 "time"
    rotation_when: str = "midnight"  # 当rotation_strategy为"time"时生效
    rotation_interval: int = 1
    
    # 格式配置
    log_format: str = "%(asctime)s - %(name)s - %(levelname)s - %(module)s:%(lineno)d - %(message)s"
    date_format: str = "%Y-%m-%d %H:%M:%S"
    json_format: bool = False  # 是否同时输出JSON格式日志
    
    # 组件特定格式
    component_specific_format: Dict[str, str] = field(default_factory=dict)
    
    # 异步日志
    async_logging: bool = True
    async_queue_size: int = 10000
    
    # 错误通知
    error_notification: bool = False


# ----------------------------
# Web 服务配置
# ----------------------------
@dataclass
class WebConfig:
    """Web服务配置"""
    host: str = "0.0.0.0"
    port: int = 7860
    share: bool = True  # 是否生成公网链接
    title: str = "大学生五育并举访谈智能体"
    max_sessions: int = 100  # 最大同时会话数
    session_timeout: int = 3600  # 会话超时时间（秒）


# ----------------------------
# 日志配置
# ----------------------------
@dataclass
class LogConfig:
    """日志配置"""
    level: str = "INFO"  # DEBUG, INFO, WARNING, ERROR
    log_to_file: bool = True
    log_to_console: bool = True
    log_format: str = "[%(asctime)s] [%(levelname)s] %(name)s: %(message)s"
    date_format: str = "%Y-%m-%d %H:%M:%S"
    max_file_size: int = 10 * 1024 * 1024  # 10MB
    backup_count: int = 5


# ----------------------------
# 默认配置实例
# ----------------------------
INTERVIEW_CONFIG = InterviewConfig()
WEB_CONFIG = WebConfig()
LOG_CONFIG = LogConfig()


# ----------------------------
# 确保目录存在
# ----------------------------
def ensure_dirs():
    """确保必要的目录存在"""
    for dir_path in [LOG_DIR, EXPORT_DIR]:
        if not os.path.exists(dir_path):
            os.makedirs(dir_path)
