import { useEffect, useState } from 'react'
import type { FormEvent } from 'react'
import { CircleMarker, GeoJSON, MapContainer, Popup, Rectangle, TileLayer, useMap } from 'react-leaflet'
import 'leaflet/dist/leaflet.css'
import L from 'leaflet'
import {
  LayoutDashboard,
  PlusCircle,
  MapPin,
  Settings,
  LogOut,
  Sun,
  Map as MapIcon,
  Calendar,
  ArrowRight,
  Search,
  Building2,
  Navigation,
  Sparkles,
  Activity,
  ChevronRight,
  Layers,
  X,
  TreePine,
  School,
  Hospital,
  UtensilsCrossed,
  Pill,
  Bus,
  Road,
  Landmark,
  SquareArrowOutUpRight,
  Check,
  Save,
  Trash2,
  ExternalLink
} from 'lucide-react'
import './App.css'


const API = 'http://localhost:8000/api'
const CELL = 0.005

type Mode = 'land' | 'business'
type Page = 'dashboard' | 'analysis' | 'locations' | 'settings'

type Factors = { positive_factors: string[]; negative_factors: string[] }
type BudgetEstimate = {
  price_per_cent_inr: number
  formatted_price: string
  factors: {
    source: string
    population_density: string
    distance_to_road: string
    school_count?: number
    hospital_count?: number
  }
}
type Candidate = {
  lat: number
  lon: number
  model_score: number
  budget_estimate?: BudgetEstimate
  details: {
    population: number
    competitors: number
    schools: number
    colleges: number
    hospitals: number
    bus_stops: number
    road_density: number
    distance_to_major_road: number
  }
  explanation: Factors
}
type Recommendation = Factors & { business: string; score_percent: number }
type SavedLocation = {
  id: string
  name: string
  lat: number
  lon: number
  mode: Mode
  business?: string
  score?: number
  savedAt: string
}

type LandParcel = {
  name: string
  land_type: string
  label: string
  approx_area_m2: number
  centroid_lat: number
  centroid_lon: number
  surroundings: {
    schools: number
    hospitals: number
    restaurants: number
    pharmacies: number
    bus_stops: number
    major_roads: number
    banks: number
  }
  tags: Record<string, string>
}

function Viewport({ center }: { center: [number, number] }) {
  const map = useMap()
  useEffect(() => { map.flyTo(center, 13, { animate: true, duration: 1.5 }) }, [center, map])
  return null
}

function heat(score: number, min: number, max: number) {
  const r = max === min ? 1 : (score - min) / (max - min)
  return r > .75 ? '#10b981' : r > .5 ? '#f59e0b' : r > .25 ? '#f97316' : '#ef4444'
}

function budgetHeat(price: number, min: number, max: number) {
  const r = max === min ? 0.5 : (price - min) / (max - min)
  return r > .75 ? '#dc2626' : r > .5 ? '#f97316' : r > .25 ? '#eab308' : '#16a34a'
}

const formatNum = (n: number | null | undefined, suffix = '') =>
  n === null || n === undefined ? 'N/A' : `${n}${suffix}`

const CATEGORY_COLORS: Record<string, string> = {
  pharmacy: '#10b981', restaurant: '#2563eb', fast_food: '#3b82f6', cafe: '#f59e0b',
  bank: '#f97316', hospital: '#ec4899', clinic: '#db2777', doctors: '#c026d3',
  school: '#eab308', college: '#ca8a04', university: '#a16207', education: '#eab308',
  supermarket: '#14b8a6', convenience: '#0d9488', grocery: '#0f766e', grocery_store: '#14b8a6',
  bakery: '#fb7185', clothes: '#e11d48', fashion: '#be123c', electronics: '#8b5cf6',
  mobile_phone: '#7c3aed', books: '#6366f1', furniture: '#a16207', beauty: '#ec4899',
  hairdresser: '#f43f5e', sports: '#06b6d4', hardware: '#d97706', car: '#64748b',
  bicycle: '#0891b2', office: '#8b5cf6', bus_stop: '#64748b', road: '#94a3b8',
}

const SHOP_LEGEND = [
  ['pharmacy', 'Pharmacy'], ['restaurant', 'Restaurant'], ['cafe', 'Cafe'], ['bank', 'Bank'],
  ['supermarket', 'Grocery / supermarket'], ['bakery', 'Bakery'], ['clothes', 'Clothing'],
  ['electronics', 'Electronics'], ['mobile_phone', 'Mobile shop'], ['furniture', 'Furniture'],
  ['beauty', 'Beauty / salon'], ['books', 'Books'], ['sports', 'Sports'], ['hardware', 'Hardware'],
  ['office', 'Office / other'], ['bus_stop', 'Transit'],
]

const featureTokens = (props: any) => [props?.amenity, props?.shop, props?.category, props?.office, props?.highway]
  .filter(Boolean).map((value: string) => value.toLowerCase())

const isFeatureCompetitor = (feature: any, business: string) => {
  const tokens = featureTokens(feature.properties || {})
  const b = business.toLowerCase()
  if (b === 'restaurant') return tokens.some(t => ['restaurant', 'fast_food'].includes(t))
  if (b === 'cafe') return tokens.includes('cafe')
  if (b === 'grocery') return tokens.some(t => ['supermarket', 'convenience', 'grocery', 'grocery_store'].includes(t))
  if (b === 'clinic') return tokens.some(t => ['clinic', 'doctors', 'healthcare'].includes(t))
  if (b === 'school') return tokens.some(t => ['school', 'college', 'university', 'education'].includes(t))
  if (b === 'hospital') return tokens.some(t => ['hospital', 'clinic', 'doctors', 'healthcare'].includes(t))
  return tokens.includes(b) || tokens.includes(`shop_${b}`)
}

