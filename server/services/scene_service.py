import os
import json
from server.config.config import load_config
from typing import Dict, List
from .base_service import SingletonService
import logging

logger = logging.getLogger(__name__)


class SceneService(SingletonService):
    def _initialize(self):
        self.config = load_config()
        self.scenes_cache = {}

    def _get_scene_path(self, project_name: str) -> str:
        return os.path.join(self.config['projects_path'], project_name, 'scenes.json')

    def load_scenes(self, project_name: str) -> Dict[str, str]:
        """
        Load scene information for a project.
        """
        if project_name in self.scenes_cache:
            return self.scenes_cache[project_name]

        scenes_path = self._get_scene_path(project_name)
        default_scenes = {}

        if not os.path.exists(scenes_path):
            self.scenes_cache[project_name] = default_scenes
            return default_scenes

        with open(scenes_path, 'r', encoding='utf-8') as f:
            scenes = json.load(f)

        self.scenes_cache[project_name] = scenes
        return scenes

    def update_scenes(self, project_name: str, new_scenes: Dict[str, str], force_update: bool = False) -> bool:
        """
        Update scene information for a project.
        """
        try:
            scenes_path = self._get_scene_path(project_name)
            scenes = self.load_scenes(project_name)

            for scene_name, scene_desc in new_scenes.items():
                if scene_name:
                    if not force_update and scene_name in scenes:
                        continue
                    scenes[scene_name] = scene_desc
                    logger.info(f"Updated scene: {scene_name}, {scene_desc}")

            self.scenes_cache[project_name] = scenes

            with open(scenes_path, 'w', encoding='utf-8') as f:
                json.dump(scenes, f, ensure_ascii=False, indent=2)

            return True
        except Exception as e:
            logger.error(f"Error updating scene information: {str(e)}")
            raise e

    def delete_scenes(self, project_name: str, scene_names: List[str]) -> bool:
        """
        Delete scene information for a project.
        """
        try:
            scenes = self.load_scenes(project_name)

            for scene_name in scene_names:
                if scene_name in scenes:
                    del scenes[scene_name]

            self.scenes_cache[project_name] = scenes
            scenes_path = self._get_scene_path(project_name)

            with open(scenes_path, 'w', encoding='utf-8') as f:
                json.dump(scenes, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            logger.error(f"Error deleting scene information: {str(e)}")
            raise e

    def get_scene_names(self, project_name: str) -> List[str]:
        """
        Get all scene names for a project.
        """
        scenes = self.load_scenes(project_name)
        return list(scenes.keys())

    def get_scene_descs(self, project_name: str, scene_names: List[str]) -> List[str]:
        """
        Get descriptions for multiple scenes in a project.
        """
        scenes = self.load_scenes(project_name)
        return [scenes[scene_name] for scene_name in scene_names if scene_name in scenes]

    def get_scene_dict(self, project_name: str, scene_names: List[str]) -> Dict[str, str]:
        """
        Get dictionary of scenes for a project.
        """
        scenes = self.load_scenes(project_name)
        return {scene_name: scenes[scene_name] for scene_name in scene_names if scene_name in scenes}
