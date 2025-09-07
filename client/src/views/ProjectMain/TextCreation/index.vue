<template>
  <div class="text-creation">
    <!-- Chapter list bar -->
    <div class="chapter-header">
      <el-select
        v-model="currentChapter"
        class="chapter-select"
        :placeholder="t('chapter.selectPlaceholder')"
        @change="handleChapterChange"
        :disabled="isOperating"
      >
        <el-option
          v-for="chapter in chapters"
          :key="chapter"
          :label="chapter"
          :value="chapter"
        />
      </el-select>
      <el-button type="primary" @click="handleAddChapter" :loading="adding" :disabled="isOperating">
        <el-icon><Plus /></el-icon>
        {{ t('textCreation.addChapter') }}
      </el-button>
    </div>

    <!-- Settings bar -->
    <div class="settings-bar">
      <el-switch
        v-model="isContinueMode"
        :active-text="t('textCreation.continueMode')"
        :inactive-text="t('textCreation.createMode')"
      />
      <el-checkbox
        v-model="useLastChapter"
      >
        {{ t('textCreation.useLastChapter') }}
      </el-checkbox>
    </div>

    <!-- Text content area -->
    <el-input
      v-model="content"
      type="textarea"
      :rows="20"
      :maxlength="9999"
      :show-word-limit="true"
      :placeholder="inputPlaceholder"
      resize="none"
      ref="contentInput"
    />

    <!-- Action bar -->
    <div class="action-bar">
      <el-button
        type="primary"
        @click="handleSplitChapter"
        :disabled="!currentChapter || !content || isOperating"
        :loading="splitting"
      >
        <el-icon><ScaleToOriginal /></el-icon>
        {{ t('textCreation.splitChapter') }}
      </el-button>
      <el-button
        type="primary"
        @click="handleExtractCharacters"
        :disabled="!currentChapter || !content || isOperating"
        :loading="extracting"
      >
        <el-icon><User /></el-icon>
        {{ t('textCreation.extractCharacters') }}
      </el-button>
      <div class="right-buttons">
        <el-button
          type="primary"
          @click="()=>handleSave()"
          :loading="saving"
          :disabled="!canSave"
        >
          <el-icon><Check /></el-icon>
          {{ t('common.save') }}
        </el-button>
        <el-button
          :type="generating ? 'danger' : 'primary'"
          @click="handleGenerate"
        >
          <el-icon><VideoPause v-if="generating" /><Plus v-else /></el-icon>
          {{ generating ? t('textCreation.stop') : t('textCreation.generate') }}
        </el-button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, watch, nextTick } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { ElMessage } from 'element-plus'
import { Plus, ScaleToOriginal, Check, User, VideoPause } from '@element-plus/icons-vue'
import { chapterApi } from '@/api/chapter_api'

const route = useRoute()
const router = useRouter()
const { t } = useI18n()
const projectName = computed(() => route.params.name as string)

// State variables
const chapters = ref<string[]>([])  // Chapter list
const currentChapter = ref('')  // Current selected chapter
const content = ref('')  // Current chapter content
const isContinueMode = ref(false)  // Continue mode toggle
const useLastChapter = ref(true)  // Use last chapter as context
const hasContentChanged = ref(false)  // Track content changes

// Loading states
const saving = ref(false)  // Saving in progress
const adding = ref(false)  // Adding chapter in progress
const generating = ref(false)  // Generating content in progress
const splitting = ref(false)  // Splitting chapter in progress
const extracting = ref(false)  // Extracting characters in progress

// Auto-save timer
let autoSaveTimer: ReturnType<typeof setTimeout> | null = null

// Textarea reference
const contentInput = ref(null)

// Watch content changes, trigger auto-save after 5 seconds
watch(content, async () => {
  if (autoSaveTimer) {
    clearTimeout(autoSaveTimer)
  }
  
  // Mark content as changed
  hasContentChanged.value = true
  
  // Auto-scroll to textarea bottom
  await nextTick()
  if (contentInput.value) {
    const textarea = contentInput.value.$el.querySelector('textarea')
    textarea.scrollTop = textarea.scrollHeight
  }
})

// Computed properties
const isOperating = computed(() => {
  return saving.value || adding.value || generating.value || splitting.value || extracting.value
})

const canSave = computed(() => {
  return !isOperating.value && content.value.trim() && hasContentChanged.value
})

const inputPlaceholder = computed(() => {
  return isContinueMode.value
    ? t('textCreation.continuePlaceholder')
    : t('textCreation.createPlaceholder')
})

// Fetch chapter list
const fetchChapterList = async () => {
  try {
    const response = await chapterApi.getChapterList(projectName.value)
    chapters.value = response
    if (chapters.value.length > 0) {
      currentChapter.value = chapters.value[chapters.value.length - 1]
      await fetchChapterContent()
    }
  } catch (error: any) {
    ElMessage.error(error.message || t('error.fetchChapterListFailed'))
  }
}

// Fetch current chapter content
const fetchChapterContent = async () => {
  if (!currentChapter.value) return
  
  try {
    const response = await chapterApi.getChapterContent(
      projectName.value,
      currentChapter.value
    )
    content.value = response.content
    // Reset content change flag
    hasContentChanged.value = false
  } catch (error: any) {
    ElMessage.error(error.message || t('error.fetchChapterContentFailed'))
  }
}

// Handle chapter selection change
const handleChapterChange = async () => {
  await fetchChapterContent()
}

