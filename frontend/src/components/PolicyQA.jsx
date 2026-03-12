import { useEffect, useRef, useState } from 'react'
import { askQuestion } from '../services/api.js'
import './PolicyQA.css'

const SUGGESTED = [
  'Which policy has better coverage overall?',
  'What are the key premium differences?',
  'Which exclusions are unique to each policy?',
  'Which policy has a lower out-of-pocket maximum?',
]

const CONFIDENCE_META = {
  high:   { label: 'High confidence',   cls: 'conf-high'   },
  medium: { label: 'Medium confidence', cls: 'conf-medium' },
  low:    { label: 'Low confidence',    cls: 'conf-low'    },
}

const SECTION_ICONS = {
  coverage:   '🛡️',
  exclusions: '🚫',
  premiums:   '💰',
  summary:    '📊',
}

export default function PolicyQA({ comparisonId }) {
  const [messages, setMessages] = useState([])
  const [input, setInput]       = useState('')
  const [loading, setLoading]   = useState(false)
  const [error, setError]       = useState(null)
  const bottomRef               = useRef(null)
  const inputRef                = useRef(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, loading])

  async function submit(question) {
    const q = (question ?? input).trim()
    if (!q || loading) return

    setInput('')
    setError(null)
    setMessages((prev) => [...prev, { role: 'user', text: q }])
    setLoading(true)

    try {
      const data = await askQuestion(comparisonId, q)
      setMessages((prev) => [...prev, { role: 'assistant', ...data }])
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
      inputRef.current?.focus()
    }
  }

  function handleKey(e) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      submit()
    }
  }

  return (
    <div className="pqa-card card">
      {/* ── Header ─────────────────────────────────────────────── */}
      <div className="pqa-header">
        <span className="pqa-header-icon">💬</span>
        <div>
          <h3 className="pqa-title">Ask About This Comparison</h3>
          <p className="pqa-subtitle">Ask any question and get an instant AI-powered answer</p>
        </div>
      </div>

      {/* ── Suggested questions (shown only before first message) ─ */}
      {messages.length === 0 && (
        <div className="pqa-suggestions">
          <p className="pqa-suggest-label">Try asking:</p>
          <div className="pqa-suggest-grid">
            {SUGGESTED.map((q) => (
              <button key={q} className="pqa-suggest-btn" onClick={() => submit(q)}>
                {q}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* ── Chat messages ──────────────────────────────────────── */}
      {messages.length > 0 && (
        <div className="pqa-messages">
          {messages.map((msg, i) =>
            msg.role === 'user' ? (
              <UserBubble key={i} text={msg.text} />
            ) : (
              <AssistantBubble key={i} msg={msg} />
            )
          )}
          {loading && <ThinkingBubble />}
          {error && (
            <div className="pqa-error alert alert-error" role="alert">
              {error}
            </div>
          )}
          <div ref={bottomRef} />
        </div>
      )}

      {/* Loading indicator when no messages yet */}
      {messages.length === 0 && loading && (
        <div className="pqa-messages">
          <ThinkingBubble />
          {error && (
            <div className="pqa-error alert alert-error" role="alert">
              {error}
            </div>
          )}
          <div ref={bottomRef} />
        </div>
      )}

      {/* ── Input row ──────────────────────────────────────────── */}
      <div className="pqa-input-row">
        <textarea
          ref={inputRef}
          className="pqa-textarea"
          placeholder="Ask anything about these policies…"
          rows={2}
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKey}
          disabled={loading}
          maxLength={500}
        />
        <button
          className="btn btn-primary pqa-send-btn"
          onClick={() => submit()}
          disabled={loading || input.trim().length < 5}
          aria-label="Send question"
        >
          {loading ? <span className="btn-spinner" /> : '⚡ Ask'}
        </button>
      </div>
      <p className="pqa-hint">Press Enter to send · Shift+Enter for new line</p>
    </div>
  )
}

function UserBubble({ text }) {
  return (
    <div className="pqa-bubble pqa-bubble-user">
      <span className="pqa-bubble-avatar pqa-avatar-user">You</span>
      <div className="pqa-bubble-body">{text}</div>
    </div>
  )
}

function AssistantBubble({ msg }) {
  const conf = CONFIDENCE_META[msg.confidence] ?? null
  return (
    <div className="pqa-bubble pqa-bubble-ai">
      <span className="pqa-bubble-avatar pqa-avatar-ai">AI</span>
      <div className="pqa-bubble-body">
        <p className="pqa-answer-text">{msg.answer}</p>

        <div className="pqa-meta">
          {conf && (
            <span className={`pqa-conf ${conf.cls}`}>{conf.label}</span>
          )}
          {msg.relevant_sections?.length > 0 && (
            <div className="pqa-sections">
              {msg.relevant_sections.map((s) => (
                <span key={s} className="pqa-section-chip">
                  {SECTION_ICONS[s] ?? '📌'} {s}
                </span>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

function ThinkingBubble() {
  return (
    <div className="pqa-bubble pqa-bubble-ai">
      <span className="pqa-bubble-avatar pqa-avatar-ai">AI</span>
      <div className="pqa-bubble-body pqa-thinking">
        <span /><span /><span />
      </div>
    </div>
  )
}
