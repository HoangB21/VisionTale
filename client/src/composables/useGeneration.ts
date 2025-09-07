import { ref, reactive, onBeforeUnmount, readonly } from 'vue';
import { ElMessage } from 'element-plus';
import { mediaApi } from '@/api/media_api';
import { useI18n } from 'vue-i18n';

export interface GenerationPrompt {
    id: string;
    prompt: string;
}

/**
 * @description A Vue composable function for handling general asynchronous generation tasks
 */
export const useGeneration = () => {
    const { t } = useI18n();

    // Internal state
    const isGenerating = ref(false);
    const submittedPrompts = ref<GenerationPrompt[]>([]);
    const generationProgress = reactive({
        current: 0,
        total: 0,
        status: '', // 'running', 'completed', 'error', 'cancelled'
        taskId: '',
        errors: [] as string[],
        completedIds: [] as string[],
    });
    let progressTimer: ReturnType<typeof setInterval> | null = null;

    /**
     * @description Reset all generation-related states
     */
    const resetProgress = () => {
        if (progressTimer) {
            clearInterval(progressTimer);
            progressTimer = null;
        }
        isGenerating.value = false;
        submittedPrompts.value = [];
        generationProgress.current = 0;
        generationProgress.total = 0;
        generationProgress.status = '';
        generationProgress.taskId = '';
        generationProgress.errors = [];
        generationProgress.completedIds = [];
    };

    /**
     * @description Check generation progress
     */
    const checkProgress = async () => {
        if (!generationProgress.taskId) {
            resetProgress();
            return;
        }

        try {
            const response = await mediaApi.getProgress(generationProgress.taskId);
            const { status, current, total, errors } = response;

            // Update progress
            const newCompletedCount = current;
            const alreadyKnownCompletedCount = generationProgress.completedIds.length;
            if (newCompletedCount > alreadyKnownCompletedCount) {
                const newIds = submittedPrompts.value.slice(alreadyKnownCompletedCount, newCompletedCount).map(p => p.id);
                generationProgress.completedIds.push(...newIds);
            }

            generationProgress.status = status;
            generationProgress.current = current;
            generationProgress.total = total;
            generationProgress.errors = errors || [];

            if (status === 'completed' || status === 'error' || status == 'cancelled' || status === 'not_found') {
                // Stop polling immediately to prevent repeated prompts
                if (progressTimer) {
                    clearInterval(progressTimer);
                    progressTimer = null;
                }

                if (status === 'completed') {
                    ElMessage.success(t('common.success'));
                } else if (status === 'cancelled') {
                    ElMessage.info(t('storyboardProcess.generationCancelled'));
                } else if (status === 'error') {
                    ElMessage.error(errors?.join('\n') || t('common.error'));
                }

                // Delay reset to allow UI to display final state
                setTimeout(() => {
                    resetProgress();
                }, 1500);
            }
        } catch (error) {
            console.error('Failed to check generation progress:', error);
            ElMessage.error(t('common.error'));
            resetProgress();
        }
    };

    /**
     * @description Start a generation task
     * @param prompts Array of objects containing id and prompt
     * @param apiCall A function returning a Promise resolving to {task_id: string, total: number}
     */
    const start = async (
        prompts: GenerationPrompt[],
        apiCall: () => Promise<{ task_id: string; total: number }>
    ) => {
        if (!prompts || prompts.length === 0) {
            ElMessage.warning(t('storyboardProcess.noPrompts'));
            return;
        }

        if (isGenerating.value) {
            ElMessage.warning(t('storyboardProcess.generationInProgress'));
            return;
        }

        try {
            isGenerating.value = true;
            submittedPrompts.value = [...prompts]; // Save a copy of submitted prompts
            generationProgress.completedIds = []; // Clear previous records

            const data = await apiCall();

            generationProgress.taskId = data.task_id;
            generationProgress.total = data.total;
            generationProgress.current = 0;
            generationProgress.status = 'running';

            if (progressTimer) clearInterval(progressTimer);
            progressTimer = setInterval(checkProgress, 1000);
        } catch (error) {
            console.error('Failed to start generation:', error);
            ElMessage.error(t('common.operationFailed'));
            resetProgress();
        }
    };

    /**
     * @description Stop the current generation task
     */
    const stop = async () => {
        if (!generationProgress.taskId) return;
        try {
            await mediaApi.cancelTask(generationProgress.taskId);
            ElMessage.success(t('storyboardProcess.stopGenerationSuccess'));
            // checkProgress will handle subsequent state reset
        } catch (error) {
            console.error('Failed to stop generation:', error);
            ElMessage.error(t('common.error'));
            resetProgress();
        }
    };

    // Ensure timer is cleared when component is unmounted
    onBeforeUnmount(() => {
        if (progressTimer) {
            clearInterval(progressTimer);
        }
    });

    // Return read-only state and callable methods
    return {
        isGenerating,
        generationProgress,
        start,
        stop,
    };
}