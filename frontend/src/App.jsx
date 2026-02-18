import { useEffect, useMemo, useState } from 'react'

const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL || '').replace(/\/$/, '')

const CARD_ACCENTS = [
  { bg: 'bg-sky-50',     border: 'border-sky-200' },
  { bg: 'bg-violet-50',  border: 'border-violet-200' },
  { bg: 'bg-amber-50',   border: 'border-amber-200' },
  { bg: 'bg-rose-50',    border: 'border-rose-200' },
  { bg: 'bg-teal-50',    border: 'border-teal-200' },
  { bg: 'bg-indigo-50',  border: 'border-indigo-200' },
]

function fmt(price) {
  return typeof price === 'number'
    ? `₹${price.toLocaleString('en-IN', { maximumFractionDigits: 0 })}`
    : 'N/A'
}

const initialState = {
  title: '',
  price: null,
  image_url: null,
  thumbnail_images: [],
  source: '',
  marketplace: '',
  tracker_url: null,
  alternatives_count: 0,
  alternatives: [],
  status: '',
  error: null,
}

export default function App() {
  const [url, setUrl] = useState('')
  const [result, setResult] = useState(initialState)
  const [loading, setLoading] = useState(false)
  const [errorToast, setErrorToast] = useState('')
  const [activeImg, setActiveImg] = useState(null)
  const [sort, setSort] = useState('asc')
  const [history, setHistory] = useState([])
  const [historyOpen, setHistoryOpen] = useState(false)
  const [copied, setCopied] = useState(false)

  const hasResult = useMemo(() => result.status === 'Success', [result.status])

  // Product thumbnails from the API (actual product images, not logos)
  const thumbnails = useMemo(() => {
    if (result.thumbnail_images && result.thumbnail_images.length > 0)
      return result.thumbnail_images
    return result.image_url ? [result.image_url] : []
  }, [result.thumbnail_images, result.image_url])

  const displayImg = activeImg ?? result.image_url

  const sortedAlternatives = useMemo(() => {
    const withPrice = [...result.alternatives].filter(a => typeof a.price === 'number')
    const noPrice = result.alternatives.filter(a => typeof a.price !== 'number')
    withPrice.sort((a, b) => sort === 'asc' ? a.price - b.price : b.price - a.price)
    return [...withPrice, ...noPrice]
  }, [result.alternatives, sort])

  const { bestPrice, worstPrice, maxPrice } = useMemo(() => {
    const prices = result.alternatives.map(a => a.price).filter(p => typeof p === 'number')
    return {
      bestPrice: prices.length ? Math.min(...prices) : null,
      worstPrice: prices.length ? Math.max(...prices) : null,
      maxPrice: prices.length ? Math.max(...prices) : 1,
    }
  }, [result.alternatives])

  const bestOffer = useMemo(() => {
    const pricedOffers = result.alternatives.filter(offer => typeof offer.price === 'number')
    if (pricedOffers.length === 0) return null
    return pricedOffers.reduce((minOffer, offer) => (offer.price < minOffer.price ? offer : minOffer), pricedOffers[0])
  }, [result.alternatives])

  const spreadAmount = bestPrice !== null && worstPrice !== null ? worstPrice - bestPrice : 0
  const spreadPercent = bestPrice !== null && worstPrice !== null && worstPrice > 0
    ? Math.round((spreadAmount / worstPrice) * 100)
    : 0

  const volatilityLabel = spreadPercent <= 8 ? 'Stable' : spreadPercent <= 20 ? 'Moderate' : 'Volatile'

  const pricedCount = result.alternatives.filter(offer => typeof offer.price === 'number').length
  const totalCount = result.alternatives_count || result.alternatives.length || 1
  const completenessRatio = Math.min(pricedCount / totalCount, 1)
  const sellerFactor = Math.min(pricedCount / 6, 1) * 35
  const spreadFactor = (1 - Math.min(spreadPercent / 100, 1)) * 40
  const completenessFactor = completenessRatio * 25
  const confidenceScore = Math.max(0, Math.min(100, Math.round(sellerFactor + spreadFactor + completenessFactor)))

  const recommendationText = !bestOffer
    ? 'Need more price data before recommending a seller.'
    : spreadPercent >= 25
      ? `Wait — price spread is high. Best current option is ${bestOffer.seller || 'the lowest priced seller'}.`
      : spreadPercent >= 10
        ? `Buy from ${bestOffer.seller || 'the lowest priced seller'} now, but recheck prices later.`
        : `Buy from ${bestOffer.seller || 'the lowest priced seller'} now — prices look stable.`

  // Feature 7: auto-fetch if ?url= param present
  useEffect(() => {
    const params = new URLSearchParams(window.location.search)
    const sharedUrl = params.get('url')
    if (!sharedUrl) return
    setUrl(sharedUrl)
    doFetch(sharedUrl)
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  async function doFetch(targetUrl) {
    setLoading(true)
    setErrorToast('')
    setResult(initialState)
    setActiveImg(null)
    try {
      const response = await fetch(`${API_BASE_URL}/api/v1/compare`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ url: targetUrl }),
      })
      const data = await response.json().catch(() => ({}))
      if (!response.ok) {
        const safeError =
          data?.error ||
          (Array.isArray(data?.details) && data.details.length > 0
            ? String(data.details[0]?.msg)
            : 'Scrape failed. Please verify the URL and try again.')
        setErrorToast(safeError)
        return
      }
      setResult({
        title: data.title,
        price: data.price,
        image_url: data.image_url,
        thumbnail_images: Array.isArray(data.thumbnail_images) ? data.thumbnail_images : [],
        source: data.source,
        marketplace: data.marketplace,
        tracker_url: data.tracker_url,
        alternatives_count: data.alternatives_count ?? 0,
        alternatives: Array.isArray(data.alternatives) ? data.alternatives : [],
        status: data.status,
        error: data.error,
      })
    } catch {
      setErrorToast('Network error while contacting backend. Please retry.')
    } finally {
      setLoading(false)
    }
  }

  // Feature 5: fetch history
  async function fetchHistory() {
    try {
      const res = await fetch(`${API_BASE_URL}/api/v1/history`)
      if (res.ok) setHistory(await res.json())
    } catch { /* silent */ }
  }

  function handleToggleHistory() {
    if (!historyOpen) fetchHistory()
    setHistoryOpen(h => !h)
  }

  // Feature 4: copy product URL
  function handleCopyLink() {
    if (!url.trim()) return
    navigator.clipboard.writeText(url.trim())
      .then(() => {
        setCopied(true)
        setTimeout(() => setCopied(false), 2000)
      })
      .catch(() => setErrorToast('Unable to copy. Please copy the URL manually.'))
  }

  // Feature 7: copy shareable link with ?url= param
  function handleShare() {
    if (!url.trim()) return
    const shareUrl = `${window.location.origin}${window.location.pathname}?url=${encodeURIComponent(url.trim())}`
    navigator.clipboard.writeText(shareUrl)
      .then(() => {
        setCopied('share')
        setTimeout(() => setCopied(false), 2500)
      })
      .catch(() => setErrorToast('Unable to copy share link. Please copy from address bar.'))
  }

  async function onSubmit(event) {
    event.preventDefault()
    if (!url.trim()) { setErrorToast('Please enter a product URL.'); return }

    await doFetch(url.trim())
  }

  return (
    <div className="min-h-screen bg-white">

      {/* ── Hero Header ───────────────────────────────────────── */}
      <header style={{ background: '#1a5a8b' }}>
        <div className="mx-auto max-w-screen-2xl px-10 py-14 flex flex-col items-start gap-3">
          <h1 className="text-7xl font-black tracking-tight text-white leading-none">
            BETTER PRICE
          </h1>
          <p className="text-lg font-light text-white/80 max-w-xl">
            Instantly compare prices across sellers and find the best deal.
          </p>
        </div>
      </header>
      {/* ── How-to banner ─────────────────────────────────────── */}
      <div className="mx-auto max-w-screen-2xl px-8 pt-6">
        <div className="rounded-2xl border border-sky-200 bg-white px-6 py-4 shadow-sm">
          <h2 className="mb-1 text-sm font-bold uppercase tracking-wide" style={{ color: '#01487e' }}>
            How it works
          </h2>
          <ol className="flex flex-col gap-1 text-sm text-slate-600 sm:flex-row sm:gap-8">
            <li><span className="font-semibold" style={{ color: '#01487e' }}>1.</span> Copy a product URL from Amazon or Flipkart.</li>
            <li><span className="font-semibold" style={{ color: '#01487e' }}>2.</span> Paste it below and click <strong>Compare</strong>.</li>
            <li><span className="font-semibold" style={{ color: '#01487e' }}>3.</span> View the best prices across all sellers instantly.</li>
          </ol>
        </div>
      </div>

      <main className="mx-auto max-w-screen-2xl px-8 py-6 space-y-6">

        {/* ── Search card ───────────────────────────────────────── */}
        <section className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
          <div className="flex items-center justify-between mb-1">
            <h2 className="text-xl font-bold text-slate-900">Compare Product Price</h2>
            {/* Feature 5: history toggle */}
            <button
              type="button"
              onClick={handleToggleHistory}
              className="flex items-center gap-1.5 rounded-xl border border-slate-200 px-3 py-1.5 text-xs font-semibold text-slate-600 transition hover:border-[#01487e] hover:text-[#01487e]"
            >
              <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
              {historyOpen ? 'Hide History' : 'History'}
            </button>
          </div>
          <p className="mb-5 text-sm text-slate-500">
            Paste an Amazon <span className="font-medium text-slate-700">(amazon.in / amazon.com)</span> or
            Flipkart URL. Unsupported domains are blocked automatically.
          </p>

          <form className="flex flex-col gap-3 sm:flex-row" onSubmit={onSubmit}>
            <input
              type="url"
              placeholder="https://www.amazon.in/dp/B0..."
              className="w-full rounded-xl border border-slate-300 px-4 py-3 text-sm shadow-inner outline-none transition focus:border-[#01487e] focus:ring-2 focus:ring-[#01487e]/20"
              value={url}
              onChange={(e) => setUrl(e.target.value)}
            />
            <div className="flex shrink-0 gap-2">
              {/* Feature 4: copy URL */}
              <button type="button" onClick={handleCopyLink} title="Copy product URL"
                className="rounded-xl border border-slate-300 px-3 py-3 text-slate-500 transition hover:border-[#01487e] hover:text-[#01487e]">
                {copied === true
                  ? <svg className="h-4 w-4 text-emerald-500" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}><path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" /></svg>
                  : <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}><path strokeLinecap="round" strokeLinejoin="round" d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" /></svg>}
              </button>
              {/* Feature 7: share link */}
              <button type="button" onClick={handleShare} title="Copy shareable result link"
                className="rounded-xl border border-slate-300 px-3 py-3 text-slate-500 transition hover:border-[#01487e] hover:text-[#01487e]">
                {copied === 'share'
                  ? <svg className="h-4 w-4 text-emerald-500" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}><path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" /></svg>
                  : <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}><path strokeLinecap="round" strokeLinejoin="round" d="M8.684 13.342C8.886 12.938 9 12.482 9 12c0-.482-.114-.938-.316-1.342m0 2.684a3 3 0 110-2.684m0 2.684l6.632 3.316m-6.632-6l6.632-3.316m0 0a3 3 0 105.367-2.684 3 3 0 00-5.367 2.684zm0 9.316a3 3 0 105.368 2.684 3 3 0 00-5.368-2.684z" /></svg>}
              </button>
              <button
                type="submit"
                disabled={loading}
                className="rounded-xl px-7 py-3 text-sm font-bold text-white shadow transition hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-60"
                style={{ background: '#01487e' }}
              >
                {loading ? 'Checking…' : 'Compare'}
              </button>
            </div>
          </form>

          {/* Feature 5: history panel */}
          {historyOpen && (
            <div className="mt-5 rounded-2xl border border-slate-200 bg-slate-50 p-4">
              <p className="mb-3 text-xs font-bold uppercase tracking-widest text-slate-400">Recent Searches</p>
              {history.length === 0 ? (
                <p className="text-sm text-slate-400">No history yet.</p>
              ) : (
                <ul className="flex flex-col gap-2">
                  {history.map((h) => (
                    <li key={h.id} className="flex items-center justify-between gap-3 rounded-xl border border-slate-100 bg-white px-4 py-2 shadow-sm">
                      <div className="min-w-0">
                        <p className="max-w-2xl truncate text-xs font-semibold text-slate-700">{h.url}</p>
                        <p className="text-xs text-slate-400">
                          {h.marketplace} · {h.detected_price ? fmt(h.detected_price) : 'N/A'} · {new Date(h.timestamp).toLocaleString()}
                        </p>
                      </div>
                      <button type="button" onClick={() => { setUrl(h.url); setHistoryOpen(false) }}
                        className="shrink-0 rounded-lg px-3 py-1 text-xs font-bold text-white" style={{ background: '#01487e' }}>
                        Reuse
                      </button>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          )}

          {loading && (
            <div className="mt-4 flex items-center gap-3 rounded-xl border border-sky-200 bg-sky-50 px-4 py-3 text-sm text-sky-700">
              <svg className="h-4 w-4 animate-spin" viewBox="0 0 24 24" fill="none">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
              </svg>
              Scraping live data — this may take a few seconds…
            </div>
          )}
        </section>

        {/* ── LEFT / RIGHT product panel ────────────────────────── */}
        {hasResult && (
          <section className="animate-fadein rounded-2xl border border-slate-200 bg-white shadow-sm overflow-hidden">

            {/* top badge bar */}
            <div className="flex items-center gap-2 border-b border-slate-100 px-6 py-3">
              <span className="inline-block h-2.5 w-2.5 rounded-full bg-emerald-400" />
              <span className="text-sm font-bold text-slate-700">Live Result</span>
              <span
                className="ml-auto rounded-full px-3 py-0.5 text-xs font-semibold capitalize text-white"
                style={{ background: '#01487e' }}
              >
                {result.marketplace}
              </span>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-[430px_minmax(0,1fr)] xl:grid-cols-[500px_minmax(0,1fr)]">

              {/* ── LEFT: image + thumbnails ─────────────────────── */}
              <div className="flex flex-col gap-3 border-b border-slate-100 p-4 md:border-b-0 md:border-r">

                {/* Main image */}
                <div className="flex aspect-square w-full items-center justify-center overflow-hidden rounded-2xl border border-slate-200 bg-slate-50">
                  {displayImg ? (
                    <img
                      src={displayImg}
                      alt={result.title}
                      className="h-full w-full object-contain p-3 transition-all duration-300"
                    />
                  ) : (
                    <svg className="h-16 w-16 text-slate-300" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
                    </svg>
                  )}
                </div>

                {/* Thumbnail bento grid — short cards, click to preview large image */}
                {thumbnails.length > 1 && (
                  <div className="grid grid-cols-3 gap-2">
                    {thumbnails.map((src, i) => {
                      const isActive = (activeImg ?? result.image_url) === src
                      return (
                        <button
                          key={`${src}-${i}`}
                          onClick={() => setActiveImg(src)}
                          className={`group relative h-20 overflow-hidden rounded-lg border-2 bg-slate-50 transition-all duration-200 hover:scale-[1.02] hover:shadow-md ${isActive ? 'border-[#01487e] shadow-md ring-2 ring-[#01487e]/30 scale-[1.02]' : 'border-slate-200 shadow-sm'}`}
                        >
                          <img src={src} alt={`Thumbnail ${i + 1}`} className="h-full w-full object-contain p-1.5 transition-transform duration-200 group-hover:scale-105" />
                          {isActive && (
                            <span className="absolute bottom-1 right-1 flex h-4 w-4 items-center justify-center rounded-full text-white text-[9px] font-bold shadow-md" style={{ background: '#01487e' }}>✓</span>
                          )}
                        </button>
                      )
                    })}
                  </div>
                )}
              </div>

              {/* ── RIGHT: title + all prices ────────────────────── */}
              <div className="min-w-0 flex flex-col gap-4 p-5 md:p-6">

                {/* Title */}
                <div>
                  <p className="text-xl font-bold leading-snug text-slate-900">{result.title}</p>
                </div>

                {/* Feature 1: Best Deal + Smart Recommendation */}
                {bestOffer && bestPrice !== null && worstPrice !== null && (
                  <div className="rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-3">
                    <div className="flex items-start gap-4">
                      <div className="flex h-10 w-10 shrink-0 items-center justify-center overflow-hidden rounded-full border border-emerald-200 bg-emerald-500 text-base text-white shadow-sm">
                        {bestOffer.logo_url ? (
                          <img src={bestOffer.logo_url} alt={bestOffer.seller || 'Best seller'} className="h-full w-full object-contain p-2 bg-white" />
                        ) : (
                          '🏆'
                        )}
                      </div>
                      <div className="min-w-0 flex-1">
                        <p className="text-base font-extrabold text-emerald-800">Best deal: {fmt(bestPrice)}</p>
                        <p className="text-xs font-semibold text-emerald-700">
                          {bestOffer.seller || 'Best seller'} · Source: {result.source || 'buyhatke'}
                        </p>
                        <p className="mt-1 text-xs text-emerald-700">
                          Save {fmt(spreadAmount)} ({spreadPercent}%) vs the highest listed price
                        </p>
                      </div>
                    </div>

                    <div className="mt-3 grid grid-cols-1 gap-2.5 sm:grid-cols-3">
                      <div className="rounded-lg border border-emerald-200 bg-white/90 px-3 py-2">
                        <p className="text-[11px] font-bold uppercase tracking-wide text-emerald-500">Smart Buy Recommendation</p>
                        <p className="mt-1 text-xs font-semibold text-slate-700">{recommendationText}</p>
                      </div>
                      <div className="rounded-lg border border-emerald-200 bg-white/90 px-3 py-2">
                        <p className="text-[11px] font-bold uppercase tracking-wide text-emerald-500">Deal Confidence Score</p>
                        <p className="mt-1 text-lg font-extrabold text-[#01487e]">{confidenceScore}/100</p>
                      </div>
                      <div className="rounded-lg border border-emerald-200 bg-white/90 px-3 py-2">
                        <p className="text-[11px] font-bold uppercase tracking-wide text-emerald-500">Price Volatility</p>
                        <p className={`mt-1 text-sm font-extrabold ${volatilityLabel === 'Stable' ? 'text-emerald-600' : volatilityLabel === 'Moderate' ? 'text-amber-600' : 'text-rose-600'}`}>
                          {volatilityLabel}
                        </p>
                      </div>
                    </div>
                  </div>
                )}

                {/* Feature 2: Price Bar Chart */}
                {(() => {
                  const BAR_SOLIDS = [
                    '#10b981',
                    '#6366f1',
                    '#f59e0b',
                    '#ec4899',
                    '#14b8a6',
                    '#8b5cf6',
                    '#f43f5e',
                    '#0ea5e9',
                  ]
                  const priceOffers = sortedAlternatives.filter(a => typeof a.price === 'number')
                  if (priceOffers.length <= 1) return null
                  return (
                    <div className="rounded-2xl border border-slate-200 bg-slate-50 px-5 py-5 shadow-sm">
                      <p className="mb-4 text-xs font-black uppercase tracking-[0.2em] text-slate-400">Price Comparison</p>
                      <div className="flex flex-col gap-3.5">
                        {priceOffers.map((offer, i) => {
                          const isBest = offer.price === bestPrice
                          const pct = Math.max(8, Math.round((offer.price / maxPrice) * 100))
                          const color = BAR_SOLIDS[i % BAR_SOLIDS.length]
                          return (
                            <div key={i} className="flex items-center gap-4">
                              <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full text-[10px] font-black text-white" style={{ background: color }}>
                                {i + 1}
                              </span>
                              <p className="w-28 shrink-0 truncate text-sm font-semibold text-slate-700">{offer.seller || '?'}</p>
                              <div className="relative flex-1 h-3.5 rounded-full bg-slate-200 overflow-hidden">
                                <div
                                  className="h-full rounded-full transition-all duration-700"
                                  style={{ width: `${pct}%`, background: color }}
                                />
                              </div>
                              <p className="w-24 shrink-0 whitespace-nowrap text-right text-sm font-black tabular-nums" style={{ color: isBest ? '#10b981' : '#334155' }}>
                                {fmt(offer.price)}
                              </p>
                              {isBest && (
                                <span className="shrink-0 rounded-full px-2 py-0.5 text-[10px] font-black text-white" style={{ background: '#10b981' }}>
                                  BEST
                                </span>
                              )}
                            </div>
                          )
                        })}
                      </div>
                    </div>
                  )
                })()}

              </div>
            </div>

            {/* Centered main price */}
            {result.price !== null && (
              <div className="border-t border-slate-100 px-4 py-5 md:px-6 md:py-6">
                <div className="mx-auto w-full max-w-2xl rounded-2xl border border-sky-200 bg-sky-50 px-6 py-5 text-center shadow-sm">
                  <p className="text-[11px] font-black uppercase tracking-[0.2em] text-slate-500">Current Price</p>
                  <p className="mt-1 text-5xl font-extrabold" style={{ color: '#01487e' }}>
                    {fmt(result.price)}
                  </p>
                </div>
              </div>
            )}

            {/* Centered seller prices */}
            {result.alternatives.length > 0 && (
              <div className="border-t border-slate-100 px-4 py-5 md:px-6 md:py-6">
                <div className="mx-auto w-full max-w-4xl rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
                  <div className="mb-4 flex items-center justify-between gap-3">
                    <span className="text-xs font-bold uppercase tracking-widest text-slate-400">
                      {result.alternatives_count || result.alternatives.length} sellers
                    </span>
                    <div className="flex items-center gap-2">
                      <span className="text-xs font-semibold text-slate-400">Sort:</span>
                      <button type="button" onClick={() => setSort('asc')}
                        className={`rounded-lg px-3 py-1 text-xs font-bold transition ${sort === 'asc' ? 'text-white shadow' : 'border border-slate-300 text-slate-500 hover:border-[#01487e]'}`}
                        style={sort === 'asc' ? { background: '#01487e' } : {}}>
                        Lowest First
                      </button>
                      <button type="button" onClick={() => setSort('desc')}
                        className={`rounded-lg px-3 py-1 text-xs font-bold transition ${sort === 'desc' ? 'text-white shadow' : 'border border-slate-300 text-slate-500 hover:border-[#01487e]'}`}
                        style={sort === 'desc' ? { background: '#01487e' } : {}}>
                        Highest First
                      </button>
                    </div>
                  </div>

                  <div className="flex flex-col gap-3">
                    {sortedAlternatives.map((offer, index) => {
                      const accent = CARD_ACCENTS[index % CARD_ACCENTS.length]
                      const isBest = typeof offer.price === 'number' && offer.price === bestPrice
                      const diff = typeof offer.price === 'number' && bestPrice !== null
                        ? offer.price - bestPrice : null
                      return (
                        <div
                          key={`${offer.seller}-${index}`}
                          className={`animate-fadein flex items-center justify-between rounded-xl border px-4 py-3 transition hover:shadow-md ${isBest ? 'border-emerald-300 bg-emerald-50' : `${accent.border} ${accent.bg}`}`}
                          style={{ animationDelay: `${index * 50}ms` }}
                        >
                          <div className="flex min-w-0 items-center gap-3">
                            <div className="flex h-12 w-12 shrink-0 items-center justify-center overflow-hidden rounded-lg border border-white bg-white shadow-sm">
                              {offer.logo_url
                                ? <img src={offer.logo_url} alt={offer.seller} className="h-full w-full object-contain p-1" />
                                : <span className="text-sm font-bold text-slate-400">{offer.seller?.slice(0, 1) || '?'}</span>}
                            </div>
                            <div className="min-w-0">
                              <div className="flex items-center gap-2">
                                <p className="truncate text-sm font-bold text-slate-900">{offer.seller || 'Unknown'}</p>
                                {isBest && (
                                  <span className="shrink-0 rounded-full bg-emerald-500 px-2 py-0.5 text-[9px] font-bold text-white">Best Deal</span>
                                )}
                              </div>
                              <div className="flex items-center gap-2">
                                <p className="whitespace-nowrap text-base font-extrabold text-green-700 tabular-nums">
                                  {typeof offer.price === 'number' ? fmt(offer.price) : offer.price_display || 'N/A'}
                                </p>
                                {diff !== null && diff > 0 && (
                                  <span className="whitespace-nowrap text-xs font-semibold text-slate-400">+{fmt(diff)} vs best</span>
                                )}
                              </div>
                            </div>
                          </div>
                          {offer.link ? (
                            <a href={offer.link} target="_blank" rel="noreferrer"
                              className="ml-3 shrink-0 rounded-lg px-4 py-2 text-xs font-bold text-white shadow transition hover:opacity-90"
                              style={{ background: '#01487e' }}>
                              Buy Now
                            </a>
                          ) : (
                            <span className="ml-3 shrink-0 rounded-lg border border-slate-300 px-4 py-2 text-xs font-semibold text-slate-400">
                              No Link
                            </span>
                          )}
                        </div>
                      )
                    })}
                  </div>
                </div>
              </div>
            )}
          </section>
        )}
      </main>

      {/* ── Footer ──────────────────────────────────────────────── */}
      <footer className="mt-10 border-t border-slate-200 bg-white py-5 text-center text-xs text-slate-400">
        PricePulse &mdash; Assessment Build &nbsp;·&nbsp; Live data via BuyHatke
      </footer>

      {/* ── Share copied toast ─────────────────────────────────── */}
      {copied === 'share' && (
        <div className="fixed bottom-5 right-5 z-50 animate-fadein rounded-2xl border border-emerald-200 bg-emerald-50 px-5 py-3 text-sm font-semibold text-emerald-700 shadow-xl">
          Shareable link copied to clipboard!
        </div>
      )}

      {/* ── Error toast ─────────────────────────────────────────── */}
      {errorToast && (
        <div className="fixed right-5 top-5 z-50 max-w-sm animate-fadein rounded-2xl border border-red-200 bg-red-50 px-5 py-4 shadow-xl">
          <div className="flex items-start gap-3">
            <svg className="mt-0.5 h-4 w-4 shrink-0 text-red-500" viewBox="0 0 20 20" fill="currentColor">
              <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm-.75-11.25a.75.75 0 011.5 0v4a.75.75 0 01-1.5 0v-4zm.75 7a1 1 0 100-2 1 1 0 000 2z" clipRule="evenodd" />
            </svg>
            <p className="flex-1 text-sm text-red-700">{errorToast}</p>
            <button type="button" onClick={() => setErrorToast('')} className="text-xs font-bold text-red-500 hover:text-red-700">✕</button>
          </div>
        </div>
      )}
    </div>
  )
}