const getCategoryColor = (props: any, targetBusiness?: string) => {
  if (!props) return '#94a3b8'
  if (targetBusiness && isFeatureCompetitor({ properties: props }, targetBusiness)) return '#ef4444'
  const tokens = featureTokens(props)
  const exact = tokens.find(token => CATEGORY_COLORS[token])
  if (exact) return CATEGORY_COLORS[exact]
  const shopCategory = tokens.find(token => token.startsWith('shop_'))?.replace('shop_', '')
  return (shopCategory && CATEGORY_COLORS[shopCategory]) || CATEGORY_COLORS.office
}

// Colour palette for empty-land parcel types
const LAND_COLORS: Record<string, string> = {
  vacant:            '#f97316', // orange
  brownfield:        '#ef4444', // red
  farmland:          '#22c55e', // green
  meadow:            '#84cc16', // lime
  grass:             '#86efac', // light-green
  greenfield:        '#4ade80', // emerald
  landfill:          '#78716c', // stone
  quarry:            '#a8a29e', // warm-gray
  allotments:        '#fbbf24', // amber
  orchard:           '#f472b6', // pink
  park:              '#34d399', // teal-green
  garden:            '#6ee7b7', // light teal
  recreation_ground: '#5eead4', // cyan
  nature_reserve:    '#2dd4bf', // teal
};

function getLandColor(landType: string): string {
  return LAND_COLORS[landType] || '#a78bfa';
}

// --- Dashboard View Component ---
const DashboardView = ({ onNavigate }: { onNavigate: (p: Page, m?: Mode) => void }) => (
  <div className="page-content fade-in">
    <div className="page-header">
      <div>
        <h1>Dashboard</h1>
        <p>GeoBusiness AI — Geographic business and location suitability prototype.</p>
      </div>
      <div className="header-actions">
        <button className="btn btn-outline" onClick={() => onNavigate('locations')}><MapPin size={16}/> Saved Locations</button>
      </div>
    </div>

    <div className="dashboard-grid">
      {/* Quick Actions for the Two Main Workflows */}
      <div className="workflow-card land-workflow" onClick={() => onNavigate('analysis', 'land')}>
        <div className="workflow-icon"><Layers size={24} /></div>
        <div className="workflow-content">
          <h3>Evaluate Land</h3>
          <span className="workflow-subtitle">LAND → BUSINESS</span>
          <p>Analyse a selected location and rank supported business categories based on demographics and POIs.</p>
        </div>
        <ArrowRight className="workflow-arrow" size={20} />
      </div>

      <div className="workflow-card business-workflow" onClick={() => onNavigate('analysis', 'business')}>
        <div className="workflow-icon"><Building2 size={24} /></div>
        <div className="workflow-content">
          <h3>Place Business</h3>
          <span className="workflow-subtitle">BUSINESS → LAND</span>
          <p>Select a business category and search an area to rank candidate geographic cells by suitability score.</p>
        </div>
        <ArrowRight className="workflow-arrow" size={20} />
      </div>
    </div>

    <div className="dashboard-metrics">
      <div className="metric-card">
        <Activity className="metric-icon" size={20} />
        <div className="metric-details">
          <span className="metric-val">2 AI Models</span>
          <span className="metric-label">Random Forest & Gradient Boosting</span>
        </div>
      </div>
      <div className="metric-card">
        <MapIcon className="metric-icon" size={20} />
        <div className="metric-details">
          <span className="metric-val">10+</span>
          <span className="metric-label">Spatial Features Derived</span>
        </div>
      </div>
      <div className="metric-card">
        <Building2 className="metric-icon" size={20} />
        <div className="metric-details">
          <span className="metric-val">Multiple</span>
          <span className="metric-label">Business Categories Supported</span>
        </div>
      </div>
    </div>

    <div className="recent-section mt-4">
      <div className="section-header">
        <h3>Recent Analyses</h3>
        <span className="total-count">2 total reports</span>
      </div>

      <div className="recent-grid">
        <div className="report-card">
          <div className="report-card-header">
            <span className="badge" style={{ background: 'rgba(59, 130, 246, 0.15)', color: '#3b82f6' }}>Pharmacy</span>
            <span className="date"><Calendar size={12}/> Oct 6, 2026</span>
          </div>
          <h4>Coimbatore South Expansion</h4>
          <div className="location-info">
            <MapPin size={14} className="text-primary"/> Coimbatore, Tamil Nadu
          </div>
          <div className="target-info">Workflow: Business → Land</div>

          <button className="view-report-btn" onClick={() => onNavigate('analysis', 'business')}>
            Open Analysis <ArrowRight size={14}/>
          </button>
        </div>

        <div className="report-card">
          <div className="report-card-header">
            <span className="badge" style={{ background: 'rgba(16, 185, 129, 0.15)', color: '#10b981' }}>Land Evaluation</span>
            <span className="date"><Calendar size={12}/> Oct 5, 2026</span>
          </div>
          <h4>RS Puram Plot</h4>
          <div className="location-info">
            <MapPin size={14} className="text-primary"/> 11.0168, 76.9558
          </div>
          <div className="target-info">Workflow: Land → Business</div>

          <button className="view-report-btn" onClick={() => onNavigate('analysis', 'land')}>
            Open Analysis <ArrowRight size={14}/>
          </button>
        </div>
      </div>
    </div>
  </div>
)


// ── Map Legend Component ──────────────────────────────────────────────────────
const LAND_DOT_LEGEND = SHOP_LEGEND.map(([key, label]) => ({ color: CATEGORY_COLORS[key], label }))

const BUSINESS_SCORE_LEGEND = [
  { color: '#10b981', label: 'High score (top 25 %)' },
  { color: '#f59e0b', label: 'Good score (50–75 %)' },
  { color: '#f97316', label: 'Moderate (25–50 %)' },
  { color: '#ef4444', label: 'Low score (bottom 25 %)' },
]

const BUSINESS_BUDGET_LEGEND = [
  { color: '#16a34a', label: 'Lower budget' },
  { color: '#eab308', label: 'Mid budget' },
  { color: '#f97316', label: 'High budget' },
  { color: '#dc2626', label: 'Highest budget' },
]

