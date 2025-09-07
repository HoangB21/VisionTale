import asyncio
from fastapi import APIRouter, HTTPException, status
from fastapi.responses import FileResponse
from typing import Optional, Tuple, Dict
import os
from pathlib import Path
from pydantic import BaseModel
from concurrent.futures import ThreadPoolExecutor
from server.config.config import load_config
from server.services.video_service import VideoService
from server.utils.response import make_response, APIException
import logging
from PIL import Image

router = APIRouter(prefix='/video')
logger = logging.getLogger(__name__)

# Create a global singleton instance of the video service
video_service = VideoService()


class VideoSettings(BaseModel):
    project_name: Optional[str] = None
    chapter_name: Optional[str] = None
    """Video effect configuration model"""
    fade_duration: Optional[float] = 1  # Fade in/out duration (seconds)
    fps: Optional[float] = 20
    use_pan: Optional[bool] = True  # Whether to use camera panning effect
    # 50% of the original image available horizontally, 50% vertically
    pan_range: Optional[Tuple[float, float]] = (0.5, 0.5)
    resolution: Optional[Tuple[int, int]] = (1600, 900)


@router.post("/generate_video")
async def generate_video(settings: Optional[VideoSettings] = None):
    try:
        config = load_config()
        base_path = config.get('projects_path', 'projects/')
        chapter_path = os.path.join(
            base_path, settings.project_name, settings.chapter_name)

        if not os.path.exists(chapter_path):
            return make_response(status='error', msg='chapter does not exist')

        output_path = await video_service.generate_video(
            str(chapter_path),
            video_settings=settings.model_dump(
                exclude_unset=True) if settings else None
        )

        return make_response(
            data={"video_path": output_path},
            msg="Video generated successfully"
        )
    except APIException as e:
        return make_response(status='error', msg=e.detail)
    except Exception as e:
        return make_response(status='error', msg=str(e))


@router.get("/get_video")
async def get_video(project_name: str, chapter_name: str):
    """API to get video file"""
    try:
        config = load_config()
        video_path = Path(config['projects_path']) / \
            project_name / chapter_name / "video.mp4"

        if not video_path.exists():
            return make_response(status='error', msg='Video does not exist')

        return FileResponse(
            video_path,
            media_type="video/mp4",
            filename=f"{chapter_name}_video.mp4"
        )
    except APIException as e:
        return make_response(status='error', msg=e.detail)
    except Exception as e:
        return make_response(status='error', msg=str(e))


@router.get("/generation_progress")
async def get_generation_progress() -> Dict:
    """API to get video generation progress"""
    try:
        progress_data = video_service.get_progress()
        return make_response(
            data=progress_data,
            msg="Progress retrieved successfully"
        )
    except Exception as e:
        return make_response(status='error', msg=str(e))


@router.post("/cancel_generation")
async def cancel_generation():
    """API to cancel video generation"""
    try:
        result = video_service.cancel_generation()
        return make_response(
            data={"cancelled": result},
            msg="Video generation cancelled"
        )
    except Exception as e:
        return make_response(status='error', msg=str(e))
