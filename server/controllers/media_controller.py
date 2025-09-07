from fastapi import APIRouter, Depends, HTTPException, Request, Response, Query, Body
from fastapi.responses import FileResponse
from server.config.config import load_config, get_prompt_style_by_name
from server.services.image_service import ImageService
from server.services.audio_service import AudioService
from server.utils.response import make_response
import os
import datetime
import logging

config = load_config()
router = APIRouter(prefix='/media')
image_service = ImageService()
audio_service = AudioService()
logger = logging.getLogger(__name__)


@router.post('/generate_images')
async def generate_images(request: Request):
    """Generate images API"""
    try:
        data = await request.json()

        # Get project, chapter, and prompt information
        project_name = data.get('project_name')
        chapter_name = data.get('chapter_name')
        prompts = data.get('prompts')
        image_settings = data.get('imageSettings')
        reference_image_infos = data.get('reference_image_infos')

        if not all([project_name, chapter_name, prompts]):
            return make_response(status='error', msg='Missing required parameters: project_name, chapter_name, prompts')

        # Get workflow and parameters
        workflow = data.get('workflow', config.get(
            'default_workflow', {}).get('name', 'default_workflow.json'))
        params = {}
        width = image_settings.get('width', 512)
        height = image_settings.get('height', 768)
        style = image_settings.get('style', 'sai-anime')

        style_template = "{prompt}"
        negative_prompt = ""
        if style:
            # Get style data
            style_data = get_prompt_style_by_name(style)
            if not style_data:
                return make_response(status='error', msg=f'Specified style not found: {style}')

            style_template = style_data.get('prompt')
            negative_prompt = style_data.get('negative_prompt', "")

        params['width'] = width
        params['height'] = height
        if negative_prompt:
            params['negative_prompt'] = negative_prompt

        reference_image_paths = []
        if config['comfyui'].get('reference_image_mode', True) and reference_image_infos:
            for info in reference_image_infos:
                character1 = info.get('character1', '')
                character2 = info.get('character2', '')
                scene = info.get('scene', '')
                path1 = os.path.join(config['projects_path'], project_name,
                                     "Character", character1, "image.png") if character1 else ''
                path2 = os.path.join(config['projects_path'], project_name,
                                     "Character", character2, "image.png") if character2 else ''
                path3 = os.path.join(
                    config['projects_path'], project_name, "Scene", scene, "image.png") if scene else ''
                reference_image_paths.append((path1, path2, path3))

            # Use this workflow when reference images are provided
            workflow = "nunchaku-flux-kontext-multi-images.json"
            params['reference_image_paths'] = reference_image_paths

        # Build output path array
        output_dirs = []
        processed_prompts = []
        for prompt_data in prompts:
            span_id = prompt_data.get('id', '')

            # Build output path (consistent with image retrieval)
            span_path = os.path.join(
                config['projects_path'], project_name, chapter_name, str(span_id))
            output_dirs.append(span_path)

            # Ensure directory exists
            os.makedirs(span_path, exist_ok=True)
            logger.info(f"Created output directory: {span_path}")

            # Get original prompt
            prompt_text = prompt_data.get('prompt', '')

            # Apply style template if available
            processed_prompt = style_template.replace(
                '{prompt}', prompt_text) if style_template and '{prompt}' in style_template else prompt_text
            processed_prompts.append(processed_prompt)

        # Validate prompts
        if not all(processed_prompts):
            return make_response(status='error', msg='Empty prompt field found in prompts')

        try:
            # Call image service to generate images
            result = image_service.generate_images(
                prompts=processed_prompts,
                output_dirs=output_dirs,
                workflow=workflow,
                params=params
            )
            return make_response(
                data=result,
                msg='Image generation task submitted'
            )
        except Exception as e:
            logger.error(f"Error generating images: {str(e)}")
            return make_response(status='error', msg=str(e))

    except Exception as e:
        logger.error(f"Error processing request: {str(e)}")
        return make_response(status='error', msg=f'Error processing request: {str(e)}')


