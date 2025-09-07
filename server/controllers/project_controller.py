from fastapi import APIRouter, Depends, HTTPException, Request
import os
# from server.services.chapter_file_service import ChapterFileService
from server.services.llm_service import LLMService
from server.config.config import load_config
import json
from datetime import datetime
from server.utils.response import make_response
import shutil

router = APIRouter(prefix='/project')


@router.post('/create')
async def create_project(request: Request):
    """Create a new project"""
    try:
        data = await request.json()
        project_name = data.get('project_name')

        if not project_name:
            return make_response(status='error', msg='Project name cannot be empty')

        config = load_config()
        projects_path = config.get('projects_path', 'projects/')

        # Create project directory
        project_path = os.path.join(projects_path, project_name)
        if os.path.exists(project_path):
            return make_response(status='error', msg='Project already exists')

        os.makedirs(project_path)

        # Create empty knowledge graph file
        kg_path = os.path.join(project_path, 'kg.json')
        with open(kg_path, 'w', encoding='utf-8') as f:
            json.dump({
                'locked_entities': [],
                'relationships': [],
                'entities': []
            }, f, ensure_ascii=False, indent=2)

        scenes_path = os.path.join(project_path, 'scenes.json')
        with open(scenes_path, 'w', encoding='utf-8') as f:
            json.dump({}, f, ensure_ascii=False, indent=2)

        # Automatically create first chapter
        first_chapter = 'chapter1'
        first_chapter_path = os.path.join(project_path, first_chapter)

        # Create new chapter directory and content.txt file
        os.makedirs(first_chapter_path, exist_ok=True)
        content_file = os.path.join(first_chapter_path, 'content.txt')
        with open(content_file, 'w', encoding='utf-8') as f:
            f.write('')

        return make_response(
            data={
                'project_name': project_name,
                'first_chapter': first_chapter
            },
            msg='Project created successfully'
        )
    except Exception as e:
        return make_response(status='error', msg=f'Error creating project: {str(e)}')


@router.get('/info')
async def get_project_info(project_name: str):
    """Retrieve project information"""
    if not project_name:
        return make_response(status='error', msg='Project ID cannot be empty')

    config = load_config()
    projects_path = config.get('projects_path', 'projects/')

    # Build project path
    project_path = os.path.join(projects_path, project_name)
    if not os.path.exists(project_path):
        return make_response(status='error', msg='Project does not exist')

    try:
        # Get chapter list
        chapters = []
        for chapter_dir in sorted(os.listdir(project_path)):
            if chapter_dir.startswith('chapter'):
                chapter_path = os.path.join(project_path, chapter_dir)
                if os.path.isdir(chapter_path):
                    # Get chapter information
                    spans = []
                    for span_dir in sorted(os.listdir(chapter_path)):
                        span_path = os.path.join(chapter_path, span_dir)
                        if os.path.isdir(span_path):
                            # Get span information
                            span_info = {
                                'id': span_dir,
                                'has_content': os.path.exists(os.path.join(span_path, 'span.txt')),
                                'has_prompt': os.path.exists(os.path.join(span_path, 'prompt.txt')),
                                'images': [f for f in os.listdir(span_path) if f.lower().endswith(('.png', '.jpg', '.jpeg', '.gif'))],
                                'audios': [f for f in os.listdir(span_path) if f.lower().endswith('.wav')]
                            }
                            spans.append(span_info)

                    chapters.append({
                        'id': chapter_dir,
                        'spans': spans
                    })

        # Get knowledge graph
        kg_path = os.path.join(project_path, 'kg.json')
        with open(kg_path, 'r', encoding='utf-8') as f:
            knowledge_graph = json.load(f)

        return make_response(
            data={
                'project_name': project_name,
                'chapters': chapters,
                'knowledge_graph': knowledge_graph
            },
            msg='Project information retrieved successfully'
        )
    except Exception as e:
        return make_response(status='error', msg=f'Error retrieving project information: {str(e)}')


@router.get('/kg')
async def get_knowledge_graph(project_name: str):
    """Retrieve project knowledge graph"""
    if not project_name:
        return make_response(status='error', msg='Project ID cannot be empty')

    config = load_config()
    projects_path = config.get('projects_path', 'projects/')

    # Build knowledge graph file path
    kg_path = os.path.join(projects_path, project_name, 'kg.json')
    if not os.path.exists(kg_path):
        return make_response(status='error', msg='Knowledge graph does not exist')

    try:
        with open(kg_path, 'r', encoding='utf-8') as f:
            knowledge_graph = json.load(f)

        return make_response(
            data={
                'project_name': project_name,
                'knowledge_graph': knowledge_graph
            },
            msg='Knowledge graph retrieved successfully'
        )
    except Exception as e:
        return make_response(status='error', msg=f'Error retrieving knowledge graph: {str(e)}')


