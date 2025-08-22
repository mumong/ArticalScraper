#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
简化的配置管理器
"""

import yaml
import logging
from pathlib import Path
from typing import Dict, Any


class ConfigManager:
    """简化的配置管理器"""
    
    def __init__(self, config_file: str = "config.yaml"):
        self.config_file = Path(config_file)
        self.logger = logging.getLogger(__name__)
        self.config = {}
        self.load_config()
    
    def load_config(self):
        """加载配置文件"""
        if not self.config_file.exists():
            raise FileNotFoundError(f"配置文件不存在: {self.config_file}")
        
        try:
            with open(self.config_file, 'r', encoding='utf-8') as f:
                self.config = yaml.safe_load(f)
            
            # 处理环境变量
            self._process_env_vars()
            
            self.logger.info(f"配置加载成功: {self.config_file}")
            
        except Exception as e:
            self.logger.error(f"配置加载失败: {e}")
            raise
    
    def _process_env_vars(self):
        """处理环境变量替换 - 已简化为直接读取配置"""
        # 为了独立运行，不再依赖环境变量
        # 所有配置直接在config.yaml中设置
        pass
    
    def get(self, key: str, default=None):
        """获取配置项"""
        keys = key.split('.')
        value = self.config
        
        try:
            for k in keys:
                value = value[k]
            return value
        except (KeyError, TypeError):
            return default
    
    def get_database_path(self) -> str:
        """获取数据库路径"""
        return self.get('database.path', 'data/tech_articles.db')
    
    def get_log_config(self) -> Dict[str, Any]:
        """获取日志配置"""
        return self.get('logging', {})
    
    def get_crawler_config(self) -> Dict[str, Any]:
        """获取爬虫配置"""
        return self.get('crawler', {})
    
    def get_ai_config(self) -> Dict[str, Any]:
        """获取AI配置"""
        return self.get('ai', {})
    
    def get_sources_config(self) -> Dict[str, Any]:
        """获取数据源配置"""
        return self.get('sources', {})
    
    def get_report_config(self) -> Dict[str, Any]:
        """获取报告配置"""
        return self.get('report', {})
    
    def get_prompt(self, prompt_name: str) -> str:
        """获取提示词模板"""
        return self.get(f'prompts.{prompt_name}', '')
    
    def get_ai_config(self) -> Dict[str, Any]:
        """获取AI配置"""
        return self.get('ai', {})
    
    def get_enabled_sources(self) -> Dict[str, Dict[str, Any]]:
        """获取启用的数据源"""
        sources = self.get_sources_config()
        enabled = {}
        
        for source_id, source_config in sources.items():
            if source_config.get('enabled', True):
                enabled[source_id] = source_config
        
        return enabled