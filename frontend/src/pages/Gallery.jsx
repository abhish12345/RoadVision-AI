import { useEffect, useState, useCallback } from 'react'
import { useParams, Link } from 'react-router-dom'
import { getTaskImages, getImageUrl } from '../api'
import { ArrowLeft, Filter, Download, ZoomIn, X, ChevronLeft, ChevronRight } from 'lucide-react'

const DEFECT_COLORS = {
  pothole: 'bg-red-900 text-red-300',
  alligator_crack: 'bg-orange-900 text-orange-300',
  longitudinal_crack: 'bg-yellow-900 text-yellow-300',
  transverse_crack: 'bg-pink-900 text-pink-300',
  patching: 'bg-gray-700 text-gray-300',
  bleeding_ravelling: 'bg-blue-900 text-blue-300',
  road_sign: 'bg-green-900 text-green-300',
  crash_barrier: 'bg-red-900 text-red-300',
  km_stone: 'bg-cyan-900 text-cyan-300',
  street_light: 'bg-yellow-900 text-yellow-300',
}

export default function Gallery() {
  const { taskId } = useParams()
  const [images, setImages] = useState([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(true)
  const [page, setPage] = useState(0)
  const [lightbox, setLightbox] = useState(null)
  const [filters, setFilters] = useState({
    camera_type: '',
    class_filter: '',
    annotated_only: false,
    min_confidence: 0,
  })
  const [showFilters, setShowFilters] = useState(false)
  const LIMIT = 24

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const params = { skip: page * LIMIT, limit: LIMIT, ...filters }
      if (!params.camera_type) delete params.camera_type
      if (!params.class_filter) delete params.class_filter
      if (!params.min_confidence) delete params.min_confidence
      const res = await getTaskImages(taskId, params)
      setImages(res.data.images)
      setTotal(res.data.total)
    } catch {}
    setLoading(false)
  }, [taskId, page, filters])

  useEffect(() => { load() }, [load])

  const openLightbox = (img, idx) => setLightbox({ img, idx })
  const closeLightbox = () => setLightbox(null)
  const prevImg = () => lightbox && setLightbox({ img: images[lightbox.idx - 1], idx: lightbox.idx - 1 })
  const nextImg = () => lightbox && setLightbox({ img: images[lightbox.idx + 1], idx: lightbox.idx + 1 })

  return (
    <div className="p-6 space-y-5">
      <div className="flex items-center justify-between">
        <div>
          <Link to={`/tasks/${taskId}`} className="flex items-center gap-2 text-gray-400 hover:text-white mb-2 text-sm">
            <ArrowLeft size={14} /> Back to Task
          </Link>
          <h1 className="text-2xl font-bold text-white">Image Gallery</h1>
          <p className="text-gray-500 text-sm">{total} detected frames</p>
        </div>
        <button
          onClick={() => setShowFilters(!showFilters)}
          className="btn-secondary flex items-center gap-2"
        >
          <Filter size={15} /> Filters
        </button>
      </div>

      {/* Filters */}
      {showFilters && (
        <div className="card grid grid-cols-2 lg:grid-cols-4 gap-4">
          <div>
            <label className="label">Camera Type</label>
            <select className="input" value={filters.camera_type} onChange={e => setFilters({ ...filters, camera_type: e.target.value })}>
              <option value="">All</option>
              <option value="pave">PAVE</option>
              <option value="row">ROW</option>
            </select>
          </div>
          <div>
            <label className="label">Detection Class</label>
            <input className="input" placeholder="e.g. pothole" value={filters.class_filter}
              onChange={e => setFilters({ ...filters, class_filter: e.target.value })} />
          </div>
          <div>
            <label className="label">Min Confidence (%)</label>
            <input type="number" className="input" min={0} max={100} value={filters.min_confidence * 100}
              onChange={e => setFilters({ ...filters, min_confidence: e.target.value / 100 })} />
          </div>
          <div className="flex items-end">
            <label className="flex items-center gap-2 cursor-pointer">
              <input type="checkbox" checked={filters.annotated_only}
                onChange={e => setFilters({ ...filters, annotated_only: e.target.checked })}
                className="w-4 h-4 rounded" />
              <span className="text-sm text-gray-400">Annotated only</span>
            </label>
          </div>
        </div>
      )}

      {/* Grid */}
      {loading ? (
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-6 gap-3">
          {Array(12).fill(0).map((_, i) => (
            <div key={i} className="aspect-video bg-gray-800 rounded-lg animate-pulse" />
          ))}
        </div>
      ) : images.length === 0 ? (
        <div className="card text-center py-16">
          <p className="text-gray-500">No images found with current filters</p>
        </div>
      ) : (
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-6 gap-3">
          {images.map((img, idx) => (
            <div
              key={img.id}
              className="relative group cursor-pointer rounded-lg overflow-hidden bg-gray-800 aspect-video"
              onClick={() => openLightbox(img, idx)}
            >
              <img
                src={img.annotated_url || img.image_url}
                alt={`Frame ${img.frame_number}`}
                className="w-full h-full object-cover"
                loading="lazy"
                onError={e => { e.target.src = img.image_url }}
              />
              {/* Overlay */}
              <div className="absolute inset-0 bg-black/0 group-hover:bg-black/40 transition-all flex items-center justify-center">
                <ZoomIn size={24} className="text-white opacity-0 group-hover:opacity-100 transition-opacity" />
              </div>
              {/* Info bar */}
              <div className="absolute bottom-0 left-0 right-0 bg-gradient-to-t from-black/80 to-transparent p-2">
                <div className="flex flex-wrap gap-1">
                  {img.detections?.slice(0, 2).map((d, i) => (
                    <span key={i} className={`text-xs px-1.5 py-0.5 rounded ${DEFECT_COLORS[d.normalized_class] || 'bg-gray-700 text-gray-300'}`}>
                      {d.normalized_class?.replace(/_/g, ' ')}
                    </span>
                  ))}
                  {img.detections?.length > 2 && (
                    <span className="text-xs text-gray-400">+{img.detections.length - 2}</span>
                  )}
                </div>
                {img.chainage && (
                  <div className="text-xs text-gray-400 mt-0.5">Ch: {img.chainage?.toFixed(3)} km</div>
                )}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Pagination */}
      {total > LIMIT && (
        <div className="flex items-center justify-center gap-3">
          <button onClick={() => setPage(p => Math.max(0, p - 1))} disabled={page === 0} className="btn-secondary py-1.5 px-3">
            <ChevronLeft size={16} />
          </button>
          <span className="text-sm text-gray-400">
            Page {page + 1} of {Math.ceil(total / LIMIT)}
          </span>
          <button onClick={() => setPage(p => p + 1)} disabled={(page + 1) * LIMIT >= total} className="btn-secondary py-1.5 px-3">
            <ChevronRight size={16} />
          </button>
        </div>
      )}

      {/* Lightbox */}
      {lightbox && (
        <div className="fixed inset-0 bg-black/90 z-50 flex items-center justify-center p-4" onClick={closeLightbox}>
          <button className="absolute top-4 right-4 text-white hover:text-gray-300" onClick={closeLightbox}>
            <X size={28} />
          </button>
          {lightbox.idx > 0 && (
            <button className="absolute left-4 text-white hover:text-gray-300" onClick={e => { e.stopPropagation(); prevImg() }}>
              <ChevronLeft size={40} />
            </button>
          )}
          {lightbox.idx < images.length - 1 && (
            <button className="absolute right-4 text-white hover:text-gray-300" onClick={e => { e.stopPropagation(); nextImg() }}>
              <ChevronRight size={40} />
            </button>
          )}
          <div className="max-w-4xl w-full" onClick={e => e.stopPropagation()}>
            <img
              src={lightbox.img.annotated_url || lightbox.img.image_url}
              alt="Detection"
              className="w-full rounded-xl"
              onError={e => { e.target.src = lightbox.img.image_url }}
            />
            <div className="mt-3 flex flex-wrap gap-2 items-center">
              <span className="text-gray-400 text-sm">Frame {lightbox.img.frame_number}</span>
              {lightbox.img.chainage && <span className="text-gray-400 text-sm">Ch: {lightbox.img.chainage?.toFixed(3)} km</span>}
              {lightbox.img.latitude && <span className="text-gray-400 text-sm">{lightbox.img.latitude?.toFixed(6)}, {lightbox.img.longitude?.toFixed(6)}</span>}
              {lightbox.img.detections?.map((d, i) => (
                <span key={i} className={`text-xs px-2 py-1 rounded ${DEFECT_COLORS[d.normalized_class] || 'bg-gray-700 text-gray-300'}`}>
                  {d.normalized_class?.replace(/_/g, ' ')} ({(d.confidence * 100).toFixed(0)}%)
                </span>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