function MapLegend({ mode }: { mode: Mode }) {
  const [open, setOpen] = useState(true)
  const items = mode === 'land' ? LAND_DOT_LEGEND : [...BUSINESS_SCORE_LEGEND, ...BUSINESS_BUDGET_LEGEND]

  return (
    <div className={`map-legend ${open ? 'map-legend--open' : ''}`}>
      <button
        type="button"
        className="map-legend-toggle"
        onClick={() => setOpen(o => !o)}
        title={open ? 'Collapse legend' : 'Expand legend'}
      >
        <span className="map-legend-icon">◉</span>
        <span className="map-legend-label">Legend</span>
        <span className="map-legend-chevron">{open ? '▲' : '▼'}</span>
      </button>
      {open && (
        <ul className="map-legend-list">
          {mode === 'land' && (
            <li className="map-legend-group-title">Nearby amenities</li>
          )}
          {mode === 'business' && (
            <li className="map-legend-group-title">Location score</li>
          )}
          {items.map(({ color, label }) => (
            <li key={label} className="map-legend-item">
              <span className="map-legend-dot" style={{ background: color }} />
              <span>{label}</span>
            </li>
          ))}
          {mode === 'land' && (
            <>
              <li className="map-legend-divider" />
              <li className="map-legend-group-title">Target</li>
              <li className="map-legend-item">
                <span className="map-legend-dot" style={{ background: '#ef4444', boxShadow: '0 0 0 2px #fff2' }} />
                <span>Searched location</span>
              </li>
            </>
          )}
        </ul>
      )}
    </div>
  )
}

// ── Locations View Component ──────────────────────────────────────────────────
const LocationsView = ({
  locations,
  onAnalyze,
  onRemove,
  onViewMap,
}: {
  locations: SavedLocation[]
  onAnalyze: (location: SavedLocation) => void
  onRemove: (id: string) => void
  onViewMap: () => void
}) => (
  <div className="page-content fade-in">
    <div className="page-header">
      <div>
        <span className="eyebrow">Workspace</span>
        <h1>Saved locations</h1>
        <p>Keep promising areas together so you can compare them before making a decision.</p>
      </div>
      <div className="header-actions">
        <button type="button" className="btn btn-primary" onClick={onViewMap}><MapIcon size={16}/> View all on map</button>
      </div>
    </div>
    {locations.length === 0 ? (
      <div className="empty-state"><MapPin size={28}/><h3>No saved locations yet</h3><p>Run an analysis, then save the area from the analysis header.</p></div>
    ) : (
      <div className="locations-grid">
        {locations.map(location => (
          <article key={location.id} className="location-card">
            <div className="location-card-image"><span className={`location-mode ${location.mode}`}>{location.mode === 'land' ? 'Land evaluation' : 'Business placement'}</span><MapPin size={32}/></div>
            <div className="location-card-content">
              <div className="loc-header"><h4>{location.name}</h4><span className="badge">{location.business || 'Area'}</span></div>
              <div className="loc-meta"><span className="loc-coord">{location.lat.toFixed(4)}, {location.lon.toFixed(4)}</span>{location.score !== undefined && <span className="loc-score">Score: {location.score.toFixed(0)}%</span>}</div>
              <p className="loc-desc">Saved {new Date(location.savedAt).toLocaleDateString()} for quick comparison and follow-up analysis.</p>
              <div className="loc-actions">
                <button type="button" className="btn btn-primary btn-sm" onClick={() => onAnalyze(location)}><ExternalLink size={14}/> Analyze again</button>
                <button type="button" className="btn btn-outline btn-sm text-danger" aria-label={`Remove ${location.name}`} onClick={() => onRemove(location.id)}><Trash2 size={14}/></button>
              </div>
            </div>
          </article>
        ))}
      </div>
    )}
  </div>
)

// ── Settings View Component ───────────────────────────────────────────────────
const SettingsView = ({ theme, toggleTheme, showLabels, toggleLabels, onSaved }: { theme: 'dark' | 'light', toggleTheme: () => void, showLabels: boolean, toggleLabels: () => void, onSaved: () => void }) => {
  const [name, setName] = useState('Rohit')
  const [email, setEmail] = useState('rohitc295@gmail.com')
  const [saved, setSaved] = useState(false)
  const saveProfile = () => { setSaved(true); onSaved(); window.setTimeout(() => setSaved(false), 2200) }
  return (
    <div className="page-content fade-in">
      <div className="page-header"><div><span className="eyebrow">Workspace</span><h1>Settings</h1><p>Customize your GeoBusiness workspace and map behavior.</p></div></div>
      <div className="settings-container">
        <div className="settings-section"><h3>Profile</h3><div className="settings-card"><div className="profile-edit"><div className="avatar-lg">{name.slice(0, 1).toUpperCase()}</div><div className="profile-details"><label className="field-label" htmlFor="profile-name">Display name</label><input id="profile-name" value={name} onChange={e => setName(e.target.value)} className="settings-input" /><label className="field-label" htmlFor="profile-email">Email address</label><input id="profile-email" type="email" value={email} onChange={e => setEmail(e.target.value)} className="settings-input" /><button type="button" className="btn btn-primary mt-2" onClick={saveProfile}>{saved ? <><Check size={15}/> Saved</> : <><Save size={15}/> Save profile</>}</button></div></div></div></div>
        <div className="settings-section"><h3>Preferences</h3><div className="settings-card"><div className="setting-row"><div><h4>Dark mode</h4><p>Toggle between a focused dark workspace and a light canvas.</p></div><label className="switch"><input aria-label="Dark mode" type="checkbox" checked={theme === 'dark'} onChange={toggleTheme}/><span className="slider round"></span></label></div><div className="setting-row"><div><h4>Map labels</h4><p>Show business and amenity names directly on the map.</p></div><label className="switch"><input aria-label="Map labels" type="checkbox" checked={showLabels} onChange={toggleLabels}/><span className="slider round"></span></label></div></div></div>
      </div>
    </div>
  )
}

