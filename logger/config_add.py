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