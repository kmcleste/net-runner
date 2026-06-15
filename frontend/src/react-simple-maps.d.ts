declare module 'react-simple-maps' {
  import { ReactNode, SVGProps } from 'react'

  export interface ComposableMapProps extends SVGProps<SVGSVGElement> {
    projection?: string
    projectionConfig?: Record<string, unknown>
    width?: number
    height?: number
    children?: ReactNode
  }

  export function ComposableMap(props: ComposableMapProps): JSX.Element

  export interface GeographiesProps {
    geography: string | object
    children: (args: { geographies: Geography[] }) => ReactNode
    parseGeographies?: (features: unknown[]) => Geography[]
  }

  export interface Geography {
    rsmKey: string
    id: string
    type: string
    properties: Record<string, unknown>
    geometry: Record<string, unknown>
  }

  export interface GeographyProps extends SVGProps<SVGPathElement> {
    geography: Geography
    style?: {
      default?: React.CSSProperties
      hover?: React.CSSProperties
      pressed?: React.CSSProperties
    }
  }

  export function Geographies(props: GeographiesProps): JSX.Element
  export function Geography(props: GeographyProps): JSX.Element

  export interface MarkerProps extends SVGProps<SVGGElement> {
    coordinates: [number, number]
    children?: ReactNode
  }

  export function Marker(props: MarkerProps): JSX.Element

  export interface ZoomableGroupProps {
    center?: [number, number]
    zoom?: number
    children?: ReactNode
  }

  export function ZoomableGroup(props: ZoomableGroupProps): JSX.Element
}
