import request from './request'

interface GenerateChapterParams {
  project_name: string
  chapter_name: string
  prompt: string
  is_continuation: boolean
  use_last_chapter: boolean
}

interface SaveChapterParams {
  project_name: string
  chapter_name: string
  content: string
}

interface ChapterContent {
  content: string
}

interface ChapterResponse {
  chapter: string
}

export const chapterApi = {
  // Get chapter list
  getChapterList(projectName: string) {
    return request.get<string[]>('/chapter/list', { project_name: projectName })
  },

  // Get chapter content
  getChapterContent(projectName: string, chapterName: string) {
    return request.get<ChapterContent>('/chapter/content', {
      project_name: projectName,
      chapter_name: chapterName
    })
  },

  // Generate chapter content
  generateChapter(params: GenerateChapterParams & { signal?: AbortSignal }) {
    return request.stream('/chapter/generate', params, {
      signal: params.signal
    })
  },

  // Save chapter content
  saveChapterContent(params: SaveChapterParams) {
    return request.post('/chapter/save', params)
  },

  // Create new chapter
  createChapter(projectName: string) {
    return request.post<ChapterResponse>('/chapter/create', { project_name: projectName })
  },

  /**
   * Split chapter content and generate prompts
   */
  splitChapter(projectName: string, chapterName: string) {
    return request.post('/chapter/split_text', {
      project_name: projectName,
      chapter_name: chapterName
    })
  },

  // Extract characters from chapter
  extractCharacters(projectName: string, chapterName: string) {
    return request.post('/chapter/extract_characters', {
      project_name: projectName,
      chapter_name: chapterName
    }, { raw: true })
  },

  /**
   * Get chapter scene list
   */
  getChapterSceneList(projectName: string, chapterName: string) {
    return request.get('/chapter/scene_list', {
      project_name: projectName,
      chapter_name: chapterName
    })
  },

  // Save scene modifications
  saveScenes(projectName: string, chapterName: string, scenes: any[]) {
    return request.post('/chapter/save_scenes', {
      project_name: projectName,
      chapter_name: chapterName,
      scenes
    })
  },

  translatePrompt(projectName: string, prompts: string[]) {
    console.log("Translate prompts: ", prompts);

    return request.post<string[]>('/chapter/translate_prompt', {
      project_name: projectName,
      prompts
    })
  }
}