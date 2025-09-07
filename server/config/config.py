import json
import os
import yaml
from typing import Dict, Any

config = {}  # Global dictionary shared across modules


def load_config() -> Dict[str, Any]:
    global config
    """Load configuration from config.yaml and update global dictionary"""
    config_path = os.path.join(os.path.dirname(__file__), 'config.yaml')
    with open(config_path, 'r', encoding='utf-8') as f:
        new_config = yaml.safe_load(f) or {}

    # Clear and update global dictionary
    config.clear()
    config.update(new_config)

    # Handle computed properties
    server_dir = os.path.dirname(os.path.dirname(__file__))

    # Convert paths
    if 'relative_projects_path' in config and 'projects_path' not in config:
        config['projects_path'] = os.path.abspath(
            os.path.join(server_dir, config['relative_projects_path']))

    if 'relative_prompts_path' in config and 'prompts_path' not in config:
        config['prompts_path'] = os.path.abspath(
            os.path.join(server_dir, config['relative_prompts_path']))

    if 'default_workflow' in config and 'file' in config['default_workflow']:
        config['default_workflow']['file'] = os.path.abspath(
            os.path.join(server_dir, config['default_workflow']['file']))

    if 'relative_workflow_path' in config and 'workflow_path' not in config:
        config['workflow_path'] = os.path.abspath(
            os.path.join(server_dir, config['relative_workflow_path']))

    # Scan workflow files
    workflow_path = config.get('workflow_path', '')
    config['all_workflow'] = []
    if os.path.exists(workflow_path) and os.path.isdir(workflow_path):
        config['all_workflow'] = [f for f in os.listdir(
            workflow_path) if f.endswith('.json')]

    return config


def save_config(_config: Dict[str, Any]) -> None:
    global config
    """Save configuration and update global dictionary (excluding computed properties)"""
    config_path = os.path.join(os.path.dirname(__file__), 'config.yaml')
    with open(config_path, 'w', encoding='utf-8') as f:
        yaml.dump(_config, f, allow_unicode=True, sort_keys=False)

    # Update only base configuration, preserving computed properties in memory
    config.clear()
    config.update(_config)
    # Reload config to regenerate computed properties
    load_config()


def update_config(updates: Dict[str, Any]) -> Dict[str, Any]:
    global config
    """Update configuration while keeping global dictionary reference intact"""

    # Create a copy of base configuration (filter out computed properties)
    filtered_config = {
        k: v for k, v in config.items()
        if k not in ['projects_path', 'prompts_path', 'workflow_path', 'all_workflow']
    }

    # Handle nested updates
    for key, value in updates.items():
        keys = key.split('.') if '.' in key else [key]
        current = filtered_config
        for k in keys[:-1]:
            current = current.setdefault(k, {})
        current[keys[-1]] = value

    # Save and reload configuration
    save_config(filtered_config)
    return config


def load_prompt_styler():
    prompt_styler_path = os.path.join(
        os.path.dirname(__file__), 'prompt_styler.json')
    with open(prompt_styler_path, 'r', encoding='utf-8') as f:
        styles = json.load(f)
    return styles


def save_prompt_styler(styles):
    prompt_styler_path = os.path.join(
        os.path.dirname(__file__), 'prompt_styler.json')
    with open(prompt_styler_path, 'w', encoding='utf-8') as f:
        json.dump(styles, f, ensure_ascii=False, indent=4)


def get_prompt_style_by_name(style_name: str) -> Dict[str, Any] | None:
    """Find prompt style by name"""
    styles = load_prompt_styler()
    for style in styles:
        if style.get('name') == style_name:
            return style
    return None
