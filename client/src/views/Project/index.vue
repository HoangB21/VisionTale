<template>
  <div class="project-container">
    <el-row :gutter="20">
      <!-- Project card list -->
      <el-col v-for="project in projects" :key="project" :xs="24" :sm="12" :md="8" :lg="6" :xl="4">
        <el-card class="project-card" shadow="hover">
          <div class="project-content" @click="handleCardClick(project)">
            <h3>{{ project }}</h3>
          </div>
          <template #footer>
            <div class="project-actions">
              <el-button type="primary" size="small" @click.stop="handleEdit(project)">
                <el-icon><Edit /></el-icon>
                {{ t('project.edit') }}
              </el-button>
              <el-button type="danger" size="small" @click.stop="handleDelete(project)">
                <el-icon><Delete /></el-icon>
                {{ t('project.delete') }}
              </el-button>
            </div>
          </template>
        </el-card>
      </el-col>

      <!-- Add project card -->
      <el-col :xs="24" :sm="12" :md="8" :lg="6" :xl="4">
        <el-card class="project-card add-project-card" shadow="hover" @click="showCreateDialog">
          <div class="add-project-content">
            <el-icon :size="40"><Plus /></el-icon>
            <span>{{ t('project.create') }}</span>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- Create project dialog -->
    <el-dialog
      v-model="createDialogVisible"
      :title="t('project.createTitle')"
      width="50%"
      :close-on-click-modal="false"
      @keydown.enter="handleCreate"
      @close="createForm.projectName = ''"
    >
      <el-form :model="createForm" :rules="rules" ref="createFormRef">
        <el-form-item :label="t('project.name')" prop="projectName">
          <el-input v-model="createForm.projectName" :placeholder="t('project.namePlaceholder')" />
        </el-form-item>
        <el-form-item :label="t('project.content')" prop="storyContent">
          <el-input
            v-model="createForm.storyContent"
            type="textarea"
            :rows="6"
            :placeholder="t('project.contentPlaceholder')"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <span class="dialog-footer">
          <el-button @click="createDialogVisible = false">{{ t('common.cancel') }}</el-button>
          <el-button type="primary" @click="handleCreate" :loading="creating">
            {{ t('common.confirm') }}
          </el-button>
        </span>
      </template>
    </el-dialog>

    <!-- Loading dialog -->
    <el-dialog
      v-model="loadingDialogVisible"
      :show-close="false"
      :close-on-click-modal="false"
      :close-on-press-escape="false"
      width="30%"
    >
      <div class="loading-content">
        <el-icon class="loading-icon"><Loading /></el-icon>
        <span>{{ t('project.creating') }}</span>
      </div>
    </el-dialog>

    <!-- Edit project dialog -->
    <el-dialog
      v-model="editDialogVisible"
      :title="t('project.editTitle')"
      width="30%"
      :close-on-click-modal="false"
    >
      <el-form :model="createForm" :rules="rules" ref="createFormRef">
        <el-form-item :label="t('project.name')" prop="projectName">
          <el-input v-model="createForm.projectName" :placeholder="t('project.namePlaceholder')" />
        </el-form-item>
      </el-form>
      <template #footer>
        <span class="dialog-footer">
          <el-button @click="editDialogVisible = false">{{ t('common.cancel') }}</el-button>
          <el-button type="primary" @click="handleEditSubmit" :loading="editing">
            {{ t('common.confirm') }}
          </el-button>
        </span>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Edit, Delete, Plus } from '@element-plus/icons-vue'
import projectApi from '@/api/project_api'
import type { FormInstance } from 'element-plus'
import { useRouter } from 'vue-router'

import { Loading } from '@element-plus/icons-vue' // Thêm Loading icon
import { chapterApi } from '@/api/chapter_api'
import { entityApi } from '@/api/entity_api'
import mediaApi from '@/api/media_api'
import { useGeneration } from '@/composables/useGeneration'
import { videoApi } from '@/api/video_api'

const { t } = useI18n()
const router = useRouter()

// Data
const projects = ref<string[]>([])
const createDialogVisible = ref(false)
const editDialogVisible = ref(false)
const creating = ref(false)
const editing = ref(false)
const createForm = ref({
  projectName: '',
  storyContent: '',
})
const editForm = ref({
  projectName: '',
  oldName: ''
})

const loadingDialogVisible = ref(false)
const { isGenerating, generationProgress, start, stop } = useGeneration();
const { 
  isGenerating: isGeneratingAudio, 
  generationProgress: audioGenerationProgress, 
  start: startAudioGeneration, 
  stop: stopAudioGeneration 
} = useGeneration();

