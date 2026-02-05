"""
配置管理器 - 管理 GUI 配置的读写和验证
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class ConfigManager:
    """配置读写管理器"""
    
    # 配置文件路径（相对于项目根目录）
    CONFIG_FILE = Path('config.json')
    
    @classmethod
    def load(cls) -> dict:
        """
        加载配置
        
        Returns:
            完整配置字典，如果文件不存在则返回默认配置
        
        Raises:
            json.JSONDecodeError: 配置文件格式错误（已处理，返回默认值）
        """
        if not cls.CONFIG_FILE.exists():
            logger.info("config.json 不存在，使用默认配置")
            return cls.get_default()
        
        try:
            with open(cls.CONFIG_FILE, 'r', encoding='utf-8') as f:
                config = json.load(f)
            
            # 合并默认值（确保所有字段存在）
            default = cls.get_default()
            merged = cls._deep_merge(default, config)
            
            # 验证配置
            is_valid, errors = cls.validate(merged)
            if not is_valid:
                logger.warning(f"配置验证失败: {errors}，使用部分默认值")
            
            return merged
        
        except json.JSONDecodeError as e:
            logger.error(f"config.json 格式错误: {e}，使用默认配置")
            # 备份损坏的文件
            backup_path = cls.CONFIG_FILE.with_suffix('.json.bak')
            cls.CONFIG_FILE.rename(backup_path)
            logger.info(f"已备份损坏的配置到 {backup_path}")
            return cls.get_default()
    
    @classmethod
    def save(cls, config: dict) -> None:
        """
        保存配置
        
        Args:
            config: 完整配置字典
        
        Raises:
            PermissionError: 无写入权限
            OSError: 其他文件系统错误
        """
        # 更新最后修改时间
        config['last_modified'] = datetime.now().isoformat()
        
        with open(cls.CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
        
        logger.info(f"配置已保存到 {cls.CONFIG_FILE}")
    
    @classmethod
    def get_default(cls) -> dict:
        """
        获取默认配置
        
        Returns:
            默认配置字典
        """
        return {
            "version": "1.0",
            "last_modified": "",
            "theme": "light",
            "asr": {
                "model_type": "fun_asr_nano",
                "vulkan_enable": False,
                "vulkan_force_fp32": False
            },
            "scenes": [
                {
                    "name": "直接打字",
                    "key": "caps_lock",
                    "type": "keyboard",
                    "mode": "hold",
                    "processor": "direct",
                    "enabled": True
                }
            ],
            "llm": {
                "configs": [],
                "processors": {
                    "light": "",
                    "deep": "",
                    "translate": ""
                },
                "interrupt_key": "escape"
            },
            "overlay": {
                "enabled": True,
                "position": "bottom_center",
                "opacity": 0.9,
                "auto_hide_delay": 1.5
            },
            "general": {
                "auto_start_service": False,
                "minimize_to_tray": True
            }
        }
    
    @classmethod
    def validate(cls, config: dict) -> Tuple[bool, List[str]]:
        """
        验证配置合法性
        
        Args:
            config: 配置字典
        
        Returns:
            (是否有效, 错误列表)
        """
        errors = []
        
        # 验证主题
        if config.get('theme') not in ('light', 'dark'):
            errors.append(f"无效的主题值: {config.get('theme')}")
        
        # 验证 ASR 配置
        asr = config.get('asr', {})
        valid_models = ('fun_asr_nano', 'sense_voice', 'paraformer')
        if asr.get('model_type') not in valid_models:
            errors.append(f"无效的 ASR 模型: {asr.get('model_type')}")
        
        # 验证场景配置 (scenes)
        scenes = config.get('scenes', [])
        if not isinstance(scenes, list):
            errors.append("scenes 必须是数组")
        else:
            seen_keys = set()
            for i, scene in enumerate(scenes):
                key = scene.get('key')
                if not key:
                    errors.append(f"场景 {i+1} 缺少 key 字段")
                elif key in seen_keys:
                    errors.append(f"场景按键重复: {key}")
                else:
                    seen_keys.add(key)
                
                if scene.get('type') not in ('keyboard', 'mouse'):
                    errors.append(f"场景 {i+1} 无效的类型: {scene.get('type')}")
                
                if scene.get('mode') not in ('hold', 'toggle'):
                    errors.append(f"场景 {i+1} 无效的模式: {scene.get('mode')}")
        
        # 验证 LLM 配置
        llm = config.get('llm', {})
        configs = llm.get('configs', [])
        if not isinstance(configs, list):
            errors.append("llm.configs 必须是数组")
        
        # 验证悬浮窗配置
        overlay = config.get('overlay', {})
        # 支持内部ID和中文显示值
        valid_positions = {
            'bottom_left': 'bottom_left', '左下角': 'bottom_left',
            'bottom_center': 'bottom_center', '屏幕中下': 'bottom_center',
            'bottom_right': 'bottom_right', '右下角': 'bottom_right'
        }
        current_pos = overlay.get('position')
        if current_pos not in valid_positions:
            errors.append(f"无效的悬浮窗位置: {current_pos}")
        else:
            # 自动规范化为内部ID
            overlay['position'] = valid_positions[current_pos]
        
        opacity = overlay.get('opacity', 0.85)
        if not (0.3 <= opacity <= 1.0):
            errors.append(f"透明度超出范围 (0.3-1.0): {opacity}")
        
        return (len(errors) == 0, errors)
    
    @classmethod
    def _deep_merge(cls, base: dict, override: dict) -> dict:
        """
        深度合并两个字典，override 覆盖 base
        
        Args:
            base: 基础字典
            override: 覆盖字典
        
        Returns:
            合并后的字典
        """
        result = base.copy()
        
        for key, value in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = cls._deep_merge(result[key], value)
            else:
                result[key] = value
        
        return result
