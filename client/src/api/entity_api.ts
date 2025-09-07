import request from './request'

export interface CharacterAttributes {
  role?: string
  description?: string
  [key: string]: any
}

export interface UpdateCharacterParams {
  name: string
  attributes: CharacterAttributes
}

export interface UpdateSceneParams {
  name: string
  prompt: string
}

export interface CreateCharacterParams {
  name: string
  attributes: CharacterAttributes
}

export interface CreateSceneParams {
  name: string
  prompt: string
}

export const entityApi = {
  // Get character list
  getCharacterList(projectName: string) {
    return request.get('entity/character/list', { project_name: projectName })
  },

  // Create character
  createCharacter(projectName: string, params: CreateCharacterParams) {
    return request.post('entity/character/create', {
      project_name: projectName,
      name: params.name,
      attributes: params.attributes
    })
  },

  // Update character
  updateCharacter(projectName: string, params: UpdateCharacterParams) {
    return request.post('entity/character/update', {
      project_name: projectName,
      name: params.name,
      attributes: params.attributes
    })
  },

  // Toggle lock status
  toggleLock(projectName: string, entityName: string) {
    return request.post('entity/character/toggle_lock', {
      project_name: projectName,
      entity_name: entityName
    })
  },

  // Delete character
  deleteCharacter(projectName: string, entityName: string) {
    return request.delete(`entity/character/${entityName}`, { project_name: projectName })
  },

  // Get scene list
  getSceneList(projectName: string) {
    return request.get('entity/scene/list', { project_name: projectName })
  },

  // Create scene
  createScene(projectName: string, params: CreateSceneParams) {
    return request.post('entity/scene/create', {
      project_name: projectName,
      name: params.name,
      prompt: params.prompt
    })
  },

  // Update scene
  updateScene(projectName: string, params: UpdateSceneParams) {
    return request.post('entity/scene/update', {
      project_name: projectName,
      name: params.name,
      prompt: params.prompt
    })
  },

  // Delete scene
  deleteScene(projectName: string, entityName: string) {
    return request.delete(`entity/scene/${entityName}`, { project_name: projectName })
  }
}