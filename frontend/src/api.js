import axios from 'axios'

const API = axios.create({
  baseURL: 'http://localhost:8000',
  timeout: 30000,
})

// Tasks
export const getTasks = () => API.get('/api/tasks/')
export const getTask = (id) => API.get(`/api/tasks/${id}`)
export const createTask = (data) => API.post('/api/tasks/', data)
export const updateTask = (id, data) => API.put(`/api/tasks/${id}`, data)
export const deleteTask = (id) => API.delete(`/api/tasks/${id}`)
export const getTaskStats = (id) => API.get(`/api/tasks/${id}/stats`)

// Videos
export const uploadVideo = (formData, onProgress) =>
  API.post('/api/videos/upload', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: 0,
    onUploadProgress: (e) => {
      if (onProgress) onProgress(Math.round((e.loaded * 100) / e.total))
    },
  })
export const getVideoProgress = (id) => API.get(`/api/videos/${id}/progress`)
export const getVideoDetections = (id, params) => API.get(`/api/videos/${id}/detections`, { params })
export const deleteVideo = (id) => API.delete(`/api/videos/${id}`)
export const pauseVideo = (id) => API.post(`/api/videos/${id}/pause`)
export const resumeVideo = (id) => API.post(`/api/videos/${id}/resume`)
export const cancelVideo = (id) => API.post(`/api/videos/${id}/cancel`)

// Images
export const getTaskImages = (taskId, params) => API.get(`/api/images/task/${taskId}`, { params })
export const getMapData = (taskId, cameraType) =>
  API.get(`/api/images/task/${taskId}/map-data`, { params: { camera_type: cameraType } })
export const getHeatmapData = (taskId) => API.get(`/api/images/task/${taskId}/heatmap`)
export const getImageUrl = (detectionId, annotated = false) =>
  `http://localhost:8000/api/images/serve/${detectionId}${annotated ? '?annotated=true' : ''}`

// Reports
export const downloadExcelReport = (taskId, cameraType) => {
  const q = cameraType ? `?camera_type=${cameraType}` : ''
  window.open(`http://localhost:8000/api/reports/task/${taskId}/excel${q}`, '_blank')
}
export const downloadPdfReport = (taskId) => {
  window.open(`http://localhost:8000/api/reports/task/${taskId}/pdf`, '_blank')
}
export const downloadCsvReport = (taskId, cameraType) => {
  const q = cameraType ? `?camera_type=${cameraType}` : ''
  window.open(`http://localhost:8000/api/reports/task/${taskId}/csv${q}`, '_blank')
}
export const downloadKmlReport = (taskId, cameraType) => {
  const q = cameraType ? `?camera_type=${cameraType}` : ''
  window.open(`http://localhost:8000/api/reports/task/${taskId}/kml${q}`, '_blank')
}
export const downloadGeoJsonReport = (taskId, cameraType) => {
  const q = cameraType ? `?camera_type=${cameraType}` : ''
  window.open(`http://localhost:8000/api/reports/task/${taskId}/geojson${q}`, '_blank')
}

// Legacy single-video report download
export const downloadReport = (videoId) => {
  window.open(`http://localhost:8000/api/videos/${videoId}/report/download`, '_blank')
}

// Models
export const getModelStatus = () => API.get('/api/models/status')

export default API
