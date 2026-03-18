import { useRef, useState } from 'react'
import './FileUploader.css'

const MAX_MB = 5
const MAX_BYTES = MAX_MB * 1024 * 1024

function DropZone({ label, file, onFile, disabled }) {
  const inputRef = useRef(null)
  const [dragging, setDragging] = useState(false)

  function validate(f) {
    if (!f) return null
    if (f.type !== 'text/plain' && !f.name.toLowerCase().endsWith('.txt')) {
      return 'Only plain-text (.txt) files are accepted.'
    }
    if (f.size > MAX_BYTES) {
      return `File exceeds the ${MAX_MB} MB limit.`
    }
    return null
  }

  function handleFile(f) {
    const err = validate(f)
    if (err) { alert(err); return }
    onFile(f)
  }

  function onDrop(e) {
    e.preventDefault()
    setDragging(false)
    if (disabled) return
    const f = e.dataTransfer.files[0]
    if (f) handleFile(f)
  }

  function onInputChange(e) {
    const f = e.target.files[0]
    if (f) handleFile(f)
    // reset so the same file can be re-selected later
    e.target.value = ''
  }

  return (
    <div
      className={`drop-zone ${dragging ? 'dragging' : ''} ${file ? 'has-file' : ''} ${disabled ? 'disabled' : ''}`}
      onClick={() => !disabled && inputRef.current?.click()}
      onDragOver={(e) => { e.preventDefault(); if (!disabled) setDragging(true) }}
      onDragLeave={() => setDragging(false)}
      onDrop={onDrop}
      role="button"
      tabIndex={0}
      aria-label={label}
      onKeyDown={(e) => e.key === 'Enter' && !disabled && inputRef.current?.click()}
    >
      <input
        ref={inputRef}
        type="file"
        accept=".txt,text/plain"
        style={{ display: 'none' }}
        onChange={onInputChange}
        disabled={disabled}
      />

      {file ? (
        <div className="file-info">
          <div className="file-icon">📄</div>
          <div className="file-meta">
            <span className="file-name">{file.name}</span>
            <span className="file-size">{(file.size / 1024).toFixed(1)} KB</span>
          </div>
          {!disabled && (
            <button
              className="remove-btn"
              onClick={(e) => { e.stopPropagation(); onFile(null) }}
              aria-label="Remove file"
            >
              ✕
            </button>
          )}
        </div>
      ) : (
        <div className="drop-placeholder">
          <span className="upload-icon">📂</span>
          <p className="drop-label">{label}</p>
          <p className="drop-hint">Drag & drop or click to browse</p>
          <p className="drop-hint">TXT only · max {MAX_MB} MB</p>
        </div>
      )}
    </div>
  )
}

export default function FileUploader({ onCompare, loading }) {
  const [file1, setFile1] = useState(null)
  const [file2, setFile2] = useState(null)
  const [progress, setProgress] = useState(0)
  const [llmProvider, setLlmProvider] = useState(() => {
    const saved = window.localStorage.getItem('pasta-llm-provider')
    return saved === 'ollama' ? 'ollama' : 'groq'
  })

  const canSubmit = file1 && file2 && !loading

  function handleSubmit(e) {
    e.preventDefault()
    if (!canSubmit) return
    window.localStorage.setItem('pasta-llm-provider', llmProvider)
    onCompare(file1, file2, setProgress, llmProvider)
  }

  return (
    <form className="uploader-form" onSubmit={handleSubmit}>
      <div className="provider-row">
        <label htmlFor="llm-provider" className="provider-label">AI Provider</label>
        <select
          id="llm-provider"
          className="provider-select"
          value={llmProvider}
          onChange={(e) => setLlmProvider(e.target.value)}
          disabled={loading}
        >
          <option value="groq">Groq (cloud)</option>
          <option value="ollama">Ollama (local)</option>
        </select>
      </div>

      <div className="drop-row">
        <div className="drop-col">
          <p className="policy-label policy1-label">Policy 1</p>
          <DropZone
            label="Upload first policy TXT"
            file={file1}
            onFile={setFile1}
            disabled={loading}
          />
        </div>

        <div className="vs-divider">VS</div>

        <div className="drop-col">
          <p className="policy-label policy2-label">Policy 2</p>
          <DropZone
            label="Upload second policy TXT"
            file={file2}
            onFile={setFile2}
            disabled={loading}
          />
        </div>
      </div>

      {loading && (
        <div className="upload-progress">
          <div className="progress-bar-wrap">
            <div className="progress-bar" style={{ width: `${progress}%` }} />
          </div>
          <p className="progress-text">
            {progress < 100 ? `Uploading… ${progress}%` : 'Analysing policies…'}
          </p>
        </div>
      )}

      <button
        type="submit"
        className="btn btn-primary compare-btn"
        disabled={!canSubmit}
      >
        {loading ? (
          <>
            <span className="btn-spinner" />
            Comparing…
          </>
        ) : (
          '⚡ Compare Policies'
        )}
      </button>
    </form>
  )
}
