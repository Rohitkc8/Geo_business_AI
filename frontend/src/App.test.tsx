import { cleanup, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import App from './App'

const response = (body: unknown, ok = true) => Promise.resolve({ ok, json: () => Promise.resolve(body) })

afterEach(() => { cleanup(); vi.unstubAllGlobals(); window.localStorage.clear() })

describe('GeoBusiness redesigned workflows', () => {
  it('runs land evaluation, saves the location, and manages the saved card', async () => {
    const fetch = vi.fn((input: string) => {
      if (input.endsWith('/business-types')) return response({ business_types: ['pharmacy'] })
      if (input.endsWith('/geocode')) return response({ latitude: 11.008, longitude: 76.95, display_name: 'RS Puram' })
      if (input.includes('/analyze-location')) return response({ recommendations: [{ business: 'Pharmacy', score_percent: 80, positive_factors: ['Good access'], negative_factors: [] }], budget_estimate: { formatted_price: '₹500,000 per cent', factors: { source: 'Fallback', population_density: '1200', distance_to_road: '180m' } } })
      return response({ type: 'FeatureCollection', features: [] })
    })
    vi.stubGlobal('fetch', fetch)
    const user = userEvent.setup()
    render(<App />)
    await user.click(screen.getByRole('button', { name: 'New Analysis' }))
    await user.type(screen.getByLabelText('Location'), 'RS Puram, Coimbatore')
    await user.click(screen.getByRole('button', { name: 'Run Analysis' }))
    expect((await screen.findAllByText('Pharmacy')).length).toBeGreaterThan(0)
    await user.click(screen.getByRole('button', { name: 'Save this analysis' }))
    expect(await screen.findByRole('status')).toHaveTextContent('Location saved')
    await user.click(screen.getAllByRole('button', { name: 'Saved Locations' })[0])
    expect(await screen.findByText('RS Puram, Coimbatore')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: /Remove RS Puram/ }))
    expect(await screen.findByText('No saved locations yet')).toBeInTheDocument()
  })

  it('shows a useful message when geocoding returns no result', async () => {
    const fetch = vi.fn((input: string) => input.endsWith('/business-types') ? response({ business_types: [] }) : response({ detail: 'Location not found' }, false))
    vi.stubGlobal('fetch', fetch)
    const user = userEvent.setup()
    render(<App />)
    await user.click(screen.getByRole('button', { name: 'New Analysis' }))
    await user.type(screen.getByLabelText('Location'), 'not-a-real-place')
    await user.click(screen.getByRole('button', { name: 'Run Analysis' }))
    expect(await screen.findByText('The requested location could not be found.')).toBeInTheDocument()
  })

  it('runs business placement, compares candidates, and interacts with the map controls', async () => {
    const candidate = (lat: number, lon: number, score: number) => ({ lat, lon, model_score: score, budget_estimate: { price_per_cent_inr: 725000, formatted_price: '₹725,000 per cent', factors: { source: 'Prototype', population_density: '1200', distance_to_road: '90m' } }, details: { population: 1200, competitors: 1, schools: 2, colleges: 0, hospitals: 1, bus_stops: 3, road_density: 8, distance_to_major_road: 90 }, explanation: { positive_factors: ['Good road density'], negative_factors: [] } })
    const fetch = vi.fn((input: string) => {
      if (input.endsWith('/business-types')) return response({ business_types: ['pharmacy'] })
      if (input.endsWith('/geocode')) return response({ latitude: 11, longitude: 76, display_name: 'Coimbatore' })
      if (input.includes('/find-best-locations')) return response({ candidates: [candidate(11, 76, 42.5), candidate(11.005, 76.005, 38.2), candidate(11.01, 76.01, 31.7)] })
      return response({ type: 'FeatureCollection', features: [] })
    })
    vi.stubGlobal('fetch', fetch)
    const user = userEvent.setup()
    render(<App />)
    await user.click(screen.getByRole('button', { name: 'New Analysis' }))
    await user.click(screen.getByRole('button', { name: 'Place Business' }))
    await user.type(screen.getByLabelText('Search area'), 'Coimbatore')
    await user.click(screen.getByRole('button', { name: 'Run Analysis' }))
    await user.click((await screen.findAllByRole('button', { name: /Rank #1/ }))[0])
    expect(screen.getByText('Selected Hotspot')).toBeInTheDocument()
    expect(screen.getAllByText('Population').length).toBeGreaterThan(0)
    await user.click(screen.getAllByRole('button', { name: /Compare/ })[0])
    await user.click(screen.getAllByRole('button', { name: /Compare/ })[1])
    expect(await screen.findByText('Compare locations')).toBeInTheDocument()
    expect(screen.getByText('Budget / cent')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Fit results' }))
    await user.click(screen.getByRole('button', { name: 'Export PDF report' }))
    expect(await screen.findByRole('heading', { name: 'Location analysis report' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Save as PDF' })).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Back to analysis' }))
    expect(await screen.findByText('Compare locations')).toBeInTheDocument()
    await waitFor(() => expect(fetch).toHaveBeenCalled())
  })
})
