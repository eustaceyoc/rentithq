export function AuthPanelArt() {
  return (
    <svg
      className="auth-art"
      viewBox="0 0 480 640"
      preserveAspectRatio="xMidYMax meet"
      aria-hidden="true"
      focusable="false"
    >
      <g
        fill="none"
        stroke="var(--cream)"
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      >
        <path d="M48 588 H432" opacity="0.7" />
        <path d="M72 372 H148 V588 H72 Z" />
        <path d="M148 214 H404 V588 H148 Z" />
        <path d="M136 214 H416" />
        <path d="M148 196 H404" opacity="0.65" />
      </g>

      <g stroke="var(--cream)" strokeWidth="1.5">
        <rect x="90" y="408" width="28" height="36" fill="var(--amber)" />
        <rect x="90" y="484" width="28" height="36" fill="none" />
        <path d="M104 408 V444" opacity="0.4" />
        <path d="M104 484 V520" opacity="0.65" />

        <rect x="176" y="246" width="40" height="48" fill="var(--amber)" />
        <rect x="256" y="246" width="40" height="48" fill="none" />
        <rect x="336" y="246" width="40" height="48" fill="none" />
        <rect x="176" y="316" width="40" height="48" fill="none" />
        <rect x="256" y="316" width="40" height="48" fill="none" />
        <rect x="336" y="316" width="40" height="48" fill="var(--amber)" />
        <rect x="176" y="386" width="40" height="48" fill="none" />
        <rect x="256" y="386" width="40" height="48" fill="var(--amber)" />
        <rect x="336" y="386" width="40" height="48" fill="none" />
        <rect x="176" y="456" width="40" height="48" fill="none" />
        <rect x="336" y="456" width="40" height="48" fill="var(--amber)" />

        <path d="M276 246 V294 M356 246 V294 M196 316 V364 M276 316 V364 M196 386 V434 M356 386 V434 M196 456 V504" opacity="0.65" />
        <path d="M196 246 V294 M356 316 V364 M276 386 V434 M356 456 V504" opacity="0.4" />
      </g>

      <g stroke="var(--cream)" strokeWidth="1.5">
        <rect x="250" y="500" width="52" height="88" fill="var(--clay)" />
        <circle cx="288" cy="546" r="2.5" fill="var(--cream)" stroke="none" />
      </g>
    </svg>
  )
}
