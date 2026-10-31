import { useState } from 'react'
import { Link } from 'react-router-dom'
import { ProductWindow } from './ProductWindow'

const NAV = [
  { href: '#house', label: 'The house' },
  { href: '#ledger', label: 'The ledger' },
  { href: '#repairs', label: 'Repairs' },
  { href: '#questions', label: 'Questions' },
]

export function LandingHeader() {
  const [open, setOpen] = useState(false)
  function close() {
    setOpen(false)
  }
  return (
    <header className="site-header">
      <div className="site-bar">
        <Link className="brand" to="/" onClick={close}>
          Rent It HQ
        </Link>
        <nav className="site-nav" aria-label="Page">
          {NAV.map((item) => (
            <a key={item.href} href={item.href}>
              {item.label}
            </a>
          ))}
        </nav>
        <div className="site-actions">
          <Link className="text-link" to="/login">
            Sign in
          </Link>
          <Link className="btn btn-primary" to="/login?mode=register">
            Get started
          </Link>
          <button
            type="button"
            className="menu-toggle"
            aria-expanded={open}
            aria-controls="landing-menu"
            onClick={() => setOpen((value) => !value)}
          >
            {open ? 'Close' : 'Menu'}
          </button>
        </div>
      </div>
      {open ? (
        <nav id="landing-menu" className="menu-panel" aria-label="Page">
          {NAV.map((item) => (
            <a key={item.href} href={item.href} onClick={close}>
              {item.label}
            </a>
          ))}
          <Link to="/login" onClick={close}>
            Sign in
          </Link>
          <Link className="btn btn-primary" to="/login?mode=register" onClick={close}>
            Get started
          </Link>
        </nav>
      ) : null}
    </header>
  )
}

export function LandingHero() {
  return (
    <section className="hero" id="house">
      <p className="eyebrow">For independent hostel and apartment owners</p>
      <div className="hero-grid">
        <h1>Rooms, rent, and repairs in one place.</h1>
        <div>
          <p className="lede">
            See who is in, who has paid, and what still needs fixing. One workspace holds the
            properties, the stays, the invoices, and the repair requests.
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
      </div>
      <ProductWindow
        workspace="Harbour House"
        active="Dashboard"
        label="Sample dashboard. These figures are an example screen, not a customer result."
      >
        <p className="mock-title">Dashboard</p>
        <div className="mock-kpis">
          <div>
            <small>Rooms occupied</small>
            <b>1</b>
            <small>2 free</small>
          </div>
          <div>
            <small>Outstanding</small>
            <b>50.00</b>
            <small>GHS due</small>
          </div>
          <div>
            <small>Collected</small>
            <b>30.00</b>
            <small>GHS this month</small>
          </div>
          <div>
            <small>Open maintenance</small>
            <b>1</b>
            <small>Not finished</small>
          </div>
        </div>
        <table className="mock-table">
          <caption>Upcoming move-outs</caption>
          <thead>
            <tr>
              <th>Resident</th>
              <th>Place</th>
              <th>Last day</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td>Ama Mensah</td>
              <td>Room 12</td>
              <td>30 Jun</td>
            </tr>
          </tbody>
        </table>
      </ProductWindow>
    </section>
  )
}

export function BuiltFor() {
  const people = [
    ['Hostel owners', 'Beds in a shared room, and a whole room when someone takes it.'],
    ['Apartment owners', 'Whole units, with rooms only where the building actually has them.'],
    ['A small staff', 'Owner, property manager, finance, maintenance, and a resident sign-in.'],
  ]
  return (
    <section className="audience" aria-labelledby="built-for-title">
      <h2 id="built-for-title">Built for</h2>
      <dl>
        {people.map(([title, text]) => (
          <div key={title}>
            <dt>{title}</dt>
            <dd>{text}</dd>
          </div>
        ))}
      </dl>
    </section>
  )
}

