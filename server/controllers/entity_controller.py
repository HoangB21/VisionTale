from fastapi import APIRouter, Depends, HTTPException, Request, Query
import json
import os
import logging
import shutil
from pathlib import Path
from server.services.kg_service import KGService
from server.services.scene_service import SceneService
from server.utils.response import make_response
from server.config.config import load_config

router = APIRouter(prefix='/entity')
kg_service = KGService()
scene_service = SceneService()


@router.get('/character/list')
async def get_characters(project_name: str = Query(..., description="Project name")):
    """Retrieve all character information for a project"""
    try:
        if not project_name:
            return make_response(status='error', msg='Project does not exist')

        # Get entity list
        characters = kg_service.inquire_entity_list(project_name)
        characters = json.loads(characters) if isinstance(
            characters, str) else characters

        # Get locked entities
        locked_entities = kg_service.get_locked_entities(project_name)

        return make_response(data={
            'characters': characters,
            'locked_entities': locked_entities
        })
    except Exception as e:
        return make_response(status='error', msg=str(e))


@router.post('/character/update')
async def update_character(request: Request):
    """Update character information"""
    try:
        data = await request.json()
        project_name = data.get('project_name')
        name = data.get('name')
        attributes = data.get('attributes', {})

        if not project_name:
            return make_response(status='error', msg='Project does not exist')

        # Update entity attributes using kg_service and save
        result = kg_service.modify_entity(
            project_name, name, attributes, save_kg=True)
        return make_response(data=result)
    except Exception as e:
        return make_response(status='error', msg=str(e))


@router.post('/character/toggle_lock')
async def toggle_lock(request: Request):
    """Toggle entity prompt lock"""
    try:
        data = await request.json()
        project_name = data.get('project_name')
        entity_name = data.get('entity_name')

        if not project_name:
            return make_response(status='error', msg='Project does not exist')

        # Toggle entity lock using kg_service and save
        is_locked = kg_service.toggle_entity_lock(
            project_name, entity_name, save_kg=True)
        return make_response(data={'is_locked': is_locked})
    except Exception as e:
        return make_response(status='error', msg=str(e))


@router.delete('/character/{name}')
async def delete_character(name: str, project_name: str = Query(..., description="Project name")):
    """
    Delete a character entity

    Parameters:
        name (str): Entity name

    Returns:
        dict: Response result
    """
    try:
        if not project_name:
            return make_response(status='error', msg='Project does not exist')

        # Delete entity and save
        result = kg_service.delete_entity(project_name, name, save_kg=True)

        # Delete corresponding reference image folder
        try:
            config = load_config()
            projects_path = config.get('projects_path', 'projects')
            character_folder = Path(projects_path) / \
                project_name / "Character" / name
            if character_folder.exists() and character_folder.is_dir():
                shutil.rmtree(character_folder)
                logging.info(
                    f"Successfully deleted character folder: {character_folder}")
        except Exception as folder_e:
            # Log folder deletion failure but continue
            logging.error(
                f"Failed to delete character reference folder {name}: {folder_e}")

        # Check deletion result
        if '成功' in result:
            return make_response(data=True)
        else:
            return make_response(status='error', msg=result)

    except Exception as e:
        logging.error(f"Error deleting entity: {str(e)}")
        return make_response(status='error', msg=str(e))


@router.get('/scene/list')
async def get_scenes(project_name: str = Query(..., description="Project name")):
    """Retrieve all base scene information for a project"""
    try:
        if not project_name:
            return make_response(status='error', msg='Project does not exist')

        # Get scene list
        scenes = scene_service.load_scenes(project_name)
        scenes = json.loads(scenes) if isinstance(scenes, str) else scenes

        return make_response(data={
            'scenes': scenes,
        })
    except Exception as e:
        return make_response(status='error', msg=str(e))


@router.post('/scene/update')
async def update_scenes(request: Request):
    """Update scene information"""
    try:
        data = await request.json()
        project_name = data.get('project_name')
        name = data.get('name')
        prompt = data.get('prompt', "")

        if not project_name:
            return make_response(status='error', msg='Project does not exist')

        result = scene_service.update_scenes(
            project_name, {name: prompt}, force_update=True)
        return make_response(data=result)
    except Exception as e:
        return make_response(status='error', msg=str(e))


@router.delete('/scene/{name}')
async def delete_scene(name: str, project_name: str = Query(..., description="Project name")):
    """
    Delete a scene entity

    Parameters:
        name (str): Entity name

    Returns:
        dict: Response result
    """
    try:
        if not project_name:
            return make_response(status='error', msg='Project does not exist')

        result = scene_service.delete_scenes(project_name, [name])

        # Delete corresponding reference image folder
        try:
            config = load_config()
            projects_path = config.get('projects_path', 'projects')
            scene_folder = Path(projects_path) / project_name / "Scene" / name
            if scene_folder.exists() and scene_folder.is_dir():
                shutil.rmtree(scene_folder)
                logging.info(
                    f"Successfully deleted scene folder: {scene_folder}")
        except Exception as folder_e:
            # Log folder deletion failure but continue
            logging.error(
                f"Failed to delete scene reference folder {name}: {folder_e}")

        # Check deletion result
        if result:
            return make_response(data=result)
        else:
            return make_response(status='error', msg=result)

    except Exception as e:
        logging.error(f"Error deleting entity: {str(e)}")
        return make_response(status='error', msg=str(e))


@router.post('/character/create')
async def create_character(request: Request):
    """Create a new character entity"""
    try:
        data = await request.json()
        project_name = data.get('project_name')
        name = data.get('name')
        attributes = data.get('attributes', {})

        if not project_name:
            return make_response(status='error', msg='Project does not exist')

        # Create new entity using kg_service and save
        result = kg_service.new_entity(
            project_name, name, attributes, save_kg=True)
        return make_response(data=result)
    except Exception as e:
        logging.error(f"Error creating entity: {str(e)}")
        return make_response(status='error', msg=str(e))


@router.post('/scene/create')
async def create_scene(request: Request):
    """Create a new scene"""
    try:
        data = await request.json()
        project_name = data.get('project_name')
        name = data.get('name')
        prompt = data.get('prompt', "")

        if not project_name:
            return make_response(status='error', msg='Project does not exist')

        # Create new scene using scene_service and save
        scene_dict = {name: prompt}
        result = scene_service.update_scenes(
            project_name, scene_dict, force_update=True)
        return make_response(data=result)
    except Exception as e:
        logging.error(f"Error creating scene: {str(e)}")
        return make_response(status='error', msg=str(e))
