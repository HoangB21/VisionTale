from fastapi import APIRouter, Depends, HTTPException, Request
from server.config.config import load_config, update_config, load_prompt_styler, save_prompt_styler
import os
import json
from server.utils.response import make_response

router = APIRouter(prefix='/admin')
config = load_config()


@router.get('/config')
async def get_config():
    """Retrieve current configuration"""
    try:
        config = load_config()
        return make_response(
            data=config,
            msg='Configuration retrieved successfully'
        )
    except Exception as e:
        return make_response(status='error', msg=f'Error retrieving configuration: {str(e)}')


@router.post('/config')
async def update_configuration(request: Request):
    """Update configuration"""
    try:
        data = await request.json()
    except Exception:
        return make_response(status='error', msg='Invalid JSON data')

    if not data:
        return make_response(status='error', msg='Configuration data cannot be empty')

    try:
        update_config(data)
        return make_response(
            data=data,
            msg='Configuration updated successfully'
        )
    except Exception as e:
        return make_response(status='error', msg=f'Error updating configuration: {str(e)}')


@router.get('/prompt_styles')
async def get_prompt_styles():
    """Retrieve all prompt styles"""
    try:
        styles = load_prompt_styler()
        return make_response(
            data={'styles': styles},
            msg='Prompt styles retrieved successfully'
        )
    except Exception as e:
        return make_response(status='error', msg=f'Error retrieving prompt styles: {str(e)}')


@router.post('/prompt_styles')
async def save_prompt_styles(request: Request):
    """Save prompt styles"""
    try:
        data = await request.json()
        styles = data.get('styles')

        if not styles:
            return make_response(status='error', msg='Missing style data')

        # Save to prompt_styler.json file
        save_prompt_styler(styles)

        return make_response(data=True, msg='Prompt styles saved successfully')
    except Exception as e:
        return make_response(status='error', msg=f'Error saving prompt styles: {str(e)}')
