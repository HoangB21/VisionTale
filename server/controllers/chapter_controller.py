import asyncio
from fastapi import APIRouter, Depends, HTTPException, Request
import os
from server.config.config import load_config
import json
from datetime import datetime
from server.utils.response import make_response
from server.services.llm_service import LLMService
from server.services.chapter_file_service import ChapterFileService
import logging
from fastapi.responses import StreamingResponse

router = APIRouter(prefix='/chapter')
llm_service = LLMService()
chapter_file_server = ChapterFileService()


@router.post('/create')
async def create_chapter(request: Request):
    """Create a new chapter"""
    data = await request.json()
    project_name = data.get('project_name')

    if not project_name:
        return make_response(status='error', msg='Missing required parameters')

    try:
        config = load_config()
        projects_path = config.get('projects_path', 'projects/')
        project_path = os.path.join(projects_path, project_name)

        # Get the latest chapter number
        latest_num = chapter_file_server.get_latest_chapter(project_path)
        new_chapter = f'chapter{latest_num + 1}'
        new_chapter_path = os.path.join(project_path, new_chapter)

        # Create new chapter directory and content.txt file
        os.makedirs(new_chapter_path, exist_ok=True)
        content_file = os.path.join(new_chapter_path, 'content.txt')
        with open(content_file, 'w', encoding='utf-8') as f:
            f.write('')

        return make_response(data={'chapter': new_chapter}, msg='Chapter created successfully')

    except Exception as e:
        return make_response(status='error', msg=str(e))


@router.post('/generate')
async def generate_chapter(request: Request):
    """Generate chapter content"""
    data = await request.json()
    project_name = data.get('project_name')
    chapter_name = data.get('chapter_name')
    prompt = data.get('prompt')
    is_continuation = data.get('is_continuation', False)
    use_last_chapter = data.get('use_last_chapter', True)

    if not all([project_name, chapter_name, prompt]):
        return make_response(status='error', msg='Missing required parameters')

    try:
        config = load_config()
        projects_path = config.get('projects_path', 'projects/')
        chapter_path = os.path.join(projects_path, project_name, chapter_name)

        if not os.path.exists(chapter_path):
            return make_response(status='error', msg='Chapter path does not exist')

        # Get previous chapter content as context
        if use_last_chapter:
            last_content = chapter_file_server.get_chapter_content(
                project_name, f'chapter{int(chapter_name[7:]) - 1}')
        else:
            last_content = ''

        # Create a generator
        async def event_stream():
            try:
                if is_continuation:
                    generator = llm_service.continue_story(
                        prompt, project_name, last_content)
                else:
                    generator = llm_service.generate_text(
                        prompt, project_name, last_content)

                async for generated_text in generator:
                    if await request.is_disconnected():
                        break
                    yield f"data: {generated_text}\n\n"
            except asyncio.CancelledError:
                # Handle client disconnection
                print("Client connection interrupted")
            finally:
                # Perform necessary cleanup
                if 'generator' in locals():
                    await generator.aclose()

        return StreamingResponse(
            event_stream(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "Content-Type": "text/event-stream",
                "X-Accel-Buffering": "no"
            }
        )

    except Exception as e:
        return make_response(status='error', msg=str(e))


@router.post('/save')
async def save_chapter_content(request: Request):
    """Save chapter content"""
    data = await request.json()
    project_name = data.get('project_name')
    chapter_name = data.get('chapter_name')
    content = data.get('content')

    if not all([project_name, chapter_name, content]):
        return make_response(status='error', msg='Missing required parameters')

    try:
        config = load_config()
        projects_path = config.get('projects_path', 'projects/')
        chapter_path = os.path.join(projects_path, project_name, chapter_name)

        if not os.path.exists(chapter_path):
            os.makedirs(chapter_path)

        # Save content
        content_file = os.path.join(chapter_path, 'content.txt')
        with open(content_file, 'w', encoding='utf-8') as f:
            f.write(content)

        return make_response(msg='Save successful')

    except Exception as e:
        return make_response(status='error', msg=str(e))


