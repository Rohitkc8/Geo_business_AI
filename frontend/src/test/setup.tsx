import type { ReactNode } from 'react'
import '@testing-library/jest-dom/vitest'
import { vi } from 'vitest'

vi.mock('react-leaflet', () => ({
  MapContainer: ({ children }: { children: ReactNode }) => <div data-testid="map">{children}</div>,
  TileLayer: ({ url }: { url?: string }) => <div data-testid="tile-layer" data-url={url} />,
  Popup: ({ children }: { children: ReactNode }) => <div>{children}</div>,
  Rectangle: ({ children, eventHandlers }: { children: ReactNode; eventHandlers?: { click?: () => void } }) => <button data-testid="heat-cell" onClick={eventHandlers?.click}>{children}</button>,
  CircleMarker: ({ children }: { children: ReactNode }) => <div>{children}</div>,
  GeoJSON: () => <div data-testid="geojson" />,
  useMap: () => ({ flyTo: vi.fn() }),
}))
