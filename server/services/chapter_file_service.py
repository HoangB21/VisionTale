import os
import json
from server.config.config import load_config
from typing import Dict, List
from .base_service import SingletonService
import logging

logger = logging.getLogger(__name__)


class ChapterFileService(SingletonService):
    def __init__(self):
        self.config = load_config()
        self.projects_path = self.config.get('projects_path', 'projects/')

    def get_chapter_content(self, project_name: str, chapter_name: str) -> str:
        """
        Get the content of the content.txt file for the specified chapter.

        Args:
            project_name (str): Project name
            chapter_name (str): Chapter name, e.g. 'chapter6'

        Returns:
            str: Chapter content. Returns an empty string if the file does not exist.
        """
        try:
            chapter_path = os.path.join(
                self.projects_path, project_name, chapter_name)
            content_path = os.path.join(chapter_path, 'content.txt')
            if os.path.exists(content_path):
                with open(content_path, 'r', encoding='utf-8') as f:
                    return f.read()
            return ''
        except Exception as e:
            logger.error(f"Error reading chapter content: {e}")
            return ''

    def get_latest_chapter(self, project_path: str) -> int:
        """Get the latest chapter number"""
        if not os.path.exists(project_path):
            raise Exception(f"Project path does not exist: {project_path}")

        chapters = [d for d in os.listdir(project_path)
                    if os.path.isdir(os.path.join(project_path, d))
                    and d.startswith("chapter")]
        if not chapters:
            return 1

        latest = max(int(ch.replace("chapter", "")) for ch in chapters)
        return latest

    def generate_span_files(self, project_name: str, chapter_name: str, spans_and_prompts: List[dict]) -> None:
        """
        Generate corresponding files for each text span.

        Args:
            project_name: Project name
            chapter_name: Chapter name
            spans_and_prompts: List containing text spans and scene descriptions

        Raises:
            Exception: Raised when the chapter directory does not exist
        """
        try:
            # Build chapter directory path
            chapter_dir = os.path.join(
                self.projects_path, project_name,  chapter_name)
            print(f"Chapter directory: {chapter_dir}")
            # If chapter directory does not exist, raise an error
            if not os.path.exists(chapter_dir):
                raise Exception(
                    f"Chapter directory does not exist: {chapter_dir}")

            # Clear existing subfolders
            for item in os.listdir(chapter_dir):
                item_path = os.path.join(chapter_dir, item)
                # Only delete folders with numeric names
                if os.path.isdir(item_path) and item.isdigit():
                    import shutil
                    shutil.rmtree(item_path)

            # Create files for each span
            for i, span in enumerate(spans_and_prompts):
                span_dir = os.path.join(chapter_dir, str(i+1))
                os.makedirs(span_dir, exist_ok=True)

                # Write span.txt
                with open(os.path.join(span_dir, 'span.txt'), 'w', encoding='utf-8') as f:
                    f.write(span['content'])

                # Write prompt.json
                prompt_data = {
                    'base_scene': span['base_scene'],
                    'scene': span['scene'],
                    'prompt': ''  # Default is empty
                }
                with open(os.path.join(span_dir, 'prompt.json'), 'w', encoding='utf-8') as f:
                    json.dump(prompt_data, f, ensure_ascii=False, indent=2)

            logging.info(
                f"Generated {len(spans_and_prompts)} scene files for chapter {chapter_name}")

        except Exception as e:
            logging.error(f"Error generating scene files: {str(e)}")
            raise e