export default function App() {
  const [activePage, setActivePage] = useState<Page>('dashboard')
  const [theme, setTheme] = useState<'dark' | 'light'>('dark')
  const [showLabels, setShowLabels] = useState(false)

  const toggleTheme = () => setTheme(t => t === 'dark' ? 'light' : 'dark')
  const toggleLabels = () => setShowLabels(s => !s)

  useEffect(() => {
    document.body.className = theme === 'light' ? 'light-theme' : '';
  }, [theme]);

  const [mode, setMode] = useState<Mode>('land')
  const [query, setQuery] = useState('')
  const [business, setBusiness] = useState('pharmacy')
  const [types, setTypes] = useState<string[]>([])
  const [center, setCenter] = useState<[number, number]>([11.0168, 76.9558])
  const [candidates, setCandidates] = useState<Candidate[]>([])
  const [selected, setSelected] = useState<number | null>(null)
  const [recommendations, setRecommendations] = useState<Recommendation[]>([])
  const [geoJson, setGeoJson] = useState<any>(null)
  const [emptyLand, setEmptyLand] = useState<any>(null)
  const [showEmptyLand, setShowEmptyLand] = useState(false)
  const [loadingLand, setLoadingLand] = useState(false)
  const [selectedLand, setSelectedLand] = useState<LandParcel | null>(null)
  const [selectedLandBudget, setSelectedLandBudget] = useState<BudgetEstimate | null>(null)
  const [loadingLandBudget, setLoadingLandBudget] = useState(false)
  const [budgetEstimate, setBudgetEstimate] = useState<any>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [toast, setToast] = useState('')
  const [savedLocations, setSavedLocations] = useState<SavedLocation[]>(() => {
    try { return JSON.parse(localStorage.getItem('geobusiness.savedLocations') || '[]') } catch { return [] }
  })

  useEffect(() => {
    localStorage.setItem('geobusiness.savedLocations', JSON.stringify(savedLocations))
  }, [savedLocations])

  const notify = (message: string) => {
    setToast(message)
    window.setTimeout(() => setToast(''), 2400)
  }

  const switchMode = (nextMode: Mode) => {
    setMode(nextMode)
    setError('')
    setCandidates([])
    setRecommendations([])
    setGeoJson(null)
    setBudgetEstimate(null)
    setSelected(null)
  }

  const saveCurrentLocation = () => {
    const record: SavedLocation = {
      id: `${center[0]}-${center[1]}-${Date.now()}`,
      name: query.trim() || 'Current analysis area',
      lat: center[0], lon: center[1], mode,
      business: mode === 'business' ? business : undefined,
      score: mode === 'business' && chosen ? Math.max(0, Math.min(100, chosen.model_score)) : undefined,
      savedAt: new Date().toISOString(),
    }
    setSavedLocations(current => [record, ...current.filter(item => Math.abs(item.lat - record.lat) > 0.00001 || Math.abs(item.lon - record.lon) > 0.00001)])
    notify('Location saved to your workspace')
  }

  const openSavedLocation = (location: SavedLocation) => {
    setMode(location.mode)
    setQuery(location.name)
    setCenter([location.lat, location.lon])
    setActivePage('analysis')
    notify('Location loaded — run the analysis to refresh its results')
  }

  const removeSavedLocation = (id: string) => {
    setSavedLocations(current => current.filter(item => item.id !== id))
    notify('Saved location removed')
  }

  useEffect(() => {
    if (!selectedLand?.centroid_lat || !selectedLand?.centroid_lon) return
    const controller = new AbortController()
    fetch(`${API}/estimate-budget?lat=${selectedLand.centroid_lat}&lon=${selectedLand.centroid_lon}&radius=500`, { signal: controller.signal })
      .then(response => response.ok ? response.json() : null)
      .then(data => { if (data) setSelectedLandBudget(data) })
      .catch(() => {})
      .finally(() => { if (!controller.signal.aborted) setLoadingLandBudget(false) })
    return () => controller.abort()
  }, [selectedLand])

  useEffect(() => {
    fetch(`${API}/business-types`)
      .then(r => r.json())
      .then(d => setTypes(d.business_types || []))
      .catch(() => setError('Could not load business categories. Is the API running?'))
  }, [])

  const search = async (event: FormEvent) => {
    event.preventDefault()
    if (!query.trim()) return
    setLoading(true)
    setError('')
    setCandidates([])
    setSelected(null)
    setRecommendations([])
    setBudgetEstimate(null)
    setGeoJson(null)
    setEmptyLand(null)
    setShowEmptyLand(false)
    setSelectedLand(null)
    setSelectedLandBudget(null)

    try {
      const geoResponse = await fetch(`${API}/geocode`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query })
      })
      if (!geoResponse.ok) throw new Error('The requested location could not be found.')
      const location = await geoResponse.json()
      const position: [number, number] = [location.latitude, location.longitude]
      setCenter(position)

      if (mode === 'land') {
        const [analysisResponse, mapResponse] = await Promise.all([
          fetch(`${API}/analyze-location`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ lat: position[0], lon: position[1], radius: 500 })
          }),
          fetch(`${API}/map-data?lat=${position[0]}&lon=${position[1]}&radius=500`)
        ])
        const analysis = await analysisResponse.json()
        if (!analysisResponse.ok) throw new Error(analysis.detail || 'Model 1 could not analyse this location.')
        setRecommendations(analysis.recommendations || [])
        setBudgetEstimate(analysis.budget_estimate || null)
        if (mapResponse.ok) setGeoJson(await mapResponse.json())

        // Fetch empty land in background — don't block the main result
        setLoadingLand(true)
        fetch(`${API}/empty-land?lat=${position[0]}&lon=${position[1]}&radius=1500`)
          .then(r => r.ok ? r.json() : null)
          .then(data => {
            if (data) {
              setEmptyLand(data)
              if (data.features?.length > 0) {
                setShowEmptyLand(true) // auto-show when parcels are found
              }
            }
          })
          .catch(() => {})
          .finally(() => setLoadingLand(false))
      } else {
        const response = await fetch(`${API}/find-best-locations`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ business_type: business, start_lat: position[0], start_lon: position[1], steps: 4, step_size: CELL })
        });
        const data = await response.json()
        if (!response.ok) throw new Error(data.detail || 'Model 2 could not evaluate this area.')
        setCandidates(data.candidates || [])

        // Fetch map data in background so it doesn't block the candidates showing up
        fetch(`${API}/map-data?lat=${position[0]}&lon=${position[1]}&radius=2500`)
          .then(r => r.ok ? r.json() : null)
          .then(d => { if(d) setGeoJson(d) })
          .catch(() => {})
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unable to complete the analysis.')
    } finally {
      setLoading(false)
    }
  }

  const scores = candidates.map(c => c.model_score)
  const budgets = candidates.map(c => c.budget_estimate?.price_per_cent_inr || 0).filter(Boolean)
  const minBudget = budgets.length ? Math.min(...budgets) : 0
  const maxBudget = budgets.length ? Math.max(...budgets) : 0
  const min = scores.length ? Math.min(...scores) : 0
  const max = scores.length ? Math.max(...scores) : 1
  const chosen = selected === null ? null : candidates[selected]

  return (
    <div className="app-container">
      {toast && <div className="toast" role="status"><Check size={15}/> {toast}</div>}
      {/* Sidebar - Designed exactly like BusinessRadius */}
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-icon">
            <MapPin size={18} color="#ffffff" />
          </div>
          <div className="brand-text">
            <h2>GeoBusiness</h2>
            <span>Decision Platform</span>
          </div>
        </div>

        <nav className="nav-menu">
          <button
            type="button"
            className={`nav-item ${activePage === 'dashboard' ? 'active' : ''}`}
            onClick={() => setActivePage('dashboard')}
          >
            <LayoutDashboard size={18} />
            <span>Dashboard</span>
          </button>
          <button
            type="button"
            className={`nav-item ${activePage === 'analysis' ? 'active' : ''}`}
            onClick={() => setActivePage('analysis')}
          >
            <PlusCircle size={18} />
            <span>New Analysis</span>
          </button>
          <button
            type="button"
            className={`nav-item ${activePage === 'locations' ? 'active' : ''}`}
            onClick={() => setActivePage('locations')}
          >
            <MapIcon size={18} />
            <span>Saved Locations</span>
          </button>
          <button
            type="button"
            className={`nav-item ${activePage === 'settings' ? 'active' : ''}`}
            onClick={() => setActivePage('settings')}
          >
            <Settings size={18} />
            <span>Settings</span>
          </button>
        </nav>

        <div className="sidebar-bottom">
          <div className="user-profile">
            <div className="avatar">R</div>
            <div className="user-info">
              <h4>Rohit</h4>
              <p>rohitc295@gmail.com</p>
            </div>
          </div>
          <button className="bottom-link" onClick={toggleTheme}>
            <Sun size={16}/> {theme === 'dark' ? 'Light Mode' : 'Dark Mode'}
          </button>
          <button type="button" className="bottom-link" onClick={() => notify('Sign out is not connected to an account service yet')}><LogOut size={16}/> Sign out</button>
        </div>
      </aside>

      {/* Main Content Area */}
      <main className="main-area">
        {activePage === 'dashboard' && <DashboardView onNavigate={(p, m) => { setActivePage(p); if (m) setMode(m); }} />}
        {activePage === 'locations' && <LocationsView locations={savedLocations} onAnalyze={openSavedLocation} onRemove={removeSavedLocation} onViewMap={() => { setActivePage('analysis'); switchMode('business') }} />}
        {activePage === 'settings' && <SettingsView theme={theme} toggleTheme={toggleTheme} showLabels={showLabels} toggleLabels={toggleLabels} onSaved={() => notify('Profile preferences saved locally')} />}

        {/* Full Analysis Tool Page */}
        {activePage === 'analysis' && <div className="analysis-view visible">
          <div className="analysis-sidebar">
            <div className="analysis-header">
              <div><span className="eyebrow">Decision workspace</span><h2>New analysis</h2><p>Turn local signals into a shortlist you can defend.</p></div>
              <button type="button" className="icon-action" onClick={saveCurrentLocation} disabled={!recommendations.length && !candidates.length} title="Save this analysis"><Save size={16}/></button>
            </div>

            <div className="mode-toggle">
              <button
                type="button"
                className={`mode-btn ${mode === 'land' ? 'active' : ''}`}
                onClick={() => switchMode('land')}
              >
                Evaluate Land
              </button>
              <button
                type="button"
                className={`mode-btn ${mode === 'business' ? 'active' : ''}`}
                onClick={() => switchMode('business')}
              >
                Place Business
              </button>
            </div>

            <form onSubmit={search} className="search-form">
              {mode === 'business' && (
                <div className="input-group">
                  <label className="sr-only" htmlFor="business-type">Business type</label>
                  <Building2 className="input-icon" size={16} />
                  <select
                    id="business-type"
                    value={business}
                    onChange={e => setBusiness(e.target.value)}
                  >
                    {types.length ? types.map(t => <option key={t} value={t}>{t}</option>) : <option>Loading...</option>}
                  </select>
                </div>
              )}

              <div className="input-group">
                <label className="sr-only" htmlFor="location-search">{mode === 'land' ? 'Location' : 'Search area'}</label>
                <Search className="input-icon" size={16} />
                <input
                  id="location-search"
                  value={query}
                  onChange={e => setQuery(e.target.value)}
                  placeholder={mode === 'land' ? 'Enter location to evaluate...' : 'Enter target city/area...'}
                />
              </div>

              <button
                type="submit"
                disabled={loading}
                className="btn btn-primary w-full mt-2"
              >
                {loading ? (
                  <span><Sparkles size={16} className="spin-icon" /> Analyzing...</span>
                ) : (
                  <span><Navigation size={16} /> Run Analysis</span>
                )}
              </button>
            </form>

            {error && <div className="error-box"><Activity size={16}/> {error}</div>}

            <div className="results-container scrollable">
              {/* Budget Estimate */}
              {mode === 'land' && budgetEstimate && (
                <div className="results-wrapper">
                  <h3 className="section-title">Estimated Land Budget (per cent)</h3>
                  <div className="data-card" style={{ borderColor: '#10b981', backgroundColor: 'rgba(16, 185, 129, 0.05)' }}>
                    <div className="card-header" style={{ marginBottom: '8px' }}>
                      <div className="biz-title">
                        <h4>Budget Estimate</h4>
                      </div>
                      <span className="score-badge" style={{ backgroundColor: '#10b981', color: '#ffffff' }}>{budgetEstimate.formatted_price}</span>
                    </div>
                    <div className="factors">
                      <div className="factor" style={{ color: '#a1a1aa', fontSize: '12px' }}>
                        Based on {budgetEstimate.factors.source} (Pop. Density: {budgetEstimate.factors.population_density}, Road Dist: {budgetEstimate.factors.distance_to_road})
                      </div>
                    </div>
                  </div>
                </div>
              )}

              {/* Recommendations */}
              {mode === 'land' && recommendations.length > 0 && (
                <div className="results-wrapper">
                  <h3 className="section-title">AI Recommendations</h3>
                  {recommendations.map((r, i) => {
                    const count = geoJson?.features?.filter((f: any) => isFeatureCompetitor(f, r.business)).length || 0;
                    return (
                      <div key={r.business + i} className="data-card">
                        <div className="card-header">
                          <div className="biz-title">
                            <h4>{r.business}</h4>
                            <span className="competitor-count-badge" style={{ fontSize: '11px', color: '#ef4444', marginLeft: '8px' }}>
                              {count} {count === 1 ? 'competitor' : 'competitors'} nearby
                            </span>
                          </div>
                          <span className="score-badge">{r.score_percent}%</span>
                        </div>
                        <div className="factors">
                          {r.positive_factors.slice(0, 2).map((x, i) => (
                            <div key={i} className="factor pos"><ChevronRight size={14} /> {x}</div>
                          ))}
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}

              {/* Empty Land Layer Toggle */}
              {mode === 'land' && (emptyLand || loadingLand) && (
                <div className="empty-land-panel">
                  <div className="empty-land-header">
                    <div className="empty-land-title">
                      <Layers size={16} />
                      <span>Empty Land Parcels</span>
                      {loadingLand && <span className="land-loading-badge">loading…</span>}
                      {emptyLand && !loadingLand && (
                        <span className="land-count-badge">{emptyLand.features?.length ?? 0} found</span>
                      )}
                    </div>
                    {emptyLand && (
                      <button
                        type="button"
                        className={`layer-toggle-btn ${showEmptyLand ? 'active' : ''}`}
                        onClick={() => setShowEmptyLand(v => !v)}
                        title={showEmptyLand ? 'Hide empty land layer' : 'Show empty land layer'}
                      >
                        {showEmptyLand ? 'Hide' : 'Show'}
                      </button>
                    )}
                  </div>

                  {/* Mini legend */}
                  {emptyLand && showEmptyLand && (
                    <div className="land-legend">
                      {Array.from(
                        new Set((emptyLand.features as any[]).map((f: any) => f.properties?.land_type).filter(Boolean))
                      ).map((type: any) => (
                        <div key={type} className="legend-item">
                          <span className="legend-dot" style={{ background: getLandColor(type) }} />
                          <span>{type.replace(/_/g, ' ')}</span>
                        </div>
                      ))}
                    </div>
                  )}

                  {showEmptyLand && emptyLand && (
                    <p className="land-hint">Click a parcel on the map to see details</p>
                  )}
                </div>
              )}

              {/* Selected Land Parcel Detail Panel */}
              {mode === 'land' && selectedLand && (
                <div className="land-detail-panel">
                  <div className="land-detail-header">
                    <div className="land-detail-title">
                      <span className="land-type-dot" style={{ background: getLandColor(selectedLand.land_type) }} />
                      <div>
                        <h4>{selectedLand.name || selectedLand.label}</h4>
                        <span className="land-type-tag">{selectedLand.land_type.replace(/_/g, ' ')}</span>
                      </div>
                    </div>
                    <button
                      type="button"
                      className="land-close-btn"
                      onClick={() => { setSelectedLand(null); setSelectedLandBudget(null); setLoadingLandBudget(false) }}
                      title="Close"
                    >
                      <X size={14} />
                    </button>
                  </div>

                  <div className="land-detail-meta">
                    <div className="land-meta-item">
                      <TreePine size={13} />
                      <span>Area</span>
                      <strong>
                        {selectedLand.approx_area_m2
                          ? selectedLand.approx_area_m2 >= 10000
                            ? `${(selectedLand.approx_area_m2 / 10000).toFixed(2)} ha`
                            : `${selectedLand.approx_area_m2.toLocaleString()} m²`
                          : 'N/A'}
                      </strong>
                    </div>
                    <div className="land-meta-item">
                      <SquareArrowOutUpRight size={13} />
                      <span>Coords</span>
                      <strong>
                        {selectedLand.centroid_lat?.toFixed(5)}, {selectedLand.centroid_lon?.toFixed(5)}
                      </strong>
                    </div>
                  </div>

                  {selectedLand.surroundings && Object.keys(selectedLand.surroundings).length > 0 && (
                    <>
                      <div className="land-surround-title">Surroundings within 500 m</div>
                      <div className="land-surround-grid">
                        <div className="surround-item">
                          <div className="surround-icon school-icon"><School size={14} /></div>
                          <div className="surround-info">
                            <span>Schools</span>
                            <strong>{selectedLand.surroundings.schools ?? 0}</strong>
                          </div>
                        </div>
                        <div className="surround-item">
                          <div className="surround-icon hospital-icon"><Hospital size={14} /></div>
                          <div className="surround-info">
                            <span>Hospitals</span>
                            <strong>{selectedLand.surroundings.hospitals ?? 0}</strong>
                          </div>
                        </div>
                        <div className="surround-item">
                          <div className="surround-icon restaurant-icon"><UtensilsCrossed size={14} /></div>
                          <div className="surround-info">
                            <span>Restaurants</span>
                            <strong>{selectedLand.surroundings.restaurants ?? 0}</strong>
                          </div>
                        </div>
                        <div className="surround-item">
                          <div className="surround-icon pharmacy-icon"><Pill size={14} /></div>
                          <div className="surround-info">
                            <span>Pharmacies</span>
                            <strong>{selectedLand.surroundings.pharmacies ?? 0}</strong>
                          </div>
                        </div>
                        <div className="surround-item">
                          <div className="surround-icon bus-icon"><Bus size={14} /></div>
                          <div className="surround-info">
                            <span>Bus Stops</span>
                            <strong>{selectedLand.surroundings.bus_stops ?? 0}</strong>
                          </div>
                        </div>
                        <div className="surround-item">
                          <div className="surround-icon road-icon"><Road size={14} /></div>
                          <div className="surround-info">
                            <span>Major Roads</span>
                            <strong>{selectedLand.surroundings.major_roads ?? 0}</strong>
                          </div>
                        </div>
                        <div className="surround-item">
                          <div className="surround-icon bank-icon"><Landmark size={14} /></div>
                          <div className="surround-info">
                            <span>Banks</span>
                            <strong>{selectedLand.surroundings.banks ?? 0}</strong>
                          </div>
                        </div>
                      </div>
                    </>
                  )}

                  <div className="selected-land-budget">
                    <div className="selected-land-budget-heading">
                      <div>
                        <span className="eyebrow">Parcel estimate</span>
                        <strong>Land budget per cent</strong>
                      </div>
                      {loadingLandBudget ? <span className="budget-loading">Calculating…</span> : selectedLandBudget && <strong className="land-price">{selectedLandBudget.formatted_price}</strong>}
                    </div>
                    {selectedLandBudget && <small>Based on {selectedLandBudget.factors.source} · {selectedLandBudget.factors.distance_to_road} to major road · population density {selectedLandBudget.factors.population_density}</small>}
                    {!loadingLandBudget && !selectedLandBudget && <small>Budget could not be calculated for this parcel.</small>}
                  </div>

                  {selectedLand.tags && Object.keys(selectedLand.tags).length > 0 && (
                    <details className="land-tags-details">
                      <summary>OSM Tags</summary>
                      <div className="land-tags-body">
                        {Object.entries(selectedLand.tags).map(([k, v]) => (
                          <div key={k} className="land-tag-row">
                            <span className="land-tag-key">{k}</span>
                            <span className="land-tag-val">{v}</span>
                          </div>
                        ))}
                      </div>
                    </details>
                  )}
                </div>
              )}

              {/* Candidates */}
              {mode === 'business' && candidates.length > 0 && (
                <div className="results-wrapper">
                  <div className="scan-summary">
                    <div>
                      <span className="scan-summary-kicker">Market scan complete</span>
                      <strong>{candidates.length} locations ranked</strong>
                      <small>Click any card or map cell to compare suitability and budget.</small>
                    </div>
                    <div className="scan-summary-stats">
                      <span><b>{Math.round(Math.max(...scores))}</b><small>best score</small></span>
                      {budgets.length > 0 && <span><b>₹{Math.round(minBudget / 1000)}k–₹{Math.round(maxBudget / 1000)}k</b><small>budget / cent</small></span>}
                    </div>
                  </div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
                    <h3 className="section-title" style={{ margin: 0 }}>Top Hotspots</h3>
                    {geoJson && (
                      <span className="badge" style={{ backgroundColor: '#ef4444', color: '#fff', fontSize: '11px', padding: '4px 8px', borderRadius: '12px' }}>
                        {geoJson.features?.filter((f: any) => isFeatureCompetitor(f, business)).length || 0} Competitors Nearby
                      </span>
                    )}
                  </div>
                  {candidates.map((c, i) => (
                    <button
                      type="button"
                      key={`${c.lat}-${c.lon}`}
                      onClick={() => setSelected(i)}
                      className={`data-card candidate-btn ${selected === i ? 'selected' : ''}`}
                    >
                      <div className="candidate-info">
                        <strong>Rank #{i + 1}</strong>
                        <span className="score">Score: {c.model_score.toFixed(2)}</span>
                      </div>
                      <div className="candidate-coords"><MapPin size={12}/> {c.lat.toFixed(4)}, {c.lon.toFixed(4)}</div>
                      {c.budget_estimate && <div className="candidate-budget"><span>Estimated land budget</span><strong>{c.budget_estimate.formatted_price}</strong></div>}
                    </button>
                  ))}
                </div>
              )}

              {/* Candidate Details */}
              {(mode === 'business' && chosen) && (
                <div className="details-panel mt-4">
                  <h4>Selected Hotspot</h4>
                  <div className="metrics-grid">
                    <div className="metric-box">
                      <label>Population</label>
                      <strong>{formatNum(chosen.details.population)}</strong>
                    </div>
                    <div className="metric-box">
                      <label>Competition</label>
                      <strong>{formatNum(chosen.details.competitors)}</strong>
                    </div>
                  </div>
                  {chosen.budget_estimate && (
                    <div className="selected-budget-card">
                      <div><span>Estimated land budget</span><strong>{chosen.budget_estimate.formatted_price}</strong></div>
                      <small>{chosen.budget_estimate.factors.source} · {chosen.budget_estimate.factors.distance_to_road} to major road</small>
                    </div>
                  )}
                </div>
              )}
            </div>
          </div>

          <div className="analysis-map-area">
            <MapContainer center={center} zoom={13} className="full-map">
              <TileLayer
                attribution="&copy; OpenStreetMap contributors"
                url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
              />
              <Viewport center={center} />

              {mode === 'land' && (
                <CircleMarker center={center} radius={8} pathOptions={{ color: '#ef4444', fillColor: '#ef4444', fillOpacity: 0.8, weight: 2 }}>
                  <Popup>Target Location</Popup>
                </CircleMarker>
              )}

              {(mode === 'land' || mode === 'business') && geoJson && (
                <GeoJSON
                  key={`${JSON.stringify(geoJson)}-${showLabels}`}
                  data={mode === 'business' ? {
                    ...geoJson,
                    features: (geoJson.features || []).filter((f: any) => isFeatureCompetitor(f, business))
                  } : geoJson}
                  pointToLayer={(feature, latlng) => {
                    const color = getCategoryColor(feature.properties, mode === 'business' ? business : undefined);
                    const isCompetitor = mode === 'business' && isFeatureCompetitor(feature, business);
                    return L.circleMarker(latlng, {
                      radius: isCompetitor ? 7 : 5,
                      color: '#ffffff',
                      weight: 1.5,
                      fillColor: color,
                      fillOpacity: 0.9
                    });
                  }}
                  onEachFeature={(feature, layer) => {
                    if (feature.properties) {
                      const name = feature.properties.name || 'Unknown Location';
                      const p = feature.properties;
                      const displayCat = p.amenity || p.shop || p.category || 'Amenity';
                      const isCompetitor = mode === 'business' && isFeatureCompetitor(feature, business);
                      const tag = isCompetitor ? '<br/><span style="color:#ef4444;font-weight:bold">Competitor</span>' : '';
                      layer.bindPopup(`<strong>${name}</strong><br/><span style="text-transform:capitalize;color:#666;font-size:0.8rem">${displayCat}</span>${tag}`);
                      if (showLabels && name !== 'Unknown Location') {
                        layer.bindTooltip(name, { permanent: true, direction: 'right', className: 'poi-label-tooltip', offset: [10, 0] });
                      }
                    }
                  }}
                />
              )}

              {/* Empty Land Layer — rendered BELOW amenity dots so dots stay visible */}
              {mode === 'land' && showEmptyLand && emptyLand && (
                <GeoJSON
                  key={`empty-land-${JSON.stringify(center)}-${showEmptyLand}`}
                  data={emptyLand}
                  style={(feature) => {
                    const landType = feature?.properties?.land_type || '';
                    const color = getLandColor(landType);
                    const isSelected = selectedLand?.centroid_lat === feature?.properties?.centroid_lat &&
                                       selectedLand?.centroid_lon === feature?.properties?.centroid_lon;
                    return {
                      color: isSelected ? '#ffffff' : color,
                      weight: isSelected ? 3 : 2,
                      fillColor: color,
                      fillOpacity: isSelected ? 0.65 : 0.35,
                      opacity: 0.9,
                      dashArray: isSelected ? undefined : '4 3',
                    };
                  }}
                  onEachFeature={(feature, layer) => {
                    const p = feature.properties || {};
                    const areaHa = p.approx_area_m2
                      ? (p.approx_area_m2 / 10000).toFixed(2)
                      : 'N/A';
                    layer.bindTooltip(
                      `<strong>${p.name || p.label || 'Empty Land'}</strong><br/><span style="font-size:0.78rem;text-transform:capitalize;color:#64748b">${(p.land_type || '').replace(/_/g, ' ')}</span><br/><span style="font-size:0.75rem">📐 ${areaHa} ha — click for details</span>`,
                      { sticky: true, opacity: 0.95 }
                    );
                    (layer as any).on('click', () => {
                      setSelectedLandBudget(null)
                      setLoadingLandBudget(true)
                      setSelectedLand(p as LandParcel);
                    });
                    (layer as any).on('mouseover', function(this: any) { this.setStyle({ fillOpacity: 0.6 }); });
                    (layer as any).on('mouseout',  function(this: any) {
                      const sel = selectedLand;
                      const isSel = sel?.centroid_lat === p.centroid_lat && sel?.centroid_lon === p.centroid_lon;
                      this.setStyle({ fillOpacity: isSel ? 0.65 : 0.35 });
                    });
                  }}
                />
              )}

              {mode === 'business' && candidates.map((c, i) => (
                <Rectangle
                  key={`${c.lat}-${c.lon}`}
                  bounds={[[c.lat - CELL / 2, c.lon - CELL / 2], [c.lat + CELL / 2, c.lon + CELL / 2]]}
                  pathOptions={{
                    color: selected === i ? '#2563eb' : budgetHeat(c.budget_estimate?.price_per_cent_inr || 0, minBudget, maxBudget),
                    weight: selected === i ? 3 : 2,
                    fillColor: heat(c.model_score, min, max),
                    fillOpacity: selected === i ? 0.7 : 0.4
                  }}
                  eventHandlers={{ click: () => setSelected(i) }}
                >
                  <Popup>
                    <strong>Rank #{i + 1}</strong><br/>
                    Score: {c.model_score.toFixed(2)}<br/>
                    {c.budget_estimate ? `Land budget: ${c.budget_estimate.formatted_price}` : 'Land budget: unavailable'}
                  </Popup>
                </Rectangle>
              ))}
            </MapContainer>

            {/* ── Floating Map Legend ── */}
            {(geoJson || (mode === 'business' && candidates.length > 0)) && (
              <MapLegend mode={mode} />
            )}
          </div>
        </div>}

      </main>
    </div>
  )
}
