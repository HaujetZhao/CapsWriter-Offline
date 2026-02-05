"""
LLM 角色加载器

功能：
1. 自动加载 LLM/ 目录下的所有角色
2. 从模块中提取角色配置
3. 错误处理和验证
"""

import sys
import logging
from pathlib import Path
from typing import Dict
from util.llm.llm_role_config import RoleConfig

logger = logging.getLogger('client')


class RoleLoader:
    """角色加载器"""

    def __init__(self):
        self.roles_registry: Dict[str, RoleConfig] = {}
        from config import BASE_DIR
        self.llm_dir = Path(BASE_DIR) / 'LLM'
        self.load_all_roles()

    def register_role(self, module_name: str, module) -> str:
        """从模块注册角色

        Returns:
            角色名称
        """
        from dataclasses import fields
        
        # 1. 自动从 RoleConfig 获取所有的命名字段
        config = {'module_name': module_name}
        for f in fields(RoleConfig):
            if f.name == 'module_name':
                continue
            # 如果模块（角色脚本）里定义了这个变量，就读取它
            if hasattr(module, f.name):
                config[f.name] = getattr(module, f.name)
            # 否则不设置，让 RoleConfig 自动使用 dataclass 的默认值

        # 2. 创建 RoleConfig 对象
        role_config = RoleConfig(**config)
        
        # 3. API 配置继承：如果 api_key 为空，从 GUI 配置中查找匹配的配置
        if not role_config.api_key:
            role_config = self._inherit_api_config(role_config)

        # 空字符串和「默认」都表示默认角色
        role_name = role_config.name or RoleConfig.DEFAULT_ROLE_NAME

        self.roles_registry[role_name] = role_config

        return role_name
    
    def _inherit_api_config(self, role_config: RoleConfig) -> RoleConfig:
        """从 GUI 配置中继承 API 配置
        
        继承逻辑（优先级从高到低）：
        1. 从 llm.processors 查找当前角色的绑定（如 "翻译": "gemini / gemini-2.5-flash"）
           - 解析出 provider 和 model，完全覆盖角色文件的设置
        2. 从 llm.configs 查找匹配的 API 配置（api_url, api_key）
        3. 如果 processors 中没有绑定，则回退到角色文件的 provider/model
        """
        from dataclasses import replace
        try:
            from config import Config
            llm_config = Config.raw.get('llm', {})
            configs = llm_config.get('configs', [])
            processors = llm_config.get('processors', {})
            
            # 获取角色名
            role_name = role_config.name or RoleConfig.DEFAULT_ROLE_NAME
            logger.debug(f"[API继承] 角色: {role_name}, 原始provider: {role_config.provider}, 原始model: {role_config.model}")
            logger.debug(f"[API继承] processors: {processors}")
            logger.debug(f"[API继承] configs: {configs}")
            
            # 1. 从 processors 绑定获取 provider / model
            target_provider = role_config.provider
            target_model = role_config.model
            
            if role_name in processors:
                binding = processors[role_name]  # 如 "gemini / gemini-2.5-flash"
                if ' / ' in binding:
                    parts = binding.split(' / ', 1)
                    target_provider = parts[0].strip()
                    target_model = parts[1].strip()
            
            if not configs:
                # 没有 configs，只更新 provider/model
                return replace(role_config, provider=target_provider, model=target_model)
            
            # 2. 从 configs 查找完整 API 配置
            # 优先匹配 provider + model
            for cfg in configs:
                if cfg.get('provider') == target_provider and cfg.get('model') == target_model:
                    logger.info(f"[API继承] 精确匹配成功: provider={target_provider}, model={target_model}, api_key前4位={cfg.get('api_key', '')[:4] if cfg.get('api_key') else 'None'}")
                    return replace(
                        role_config,
                        provider=target_provider,
                        model=target_model,
                        api_url=cfg.get('base_url', ''),
                        api_key=cfg.get('api_key', '')
                    )
            
            # 其次只匹配 provider
            for cfg in configs:
                if cfg.get('provider') == target_provider:
                    return replace(
                        role_config,
                        provider=target_provider,
                        model=target_model,
                        api_url=cfg.get('base_url', ''),
                        api_key=cfg.get('api_key', '')
                    )
            
            # 没找到匹配的 configs，只更新 provider/model
            return replace(role_config, provider=target_provider, model=target_model)
        except Exception as e:
            logger.warning(f"[API继承] 继承失败: {e}")
            return role_config

    def load_all_roles(self):
        """加载所有角色"""
        self.roles_registry.clear()
        errors = []

        for file_path in sorted(self.llm_dir.glob('*.py')):
            if file_path.name == '__init__.py':
                continue

            try:
                module_name = f"LLM.{file_path.stem}"

                if module_name in sys.modules:
                    del sys.modules[module_name]

                module = __import__(module_name, fromlist=[''])

                if not hasattr(module, 'provider') or not hasattr(module, 'model'):
                    errors.append({
                        'file': file_path.name,
                        'error': '缺少必需字段',
                        'details': '缺少 provider 或 model'
                    })
                    continue

                self.register_role(module_name, module)

            except SyntaxError as e:
                errors.append({
                    'file': file_path.name,
                    'error': '语法错误',
                    'details': f"第 {e.lineno} 行: {e.msg}"
                })
            except Exception as e:
                errors.append({
                    'file': file_path.name,
                    'error': type(e).__name__,
                    'details': str(e)
                })

        return errors

    def reload_role(self, file_path: str):
        """重新加载单个角色"""
        try:
            file_path = Path(file_path)

            if file_path.suffix != '.py' or file_path.name == '__init__.py':
                return False, "不是角色文件"

            module_name = f"LLM.{file_path.stem}"

            if module_name in sys.modules:
                del sys.modules[module_name]

            module = __import__(module_name, fromlist=[''])

            if not hasattr(module, 'provider') or not hasattr(module, 'model'):
                return False, "缺少必需字段"

            self.register_role(module_name, module)

            return True, None

        except SyntaxError as e:
            return False, f"语法错误 (第 {e.lineno} 行): {e.msg}"
        except Exception as e:
            return False, f"{type(e).__name__}: {str(e)}"

    def get_roles(self) -> Dict[str, RoleConfig]:
        """获取所有角色"""
        return self.roles_registry.copy()

    def get_default_role(self) -> RoleConfig:
        """获取默认角色"""
        return self.roles_registry.get(RoleConfig.DEFAULT_ROLE_NAME, RoleConfig(name=RoleConfig.DEFAULT_ROLE_NAME, module_name='', process=False))

    def get_role_by_name(self, name: str) -> RoleConfig:
        """根据名字获取角色"""
        return self.roles_registry.get(name, RoleConfig(name=RoleConfig.DEFAULT_ROLE_NAME, module_name='', process=False))
