import { useState } from 'react'
import { Link } from 'react-router-dom'

const NAV = [
  { href: '#properties', label: 'Properties' },
  { href: '#people', label: 'Residents' },
  { href: '#ledger', label: 'Billing' },
  { href: '#repairs', label: 'Maintenance' },
  { href: '#reports', label: 'Reports' },
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
      <p className="eyebrow">Property management for hostels and apartments</p>
      <div className="hero-grid">
        <h1>One workspace for the house, the rent, and the repairs.</h1>
        <div>
          <p className="lede">
            Rent It HQ is the desk your staff work from. Properties, rooms, residents, bookings,
            invoices, and maintenance stay in the same place. It is not a public listing site.
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
      <figure className="product-shot">
        <img src="/product/dashboard.png" alt="The Rent It HQ dashboard for a demo workspace, showing occupancy, outstanding rent, and upcoming move-outs." />
        <figcaption>The dashboard in a demo workspace. These figures are sample records, not a customer result.</figcaption>
      </figure>
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
  const shots = [
    {
      id: 'properties',
      kicker: 'Properties and rooms',
      title: 'Each building, then the rooms and beds inside it',
      text: 'A property holds optional buildings and floors. Rooms can have beds. A whole unit does not. Mark a space unavailable when it cannot be let.',
      src: '/product/properties.png',
      alt: 'The properties screen listing Harbour House and Ridge Court.',
    },
    {
      id: 'people',
      kicker: 'Residents and bookings',
      title: 'Who is in, and which bed is held',
      text: 'Residents, reservations, and tenancies live on the same desk. The end date is the last occupied day. The space is free the next day.',
      src: '/product/residents.png',
      alt: 'The residents screen in the demo workspace.',
    },
    {
      id: 'ledger',
      kicker: 'Billing and payments',
      title: 'Invoices you can read, and payments you record',
      text: 'Issue an invoice, then record cash, a bank transfer, mobile money, or a card payment. Recording it does not charge a phone or a card. A resident can start a Paystack test checkout from their own invoice.',
      src: '/product/invoices.png',
      alt: 'Invoices marked paid, overdue, and outstanding, in Ghana cedis.',
    },
    {
      id: 'repairs',
      kicker: 'Maintenance',
      title: 'Repairs that stay on the list',
      text: 'File a request, set the priority, and assign it. The history of each status stays with the request. A request does not block the space.',
      src: '/product/maintenance.png',
      alt: 'The maintenance list with priority and status.',
    },
    {
      id: 'reports',
      kicker: 'Reports',
      title: 'Occupancy, arrears, and what was collected',
      text: 'Reports use the same records the staff can already open. Download the same view as a spreadsheet.',
      src: '/product/reports.png',
      alt: 'The reports screen with occupancy and a CSV download.',
    },
  ]
  return (
    <>
      {shots.map((shot) => (
        <section className="split" id={shot.id} key={shot.id}>
          <div className="split-copy">
            <p className="kicker">{shot.kicker}</p>
            <h2>{shot.title}</h2>
            <p>{shot.text}</p>
          </div>
          <figure className="product-shot">
            <img src={shot.src} alt={shot.alt} />
          </figure>
        </section>
      ))}
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
    'SMS notices. Email is the notice that can send today.',
    'Android and iOS store apps.',
    'A clock for recurring invoices. Staff can run the command; nothing in the app starts it by itself.',
  ]
  return (
    <section className="soon" aria-labelledby="soon-title">
      <div>
        <p className="kicker">Coming soon</p>
        <h2 id="soon-title">Not in the product yet</h2>
      </div>
      <div>
        <p>
          Staff still record cash and transfers by hand. A resident can start a Paystack test
          checkout on their own invoice. These three are named so they are not mistaken for
          something the workspace already does.
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
        Property management for independent hostel and apartment owners.
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