@router.get('/list')
async def get_project_list():
    """Retrieve list of all projects"""
    try:
        config = load_config()
        projects_path = config.get('projects_path', 'projects/')

        # Ensure project directory exists
        if not os.path.exists(projects_path):
            return make_response(status='error', msg='Project directory does not exist')

        # Get all project names (directory names)
        project_names = [name for name in os.listdir(projects_path)
                         if os.path.isdir(os.path.join(projects_path, name))]

        return make_response(
            data=project_names,
            msg='Project list retrieved successfully'
        )
    except Exception as e:
        return make_response(status='error', msg=f'Error retrieving project list: {str(e)}')


@router.put('/update')
async def update_project(request: Request):
    """Update project name"""
    try:
        data = await request.json()
        old_name = data.get('old_name')
        new_name = data.get('new_name')

        if not all([old_name, new_name]):
            return make_response(status='error', msg='Project name cannot be empty')

        config = load_config()
        projects_path = config.get('projects_path', 'projects/')

        # Check if original project exists
        old_project_path = os.path.join(projects_path, old_name)
        if not os.path.exists(old_project_path):
            return make_response(status='error', msg='Project does not exist')

        # Check if new name already exists
        new_project_path = os.path.join(projects_path, new_name)
        if os.path.exists(new_project_path):
            return make_response(status='error', msg='New project name already exists')

        # Rename project directory
        os.rename(old_project_path, new_project_path)

        return make_response(
            data={'project_name': new_name},
            msg='Project updated successfully'
        )
    except Exception as e:
        return make_response(status='error', msg=f'Error updating project: {str(e)}')


@router.delete('/delete/{project_name}')
async def delete_project(project_name: str):
    """Delete a project"""
    try:
        config = load_config()
        projects_path = config.get('projects_path', 'projects/')

        # Build project path
        project_path = os.path.join(projects_path, project_name)
        if not os.path.exists(project_path):
            return make_response(status='error', msg='Project does not exist')

        # Delete project directory and its contents
        shutil.rmtree(project_path)

        return make_response(msg='Project deleted successfully')
    except Exception as e:
        return make_response(status='error', msg=f'Error deleting project: {str(e)}')


@router.post('/create_from_story')
async def create_project_from_story(request: Request):
    """Create a new project and split story into chapters"""
    try:
        data = await request.json()
        project_name = data.get('project_name')
        story_content = data.get('story_content')

        if not project_name:
            return make_response(status='error', msg='Tên dự án không được để trống')
        if not story_content:
            return make_response(status='error', msg='Nội dung câu chuyện không được để trống')

        config = load_config()
        projects_path = config.get('projects_path', 'projects/')

        # Create project directory
        project_path = os.path.join(projects_path, project_name)
        if os.path.exists(project_path):
            return make_response(status='error', msg='Dự án đã tồn tại')

        os.makedirs(project_path)

        # Create empty knowledge graph file
        kg_path = os.path.join(project_path, 'kg.json')
        with open(kg_path, 'w', encoding='utf-8') as f:
            json.dump({
                'locked_entities': [],
                'relationships': [],
                'entities': []
            }, f, ensure_ascii=False, indent=2)

        # Create empty scenes file
        scenes_path = os.path.join(project_path, 'scenes.json')
        with open(scenes_path, 'w', encoding='utf-8') as f:
            json.dump({}, f, ensure_ascii=False, indent=2)

        # Split story into chapters using LLMService
        llm_service = LLMService()
        chapters = await llm_service.split_story_into_chapters(story_content)

        # Create chapter directories and content.txt files
        # chapter_file_service = ChapterFileService()
        chapter_names = []
        for i, chapter_content in enumerate(chapters, 1):
            chapter_name = f'chapter{i}'
            chapter_path = os.path.join(project_path, chapter_name)
            os.makedirs(chapter_path, exist_ok=True)
            content_file = os.path.join(chapter_path, 'content.txt')
            with open(content_file, 'w', encoding='utf-8') as f:
                f.write(chapter_content)
            chapter_names.append(chapter_name)

        return make_response(
            data={
                'project_name': project_name,
                'chapters': chapter_names
            },
            msg='Dự án và các chương được tạo thành công'
        )
    except Exception as e:
        return make_response(status='error', msg=f'Lỗi khi tạo dự án: {str(e)}')