export function FeatureShows() {
  return (
    <>
      <section className="split" id="ledger">
        <div className="split-copy">
          <p className="kicker">Residents</p>
          <h2>Who is in, and which bed is free</h2>
          <p>
            Record each property, then rooms, whole units, or beds. A reservation blocks that
            space until the last occupied day. The next day it is free.
          </p>
        </div>
        <ProductWindow workspace="Harbour House" active="Residents" label="Sample resident list.">
          <p className="mock-title">Residents</p>
          <table className="mock-table">
            <thead>
              <tr>
                <th>Name</th>
                <th>Place</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td>Ama Mensah</td>
                <td>Room 12</td>
                <td>Active</td>
              </tr>
              <tr>
                <td>Kojo Boateng</td>
                <td>Bed A</td>
                <td>Confirmed</td>
              </tr>
            </tbody>
          </table>
        </ProductWindow>
      </section>
      <section className="sand">
        <div className="sand-inner">
          <p className="pull">
            Issue an invoice, then record cash, mobile money, or a card payment against it.
            Recording the payment does not charge a phone or a card.
          </p>
          <table className="ledger-table">
            <caption>Sample invoice list. Recording a payment does not charge the resident.</caption>
            <thead>
              <tr>
                <th>Invoice</th>
                <th>Status</th>
                <th>Outstanding</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td>INV-0001 · Ama Mensah</td>
                <td>Issued</td>
                <td>50.00 GHS</td>
              </tr>
              <tr>
                <td>Receipt PAY-0001</td>
                <td>Recorded</td>
                <td>30.00 GHS</td>
              </tr>
            </tbody>
          </table>
          <ul className="quiet-points">
            <li>Invoices, allocations, refunds, and voids</li>
            <li>A receipt you can print</li>
            <li>Arrears for a date you choose</li>
          </ul>
        </div>
      </section>
      <section className="repairs" id="repairs">
        <div>
          <p className="kicker">Maintenance</p>
          <h2>Repairs that stay on the list</h2>
          <p>
            File a request for a property, room, or bed. Assign it, change the status, and keep
            the note. A request does not block the space. Reports cover occupancy, collections,
            arrears, and open work.
          </p>
        </div>
        <dl className="repair-sheet">
          <div>
            <dt>Request</dt>
            <dd>MNT-0001 · The tap drips.</dd>
          </div>
          <div>
            <dt>Priority</dt>
            <dd>High</dd>
          </div>
          <div>
            <dt>Status</dt>
            <dd>Open</dd>
          </div>
          <div>
            <dt>Who can file</dt>
            <dd>Staff, and a resident for their own stay.</dd>
          </div>
        </dl>
      </section>
    </>
  )
}

export function HowItWorks() {
  const steps = [
    ['Open a workspace', 'Create the account, name the workspace, and set the one currency you charge in.'],
    ['Add the rooms and the people', 'Record the property, then the residents and the stays that fill it.'],
    ['Collect rent and track repairs', 'Invoice, record the payment, and keep maintenance requests until they are done.'],
  ]
  return (
    <section className="steps" id="how">
      <h2>How it works</h2>
      <ol>
        {steps.map(([title, text], index) => (
          <li key={title}>
            <span>{index + 1}</span>
            <h3>{title}</h3>
            <p>{text}</p>
          </li>
        ))}
      </ol>
    </section>
  )
}

export function ComingSoon() {
  const items = [
    'Paystack mobile money and card payments that charge the resident',
    'Automatic monthly invoices',
    'Email and SMS reminders',
  ]
  return (
    <section className="soon" aria-labelledby="soon-title">
      <div>
        <p className="kicker">Coming soon</p>
        <h2 id="soon-title">Not in the product yet</h2>
      </div>
      <div>
        <p>
          Today you record a payment after it has happened. These three are named so they are not
          mistaken for something the workspace already does.
        </p>
        <ul>
          {items.map((item) => (
            <li key={item}>
              <span>Coming soon</span>
              {item}
            </li>
          ))}
        </ul>
      </div>
    </section>
  )
}

export function Questions() {
  const items = [
    ['Does recording a card or mobile-money payment charge the resident?', 'No. You record what was paid. Rent It HQ does not take the money from a phone or a card.'],
    ['Can one workspace cover a hostel and an apartment building?', 'Yes. Add each property, then use rooms, units, or beds where you need them.'],
    ['Can a resident sign in?', 'Yes, if you add them as a member. They see their own stay, invoices, and maintenance, not the whole portfolio.'],
    ['What does it cost?', 'There is no public price list on this page. Create a workspace and use the product.'],
  ]
  return (
    <section className="faq" id="questions">
      <h2>Questions owners ask</h2>
      <div>
        {items.map(([q, a]) => (
          <details key={q}>
            <summary>{q}</summary>
            <p>{a}</p>
          </details>
        ))}
      </div>
    </section>
  )
}

export function FinalCta() {
  return (
    <section className="close" aria-labelledby="final-cta">
      <h2 id="final-cta">Start with the building you already run.</h2>
      <p>Add the rooms, the people, and the rent. The rest can wait.</p>
      <Link className="btn btn-light" to="/login?mode=register">
        Get started
      </Link>
    </section>
  )
}

export function LandingFooter() {
  return (
    <footer className="site-footer">
      <p>
        <strong>Rent It HQ</strong>
        Rooms, rent, and repairs for independent hostel and apartment owners.
      </p>
      <nav aria-label="Footer">
        <a href="#house">The house</a>
        <a href="#ledger">The ledger</a>
        <a href="#repairs">Repairs</a>
        <a href="#questions">Questions</a>
        <Link to="/login">Sign in</Link>
        <Link to="/login?mode=register">Get started</Link>
        <Link to="/forgot-password">Forgot password</Link>
      </nav>
    </footer>
  )
}