@router.post('/split_text')
async def split_text(request: Request):
    """Split chapter text into spans and generate prompts"""
    data = await request.json()
    project_name = data.get('project_name')
    chapter_name = data.get('chapter_name')

    if not project_name or not chapter_name:
        return make_response(status='error', msg='Missing project_name or chapter_name')

    try:
        # Get chapter content using llm_service
        content = chapter_file_server.get_chapter_content(
            project_name, chapter_name)
        if not content:
            return make_response(status='error', msg=f'Content not found for chapter {chapter_name}')

        # Call llm_service to split text and generate descriptions
        spans_and_prompts = await llm_service.split_text_and_generate_prompts(project_name, content)

        # Check for errors
        if not spans_and_prompts:
            return make_response(status='error', msg='Text splitting failed, please try again.')

        if all('error' in span for span in spans_and_prompts):
            return make_response(status='error', msg='Text splitting failed', detail=spans_and_prompts)

        print("Split count:", len(spans_and_prompts))
        print("spans_and_prompts:", spans_and_prompts)
        # Generate corresponding files
        chapter_file_server.generate_span_files(
            project_name, chapter_name, spans_and_prompts)

        return make_response(status='success', msg='Split successful', data=spans_and_prompts)

    except Exception as e:
        return make_response(status='error', msg=f'Error splitting text: {str(e)}')


@router.get('/list')
async def get_chapter_list(project_name: str):
    """Get list of all chapters for a project"""
    if not project_name:
        return make_response(status='error', msg='Project name cannot be empty')

    config = load_config()
    projects_path = config.get('projects_path', 'projects/')
    project_path = os.path.join(projects_path, project_name)

    if not os.path.exists(project_path):
        return make_response(status='error', msg='Project does not exist')

    try:
        # Get all chapter directories and sort them
        chapters = []
        for item in sorted(os.listdir(project_path)):
            item_path = os.path.join(project_path, item)
            if os.path.isdir(item_path) and item.startswith('chapter'):
                chapters.append(item)
        # Sort chapters by number instead of string
        chapters.sort(key=lambda x: int(x.replace('chapter', '')))
        return make_response(data=chapters)
    except Exception as e:
        return make_response(status='error', msg=str(e))


@router.get('/content')
async def get_chapter_content(project_name: str, chapter_name: str):
    """Get content.txt content for specified chapter"""
    try:
        content = chapter_file_server.get_chapter_content(
            project_name, chapter_name)
        return make_response(data={'content': content}, msg='Retrieved successfully')

    except Exception as e:
        return make_response(status='error', msg=str(e))


@router.post('/extract_characters')
async def extract_characters(request: Request):
    """Extract character information from chapter"""
    data = await request.json()
    project_name = data.get('project_name')
    chapter_name = data.get('chapter_name')

    if not all([project_name, chapter_name]):
        return make_response(status='error', msg='Missing required parameters')

    try:
        config = load_config()
        projects_path = config.get('projects_path', 'projects/')
        chapter_path = os.path.join(projects_path, project_name, chapter_name)
        content_file = os.path.join(chapter_path, 'content.txt')

        if not os.path.exists(content_file):
            return make_response(status='error', msg='Chapter content file does not exist')

        # Read chapter content
        with open(content_file, 'r', encoding='utf-8') as f:
            content = f.read()

        # Call LLM service to extract characters
        characters = await llm_service.extract_character(content, project_name)
        return make_response(data=characters, msg='Extraction successful')

    except Exception as e:
        return make_response(status='error', msg=str(e))


