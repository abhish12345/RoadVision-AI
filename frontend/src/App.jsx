import { Routes, Route, Navigate } from 'react-router-dom'
import Layout from './components/Layout'
import Dashboard from './pages/Dashboard'
import Tasks from './pages/Tasks'
import TaskDetail from './pages/TaskDetail'
import CreateTask from './pages/CreateTask'
import Gallery from './pages/Gallery'
import MapView from './pages/MapView'
import Reports from './pages/Reports'
import Compare from './pages/Compare'
import VideoPlayer from './pages/VideoPlayer'

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Layout />}>
        <Route index element={<Navigate to="/dashboard" replace />} />
        <Route path="dashboard" element={<Dashboard />} />
        <Route path="tasks" element={<Tasks />} />
        <Route path="tasks/new" element={<CreateTask />} />
        <Route path="tasks/:taskId" element={<TaskDetail />} />
        <Route path="tasks/:taskId/gallery" element={<Gallery />} />
        <Route path="tasks/:taskId/map" element={<MapView />} />
        <Route path="tasks/:taskId/reports" element={<Reports />} />
        <Route path="tasks/:taskId/player" element={<VideoPlayer />} />
        <Route path="compare" element={<Compare />} />
      </Route>
    </Routes>
  )
}
