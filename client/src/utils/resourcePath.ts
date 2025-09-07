import config from '@/config'

/**
 * Generate resource access path
 * @param projectName Project name
 * @param chapterName Chapter name
 * @param spanId Span index
 * @param type Resource type ('image' | 'audio' | 'video')
 * @returns Full resource access path
 */
export const getResourcePath = (
  projectName: string,
  chapterName: string,
  spanId?: string,
  type: 'image' | 'audio' | 'video' = 'image'
): string => {
  const timestamp = Date.now()
  let endpoint = ''
  switch (type) {
    case 'image':
      endpoint = '/media/get_image'
      break;
    case 'audio':
      endpoint = '/media/get_audio'
      break;
    case 'video':
      endpoint = '/video/get_video'
      break;
  }
  if (type !== 'video')
    return `${config.baseApi}${endpoint}?project_name=${projectName}&chapter_name=${chapterName}&span_id=${spanId}&_t=${timestamp}`
  else
    return `${config.baseApi}${endpoint}?project_name=${projectName}&chapter_name=${chapterName}&_t=${timestamp}`
}