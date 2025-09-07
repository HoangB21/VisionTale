import request from './request'
import type { ProjectInfo } from '@/types/project'

export default {
    // Get project list
    getProjectList() {
        return request.get<string[]>('/project/list')
    },

    // Create new project
    createProject(projectName: string) {
        return request.post<{ project_name: string }>('/project/create', {
            project_name: projectName
        })
    },

    // Create new project with full story
    createProjectFullStory(projectName: string, story_content: string) {
        return request.post<{ project_name: string, story_content: string }>('/project/create_from_story', {
            project_name: projectName,
            story_content: story_content
        })
    },

    // Update project
    updateProject(oldName: string, newName: string) {
        return request.put<{ project_name: string }>('/project/update', {
            old_name: oldName,
            new_name: newName
        })
    },

    // Delete project
    deleteProject(projectName: string) {
        return request.delete(`/project/delete/${projectName}`)
    },

    // Get project details
    getProjectInfo(projectName: string) {
        return request.get<ProjectInfo>('/project/info', {
            project_name: projectName
        })
    }
}