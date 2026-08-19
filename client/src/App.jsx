import { useRef, useState } from 'react'
import './App.css'

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

// Steps reflect the real order a resume moves through the pipeline —
// each one only lights up once its data actually exists.
function buildSteps({ resume, hasFile, jobDescription, quality, jobMatch, atsScore }) {
  return [
    { label: 'Upload', done: hasFile },
    { label: 'Quality', done: Boolean(quality) },
    { label: 'Job match', done: Boolean(jobMatch), skip: !jobDescription.trim() && !jobMatch },
    { label: 'ATS score', done: Boolean(atsScore) },
  ]
}

function App() {
  const inputRef = useRef(null)

  const [resumeFile, setResumeFile] = useState(null)
  const [jobDescription, setJobDescription] = useState('')

  // Structured resume returned by /resume-analyze — this is what makes
  // the ATS button (case 3 & 4) skip re-upload and re-parsing entirely.
  const [parsedResume, setParsedResume] = useState(null)

  const [quality, setQuality] = useState(null)
  const [jobMatch, setJobMatch] = useState(null)
  const [atsScore, setAtsScore] = useState(null)

  const [loadingAnalyze, setLoadingAnalyze] = useState(false)
  const [loadingAts, setLoadingAts] = useState(false)
  const [error, setError] = useState('')

  const busy = loadingAnalyze || loadingAts

  const chooseResume = (file) => {
    if (!file) return
    const allowed = [
      'application/pdf',
      'image/png',
      'image/jpeg',
    ]
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
    resetResults()
    if (inputRef.current) inputRef.current.value = ''
  }

  // Case 1 (no job description) and Case 2 (job description present) both
  // go through this single call — the backend decides whether to run
  // job matching based on whether job_description was sent.
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
    } catch (err) {
      setError(err.message || 'Something went wrong while analyzing your resume.')
    } finally {
      setLoadingAnalyze(false)
    }
  }

  // Case 3 (no job description) and Case 4 (job description present) —
  // reuses the already-parsed resume, no file, no re-running quality/OCR.
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
  const steps = buildSteps({ resume: parsedResume, hasFile: Boolean(resumeFile), jobDescription, quality, jobMatch, atsScore })

  return (
    <main className="app-shell">
      <nav className="nav-bar">
        <div className="brand"><span className="brand-mark">R</span><span>ResuMate</span></div>
        <div className="status"><span className="status-dot" /> API: ready</div>
      </nav>

      <section className="intro" id="analyze">
        <div className="eyebrow">AI RESUME ANALYZER <span>→</span> CAREER SIGNAL</div>
        <h1>Make your resume<br /><em>match the moment.</em></h1>
        <p className="intro-copy">Upload a resume, add a target job if you have one, and read your resume the way a recruiter and a screen both would.</p>
      </section>

      <ol className="pipeline" aria-label="Analysis progress">
        {steps.map((step, i) => (
          <li key={step.label} className={`pipeline-step ${step.done ? 'done' : ''} ${step.skip ? 'skip' : ''}`}>
            <span className="pipeline-index">{String(i + 1).padStart(2, '0')}</span>
            <span>{step.label}</span>
          </li>
        ))}
      </ol>

      <section className="workspace">
        <div className="analyzer-card">
          <div className="card-heading">
            <div><span className="section-number">01</span><h2>Your resume</h2></div>
            <span className="required">PDF · PNG · JPG · MAX 5 MB</span>
          </div>
          <button className={`drop-zone ${resumeFile ? 'has-file' : ''}`} type="button" onClick={() => inputRef.current?.click()}>
            <input ref={inputRef} type="file" accept=".pdf,.png,.jpg,.jpeg" hidden onChange={(event) => chooseResume(event.target.files?.[0])} />
            <span className="upload-icon">↑</span>
            {resumeFile ? (
              <>
                <strong>{resumeFile.name}</strong>
                <small>{(resumeFile.size / 1024 / 1024).toFixed(2)} MB · Ready to analyze</small>
              </>
            ) : (
              <>
                <strong>Drop your resume here</strong>
                <small>or click to browse your files</small>
              </>
            )}
          </button>
          {resumeFile && <button className="remove-file" type="button" onClick={reset}>Remove file</button>}

          <div className="field-label">
            <span className="section-number">02</span>
            <label htmlFor="job-description">Add a job description <span>(optional)</span></label>
          </div>
          <textarea
            id="job-description"
            value={jobDescription}
            onChange={(event) => setJobDescription(event.target.value)}
            placeholder="Paste the role you want to tailor for..."
            rows="5"
          />

          <div className="form-footer">
            <span className="privacy">⌁ Your resume stays private</span>
            <button className="analyze-button" type="button" disabled={busy || !resumeFile} onClick={runAnalyze}>
              {loadingAnalyze ? 'Analyzing...' : quality ? 'Re-analyze resume →' : 'Analyze resume →'}
            </button>
          </div>
          {error && <p className="notice">{error}</p>}
        </div>

        <div className="result-card" id="insights">
          <div className="result-top">
            <span className="section-number">03</span>
            <span className="result-label">ANALYSIS OUTPUT</span>
            {score !== null && <span className="live-pill">LIVE RESULT</span>}
          </div>

          {score === null ? (
            <div className="empty-result">
              <div className="empty-glyph">✳</div>
              <h2>Your score will<br /><em>appear here.</em></h2>
              <p>Upload a resume and hit analyze to reveal your quality score, key strengths, and the next best edits.</p>
            </div>
          ) : (
            <>
              <div className="score-result">
                <div className="score-ring" style={{ '--score': `${score * 3.6}deg` }}>
                  <div><strong>{score}</strong><small>QUALITY SCORE</small></div>
                </div>
                <div>
                  <span className="result-kicker">{jobMatch ? 'ROLE MATCH' : 'RESUME HEALTH'}</span>
                  <h2>{score >= 70 ? <>A clearer path<br />to the shortlist.</> : <>A few fixes will<br />sharpen this.</>}</h2>
                  <p>{quality?.llm_fact_analysis?.summary_verdict || 'Your resume has been analyzed. Review the signals below and keep sharpening your story.'}</p>
                </div>
              </div>

              <div className="analysis-details">
                <div className="metric-row"><span>Completeness</span><strong>{toPercent(quality?.completeness_score?.percentage) ?? 0}%</strong></div>
                <div className="metric-row"><span>LLM fact analysis</span><strong>{quality?.llm_fact_analysis?.overall_llm_score ?? 0}%</strong></div>

                {/* {quality?.completeness_score?.breakdown?.length > 0 && (
                  <div className="fact-list">
                    {quality.completeness_score.breakdown.map((item, index) => (
                      <div className="fact-item" key={`${item.check}-${index}`}>
                        <span>{item.passed ? '✓' : '✗'} {item.check}</span>
                        <small>{item.passed ? 'Present' : 'Missing'}{item.points !== undefined ? ` · ${item.points} pts` : ''}</small>
                      </div>
                    ))}
                  </div>
                )} */}

                {quality?.llm_fact_analysis?.facts?.length > 0 && (
                  <div className="fact-list">
                    {quality.llm_fact_analysis.facts.map((fact, index) => (
                      <div className="fact-item" key={`${fact.category || 'fact'}-${index}`}>
                        <span>{fact.category || 'Resume signal'}</span>
                        <small>
                          {fact.rating || 'Reviewed'}{fact.score !== undefined ? ` · ${fact.score}/100` : ''}
                          {fact.justification ? ` — ${fact.justification}` : ''}
                        </small>
                      </div>
                    ))}
                  </div>
                )}

                {jobMatch && (
                  <>
                    <div className="metric-row"><span>Job match</span><strong>Role context applied</strong></div>
                    <div className="fact-list">
                      {typeof jobMatch.keyword_overlap === 'object' && jobMatch.keyword_overlap !== null
                        ? Object.entries(jobMatch.keyword_overlap).map(([key, value]) => (
                          <div className="fact-item" key={key}>
                            <span>{prettyLabel(key)}</span>
                            <small>{Array.isArray(value) ? value.join(', ') : String(value)}</small>
                          </div>
                        ))
                        : jobMatch.keyword_overlap !== undefined && (
                          <div className="fact-item">
                            <span>Keyword overlap</span>
                            <small>{toPercent(jobMatch.keyword_overlap) ?? jobMatch.keyword_overlap}{typeof jobMatch.keyword_overlap === 'number' ? '%' : ''}</small>
                          </div>
                        )}
                      {jobMatch.llm_match_analysis && Object.entries(jobMatch.llm_match_analysis).map(([key, value]) => (
                        <div className="fact-item" key={key}>
                          <span>{prettyLabel(key)}</span>
                          <small>{Array.isArray(value) ? value.join(', ') : String(value)}</small>
                        </div>
                      ))}
                    </div>
                  </>
                )}

                {/* ATS readout — styled like a scan terminal, since this is the one
                    output in the app that mimics what an applicant tracking system
                    actually spits out. */}
                {atsScore && (
                  <div className="ats-readout">
                    <div className="ats-readout-head">
                      <span>ATS SCAN · {atsScore.mode?.toUpperCase() || 'STANDARD'}</span>
                      <strong>{Math.round(atsScore.overall_score ?? 0)}%</strong>
                    </div>
                    <div className="ats-readout-body">
                      {atsScore.breakdown?.map((check, index) => (
                        <div className="ats-line" key={`${check.check}-${index}`}>
                          <span className={check.passed ? 'pass' : 'fail'}>{check.passed ? 'PASS' : 'FAIL'}</span>
                          <span className="ats-line-label">{check.check}</span>
                          <span className="ats-line-score">{check.score}/{check.weight ?? '—'}</span>
                        </div>
                      ))}
                    </div>
                    {atsScore.suggestions?.length > 0 && (
                      <div className="ats-suggestions">
                        <span>Fix next</span>
                        <ul>
                          {atsScore.suggestions.map((suggestion, index) => (
                            <li key={`suggestion-${index}`}>{suggestion}</li>
                          ))}
                        </ul>
                      </div>
                    )}
                  </div>
                )}
              </div>
            </>
          )}

          <div className="result-actions">
            <button className="secondary-button" type="button" disabled={!resumeFile || busy} onClick={runAnalyze}>
              {quality ? 'Re-analyze' : 'Analyze only'}
            </button>
            <button
              className={`ats-button ${atsScore ? 'active' : ''}`}
              type="button"
              disabled={!parsedResume || busy}
              title={!parsedResume ? 'Analyze your resume first' : undefined}
              onClick={runAtsScore}
            >
              {loadingAts ? 'Scoring...' : atsScore ? 'Refresh ATS score →' : 'Get ATS score →'}
            </button>
          </div>
          {!parsedResume && resumeFile && (
            <p className="hint">Analyze your resume first — the ATS score reuses that result instead of re-reading your file.</p>
          )}
        </div>
      </section>

      <section className="signal-strip" id="how-it-works">
        <div><span>01</span><strong>Upload</strong><small>Resume first, always.</small></div>
        <div><span>02</span><strong>Target</strong><small>Optional job context.</small></div>
        <div><span>03</span><strong>Screen</strong><small>See what the ATS sees.</small></div>
        <div className="strip-note">BUILT FOR THE<br /><em>next application.</em></div>
      </section>

      <footer><span>ResuMate / 2026</span><span>Resume intelligence, made useful.</span></footer>
    </main>
  )
}

export default App