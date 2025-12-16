#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
高级日志模块 - 大学生五育并举访谈智能体
提供统一的、高性能的日志输出功能
支持异步日志、结构化日志、日志旋转、上下文管理等
"""

import logging
import os
import sys
import json
import asyncio
import threading
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, Union, List, Callable
from logging.handlers import RotatingFileHandler, TimedRotatingFileHandler
from pathlib import Path
from contextvars import ContextVar
from dataclasses import dataclass, asdict, field
from enum import Enum
import queue
import time

from config import LOG_CONFIG, LOG_DIR, ensure_dirs


# ==================== 枚举和数据结构 ====================
class LogLevel(Enum):
    """日志级别枚举"""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class LogComponent(Enum):
    """日志组件枚举"""
    SYSTEM = "system"
    API = "api"
    SESSION = "session"
    INTERVIEW = "interview"
    DATABASE = "database"
    CACHE = "cache"
    SECURITY = "security"
    BUSINESS = "business"


@dataclass
class LogContext:
    """日志上下文信息"""
    request_id: str = ""
    user_id: str = ""
    session_id: str = ""
    interview_id: str = ""
    component: str = ""
    trace_id: str = ""
    extra: Dict[str, Any] = field(default_factory=dict)


@dataclass
class StructuredLog:
    """结构化日志数据类"""
    timestamp: str
    level: str
    component: str
    message: str
    module: str
    function: str
    line_no: int
    context: Dict[str, Any]
    extra: Dict[str, Any] = field(default_factory=dict)
    exception: Optional[str] = None
    duration_ms: Optional[float] = None


# ==================== 上下文管理 ====================
_log_context_var: ContextVar[LogContext] = ContextVar('log_context', default=LogContext())
_context_lock = threading.RLock()


class LogContextManager:
    """日志上下文管理器"""
    
    @staticmethod
    def get_context() -> LogContext:
        """获取当前日志上下文"""
        return _log_context_var.get()
    
    @staticmethod
    def set_context(context: LogContext):
        """设置日志上下文"""
        _log_context_var.set(context)
    
    @staticmethod
    def update_context(**kwargs):
        """更新日志上下文"""
        context = _log_context_var.get()
        for key, value in kwargs.items():
            if hasattr(context, key):
                setattr(context, key, value)
            else:
                context.extra[key] = value
        _log_context_var.set(context)
    
    @staticmethod
    def clear_context():
        """清空日志上下文"""
        _log_context_var.set(LogContext())
    
    @staticmethod
    def create_context_scope(**kwargs):
        """创建上下文作用域"""
        return LogContextScope(**kwargs)


class LogContextScope:
    """日志上下文作用域（with语句支持）"""
    
    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self.original_context = None
    
    def __enter__(self):
        self.original_context = LogContextManager.get_context()
        LogContextManager.update_context(**self.kwargs)
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        LogContextManager.set_context(self.original_context)


# ==================== 异步日志处理器 ====================
class AsyncLogHandler:
    """异步日志处理器（减少I/O阻塞）"""
    
    def __init__(self, max_queue_size: int = 10000):
        self.log_queue = queue.Queue(maxsize=max_queue_size)
        self._stop_event = threading.Event()
        self._worker_thread = None
        self._handlers = []
    
    def add_handler(self, handler: logging.Handler):
        """添加日志处理器"""
        self._handlers.append(handler)
    
    def start(self):
        """启动异步日志处理器"""
        if self._worker_thread is None or not self._worker_thread.is_alive():
            self._stop_event.clear()
            self._worker_thread = threading.Thread(
                target=self._process_logs,
                name="AsyncLogHandler",
                daemon=True
            )
            self._worker_thread.start()
    
    def stop(self):
        """停止异步日志处理器"""
        self._stop_event.set()
        if self._worker_thread:
            self._worker_thread.join(timeout=5)
    
    def emit(self, record: logging.LogRecord):
        """发送日志记录到队列"""
        try:
            self.log_queue.put_nowait(record)
        except queue.Full:
            # 队列满时丢弃日志，避免阻塞
            sys.stderr.write(f"Log queue is full, dropping log: {record.getMessage()}\n")
    
    def _process_logs(self):
        """处理日志队列"""
        while not self._stop_event.is_set():
            try:
                # 设置超时，以便定期检查停止事件
                record = self.log_queue.get(timeout=0.1)
                self._handle_record(record)
                self.log_queue.task_done()
            except queue.Empty:
                continue
            except Exception as e:
                sys.stderr.write(f"Error processing log: {e}\n")
    
    def _handle_record(self, record: logging.LogRecord):
        """处理单个日志记录"""
        for handler in self._handlers:
            try:
                handler.handle(record)
            except Exception as e:
                sys.stderr.write(f"Error in log handler {handler}: {e}\n")


# ==================== 智能日志处理器 ====================
class JsonFileHandler(RotatingFileHandler):
    """JSON格式文件处理器"""
    
    def __init__(self, filename, **kwargs):
        ensure_dirs()
        super().__init__(filename, **kwargs)
    
    def format(self, record: logging.LogRecord) -> str:
        """格式化为JSON字符串"""
        log_data = getattr(record, 'structured_data', None)
        if log_data is None:
            # 转换为结构化日志
            context = LogContextManager.get_context()
            log_data = {
                "timestamp": datetime.fromtimestamp(record.created).isoformat(),
                "level": record.levelname,
                "logger": record.name,
                "module": record.module,
                "function": record.funcName,
                "line": record.lineno,
                "message": record.getMessage(),
                "context": {
                    "request_id": context.request_id,
                    "session_id": context.session_id,
                    "user_id": context.user_id,
                    "interview_id": context.interview_id,
                    "component": context.component,
                },
                "extra": context.extra,
            }
            
            if hasattr(record, 'duration_ms'):
                log_data['duration_ms'] = record.duration_ms
            
            if record.exc_info:
                log_data['exception'] = self.formatException(record.exc_info)
        
        return json.dumps(log_data, ensure_ascii=False, default=str)


class ErrorNotificationHandler(logging.Handler):
    """错误通知处理器（可扩展为发送邮件、钉钉、企业微信等）"""
    
    def __init__(self, threshold=logging.ERROR):
        super().__init__(level=threshold)
        self.threshold = threshold
    
    def emit(self, record):
        if record.levelno >= self.threshold:
            # 这里可以实现错误通知逻辑
            # 例如：发送邮件、钉钉机器人、企业微信等
            self._send_notification(record)
    
    def _send_notification(self, record):
        """发送错误通知"""
        # 示例：打印到stderr，实际应用中可替换为真正的通知逻辑
        error_msg = self.format(record)
        sys.stderr.write(f"🚨 CRITICAL ERROR NOTIFICATION: {error_msg}\n")


# ==================== 主日志管理器 ====================
class InterviewLogger:
    """访谈系统高级日志管理器"""
    
    _instance = None
    _lock = threading.Lock()
    _loggers: Dict[str, logging.Logger] = {}
    _async_handler: Optional[AsyncLogHandler] = None
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if not hasattr(self, '_initialized'):
            self._initialized = True
            self._setup_async_handler()
    
    def _setup_async_handler(self):
        """设置异步日志处理器"""
        if LOG_CONFIG.async_logging:
            self._async_handler = AsyncLogHandler(
                max_queue_size=LOG_CONFIG.async_queue_size
            )
            self._async_handler.start()
    
    def get_logger(self, 
                   name: str = "interview",
                   component: str = None,
                   with_context: bool = True) -> logging.Logger:
        """
        获取或创建日志记录器
        
        Args:
            name: 日志记录器名称
            component: 组件名称
            with_context: 是否添加上下文信息
            
        Returns:
            配置好的 Logger 实例
        """
        logger_key = f"{name}:{component}" if component else name
        
        with self._lock:
            if logger_key in self._loggers:
                return self._loggers[logger_key]
            
            logger = logging.getLogger(logger_key)
            
            # 避免重复配置
            if logger.handlers:
                self._loggers[logger_key] = logger
                return logger
            
            # 设置日志级别
            log_level = getattr(logging, LOG_CONFIG.level, logging.INFO)
            logger.setLevel(log_level)
            
            # 避免传播到根logger
            logger.propagate = False
            
            # 创建处理器
            handlers = self._create_handlers(name, component)
            
            for handler in handlers:
                if LOG_CONFIG.async_logging and self._async_handler:
                    # 使用异步处理
                    self._async_handler.add_handler(handler)
                else:
                    logger.addHandler(handler)
            
            # 添加自定义过滤器
            if with_context:
                logger.addFilter(self._context_filter)
            
            self._loggers[logger_key] = logger
            return logger
    
    def _create_handlers(self, name: str, component: str = None) -> List[logging.Handler]:
        """创建日志处理器列表"""
        handlers = []
        
        # 创建格式化器
        formatter = self._create_formatter(component)
        
        # 控制台处理器
        if LOG_CONFIG.log_to_console:
            console_handler = logging.StreamHandler(sys.stdout)
            console_handler.setFormatter(formatter)
            console_handler.setLevel(getattr(logging, LOG_CONFIG.console_level, LOG_CONFIG.level))
            handlers.append(console_handler)
        
        # 文件处理器
        if LOG_CONFIG.log_to_file:
            # 普通文本日志
            text_handler = self._create_file_handler(name, component, formatter, text_format=True)
            handlers.append(text_handler)
            
            # JSON格式日志
            if LOG_CONFIG.json_format:
                json_handler = self._create_file_handler(name, component, formatter, text_format=False)
                json_handler.setFormatter(logging.Formatter('%(message)s'))  # JSON处理器只输出消息
                handlers.append(json_handler)
        
        # 错误通知处理器
        if LOG_CONFIG.error_notification:
            error_handler = ErrorNotificationHandler(threshold=logging.ERROR)
            error_handler.setFormatter(formatter)
            handlers.append(error_handler)
        
        return handlers
    
    def _create_file_handler(self, 
                            name: str, 
                            component: str,
                            formatter: logging.Formatter,
                            text_format: bool = True) -> logging.Handler:
        """创建文件处理器"""
        # 构建文件路径
        if component:
            filename = f"{name}_{component}"
        else:
            filename = name
        
        log_dir = Path(LOG_DIR)
        log_dir.mkdir(parents=True, exist_ok=True)
        
        if LOG_CONFIG.rotation_strategy == "time":
            # 按时间轮转
            handler = TimedRotatingFileHandler(
                filename=log_dir / f"{filename}.log",
                when=LOG_CONFIG.rotation_when,
                interval=LOG_CONFIG.rotation_interval,
                backupCount=LOG_CONFIG.backup_count,
                encoding='utf-8'
            )
        else:
            # 按大小轮转（默认）
            handler = RotatingFileHandler(
                filename=log_dir / f"{filename}.log",
                maxBytes=LOG_CONFIG.max_file_size,
                backupCount=LOG_CONFIG.backup_count,
                encoding='utf-8'
            )
        
        handler.setFormatter(formatter)
        handler.setLevel(getattr(logging, LOG_CONFIG.file_level, LOG_CONFIG.level))
        return handler
    
    def _create_formatter(self, component: str = None) -> logging.Formatter:
        """创建日志格式化器"""
        if component and LOG_CONFIG.component_specific_format.get(component):
            # 使用组件特定的格式
            fmt = LOG_CONFIG.component_specific_format[component]
        else:
            fmt = LOG_CONFIG.log_format
        
        return logging.Formatter(
            fmt,
            datefmt=LOG_CONFIG.date_format
        )
    
    def _context_filter(self, record: logging.LogRecord) -> bool:
        """上下文过滤器"""
        context = LogContextManager.get_context()
        
        # 添加上下文信息到日志记录
        record.request_id = context.request_id
        record.session_id = context.session_id
        record.user_id = context.user_id
        record.interview_id = context.interview_id
        record.component = context.component or record.name
        
        # 添加额外的上下文信息
        for key, value in context.extra.items():
            setattr(record, f"ctx_{key}", value)
        
        return True
    
    def shutdown(self):
        """关闭日志系统"""
        if self._async_handler:
            self._async_handler.stop()
        
        # 关闭所有处理器
        for logger in self._loggers.values():
            for handler in logger.handlers:
                handler.close()
        
        logging.shutdown()


# ==================== 便捷日志函数（同步） ====================
_logger_manager = InterviewLogger()


def _get_logger(component: str = None) -> logging.Logger:
    """获取日志记录器（带组件信息）"""
    return _logger_manager.get_logger("interview", component)


def debug(msg: str, 
          *args, 
          component: str = LogComponent.SYSTEM.value,
          extra: Dict[str, Any] = None,
          **kwargs):
    """记录调试日志"""
    logger = _get_logger(component)
    if extra:
        LogContextManager.update_context(**extra)
    logger.debug(msg, *args, **kwargs)


def info(msg: str, 
         *args, 
         component: str = LogComponent.SYSTEM.value,
         extra: Dict[str, Any] = None,
         **kwargs):
    """记录信息日志"""
    logger = _get_logger(component)
    if extra:
        LogContextManager.update_context(**extra)
    logger.info(msg, *args, **kwargs)


def warning(msg: str, 
            *args, 
            component: str = LogComponent.SYSTEM.value,
            extra: Dict[str, Any] = None,
            **kwargs):
    """记录警告日志"""
    logger = _get_logger(component)
    if extra:
        LogContextManager.update_context(**extra)
    logger.warning(msg, *args, **kwargs)


def error(msg: str, 
          *args, 
          component: str = LogComponent.SYSTEM.value,
          extra: Dict[str, Any] = None,
          **kwargs):
    """记录错误日志"""
    logger = _get_logger(component)
    if extra:
        LogContextManager.update_context(**extra)
    logger.error(msg, *args, **kwargs)


def critical(msg: str, 
             *args, 
             component: str = LogComponent.SYSTEM.value,
             extra: Dict[str, Any] = None,
             **kwargs):
    """记录严重错误日志"""
    logger = _get_logger(component)
    if extra:
        LogContextManager.update_context(**extra)
    logger.critical(msg, *args, **kwargs)


def exception(msg: str, 
              *args, 
              component: str = LogComponent.SYSTEM.value,
              extra: Dict[str, Any] = None,
              **kwargs):
    """记录异常日志（包含堆栈信息）"""
    logger = _get_logger(component)
    if extra:
        LogContextManager.update_context(**extra)
    logger.exception(msg, *args, **kwargs)


# ==================== 异步日志函数 ====================
async def async_debug(msg: str, *args, **kwargs):
    """异步记录调试日志"""
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, lambda: debug(msg, *args, **kwargs))


async def async_info(msg: str, *args, **kwargs):
    """异步记录信息日志"""
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, lambda: info(msg, *args, **kwargs))


async def async_error(msg: str, *args, **kwargs):
    """异步记录错误日志"""
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, lambda: error(msg, *args, **kwargs))


# ==================== 结构化日志函数 ====================
def log_structured(level: LogLevel,
                   message: str,
                   component: str,
                   extra_data: Dict[str, Any] = None,
                   exception_info: Exception = None,
                   duration_ms: float = None):
    """记录结构化日志"""
    import inspect
    
    # 获取调用者信息
    frame = inspect.currentframe().f_back
    module = inspect.getmodule(frame).__name__ if inspect.getmodule(frame) else "unknown"
    function = frame.f_code.co_name
    line_no = frame.f_lineno
    
    # 获取上下文
    context = LogContextManager.get_context()
    
    # 构建结构化日志
    structured_log = StructuredLog(
        timestamp=datetime.now().isoformat(),
        level=level.value,
        component=component,
        message=message,
        module=module,
        function=function,
        line_no=line_no,
        context=asdict(context),
        extra=extra_data or {},
        exception=str(exception_info) if exception_info else None,
        duration_ms=duration_ms
    )
    
    # 记录日志
    logger = _get_logger(component)
    log_method = getattr(logger, level.value.lower())
    
    # 创建日志记录
    record = logger.makeRecord(
        name=logger.name,
        level=getattr(logging, level.value),
        fn=module,
        lno=line_no,
        msg=json.dumps(asdict(structured_log), ensure_ascii=False, default=str),
        args=(),
        exc_info=None,
        func=function,
        extra={'structured_data': asdict(structured_log)}
    )
    
    logger.handle(record)


# ==================== 特定场景的日志记录 ====================
def log_api_call(api_name: str, 
                 success: bool, 
                 duration: float, 
                 error_msg: str = None,
                 request_data: Dict = None,
                 response_data: Dict = None):
    """记录API调用日志"""
    component = LogComponent.API.value
    level = LogLevel.INFO if success else LogLevel.ERROR
    
    extra = {
        "api_name": api_name,
        "success": success,
        "duration_ms": duration * 1000,
        "error_msg": error_msg,
        "request_data": request_data,
        "response_data": response_data
    }
    
    if success:
        message = f"API调用成功 - {api_name} - 耗时: {duration:.2f}s"
    else:
        message = f"API调用失败 - {api_name} - 耗时: {duration:.2f}s - 错误: {error_msg}"
    
    log_structured(level, message, component, extra_data=extra)


def log_session(session_id: str, 
                action: str, 
                details: str = None,
                user_id: str = None,
                metadata: Dict = None):
    """记录会话日志"""
    with LogContextManager.create_context_scope(
        session_id=session_id,
        user_id=user_id or "",
        component=LogComponent.SESSION.value
    ):
        message = f"会话操作 - {action}"
        if details:
            message += f" - {details}"
        
        log_structured(
            LogLevel.INFO,
            message,
            LogComponent.SESSION.value,
            extra_data={
                "session_id": session_id,
                "action": action,
                "details": details,
                "user_id": user_id,
                "metadata": metadata
            }
        )


def log_interview(session_id: str, 
                  event: str, 
                  data: Dict = None,
                  metrics: Dict = None):
    """记录访谈事件日志"""
    with LogContextManager.create_context_scope(
        session_id=session_id,
        component=LogComponent.INTERVIEW.value
    ):
        message = f"访谈事件 - {event}"
        
        log_structured(
            LogLevel.INFO,
            message,
            LogComponent.INTERVIEW.value,
            extra_data={
                "session_id": session_id,
                "event": event,
                "data": data,
                "metrics": metrics
            }
        )


def log_performance(operation: str, 
                    duration_ms: float,
                    component: str = LogComponent.SYSTEM.value,
                    details: Dict = None):
    """记录性能日志"""
    level = LogLevel.WARNING if duration_ms > 1000 else LogLevel.INFO
    
    log_structured(
        level,
        f"性能日志 - {operation} - 耗时: {duration_ms:.2f}ms",
        component,
        extra_data={
            "operation": operation,
            "duration_ms": duration_ms,
            "details": details
        },
        duration_ms=duration_ms
    )


# ==================== 装饰器和上下文管理器 ====================
def log_execution_time(component: str = LogComponent.SYSTEM.value):
    """记录函数执行时间的装饰器"""
    def decorator(func):
        def wrapper(*args, **kwargs):
            start_time = time.perf_counter()
            try:
                result = func(*args, **kwargs)
                return result
            finally:
                duration_ms = (time.perf_counter() - start_time) * 1000
                log_performance(
                    operation=f"{func.__module__}.{func.__name__}",
                    duration_ms=duration_ms,
                    component=component
                )
        return wrapper
    
    if callable(component):
        # 被用作无参装饰器
        func = component
        component = LogComponent.SYSTEM.value
        return decorator(func)
    
    return decorator


class LogContextScope:
    """带性能监控的日志上下文管理器"""
    
    def __init__(self, operation: str, component: str = LogComponent.SYSTEM.value, **context):
        self.operation = operation
        self.component = component
        self.context = context
        self.start_time = None
    
    def __enter__(self):
        self.start_time = time.perf_counter()
        LogContextManager.update_context(**self.context)
        info(f"开始执行: {self.operation}", component=self.component)
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        duration_ms = (time.perf_counter() - self.start_time) * 1000
        
        if exc_type is None:
            info(f"完成执行: {self.operation} - 耗时: {duration_ms:.2f}ms", 
                 component=self.component)
        else:
            error(f"执行失败: {self.operation} - 错误: {exc_val} - 耗时: {duration_ms:.2f}ms", 
                  component=self.component)
        
        LogContextManager.clear_context()


# ==================== 工具函数 ====================
def setup_logging():
    """初始化日志系统"""
    ensure_dirs()
    return _logger_manager


def shutdown_logging():
    """关闭日志系统"""
    _logger_manager.shutdown()


def get_logger(name: str = "interview", component: str = None) -> logging.Logger:
    """获取日志记录器（公开接口）"""
    return _logger_manager.get_logger(name, component)


def set_global_context(**kwargs):
    """设置全局日志上下文"""
    LogContextManager.update_context(**kwargs)


# ==================== 默认导出 ====================
__all__ = [
    'debug', 'info', 'warning', 'error', 'critical', 'exception',
    'async_debug', 'async_info', 'async_error',
    'log_structured', 'log_api_call', 'log_session', 'log_interview', 'log_performance',
    'log_execution_time', 'LogContextScope',
    'setup_logging', 'shutdown_logging', 'get_logger', 'set_global_context',
    'LogLevel', 'LogComponent', 'LogContext', 'LogContextManager',
    'InterviewLogger',
]