// Form rules
const rules = {
  projectName: [
    { required: true, message: t('project.nameRequired'), trigger: 'blur' },
    { min: 2, max: 50, message: t('project.nameLength'), trigger: 'blur' }
  ],
  storyContent: [
    { required: true, message: t('project.storyRequired'), trigger: 'blur' },
    { min: 10, max: 4000, message: t('project.storyLength'), trigger: 'blur' }
  ]
}

const createFormRef = ref<FormInstance>()
const editFormRef = ref<FormInstance>()

// Fetch project list
const fetchProjects = async () => {
  try {
    const data = await projectApi.getProjectList()
    projects.value = data
  } catch (error) {
    ElMessage.error(t('project.fetchError'))
  }
}

// Handle character generation
const handleCharacterGeneration = async (projectName: string) => {
  // extract characters from chapter1
  await chapterApi.extractCharacters(projectName, "chapter1")
  // create all characters
  const characterData = await entityApi.getCharacterList(projectName)
  
  const characterPrompts = characterData.characters
    .filter(e => e.attributes.description)
    .map(e => ({ id: e.name, prompt: e.attributes.description || '' }));
  
  // Generate character images
  await start(characterPrompts, () => mediaApi.generateImages({
    project_name: projectName,
    chapter_name: "Character", 
    imageSettings: {
      width: 512,
      height: 768,
      style: 'sai-anime'
    },
    prompts: characterPrompts
  }))
}

// Handle scene generation
const handleSceneGeneration = async (projectName: string) => {
  // Split chapter after character generation is complete
  await chapterApi.splitChapter(projectName, "chapter1")
  const sceneData = await entityApi.getSceneList(projectName)

  const sceneList = Object.entries(sceneData.scenes).map(([name, prompt]) => ({
    name,
    attributes: { description: prompt as string },
  }));

  // Only start scene generation after character generation is done
  const scenePrompts = sceneList
    .filter(e => e.attributes.description)
    .map(e => ({ id: e.name, prompt: e.attributes.description || '' }));
  
  while(isGenerating.value) {
    await new Promise(resolve => setTimeout(resolve, 2000)); // Wait for 2 seconds before checking again
  }

  await start(scenePrompts, () => mediaApi.generateImages({
    project_name: projectName,
    chapter_name: "Scene",
    imageSettings: {
      width: 512,
      height: 768,
      style: 'sai-anime'
    },
    prompts: scenePrompts
  }))
}

// Handle scene translation
const handleSceneTranslation = async (projectName: string) => {
  const sceneWithPrompt = await chapterApi.getChapterSceneList(projectName, "chapter1")
  // Get all scene descriptions to convert
  const descriptions = sceneWithPrompt.map(row => "[" + row.base_scene + "]," + row.scene)

  // Batch convert
  const translatedPrompts = await chapterApi.translatePrompt(projectName, descriptions)
  console.log("Translated: ", translatedPrompts);
  const scenesToSave = sceneWithPrompt.map((row:any, index:number) => ({
    id: index + 1,
    base_scene: row.base_scene,
    scene: row.scene,
    prompt: translatedPrompts[index] || ''
  }))
  await chapterApi.saveScenes(projectName, "chapter1", scenesToSave)
}

// Handle scene images generation
const handleSceneImagesGeneration = async (projectName: string) => {
  const input = await chapterApi.getChapterSceneList(projectName, "chapter1")
  const output = {
    project_name: "Red1",
    chapter_name: "chapter1",
    imageSettings: {
      width: 512,
      height: 768,
      style: "sai-anime",
    },
    prompts: [],
    reference_image_infos: [],
  };

  // Helper function để lấy tên nhân vật từ scene
  function extractCharacters(scene) {
    const regex = /{(.*?)}/g;
    const matches = [...scene.matchAll(regex)].map((m) => m[1]);
    return matches;
  }

  // Tạo prompts và reference_image_infos
  input.forEach((item) => {
    // Thêm vào prompts
    output.prompts.push({
      id: item.id,
      prompt: item.prompt,
    });

    // Lấy nhân vật từ scene
    const characters = extractCharacters(item.scene);

    output.reference_image_infos.push({
      character1: characters[0] || "",
      character2: characters[1] || "",
      scene: item.base_scene,
    });
  });
  while(isGenerating.value) {
    await new Promise(resolve => setTimeout(resolve, 2000)); // Wait for 2 seconds before checking again
  }
  start(output.prompts, () => mediaApi.generateImages({
    project_name: projectName,
    chapter_name: "chapter1",
    imageSettings: {
      width: 512,
      height: 768,
      style: 'sai-anime'
    },
    prompts: output.prompts,
    reference_image_infos: output.reference_image_infos
  }))
  // Generate audio for each scene
  const audioPrompts = input.map(p => ({ id: p.id, prompt: p.content || '' }));
  startAudioGeneration(audioPrompts, () => mediaApi.generateAudio({
    project_name: projectName,
    chapter_name: "chapter1",
    prompts: audioPrompts,
    audioSettings: {
      rate: "+0%",
      voice: "vi-VN-HoaiMyNeural"
    }
  }))
}
// Create project
const handleCreate = async () => {
  if (!createFormRef.value) return
  
  await createFormRef.value.validate(async (valid) => {
    if (valid) {
      try {
        creating.value = true
        loadingDialogVisible.value = true // Hiển thị loading dialog
        // Split story into chapters
        await projectApi.createProjectFullStory(createForm.value.projectName, createForm.value.storyContent)
        
        // Generate characters first
        await handleCharacterGeneration(createForm.value.projectName)

        // Then generate scenes
        await handleSceneGeneration(createForm.value.projectName)

        // Generate scene descriptions 
        await handleSceneTranslation(createForm.value.projectName)

        // Generate scene images
        await handleSceneImagesGeneration(createForm.value.projectName)

        while(isGenerating.value || isGeneratingAudio.value) {
          await new Promise(resolve => setTimeout(resolve, 2000)); // Wait for 2 seconds before checking again
        }
        // Export video for chapter1
        await videoApi.generateVideo({
          project_name: createForm.value.projectName,
          chapter_name: "chapter1",
          fade_duration: 1.0,
          fps: 20,
          resolution: [768, 768],
          use_pan: true,
          pan_range: [0, 0],
        })
        ElMessage.success(t('project.createSuccess'))
        resetCreateForm()
        await fetchProjects()
      } catch (error) {
        console.log(error)
        ElMessage.error(t('project.createError'))
      } finally {
        creating.value = false
        loadingDialogVisible.value = false // Ẩn loading dialog
      }
    }
  })
}

