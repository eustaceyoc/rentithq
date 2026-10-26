import { useEffect } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { loadSession } from '../api/session'
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
      <header className="landing-header">
        <Link className="brand" to="/">
          Rent It HQ
        </Link>
        <nav className="landing-nav" aria-label="Account">
          <Link className="btn btn-ghost" to="/login">
            Sign in
          </Link>
          <Link className="btn btn-primary" to="/login?mode=register">
            Get started
          </Link>
        </nav>
      </header>
      <main>
        <section className="hero">
          <div>
            <p className="eyebrow">For hostels and apartments</p>
            <h1>Rooms, rent, and repairs in one place.</h1>
            <p className="lede">
              Rent It HQ is for independent hostel and apartment owners. See who is in,
              who has paid, and what still needs fixing.
            </p>
            <div className="hero-actions">
              <Link className="btn btn-primary" to="/login?mode=register">
                Get started
              </Link>
              <Link className="btn btn-ghost" to="/login">
                Sign in
              </Link>
            </div>
          </div>
          <div
            className="preview"
            role="img"
            aria-label="Preview of the Rent It HQ workspace, showing occupancy, rent due, and open maintenance"
          >
            <div className="preview-side">
              <strong>Harbour House</strong>
              <span className="on">Dashboard</span>
              <span>Properties</span>
              <span>Residents</span>
              <span>Billing</span>
              <span>Maintenance</span>
            </div>
            <div className="preview-main">
              <div className="preview-kpis">
                <div>
                  <small>Rooms occupied</small>
                  <b>18</b>
                </div>
                <div>
                  <small>Outstanding</small>
                  <b>4,200</b>
                </div>
                <div>
                  <small>Collected</small>
                  <b>12,800</b>
                </div>
                <div>
                  <small>Open maintenance</small>
                  <b>3</b>
                </div>
              </div>
              <div className="preview-list">
                <div className="preview-row">
                  <span>
                    Room 12
                    <small>Ama Mensah moves out Friday</small>
                  </span>
                  <span className="pill">Stay</span>
                </div>
                <div className="preview-row">
                  <span>
                    Bed 4, dorm B
                    <small>Payment recorded, cash</small>
                  </span>
                  <span className="pill">Paid</span>
                </div>
              </div>
            </div>
          </div>
        </section>
        <section className="problems" aria-label="Problems this replaces">
          <p>A notebook for rooms and a different place for the money.</p>
          <p>Chasing rent without a clear list of who still owes.</p>
          <p>Repairs that only exist in a chat message.</p>
          <p>Guessing which beds are free tonight.</p>
        </section>
        <section className="section" id="features">
          <h2>What you keep in the workspace</h2>
          <p className="section-intro">
            The records an owner actually asks for, without a module for every idea.
          </p>
          <div className="features">
            <article>
              <h3>Properties</h3>
              <p>One workspace can hold more than one building. Apartments and hostels sit side by side.</p>
            </article>
            <article>
              <h3>Rooms and beds</h3>
              <p>Whole units, rooms, or beds. A shared dorm can be booked bed by bed.</p>
            </article>
            <article>
              <h3>Residents and bookings</h3>
              <p>Who is staying, which space they have, and when that stay ends.</p>
            </article>
            <article>
              <h3>Invoices and payments</h3>
              <p>Issue an invoice and record mobile money, card, or cash against it.</p>
            </article>
            <article>
              <h3>Maintenance</h3>
              <p>Requests with a status, so open work does not disappear into a thread.</p>
            </article>
            <article>
              <h3>Reports</h3>
              <p>Occupancy, what was collected this month, and what is still outstanding.</p>
            </article>
          </div>
        </section>
        <section className="section" id="how">
          <h2>How it works</h2>
          <ol className="steps">
            <li>
              <span className="step-no">1</span>
              <h3>Open a workspace</h3>
              <p>Create the account, name the workspace, and set the currency you charge in.</p>
            </li>
            <li>
              <span className="step-no">2</span>
              <h3>Add the rooms and the people</h3>
              <p>Record the property, then the residents and the stays that fill it.</p>
            </li>
            <li>
              <span className="step-no">3</span>
              <h3>Collect rent and track repairs</h3>
              <p>Invoice, record the payment, and keep maintenance requests until they are done.</p>
            </li>
          </ol>
        </section>
        <section className="section" id="faq">
          <h2>Questions owners ask</h2>
          <div className="faq">
            <details>
              <summary>Does recording a card or mobile-money payment charge the resident?</summary>
              <p>
                No. You record what was paid. Rent It HQ does not take the money from a phone or a card.
              </p>
            </details>
            <details>
              <summary>Can one workspace cover a hostel and an apartment building?</summary>
              <p>Yes. Add each property, then use rooms, units, or beds where you need them.</p>
            </details>
            <details>
              <summary>Can a resident sign in?</summary>
              <p>
                Yes, if you add them as a member. They see their own stay, invoices, and maintenance, not the whole portfolio.
              </p>
            </details>
            <details>
              <summary>What does it cost?</summary>
              <p>There is no public price list on this page. Create a workspace and use the product.</p>
            </details>
          </div>
        </section>
        <section className="cta-band" aria-labelledby="final-cta">
          <div>
            <h2 id="final-cta">Start with the building you already run.</h2>
            <p>Add the rooms, the people, and the rent. The rest can wait.</p>
          </div>
          <Link className="btn btn-primary" to="/login?mode=register">
            Get started
          </Link>
        </section>
      </main>
      <footer className="landing-footer">
        <span>Rent It HQ</span>
        <nav aria-label="Footer">
          <Link to="/login">Sign in</Link>
        </nav>
      </footer>
    </div>
  )
}
