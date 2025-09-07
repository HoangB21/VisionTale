import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { adminApi } from '@/api/admin_api'
import { useI18n } from 'vue-i18n'

export interface PromptStyle {
  name: string
  vietnamese_name: string
  prompt: string
  negative_prompt: string
}

export const usePromptStyleStore = defineStore('promptStyle', () => {
  const { locale } = useI18n()
  const styles = ref<PromptStyle[]>([])
  const loading = ref(false)
  const error = ref<string | null>(null)

  // Get all styles
  const fetchStyles = async () => {
    if (styles.value.length > 0) return // Skip if data already exists

    loading.value = true
    error.value = null

    try {
      const res = await adminApi.getPromptStyles()
      if (res && res.styles) {
        styles.value = res.styles
      } else {
        error.value = 'Failed to retrieve style list'
      }
    } catch (err) {
      console.error('Error retrieving style list:', err)
      error.value = 'Network error, please try again later'
    } finally {
      loading.value = false
    }
  }

  // Save style list
  const saveStyles = async (updatedStyles: PromptStyle[]) => {
    loading.value = true
    error.value = null

    try {
      const res = await adminApi.savePromptStyles(updatedStyles)
      if (res) {
        styles.value = updatedStyles
        return true
      } else {
        error.value = 'Save failed'
        return false
      }
    } catch (err) {
      console.error('Error saving styles:', err)
      error.value = 'Network error, please try again later'
      return false
    } finally {
      loading.value = false
    }
  }

  // Formatted style list for dropdown selection
  const styleOptions = computed(() => {
    return styles.value.map(style => ({
      label: locale.value === 'zh-CN' ? style.vietnamese_name : style.name,
      value: style.name
    }))
  })

  // Get style by name
  const getStyleByName = (name: string) => {
    return styles.value.find(style => style.name === name)
  }

  // Add new style
  const addStyle = async (style: PromptStyle) => {
    const updatedStyles = [...styles.value, style]
    return await saveStyles(updatedStyles)
  }

  // Update style
  const updateStyle = async (style: PromptStyle) => {
    const index = styles.value.findIndex(s => s.name === style.name)
    if (index === -1) return false

    const updatedStyles = [...styles.value]
    updatedStyles[index] = style
    return await saveStyles(updatedStyles)
  }

  // Delete style
  const deleteStyle = async (name: string) => {
    const updatedStyles = styles.value.filter(s => s.name !== name)
    return await saveStyles(updatedStyles)
  }

  return {
    styles,
    loading,
    error,
    fetchStyles,
    styleOptions,
    getStyleByName,
    addStyle,
    updateStyle,
    deleteStyle,
    saveStyles
  }
})