@router.post('/generate-audio')
async def generate_audio(request: Request):
    """Generate audio files API"""
    try:
        data = await request.json()

        # Get project, chapter, and prompt information
        project_name = data.get('project_name')
        chapter_name = data.get('chapter_name')
        prompts = data.get('prompts')
        audio_settings = data.get('audioSettings', {})

        if not all([project_name, chapter_name, prompts]):
            return make_response(status='error', msg='Missing required parameters: project_name, chapter_name, prompts')

        # Build output path array
        output_dirs = []
        prompt_texts = []
        for prompt_data in prompts:
            span_id = prompt_data.get('id')
            if span_id is None:
                return make_response(status='error', msg='Missing id field in prompts')

            # Build output path
            span_path = os.path.join(
                config['projects_path'], project_name, chapter_name, str(span_id))
            output_dirs.append(span_path)

            # Extract prompt text
            prompt_text = prompt_data.get('prompt')
            if not prompt_text:
                return make_response(status='error', msg='Empty prompt field found in prompts')
            prompt_texts.append(prompt_text)

        try:
            rate = audio_settings.get('rate', '+0%')
            if rate == '0%':
                rate = '+0%'
            # Call audio service to generate audio
            result = await audio_service.generate_audio(
                prompts=prompt_texts,
                output_dirs=output_dirs,
                voice=audio_settings.get('voice', 'zh-CN-XiaoxiaoNeural'),
                rate=rate
            )
            return make_response(
                data=result,
                msg='Audio generation task submitted'
            )
        except Exception as e:
            logger.error(f"Error generating audio: {str(e)}")
            return make_response(status='error', msg=str(e))

    except Exception as e:
        logger.error(f"Error processing request: {str(e)}")
        return make_response(status='error', msg=f'Error processing request: {str(e)}')


@router.get('/progress')
async def get_generation_progress(task_id: str = Query(..., description="Task ID")):
    """Retrieve generation task progress"""
    try:
        if not task_id:
            return make_response(status='error', msg='Missing task ID')

        # Get task progress
        if task_id.startswith('audio_'):
            progress = audio_service.get_generation_progress(task_id)
            progress['task_type'] = 'audio'
        else:
            progress = image_service.get_generation_progress(task_id)
            progress['task_type'] = 'image'

        return make_response(
            data=progress,
            msg='Progress retrieved successfully'
        )
    except ValueError as e:
        return make_response(status='error', msg=str(e))
    except Exception as e:
        logger.error(f"Error getting progress: {str(e)}")
        return make_response(status='error', msg=f'Error retrieving progress: {str(e)}')


@router.post('/cancel')
async def cancel_generation(request: Request):
    """Cancel generation task"""
    try:
        data = await request.json()
        task_id = data.get("task_id")
        logger.info(f"Preparing to cancel task: {task_id}")

        # Determine if it's an image or audio task based on task ID prefix
        if task_id.startswith('audio_'):
            success = audio_service.cancel_generation(task_id)
        else:
            success = image_service.cancel_generation(task_id)

        if success:
            return make_response(msg='Task cancelled successfully')
        else:
            return make_response(status='error', msg='Failed to cancel task')
    except Exception as e:
        logger.error(f"Error cancelling task: {str(e)}")
        return make_response(status='error', msg=str(e))


@router.get('/workflows')
async def list_workflows():
    """List all available workflows"""
    try:
        workflows = image_service.list_workflows()
        return make_response(
            data={'workflows': workflows},
            msg='Workflow list retrieved successfully'
        )
    except Exception as e:
        return make_response(status='error', msg=f'Error retrieving workflow list: {str(e)}')


@router.get('/workflow/{workflow_name}')
async def get_workflow(workflow_name: str):
    """Retrieve details of a specific workflow"""
    try:
        workflow = image_service.get_workflow(workflow_name)
        if workflow is None:
            return make_response(status='error', msg='Workflow does not exist')
        return make_response(
            data={'workflow': workflow},
            msg='Workflow retrieved successfully'
        )
    except Exception as e:
        return make_response(status='error', msg=f'Error retrieving workflow: {str(e)}')


@router.get('/get_image')
async def get_media_image(project_name: str, chapter_name: str, span_id: str):
    """Retrieve image for a specific project chapter span"""
    try:
        # Build image path (consistent with generation)
        image_path = os.path.join(
            config['projects_path'], project_name, chapter_name, str(span_id), 'image.png')
        logger.info(f"Trying to access image at: {image_path}")

        return FileResponse(image_path, media_type='image/png')

    except Exception as e:
        logger.error(f"Error accessing image: {str(e)}")
        return make_response(status='error', msg=str(e))


@router.get('/get_audio')
async def get_media_audio(project_name: str, chapter_name: str, span_id: str):
    """Retrieve audio for a specific project chapter span"""
    try:
        # Build audio path
        audio_path = os.path.join(
            config['projects_path'], project_name, chapter_name, str(span_id), 'audio.mp3')

        if not os.path.exists(audio_path):
            return make_response(status='error', msg='Audio does not exist')

        return FileResponse(audio_path, media_type='audio/mpeg')

    except Exception as e:
        logger.error(f"Error accessing audio: {str(e)}")
        return make_response(status='error', msg=str(e))
