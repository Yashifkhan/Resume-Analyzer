import { useRef, useState } from 'react'

const ANALYZE_URL = 'http://127.0.0.1:8000/resume-analyze'
const ATS_URL = 'http://127.0.0.1:8000/resume-ats-score'
const MAX_FILE_SIZE = 5 * 1024 * 1024

function toPercent(value) {
  if (value === undefined || value === null) return null
  const numeric = Number.parseFloat(String(value).replace(/[^0-9.]/g, ''))
  return Number.isNaN(numeric) ? null : Math.min(100, Math.max(0, numeric))
}

function prettyLabel(key) {
  return key.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase())
}

const STEP_META = [
  { id: 1, label: 'Setup', hint: 'Resume + target role' },
  { id: 2, label: 'Analysis', hint: 'Quality & role match' },
  { id: 3, label: 'ATS scan', hint: 'What the screener sees' },
]

function CheckIcon({ className = 'w-3.5 h-3.5' }) {
  return (
    <svg viewBox="0 0 20 20" fill="none" className={className}>
      <path d="M4 10.5l3.5 3.5L16 6" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  )
}

function CrossIcon({ className = 'w-3.5 h-3.5' }) {
  return (
    <svg viewBox="0 0 20 20" fill="none" className={className}>
      <path d="M5 5l10 10M15 5L5 15" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
    </svg>
  )
}

/* ---------- Stepper ---------- */

function Stepper({ step }) {
  return (
    <ol className="flex items-start gap-0 mb-10 sm:mb-14">
      {STEP_META.map((s, i) => {
        const state = step > s.id ? 'done' : step === s.id ? 'active' : 'upcoming'
        return (
          <li key={s.id} className="flex-1 flex items-center">
            <div className="flex flex-col items-start gap-2 min-w-0">
              <div
                className={[
                  'w-8 h-8 rounded-full flex items-center justify-center font-mono text-xs shrink-0 transition-colors',
                  state === 'done' && 'bg-[#C1633A] text-white',
                  state === 'active' && 'bg-[#1E1C18] text-[#F4F0E6] ring-4 ring-[#C1633A]/20',
                  state === 'upcoming' && 'bg-transparent text-[#B7AF9A] ring-1 ring-[#E3DBC8]',
                ].filter(Boolean).join(' ')}
              >
                {state === 'done' ? <CheckIcon /> : String(s.id).padStart(2, '0')}
              </div>
              <div className="hidden sm:block">
                <p className={['text-sm font-semibold leading-tight', state === 'upcoming' ? 'text-[#B7AF9A]' : 'text-[#1E1C18]'].join(' ')}>
                  {s.label}
                </p>
                <p className="text-xs text-[#8A836F] leading-tight">{s.hint}</p>
              </div>
            </div>
            {i < STEP_META.length - 1 && (
              <div className="flex-1 h-px mx-3 sm:mx-4 mt-4">
                <div className={['h-px w-full transition-colors', step > s.id ? 'bg-[#C1633A]' : 'bg-[#E3DBC8]'].join(' ')} />
              </div>
            )}
          </li>
        )
      })}
    </ol>
  )
}

