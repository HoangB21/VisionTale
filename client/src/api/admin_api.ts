import request from './request'

interface Config {
  [key: string]: any
}

export const adminApi = {
  // Get configuration information
  getConfig() {
    return request.get('/admin/config')
  },

  // Update configuration information
  updateConfig(config: Record<string, any>) {
    return request.post('/admin/config', config)
  },

  /**
   * Get prompt styles list
   */
  getPromptStyles() {
    return request.get('/admin/prompt_styles')
  },

  /**
   * Save prompt styles list
   * @param styles Array of prompt styles
   */
  savePromptStyles(styles: any[]) {
    return request.post('/admin/prompt_styles', { styles })
  }
}

export default adminApi