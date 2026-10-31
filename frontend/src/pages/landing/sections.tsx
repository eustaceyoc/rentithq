import { useState } from 'react'
import { Link } from 'react-router-dom'
import { ProductWindow } from './ProductWindow'

const NAV = [
  { href: '#product', label: 'Product' },
  { href: '#features', label: 'Features' },
  { href: '#how', label: 'How it works' },
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
          <span className="brand-mark" aria-hidden="true">
            R
          </span>
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
          <Link className="btn btn-ghost" to="/login">
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
    <section className="hero" id="product">
      <div className="hero-copy">
        <p className="eyebrow">For independent hostel and apartment owners</p>
        <h1>Rooms, rent, and repairs in one place.</h1>
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
      <ProductWindow
        workspace="Harbour House"
        active="Dashboard"
        label="Sample dashboard in a workspace. These figures are an example screen, not a customer result."
      >
        <p className="mock-title">Dashboard</p>
        <div className="mock-kpis">
          <div className="lead">
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
    {
      title: 'Hostel owners',
      text: 'Beds in a shared room, and a whole room when someone takes it.',
    },
    {
      title: 'Apartment owners',
      text: 'Whole units, with rooms only where the building actually has them.',
    },
    {
      title: 'A small staff',
      text: 'Owner, property manager, finance, maintenance, and a resident sign-in for their own stay.',
    },
  ]
  return (
    <section className="built-for" aria-labelledby="built-for-title">
      <h2 id="built-for-title">Built for</h2>
      <ul>
        {people.map((item) => (
          <li key={item.title}>
            <h3>{item.title}</h3>
            <p>{item.text}</p>
          </li>
        ))}
      </ul>
    </section>
  )
}

export function FeatureShows() {
  return (
    <div className="shows" id="features">
      <section className="show">
        <div>
          <h2>Who is in, and which bed is free</h2>
          <p>
            Record each property, then rooms, whole units, or beds. A reservation blocks that
            space until the last occupied day. The next day it is free.
          </p>
          <ul>
            <li>More than one property in the same workspace</li>
            <li>Residents, reservations, agreements, and stays</li>
            <li>A date check for what is free to book</li>
          </ul>
        </div>
        <ProductWindow
          workspace="Harbour House"
          active="Residents"
          label="Sample resident list."
        >
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
      <section className="show show-flip">
        <div>
          <h2>What is still owed</h2>
          <p>
            Issue an invoice, then record cash, mobile money, or a card payment against it.
            Recording the payment does not charge a phone or a card.
          </p>
          <ul>
            <li>Invoices, allocations, refunds, and voids</li>
            <li>A receipt you can print</li>
            <li>Arrears for a date you choose</li>
          </ul>
        </div>
        <ProductWindow
          workspace="Harbour House"
          active="Billing"
          label="Sample invoice list. Recording a payment does not charge the resident."
        >
          <p className="mock-title">Invoices</p>
          <table className="mock-table">
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
        </ProductWindow>
      </section>
      <section className="show">
        <div>
          <h2>Repairs that stay on the list</h2>
          <p>
            File a request for a property, room, or bed. Assign it, change the status, and keep
            the note. A request does not block the space.
          </p>
          <ul>
            <li>Priority and status, with a history of updates</li>
            <li>Residents can file a request for their own stay</li>
            <li>Reports for occupancy, collections, arrears, and open work</li>
          </ul>
        </div>
        <ProductWindow
          workspace="Harbour House"
          active="Maintenance"
          label="Sample maintenance request."
        >
          <p className="mock-title">Maintenance</p>
          <table className="mock-table">
            <thead>
              <tr>
                <th>Request</th>
                <th>Priority</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td>MNT-0001 · The tap drips.</td>
                <td>High</td>
                <td>Open</td>
              </tr>
            </tbody>
          </table>
        </ProductWindow>
      </section>
    </div>
  )
}

export function HowItWorks() {
  const steps = [
    {
      title: 'Open a workspace',
      text: 'Create the account, name the workspace, and set the one currency you charge in.',
    },
    {
      title: 'Add the rooms and the people',
      text: 'Record the property, then the residents and the stays that fill it.',
    },
    {
      title: 'Collect rent and track repairs',
      text: 'Invoice, record the payment, and keep maintenance requests until they are done.',
    },
  ]
  return (
    <section className="section" id="how">
      <h2>How it works</h2>
      <ol className="steps">
        {steps.map((step, index) => (
          <li key={step.title}>
            <span className="step-no">{index + 1}</span>
            <h3>{step.title}</h3>
            <p>{step.text}</p>
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
    <section className="section soon" aria-labelledby="soon-title">
      <div>
        <p className="eyebrow">Coming soon</p>
        <h2 id="soon-title">Not in the product yet</h2>
        <p className="section-intro">
          Today you record a payment after it has happened. These three are named so they are not
          mistaken for something the workspace already does.
        </p>
      </div>
      <ul>
        {items.map((item) => (
          <li key={item}>
            <span>Coming soon</span>
            {item}
          </li>
        ))}
      </ul>
    </section>
  )
}

export function Questions() {
  const items = [
    {
      q: 'Does recording a card or mobile-money payment charge the resident?',
      a: 'No. You record what was paid. Rent It HQ does not take the money from a phone or a card.',
    },
    {
      q: 'Can one workspace cover a hostel and an apartment building?',
      a: 'Yes. Add each property, then use rooms, units, or beds where you need them.',
    },
    {
      q: 'Can a resident sign in?',
      a: 'Yes, if you add them as a member. They see their own stay, invoices, and maintenance, not the whole portfolio.',
    },
    {
      q: 'What does it cost?',
      a: 'There is no public price list on this page. Create a workspace and use the product.',
    },
  ]
  return (
    <section className="section" id="questions">
      <h2>Questions owners ask</h2>
      <div className="faq">
        {items.map((item) => (
          <details key={item.q}>
            <summary>{item.q}</summary>
            <p>{item.a}</p>
          </details>
        ))}
      </div>
    </section>
  )
}

export function FinalCta() {
  return (
    <section className="cta-band" aria-labelledby="final-cta">
      <div>
        <h2 id="final-cta">Start with the building you already run.</h2>
        <p>Add the rooms, the people, and the rent. The rest can wait.</p>
      </div>
      <Link className="btn btn-primary" to="/login?mode=register">
        Get started
      </Link>
    </section>
  )
}

export function LandingFooter() {
  return (
    <footer className="site-footer">
      <div>
        <strong>Rent It HQ</strong>
        <p>Rooms, rent, and repairs for independent hostel and apartment owners.</p>
      </div>
      <nav aria-label="Footer">
        <a href="#product">Product</a>
        <a href="#features">Features</a>
        <a href="#how">How it works</a>
        <a href="#questions">Questions</a>
        <Link to="/login">Sign in</Link>
        <Link to="/login?mode=register">Get started</Link>
        <Link to="/forgot-password">Forgot password</Link>
      </nav>
    </footer>
  )
}