// Add new chapter
const handleAddChapter = async () => {
  try {
    adding.value = true
    const data = await chapterApi.createChapter(projectName.value)
    
    // Refresh chapter list
    await fetchChapterList()
    
    // Switch to new chapter
    currentChapter.value = data.chapter
    await fetchChapterContent()
    
    // Clear content
    content.value = ''
    
    ElMessage.success(t('textCreation.chapterCreated'))
  } catch (error: any) {
    ElMessage.error(error.message || t('common.operationFailed'))
  } finally {
    adding.value = false
  }
}

// Save chapter content, show success message if showMessage is true
const handleSave = async (showMessage = true) => {
  if (!currentChapter.value || !content.value.trim()) return
  
  try {
    saving.value = true
    await chapterApi.saveChapterContent({
      project_name: projectName.value,
      chapter_name: currentChapter.value,
      content: content.value
    })
    // Reset content change flag
    hasContentChanged.value = false
    if (showMessage) {
      ElMessage.success(t('success.saved'))
    }
  } catch (error: any) {
    ElMessage.error(error.message || t('error.saveFailed'))
  } finally {
    saving.value = false
  }
}

const abortController = ref<AbortController | null>(null) // For interrupting streaming output

// Generate or continue text content using AI
const handleGenerate = async () => {
  try {
    // Stop generation if already generating
    if (generating.value && abortController.value) {
      abortController.value.abort()
      generating.value = false
      return
    }

    generating.value = true
    abortController.value = new AbortController()
    
    // Call API (handles streaming automatically)
    const stream = await chapterApi.generateChapter({
      project_name: projectName.value,
      chapter_name: currentChapter.value,
      prompt: content.value,
      is_continuation: isContinueMode.value,
      use_last_chapter: useLastChapter.value,
      signal: abortController.value?.signal
    }) as ReadableStream

    // Clear content in non-continue mode
    if (!isContinueMode.value) content.value = ''

    const reader = stream.getReader()
    const decoder = new TextDecoder('utf-8')
    let buffer = ''
    let eventBuffer = ''
    let lastBreakLine = false // Track recent line break

    const processEvent = (eventData: string) => {
      const dataLines = eventData.split('\n')
      let contentData = ''
      
      // Combine multiple data fields
      dataLines.forEach(line => {
        if (line.startsWith('data: ')) {
          contentData += line.slice(6) // Remove "data: " prefix
        }
      })

      // Handle special characters and line breaks
      contentData = contentData
        .replace(/\\n/g, '\n')
        .replace(/\\'/g, "'")
        .replace(/\\"/g, '"')
        .trim()
      
      if (contentData && contentData !== '[DONE]') {
        content.value += contentData
        lastBreakLine = false
      } else {
        if (!lastBreakLine) {
          content.value += '\n' // Add line break
          lastBreakLine = true
        }
      }
    }

    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      
      buffer += decoder.decode(value, { stream: true })
      
      // Split complete events (SSE events are separated by \n\n)
      while (buffer.indexOf('\n\n') > -1) {
        const eventEnd = buffer.indexOf('\n\n')
        let eventChunk = buffer.slice(0, eventEnd)
        buffer = buffer.slice(eventEnd + 2)
   
        // Combine continuous event data
        eventBuffer += eventChunk
        processEvent(eventBuffer)
        eventBuffer = ''
      }
    }

    // Process remaining data
    if (buffer.length > 0) {
      processEvent(buffer)
    }

    // Ensure scroll to bottom
    await nextTick()
    if (contentInput.value) {
      const textarea = contentInput.value.$el.querySelector('textarea')
      textarea.scrollTop = textarea.scrollHeight
    }

  } catch (error: any) {
    console.log(error)
  } finally {
    generating.value = false
  }
}

// Split current chapter into multiple spans
const handleSplitChapter = async () => {
  if (!currentChapter.value || !content.value) return
  
  try {
    splitting.value = true
    await chapterApi.splitChapter(projectName.value, currentChapter.value)
    ElMessage.success(t('textCreation.splitChapterSuccess'))
    router.push(`/project/${projectName.value}/storyboard-process`)
  } catch (error: any) {
    ElMessage.error(error.message || t('textCreation.splitChapterError'))
  } finally {
    splitting.value = false
  }
}

// Extract characters from chapter
const handleExtractCharacters = async () => {
  if (!currentChapter.value || !content.value) return
  
  extracting.value = true
  try {
    const res = await chapterApi.extractCharacters(projectName.value, currentChapter.value)
    if (res) {
      ElMessage.success(t('textCreation.extractSuccess'))
      // Handle extracted character info as needed, e.g., display in a dialog
      console.log('Extracted character info:', res)
    } 
  } catch (error) {
    console.error('Failed to extract characters:', error)
    ElMessage.error(t('common.error'))
  } finally {
    extracting.value = false
  }
}

// Load chapter list on component mount
onMounted(() => {
  fetchChapterList()
})
</script>

<style lang="scss" scoped>
.text-creation {
  display: flex;
  flex-direction: column;
  gap: 20px;
  padding: 20px;
}

.chapter-header {
  display: flex;
  gap: 10px;

  .chapter-select {
    flex: 1;
  }

  button {
    width: 120px;
  }
}

.settings-bar {
  display: flex;
  gap: 20px;
  align-items: center;
}

.action-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.right-buttons {
  display: flex;
  gap: 10px;
}
</style>