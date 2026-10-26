import { BrowserRouter } from 'react-router-dom'
import { ServiceStatus } from './ServiceStatus'
import { WorkspaceHome } from './WorkspaceHome'

export default function App() {
  return (
    <BrowserRouter>
      <WorkspaceHome />
      <div className="no-print" style={{ padding: '8px 24px 24px' }}>
        <ServiceStatus />
      </div>
    </BrowserRouter>
  )
}