function App() {
  const inputRef = useRef(null)

  const [resumeFile, setResumeFile] = useState(null)
  const [jobDescription, setJobDescription] = useState('')
  const [editingSetup, setEditingSetup] = useState(true)

  // Structured resume returned by /resume-analyze — lets the ATS step
  // skip re-upload and re-parsing entirely.
  const [parsedResume, setParsedResume] = useState(null)

  const [quality, setQuality] = useState(null)
  const [jobMatch, setJobMatch] = useState(null)
  const [atsScore, setAtsScore] = useState(null)

  const [loadingAnalyze, setLoadingAnalyze] = useState(false)
  const [loadingAts, setLoadingAts] = useState(false)
  const [error, setError] = useState('')

  const busy = loadingAnalyze || loadingAts
  // Wizard position is derived from what data actually exists — the same
  // rule that used to only drive the disabled state now drives the whole layout.
  const step = atsScore ? 3 : quality ? 2 : 1

  const chooseResume = (file) => {
    if (!file) return
    const allowed = ['application/pdf', 'image/png', 'image/jpeg']
    if (!allowed.includes(file.type) && !/\.(pdf|png|jpe?g)$/i.test(file.name)) {
      setError('Please choose a PDF, PNG, or JPG resume.')
      return
    }
    if (file.size > MAX_FILE_SIZE) {
      setError('Your resume must be 5 MB or smaller.')
      return
    }
    setResumeFile(file)
    setError('')
    resetResults()
  }

  const resetResults = () => {
    setParsedResume(null)
    setQuality(null)
    setJobMatch(null)
    setAtsScore(null)
  }

  const reset = () => {
    setResumeFile(null)
    setJobDescription('')
    setError('')
    setEditingSetup(true)
    resetResults()
    if (inputRef.current) inputRef.current.value = ''
  }

  // Case 1 (no JD) and Case 2 (JD present) both go through this single call —
  // the backend decides whether to run job matching based on job_description.
  const runAnalyze = async () => {
    if (!resumeFile) {
      setError('Upload your resume before analyzing it.')
      return
    }
    setLoadingAnalyze(true)
    setError('')
    setAtsScore(null)

    const formData = new FormData()
    formData.append('file', resumeFile)
    if (jobDescription.trim()) formData.append('job_description', jobDescription.trim())

    try {
      const response = await fetch(ANALYZE_URL, { method: 'POST', body: formData })
      if (!response.ok) throw new Error(await readError(response))

      const data = await response.json()
      setQuality(data.quality || null)
      setJobMatch(data.job_match || null)
      setParsedResume(data.resume || null)
      setEditingSetup(false) // step 1 collapses, step 2 opens
    } catch (err) {
      setError(err.message || 'Something went wrong while analyzing your resume.')
    } finally {
      setLoadingAnalyze(false)
    }
  }

  // Case 3 (no JD) and Case 4 (JD present) — reuses the already-parsed
  // resume, no file, no re-running quality/OCR.
  const runAtsScore = async () => {
    if (!parsedResume) {
      setError('Analyze your resume first, then request the ATS score.')
      return
    }
    setLoadingAts(true)
    setError('')

    try {
      const response = await fetch(ATS_URL, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          resume: parsedResume,
          job_description: jobDescription.trim() || null,
        }),
      })
      if (!response.ok) throw new Error(await readError(response))

      const data = await response.json()
      setAtsScore(data.ats_score || null)
      // ATS call recomputes job_match too if a JD is present — keep it fresh.
      if (data.job_match) setJobMatch(data.job_match)
    } catch (err) {
      setError(err.message || 'Something went wrong while scoring your resume for ATS.')
    } finally {
      setLoadingAts(false)
    }
  }

  const readError = async (response) => {
    const body = await response.json().catch(() => null)
    const detail = Array.isArray(body?.detail) ? body.detail.map((d) => d.msg).join(', ') : body?.detail
    return detail || `Request failed (${response.status})`
  }

  const score = quality ? Math.round(quality.final_score ?? 0) : null

  return (
    <main className="min-h-screen bg-[#F4F0E6] text-[#1E1C18] font-['Inter',sans-serif]">
      {/* Nav */}
      <nav className="flex items-center justify-between max-w-5xl mx-auto px-6 sm:px-8 py-6">
        <div className="flex items-center gap-2 font-['Space_Grotesk',sans-serif] font-bold text-lg">
          <span className="w-7 h-7 rounded-lg bg-[#1E1C18] text-[#F4F0E6] flex items-center justify-center text-sm">R</span>
          ResuMate
        </div>
        <div className="flex items-center gap-2 text-xs font-mono text-[#6E6858]">
          <span className="w-1.5 h-1.5 rounded-full bg-[#5B7A5A]" />
          API: ready
        </div>
      </nav>

      {/* Intro */}
      <section className="max-w-5xl mx-auto px-6 sm:px-8 pt-4 pb-12">
        <p className="font-mono text-xs tracking-widest text-[#C1633A] uppercase mb-4">
          AI Resume Analyzer <span className="text-[#B7AF9A]">→</span> Career Signal
        </p>
        <h1 className="font-['Space_Grotesk',sans-serif] text-4xl sm:text-5xl font-medium leading-[1.05] mb-4">
          Make your resume<br />
          <em className="not-italic text-[#C1633A]">match the moment.</em>
        </h1>
        <p className="text-[#6E6858] max-w-xl leading-relaxed">
          Upload a resume, add a target role if you have one, and see it the way a recruiter
          and an applicant-tracking system both would — one step at a time.
        </p>
      </section>

      <section className="max-w-5xl mx-auto px-6 sm:px-8 pb-24">
        <Stepper step={step} />

        {error && (
          <div className="mb-6 flex items-start gap-2 rounded-xl border border-[#E4A091]/60 bg-[#FBEDE9] px-4 py-3 text-sm text-[#9C3B2A]">
            <CrossIcon className="w-4 h-4 mt-0.5 shrink-0" />
            {error}
          </div>
        )}

        {/* ---------------- Step 1: Setup ---------------- */}
        {editingSetup ? (
          <div className="bg-white rounded-2xl border border-[#E3DBC8] shadow-[0_1px_0_#E3DBC8] p-6 sm:p-8 mb-6">
            <div className="flex items-center justify-between mb-6">
              <h2 className="font-['Space_Grotesk',sans-serif] text-xl font-medium">Your resume</h2>
              <span className="text-xs font-mono text-[#8A836F]">PDF · PNG · JPG · MAX 5MB</span>
            </div>

            <button
              type="button"
              onClick={() => inputRef.current?.click()}
              className={[
                'w-full flex flex-col items-center justify-center gap-2 rounded-xl border-2 border-dashed px-6 py-10 text-center transition-colors',
                resumeFile ? 'border-[#C1633A] bg-[#FCF3EC]' : 'border-[#E3DBC8] hover:border-[#C1633A]/60 hover:bg-[#FAF7EE]',
              ].join(' ')}
            >
              <input
                ref={inputRef}
                type="file"
                accept=".pdf,.png,.jpg,.jpeg"
                hidden
                onChange={(event) => chooseResume(event.target.files?.[0])}
              />
              <span className="text-2xl text-[#C1633A]">↑</span>
              {resumeFile ? (
                <>
                  <strong className="text-[#1E1C18]">{resumeFile.name}</strong>
                  <small className="text-[#8A836F] text-xs">
                    {(resumeFile.size / 1024 / 1024).toFixed(2)} MB · Ready to analyze
                  </small>
                </>
              ) : (
                <>
                  <strong className="text-[#1E1C18]">Drop your resume here</strong>
                  <small className="text-[#8A836F] text-xs">or click to browse your files</small>
                </>
              )}
            </button>
            {resumeFile && (
              <button
                type="button"
                onClick={reset}
                className="mt-2 text-xs font-mono text-[#8A836F] hover:text-[#C1633A] transition-colors"
              >
                Remove file
              </button>
            )}

            <div className="mt-8 mb-2">
              <label htmlFor="job-description" className="text-sm font-semibold">
                Target role <span className="text-[#8A836F] font-normal">(optional)</span>
              </label>
              <p className="text-xs text-[#8A836F] mt-0.5">
                Adding a job description unlocks role-match scoring in the next step.
              </p>
            </div>
            <textarea
              id="job-description"
              value={jobDescription}
              onChange={(event) => setJobDescription(event.target.value)}
              placeholder="Paste the role you want to tailor for..."
              rows="5"
              className="w-full rounded-xl border border-[#E3DBC8] bg-[#FAF7EE] px-4 py-3 text-sm placeholder:text-[#B7AF9A] focus:outline-none focus:ring-2 focus:ring-[#C1633A]/40 focus:border-[#C1633A] resize-none"
            />

            <div className="flex items-center justify-between mt-6">
              <span className="text-xs text-[#8A836F] flex items-center gap-1.5">
                <span className="text-[#C1633A]">⌁</span> Your resume stays private
              </span>
              <button
                type="button"
                disabled={busy || !resumeFile}
                onClick={runAnalyze}
                className="inline-flex items-center gap-2 rounded-full bg-[#1E1C18] text-[#F4F0E6] px-6 py-3 text-sm font-semibold disabled:opacity-35 disabled:cursor-not-allowed hover:bg-[#C1633A] transition-colors"
              >
                {loadingAnalyze ? 'Analyzing…' : quality ? 'Re-analyze resume' : 'Analyze resume'}
                {!loadingAnalyze && <span>→</span>}
              </button>
            </div>
          </div>
        ) : (
          /* Collapsed step 1 summary, once analysis exists */
          <button
            type="button"
            onClick={() => setEditingSetup(true)}
            className="w-full flex items-center justify-between gap-4 bg-white rounded-2xl border border-[#E3DBC8] px-6 py-4 mb-6 text-left hover:border-[#C1633A]/50 transition-colors"
          >
            <div className="flex items-center gap-3 min-w-0">
              <span className="w-8 h-8 rounded-lg bg-[#FCF3EC] text-[#C1633A] flex items-center justify-center text-sm shrink-0">📄</span>
              <div className="min-w-0">
                <p className="text-sm font-semibold truncate">{resumeFile?.name}</p>
                <p className="text-xs text-[#8A836F] truncate">
                  {jobDescription.trim() ? 'Target role added' : 'No target role added'}
                </p>
              </div>
            </div>
            <span className="text-xs font-mono text-[#C1633A] shrink-0">Edit →</span>
          </button>
        )}

        {/* ---------------- Step 2: Analysis ---------------- */}
        {step >= 2 && quality && (
          <div className="bg-white rounded-2xl border border-[#E3DBC8] p-6 sm:p-8 mb-6">
            <div className="flex items-center justify-between mb-6">
              <h2 className="font-['Space_Grotesk',sans-serif] text-xl font-medium">Analysis output</h2>
              <span className="text-xs font-mono text-[#5B7A5A] bg-[#EDF3EA] rounded-full px-3 py-1">LIVE RESULT</span>
            </div>

            <div className="flex flex-col sm:flex-row items-start sm:items-center gap-6 mb-8">
              <div
                className="relative w-24 h-24 rounded-full shrink-0 flex items-center justify-center"
                style={{ background: `conic-gradient(#C1633A ${score * 3.6}deg, #E3DBC8 0deg)` }}
              >
                <div className="w-[72px] h-[72px] rounded-full bg-white flex flex-col items-center justify-center">
                  <strong className="text-xl font-['Space_Grotesk',sans-serif]">{score}</strong>
                  <small className="text-[9px] font-mono text-[#8A836F] tracking-wide">QUALITY</small>
                </div>
              </div>
              <div>
                <span className="text-xs font-mono text-[#C1633A] uppercase tracking-wide">
                  {jobMatch ? 'Role match' : 'Resume health'}
                </span>
                <h3 className="font-['Space_Grotesk',sans-serif] text-lg font-medium leading-snug mt-1">
                  {score >= 70 ? 'A clearer path to the shortlist.' : 'A few fixes will sharpen this.'}
                </h3>
                <p className="text-sm text-[#6E6858] mt-1 leading-relaxed">
                  {quality?.llm_fact_analysis?.summary_verdict ||
                    'Your resume has been analyzed. Review the signals below and keep sharpening your story.'}
                </p>
              </div>
            </div>

            <div className="grid grid-cols-2 gap-4 mb-6">
              <div className="rounded-xl bg-[#FAF7EE] px-4 py-3">
                <p className="text-xs text-[#8A836F]">Completeness</p>
                <p className="text-lg font-semibold font-mono">{toPercent(quality?.completeness_score?.percentage) ?? 0}%</p>
              </div>
              <div className="rounded-xl bg-[#FAF7EE] px-4 py-3">
                <p className="text-xs text-[#8A836F]">LLM fact analysis</p>
                <p className="text-lg font-semibold font-mono">{quality?.llm_fact_analysis?.overall_llm_score ?? 0}%</p>
              </div>
            </div>

            {quality?.llm_fact_analysis?.facts?.length > 0 && (
              <div className="space-y-2 mb-6">
                {quality.llm_fact_analysis.facts.map((fact, index) => (
                  <div
                    key={`${fact.category || 'fact'}-${index}`}
                    className="flex items-start justify-between gap-4 rounded-lg border border-[#E3DBC8] px-4 py-2.5"
                  >
                    <span className="text-sm font-medium shrink-0">{fact.category || 'Resume signal'}</span>
                    <small className="text-xs text-[#6E6858] text-right leading-relaxed">
                      {fact.rating || 'Reviewed'}
                      {fact.score !== undefined ? ` · ${fact.score}/100` : ''}
                      {fact.justification ? ` — ${fact.justification}` : ''}
                    </small>
                  </div>
                ))}
              </div>
            )}

            {jobMatch && (
              <div className="mb-2">
                <p className="text-sm font-semibold mb-2">Role match signals</p>
                <div className="space-y-2">
                  {typeof jobMatch.keyword_overlap === 'object' && jobMatch.keyword_overlap !== null
                    ? Object.entries(jobMatch.keyword_overlap).map(([key, value]) => (
                        <div key={key} className="flex items-start justify-between gap-4 rounded-lg border border-[#E3DBC8] px-4 py-2.5">
                          <span className="text-sm font-medium shrink-0">{prettyLabel(key)}</span>
                          <small className="text-xs text-[#6E6858] text-right">{Array.isArray(value) ? value.join(', ') : String(value)}</small>
                        </div>
                      ))
                    : jobMatch.keyword_overlap !== undefined && (
                        <div className="flex items-start justify-between gap-4 rounded-lg border border-[#E3DBC8] px-4 py-2.5">
                          <span className="text-sm font-medium">Keyword overlap</span>
                          <small className="text-xs text-[#6E6858]">
                            {toPercent(jobMatch.keyword_overlap) ?? jobMatch.keyword_overlap}
                            {typeof jobMatch.keyword_overlap === 'number' ? '%' : ''}
                          </small>
                        </div>
                      )}
                  {jobMatch.llm_match_analysis &&
                    Object.entries(jobMatch.llm_match_analysis).map(([key, value]) => (
                      <div key={key} className="flex items-start justify-between gap-4 rounded-lg border border-[#E3DBC8] px-4 py-2.5">
                        <span className="text-sm font-medium shrink-0">{prettyLabel(key)}</span>
                        <small className="text-xs text-[#6E6858] text-right">{Array.isArray(value) ? value.join(', ') : String(value)}</small>
                      </div>
                    ))}
                </div>
              </div>
            )}

            {/* Step 2 → Step 3 CTA, only when ATS hasn't been run yet */}
            {!atsScore && (
              <div className="flex items-center justify-between mt-8 pt-6 border-t border-[#E3DBC8]">
                <p className="text-xs text-[#8A836F] max-w-[60%]">
                  Next: see how an applicant-tracking system would parse and score this resume.
                </p>
                <button
                  type="button"
                  disabled={busy}
                  onClick={runAtsScore}
                  className="inline-flex items-center gap-2 rounded-full bg-[#C1633A] text-white px-6 py-3 text-sm font-semibold disabled:opacity-40 hover:bg-[#9C4C2C] transition-colors shrink-0"
                >
                  {loadingAts ? 'Scanning…' : 'Run ATS scan'}
                  {!loadingAts && <span>→</span>}
                </button>
              </div>
            )}
          </div>
        )}

        {/* ---------------- Step 3: ATS scan (signature dark terminal card) ---------------- */}
        {step === 3 && atsScore && (
          <div className="rounded-2xl bg-[#17140F] text-[#F4F0E6] p-6 sm:p-8 font-mono">
            <div className="flex items-center justify-between mb-6">
              <span className="text-xs tracking-widest uppercase text-[#C1633A]">
                ATS scan · {atsScore.mode?.toUpperCase() || 'STANDARD'}
              </span>
              <strong className="text-2xl font-['Space_Grotesk',sans-serif]">{Math.round(atsScore.overall_score ?? 0)}%</strong>
            </div>

            <div className="space-y-1.5 mb-6">
              {atsScore.breakdown?.map((check, index) => (
                <div key={`${check.check}-${index}`} className="flex items-center gap-3 text-sm py-1.5 border-b border-white/5">
                  <span
                    className={[
                      'flex items-center gap-1 shrink-0 text-xs px-2 py-0.5 rounded',
                      check.passed ? 'bg-[#2A3A28] text-[#8FBF8A]' : 'bg-[#3A2420] text-[#E08A7D]',
                    ].join(' ')}
                  >
                    {check.passed ? <CheckIcon className="w-3 h-3" /> : <CrossIcon className="w-3 h-3" />}
                    {check.passed ? 'PASS' : 'FAIL'}
                  </span>
                  <span className="flex-1 text-[#D8D2C2] truncate">{check.check}</span>
                  <span className="text-[#8A836F] shrink-0">
                    {check.score}/{check.weight ?? '—'}
                  </span>
                </div>
              ))}
            </div>

            {atsScore.suggestions?.length > 0 && (
              <div className="border-t border-white/10 pt-4">
                <p className="text-xs uppercase tracking-wide text-[#C1633A] mb-2">Fix next</p>
                <ul className="space-y-1.5">
                  {atsScore.suggestions.map((suggestion, index) => (
                    <li key={`suggestion-${index}`} className="text-sm text-[#D8D2C2] flex gap-2">
                      <span className="text-[#C1633A]">›</span>
                      {suggestion}
                    </li>
                  ))}
                </ul>
              </div>
            )}

            <button
              type="button"
              disabled={busy}
              onClick={runAtsScore}
              className="mt-6 text-xs font-mono text-[#8A836F] hover:text-[#C1633A] transition-colors disabled:opacity-40"
            >
              {loadingAts ? 'Refreshing…' : '↻ Refresh ATS score'}
            </button>
          </div>
        )}

        {/* Empty state before anything is analyzed */}
        {step === 1 && !quality && (
          <div className="rounded-2xl border border-dashed border-[#E3DBC8] px-6 py-10 text-center text-[#8A836F]">
            <div className="text-2xl mb-2">✳</div>
            <p className="text-sm max-w-sm mx-auto">
              Your quality score, role match, and ATS scan will appear here, one step at a time,
              once you analyze a resume.
            </p>
          </div>
        )}
      </section>

      <footer className="max-w-5xl mx-auto px-6 sm:px-8 py-8 border-t border-[#E3DBC8] flex items-center justify-between text-xs text-[#8A836F]">
        <span>ResuMate / 2026</span>
        <span>Resume intelligence, made useful.</span>
      </footer>
    </main>
  )
}

export default App