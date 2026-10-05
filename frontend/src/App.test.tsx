import { cleanup, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import App from './App'

const response = (body: unknown, ok = true) => Promise.resolve({ ok, json: () => Promise.resolve(body) })

afterEach(() => { cleanup(); vi.unstubAllGlobals() })

describe('GeoBusiness workflows', () => {
  it('runs the LAND → BUSINESS workflow and renders map data and model output', async () => {
    const fetch = vi.fn()
      .mockReturnValueOnce(response({ business_types: ['pharmacy'] }))
      .mockReturnValueOnce(response({ latitude: 11.008, longitude: 76.95, display_name: 'RS Puram' }))
      .mockReturnValueOnce(response({ recommendations: [{ business: 'Pharmacy', score_percent: 80, positive_factors: ['+ roads'], negative_factors: [] }] }))
      .mockReturnValueOnce(response({ type: 'FeatureCollection', features: [] }))
    vi.stubGlobal('fetch', fetch)
    const user = userEvent.setup()
    render(<App />)
    expect(screen.getByTestId('tile-layer')).toHaveAttribute('data-url', expect.stringContaining('tile.openstreetmap.org'))
    await user.type(screen.getByLabelText('Location'), 'RS Puram, Coimbatore')
    await user.click(screen.getByRole('button', { name: 'Analyse land' }))
    expect(await screen.findByText('Model 1 recommendations')).toBeInTheDocument()
    expect(screen.getByText('Pharmacy')).toBeInTheDocument()
    expect(screen.getByTestId('geojson')).toBeInTheDocument()
  })

  it('shows a useful message when geocoding returns no result', async () => {
    const fetch = vi.fn().mockReturnValueOnce(response({ business_types: [] })).mockReturnValueOnce(response({ detail: 'Location not found' }, false))
    vi.stubGlobal('fetch', fetch)
    const user = userEvent.setup()
    render(<App />)
    await user.type(screen.getByLabelText('Location'), 'not-a-real-place')
    await user.click(screen.getByRole('button', { name: 'Analyse land' }))
    expect(await screen.findByText('The requested location could not be found.')).toBeInTheDocument()
  })

  it('runs BUSINESS → LAND, displays heatmap candidates, and opens candidate details', async () => {
    const candidate = { lat: 11, lon: 76, model_score: 42.5, details: { population: 1200, competitors: 1, schools: 2, colleges: 0, hospitals: 1, bus_stops: 3, road_density: 8, distance_to_major_road: 90 }, explanation: { positive_factors: ['+ road density'], negative_factors: [] } }
    const fetch = vi.fn()
      .mockReturnValueOnce(response({ business_types: ['pharmacy'] }))
      .mockReturnValueOnce(response({ latitude: 11, longitude: 76, display_name: 'Coimbatore' }))
      .mockReturnValueOnce(response({ candidates: [candidate] }))
    vi.stubGlobal('fetch', fetch)
    const user = userEvent.setup()
    render(<App />)
    await user.click(screen.getByRole('button', { name: 'BUSINESS → LAND' }))
    await user.type(screen.getByLabelText('Search area'), 'Coimbatore')
    await user.click(screen.getByRole('button', { name: 'Find locations' }))
    await user.click(await screen.findByRole('button', { name: /#1 candidate/i }))
    expect(screen.getByText('Candidate #1 details')).toBeInTheDocument()
    expect(screen.getByText('Population')).toBeInTheDocument()
    expect(screen.getByTestId('heat-cell')).toBeInTheDocument()
  })

  it('shows API failures instead of silently continuing', async () => {
    const fetch = vi.fn()
      .mockReturnValueOnce(response({ business_types: ['pharmacy'] }))
      .mockReturnValueOnce(response({ latitude: 11, longitude: 76, display_name: 'Coimbatore' }))
      .mockReturnValueOnce(response({ detail: 'Geographic data service unavailable' }, false))
    vi.stubGlobal('fetch', fetch)
    const user = userEvent.setup()
    render(<App />)
    await user.click(screen.getByRole('button', { name: 'BUSINESS → LAND' }))
    await user.type(screen.getByLabelText('Search area'), 'Coimbatore')
    await user.click(screen.getByRole('button', { name: 'Find locations' }))
    expect(await screen.findByText('Geographic data service unavailable')).toBeInTheDocument()
    await waitFor(() => expect(fetch).toHaveBeenCalledTimes(3))
  })
})
