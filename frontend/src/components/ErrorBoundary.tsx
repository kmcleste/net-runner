import { Component, ErrorInfo, ReactNode } from 'react'

interface Props { children: ReactNode }
interface State { error: Error | null }

export class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null }

  static getDerivedStateFromError(error: Error): State {
    return { error }
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error('net-runner UI error:', error, info)
  }

  render() {
    if (this.state.error) {
      return (
        <div style={{
          height: '100vh',
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          background: '#111827',
          fontFamily: 'Courier New, monospace',
          gap: 12,
          padding: 24,
        }}>
          <div style={{ fontSize: 24, color: '#ef4444' }}>✗ UI Error</div>
          <div style={{
            background: '#1e293b',
            border: '1px solid #374151',
            borderRadius: 8,
            padding: 16,
            fontSize: 11,
            color: '#fca5a5',
            maxWidth: 480,
            wordBreak: 'break-word',
            lineHeight: 1.6,
          }}>
            {this.state.error.message}
          </div>
          <button
            onClick={() => this.setState({ error: null })}
            style={{
              background: '#1d4ed8',
              border: '1px solid #3b82f6',
              borderRadius: 6,
              color: '#f9fafb',
              fontSize: 12,
              padding: '8px 20px',
              cursor: 'pointer',
            }}
          >
            Dismiss and continue
          </button>
        </div>
      )
    }
    return this.props.children
  }
}