@router.get('/scene_list')
async def get_chapter_scene_list(project_name: str, chapter_name: str):
    """Get scene list for chapter"""
    if not project_name or not chapter_name:
        return make_response(status='error', msg='Missing project_name or chapter_name')

    try:
        config = load_config()
        projects_path = config.get('projects_path', 'projects/')
        chapter_dir = os.path.join(projects_path, project_name, chapter_name)
        if not os.path.exists(chapter_dir):
            return make_response(status='error', msg=f'Chapter directory not found: {chapter_dir}')

        scene_list = []
        # Iterate through all numerically named subfolders
        for item in sorted(os.listdir(chapter_dir), key=lambda x: int(x) if x.isdigit() else float('inf')):
            if not item.isdigit():
                continue

            span_dir = os.path.join(chapter_dir, item)
            if not os.path.isdir(span_dir):
                continue

            # Read span.txt
            span_file = os.path.join(span_dir, 'span.txt')
            prompt_file = os.path.join(span_dir, 'prompt.json')

            if not os.path.exists(span_file) or not os.path.exists(prompt_file):
                continue

            with open(span_file, 'r', encoding='utf-8') as f:
                content = f.read()

            with open(prompt_file, 'r', encoding='utf-8') as f:
                prompt_data = json.load(f)

            scene_list.append({
                'id': str(item),
                'content': content,
                'base_scene': prompt_data.get('base_scene', ''),
                'scene': prompt_data.get('scene', ''),
                'prompt': prompt_data.get('prompt', '')
            })

        return make_response(status='success', data=scene_list)

    except Exception as e:
        return make_response(status='error', msg=f'Failed to get scene list: {str(e)}')


@router.post('/translate_prompt')
async def translate_prompt(request: Request):
    """
    Convert scene description to AI drawing prompts
    Request parameters:
        project_name: Project name
        prompts: List of scene descriptions
    Returns:
        List of prompts
    """
    try:
        data = await request.json()
        project_name = data.get('project_name')
        prompts = data.get('prompts', [])

        if not project_name or not prompts:
            return make_response(status='error', msg='Missing required parameters')

        if not isinstance(prompts, list):
            return make_response(status='error', msg='prompts must be a list')

        translated_prompts = await llm_service.translate_prompt(project_name, prompts)
        return make_response(data=translated_prompts, msg='Prompt translation successful')

    except Exception as e:
        logging.error(f'Failed to convert prompts: {str(e)}')
        return make_response(status='error', msg=f'Failed to convert prompts: {str(e)}')


@router.post('/save_scenes')
async def save_scenes(request: Request):
    """
    Save scene modifications
    """
    try:
        data = await request.json()
        project_name = data.get('project_name')
        chapter_name = data.get('chapter_name')
        scenes = data.get('scenes')

        if not all([project_name, chapter_name, scenes]):
            return make_response(status='error', msg='Missing required parameters')

        # Get chapter directory
        config = load_config()
        chapter_dir = os.path.join(
            config['projects_path'], project_name, chapter_name)
        if not os.path.exists(chapter_dir):
            return make_response(status='error', msg='Chapter does not exist')
        print("Scenes: ", scenes)
        # Save modifications for each scene
        for scene in scenes:
            # Use scene number
            scene_index = scene.get('id')
            if not scene_index:
                continue

            scene_dir = os.path.join(chapter_dir, str(scene_index))

            # Create scene directory (if it doesn't exist)
            os.makedirs(scene_dir, exist_ok=True)

            # Save split segments
            if 'span' in scene:
                with open(os.path.join(scene_dir, 'span.txt'), 'w', encoding='utf-8') as f:
                    f.write(scene['span'])

            # Save scene description and prompts
            if 'scene' in scene or 'prompt' in scene:
                prompt_data = {
                    'base_scene': scene.get('base_scene', ''),
                    'scene': scene.get('scene', ''),
                    'prompt': scene.get('prompt', '')
                }
                with open(os.path.join(scene_dir, 'prompt.json'), 'w', encoding='utf-8') as f:
                    json.dump(prompt_data, f, ensure_ascii=False, indent=2)

        return make_response(status='success', msg='Save successful')

    except Exception as e:
        logging.error(f'Failed to save scenes: {str(e)}')
        return make_response(status='error', msg=f'Save failed: {str(e)}')