// Thêm hàm reset form
const resetCreateForm = () => {
  createForm.value = {
    projectName: '',
    storyContent: ''
  }
}

// Show create dialog
const showCreateDialog = () => {
  createDialogVisible.value = true
}

// Edit project
const handleEdit = (projectName: string) => {
  editForm.value.projectName = projectName
  editForm.value.oldName = projectName
  editDialogVisible.value = true
}

// Submit edit
const handleEditSubmit = async () => {
  if (!editFormRef.value) return

  await editFormRef.value.validate(async (valid) => {
    if (valid) {
      try {
        editing.value = true
        await projectApi.updateProject(editForm.value.oldName, editForm.value.projectName)
        ElMessage.success(t('project.editSuccess'))
        editDialogVisible.value = false
        await fetchProjects()
      } catch (error) {
        ElMessage.error(t('project.editError'))
      } finally {
        editing.value = false
      }
    }
  })
}

// Handle card click
const handleCardClick = (projectName: string) => {
  router.push(`/project/${projectName}`)
}

// Delete project
const handleDelete = (projectName: string) => {
  ElMessageBox.confirm(
    t('project.deleteConfirm'),
    t('common.warning'),
    {
      confirmButtonText: t('common.confirm'),
      cancelButtonText: t('common.cancel'),
      type: 'warning',
    }
  ).then(async () => {
    try {
      await projectApi.deleteProject(projectName)
      ElMessage.success(t('project.deleteSuccess'))
      await fetchProjects()
    } catch (error) {
      ElMessage.error(t('project.deleteError'))
    }
  })
}

onMounted(() => {
  fetchProjects()
})
</script>

<style scoped>
.project-container {
  padding: 20px 5vw;
  width: 100%;
}

.project-card {
  margin-bottom: 20px;
  height: 180px;
  display: flex;
  flex-direction: column;
  cursor: pointer;
  transition: transform 0.3s;
}

.project-card:hover {
  transform: translateY(-5px);
}

/* Ensure card content doesn't squeeze footer */
:deep(.el-card__body) {
  flex: 1;
  overflow: hidden;
  padding: 15px;
  min-height: 0; /* Allow content area to shrink */
}

/* Fix footer height and style */
:deep(.el-card__footer) {
  padding: 12px;
  height: 52px; /* Fixed footer height */
  box-sizing: border-box;
  flex-shrink: 0; /* Prevent footer compression */
}

.project-content {
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 0;
}

.project-content h3 {
  margin: 0;
  text-align: center;
  word-break: break-word;
  overflow: hidden;
  display: -webkit-box;
  -webkit-line-clamp: 3; /* Display up to 3 lines */
  -webkit-box-orient: vertical;
  font-size: 14px;
  line-height: 1.5;
}

.project-actions {
  display: flex;
  justify-content: center;
  gap: 10px;
}

.add-project-content {
  height: 100%;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 10px;
}

.dialog-footer {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
}

.loading-content {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 20px;
  padding: 20px;
}

.loading-icon {
  font-size: 48px;
  animation: rotating 2s linear infinite;
}

@keyframes rotating {
  from {
    transform: rotate(0deg);
  }
  to {
    transform: rotate(360deg);
  }
}
</style>