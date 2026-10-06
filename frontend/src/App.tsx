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
  SquareArrowOutUpRight
} from 'lucide-react'
import './App.css'


const API = 'http://127.0.0.1:8000/api'
const CELL = 0.005

type Mode = 'land' | 'business'
type Page = 'dashboard' | 'analysis' | 'locations' | 'settings'

type Factors = { positive_factors: string[]; negative_factors: string[] }
type Candidate = { 
  lat: number
  lon: number
  model_score: number
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

const formatNum = (n: number | null | undefined, suffix = '') => 
  n === null || n === undefined ? 'N/A' : `${n}${suffix}`

const getCategoryColor = (props: any) => {
  if (!props) return '#94a3b8';
  const cat = props.category || props.amenity || props.shop || props.healthcare || props.office || props.leisure || '';
  if (!cat) return '#8b5cf6';
  
  const colors: Record<string, string> = {
    'pharmacy': '#10b981', // green
    'restaurant': '#3b82f6', // blue
    'fast_food': '#3b82f6',
    'cafe': '#f59e0b',
    'bank': '#f97316',
    'hospital': '#ec4899',
    'clinic': '#ec4899',
    'school': '#eab308',
    'college': '#eab308',
    'supermarket': '#14b8a6',
    'convenience': '#14b8a6',
    'grocery': '#14b8a6',
  };
  return colors[cat.toLowerCase()] || '#8b5cf6';
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
const DashboardView = ({ center, onNavigate }: { center: [number, number], onNavigate: (p: Page) => void }) => (
  <div className="page-content">
    <div className="page-header">
      <div>
        <h1>Dashboard</h1>
        <p>Overview of your business intelligence.</p>
      </div>
      <div className="header-actions">
        <button className="btn btn-outline"><MapPin size={16}/> Manage Locations</button>
        <button className="btn btn-primary" onClick={() => onNavigate('analysis')}><PlusCircle size={16}/> New Analysis</button>
      </div>
    </div>
    
    <div className="embedded-map-container">
      <MapContainer center={center} zoom={13} className="dashboard-map">
        {/* Light Mode OSM Map exactly like the screenshot */}
        <TileLayer 
          attribution="&copy; OpenStreetMap contributors" 
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" 
        />
        <CircleMarker center={center} radius={6} pathOptions={{ color: '#ef4444', fillColor: '#ef4444', fillOpacity: 1 }} />
      </MapContainer>
    </div>

    <div className="recent-section">
      <div className="section-header">
        <h3>Recent Analyses</h3>
        <span className="total-count">1 total reports</span>
      </div>
      
      <div className="recent-grid">
        <div className="report-card">
          <div className="report-card-header">
            <span className="badge">Retail</span>
            <span className="date"><Calendar size={12}/> Oct 5, 2026</span>
          </div>
          <h4>Analysis #192</h4>
          <div className="location-info">
            <MapPin size={14} className="text-primary"/> 11.0168, 76.9558
          </div>
          <div className="target-info">Targeting: general public</div>
          
          <button className="view-report-btn">
            View Report <ArrowRight size={14}/>
          </button>
        </div>
      </div>
    </div>
  </div>
)


// ── Map Legend Component ──────────────────────────────────────────────────────
const LAND_DOT_LEGEND = [
  { color: '#10b981', label: 'Pharmacy' },
  { color: '#3b82f6', label: 'Restaurant / Café / Fast-food' },
  { color: '#f59e0b', label: 'Café' },
  { color: '#f97316', label: 'Bank' },
  { color: '#ec4899', label: 'Hospital / Clinic' },
  { color: '#eab308', label: 'School / College' },
  { color: '#14b8a6', label: 'Grocery / Supermarket' },
  { color: '#94a3b8', label: 'Bus stop / Road' },
  { color: '#8b5cf6', label: 'Other amenity / Shop / Office' },
]

const BUSINESS_SCORE_LEGEND = [
  { color: '#10b981', label: 'High score (top 25 %)' },
  { color: '#f59e0b', label: 'Good score (50–75 %)' },
  { color: '#f97316', label: 'Moderate (25–50 %)' },
  { color: '#ef4444', label: 'Low score (bottom 25 %)' },
]

function MapLegend({ mode }: { mode: Mode }) {
  const [open, setOpen] = useState(true)
  const items = mode === 'land' ? LAND_DOT_LEGEND : BUSINESS_SCORE_LEGEND

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

export default function App() {
  const [activePage, setActivePage] = useState<Page>('dashboard')
  
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
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

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
    setGeoJson(null)
    setEmptyLand(null)
    setShowEmptyLand(false)
    setSelectedLand(null)

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
        if (mapResponse.ok) setGeoJson(await mapResponse.json())

        // Fetch empty land in background — don't block the main result
        setLoadingLand(true)
        fetch(`${API}/empty-land?lat=${position[0]}&lon=${position[1]}&radius=1500`)
          .then(r => r.ok ? r.json() : null)
          .then(data => {
            if (data && data.features?.length > 0) {
              setEmptyLand(data)
              setShowEmptyLand(true) // auto-show when parcels are found
            }
          })
          .catch(() => {})
          .finally(() => setLoadingLand(false))
      } else {
        const response = await fetch(`${API}/find-best-locations`, { 
          method: 'POST', 
          headers: { 'Content-Type': 'application/json' }, 
          body: JSON.stringify({ business_type: business, start_lat: position[0], start_lon: position[1], steps: 4, step_size: CELL }) 
        })
        const data = await response.json()
        if (!response.ok) throw new Error(data.detail || 'Model 2 could not evaluate this area.')
        setCandidates(data.candidates || [])
      }
    } catch (err) { 
      setError(err instanceof Error ? err.message : 'Unable to complete the analysis.') 
    } finally { 
      setLoading(false) 
    }
  }

  const scores = candidates.map(c => c.model_score)
  const min = scores.length ? Math.min(...scores) : 0
  const max = scores.length ? Math.max(...scores) : 1
  const chosen = selected === null ? null : candidates[selected]

  return (
    <div className="app-container">
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
          <button className="bottom-link"><Sun size={16}/> Light Mode</button>
          <button className="bottom-link"><LogOut size={16}/> Sign Out</button>
        </div>
      </aside>

      {/* Main Content Area */}
      <main className="main-area">
        {activePage === 'dashboard' && <DashboardView center={center} onNavigate={setActivePage} />}
        
        {/* Full Analysis Tool Page */}
        <div className={`analysis-view ${activePage === 'analysis' ? 'visible' : 'hidden'}`}>
          <div className="analysis-sidebar">
            <div className="analysis-header">
              <h2>New Analysis</h2>
              <p>Run geospatial models</p>
            </div>

            <div className="mode-toggle">
              <button 
                type="button"
                className={`mode-btn ${mode === 'land' ? 'active' : ''}`}
                onClick={() => setMode('land')}
              >
                Evaluate Land
              </button>
              <button 
                type="button"
                className={`mode-btn ${mode === 'business' ? 'active' : ''}`}
                onClick={() => setMode('business')}
              >
                Place Business
              </button>
            </div>

            <form onSubmit={search} className="search-form">
              {mode === 'business' && (
                <div className="input-group">
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
              {/* Recommendations */}
              {mode === 'land' && recommendations.length > 0 && (
                <div className="results-wrapper">
                  <h3 className="section-title">AI Recommendations</h3>
                  {recommendations.map((r, i) => (
                    <div key={r.business + i} className="data-card">
                      <div className="card-header">
                        <div className="biz-title">
                          <h4>{r.business}</h4>
                        </div>
                        <span className="score-badge">{r.score_percent}%</span>
                      </div>
                      <div className="factors">
                        {r.positive_factors.slice(0, 2).map((x, i) => (
                          <div key={i} className="factor pos"><ChevronRight size={14} /> {x}</div>
                        ))}
                      </div>
                    </div>
                  ))}
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
                      onClick={() => setSelectedLand(null)}
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
                  <h3 className="section-title">Top Hotspots</h3>
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
              
              {mode === 'land' && geoJson && (
                <GeoJSON 
                  key={JSON.stringify(geoJson)}
                  data={geoJson} 
                  pointToLayer={(feature, latlng) => {
                    const color = getCategoryColor(feature.properties);
                    return L.circleMarker(latlng, { 
                      radius: 5, 
                      color: '#ffffff', 
                      weight: 1.5, 
                      fillColor: color, 
                      fillOpacity: 0.9 
                    });
                  }} 
                  onEachFeature={(feature, layer) => {
                    if (feature.properties) {
                      const name = feature.properties.name || 'Unknown Location';
                      const cat = feature.properties.category || feature.properties.amenity || feature.properties.shop || 'Amenity';
                      layer.bindPopup(`<strong>${name}</strong><br/><span style="text-transform:capitalize;color:#666;font-size:0.8rem">${cat}</span>`);
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
                    color: selected === i ? '#2563eb' : 'transparent', 
                    weight: selected === i ? 2 : 0, 
                    fillColor: heat(c.model_score, min, max), 
                    fillOpacity: selected === i ? 0.7 : 0.4 
                  }} 
                  eventHandlers={{ click: () => setSelected(i) }}
                >
                  <Popup>
                    <strong>Rank #{i + 1}</strong><br/>
                    Score: {c.model_score.toFixed(2)}
                  </Popup>
                </Rectangle>
              ))}
            </MapContainer>

            {/* ── Floating Map Legend ── */}
            {(geoJson || (mode === 'business' && candidates.length > 0)) && (
              <MapLegend mode={mode} />
            )}
          </div>
        </div>
        
        {activePage === 'locations' && (
          <div className="page-content">
            <div className="page-header">
              <div>
                <h1>Saved Locations</h1>
                <p>Manage your saved business locations.</p>
              </div>
            </div>
            <p className="text-muted">No locations saved yet.</p>
          </div>
        )}

        {activePage === 'settings' && (
          <div className="page-content">
            <div className="page-header">
              <div>
                <h1>Settings</h1>
                <p>Manage your account preferences.</p>
              </div>
            </div>
            <p className="text-muted">Settings panel goes here.</p>
          </div>
        )}
      </main>
    </div>
  )
}
