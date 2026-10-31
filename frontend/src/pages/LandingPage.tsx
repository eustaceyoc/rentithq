import { useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { loadSession } from '../api/session'
import {
  BuiltFor,
  ComingSoon,
  FeatureShows,
  FinalCta,
  HowItWorks,
  LandingFooter,
  LandingHeader,
  LandingHero,
  Questions,
} from './landing/sections'
import './landing.css'

export function LandingPage() {
  const navigate = useNavigate()

  useEffect(() => {
    document.title = 'Rent It HQ'
    const controller = new AbortController()
    loadSession(controller.signal)
      .then((session) => {
        if (session && !controller.signal.aborted) {
          navigate('/app', { replace: true })
        }
      })
      .catch(() => {
        // The public page stays available when the session check fails.
      })
    return () => {
      controller.abort()
    }
  }, [navigate])

  return (
    <div className="landing">
      <LandingHeader />
      <main>
        <LandingHero />
        <BuiltFor />
        <FeatureShows />
        <HowItWorks />
        <ComingSoon />
        <Questions />
        <FinalCta />
      </main>
      <LandingFooter />
    </div>
  )
}
