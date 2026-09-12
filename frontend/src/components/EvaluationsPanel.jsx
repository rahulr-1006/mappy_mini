const PERCENT = (value) => `${Math.round((value ?? 0) * 100)}%`
const SECONDS = (ms) => `${((ms ?? 0) / 1000).toFixed(1)}s`
const TOKENS = (n) => (n ?? 0).toLocaleString()
const USD = (n) => `$${(n ?? 0).toFixed(4)}`

function StatCard({ label, value, hint }) {
  return (
    <div className="stat-card">
      <div className="stat-value">{value}</div>
      <div className="stat-label">{label}</div>
      {hint && <div className="stat-hint">{hint}</div>}
    </div>
  )
}

export function EvaluationsPanel({
  records,
  summary,
  model,
  running,
  onRunSuite,
}) {
  const costs = summary?.estimated_hosted_cost_totals ?? {}
  const ordered = [...records].reverse()

  return (
    <>
      <div className="panel">
        <h2>Evaluation summary</h2>

        {summary?.generations === 0 ? (
          <p className="empty-state">
            No generations recorded yet — generate requirements or a diagram,
            or run the evaluation suite below.
          </p>
        ) : (
          <div className="stat-grid">
            <StatCard label="Generations" value={summary?.generations ?? 0} />
            <StatCard
              label="Total tokens"
              value={TOKENS(summary?.total_tokens)}
              hint={`${TOKENS(summary?.total_prompt_tokens)} in / ${TOKENS(summary?.total_completion_tokens)} out`}
            />
            <StatCard
              label="First-pass rate"
              value={PERCENT(summary?.avg_first_pass_rate)}
              hint="passed rules with no repair"
            />
            <StatCard
              label="Final success rate"
              value={PERCENT(summary?.avg_success_rate)}
              hint="valid after self-correction"
            />
            <StatCard
              label="Avg generation time"
              value={SECONDS(summary?.avg_duration_ms)}
              hint={`${SECONDS(summary?.total_duration_ms)} total`}
            />
            <StatCard
              label="Actual spend"
              value={USD(summary?.actual_spend_usd)}
              hint="real hosted-API cost to date"
            />
          </div>
        )}
      </div>

      {Object.keys(summary?.by_provider ?? {}).length > 1 && (
        <div className="panel">
          <h2>Local vs hosted</h2>
          <p className="empty-state">
            Same prompts, same rule checks, same metrics — run against local
            Ollama and the hosted Anthropic API.
          </p>
          <div className="table-scroll">
            <table className="eval-table">
              <thead>
                <tr>
                  <th>Provider</th>
                  <th>Runs</th>
                  <th>Tokens</th>
                  <th>First pass</th>
                  <th>Avg time</th>
                  <th>Actual spend</th>
                </tr>
              </thead>
              <tbody>
                {Object.entries(summary.by_provider).map(([name, b]) => (
                  <tr key={name}>
                    <td>
                      <span className={`badge${name === 'anthropic' ? ' badge-accent' : ''}`}>
                        {name}
                      </span>
                    </td>
                    <td>{b.generations}</td>
                    <td>{TOKENS(b.tokens)}</td>
                    <td>{PERCENT(b.avg_first_pass_rate)}</td>
                    <td>{SECONDS(b.avg_duration_ms)}</td>
                    <td>{b.spend_usd > 0 ? USD(b.spend_usd) : 'free (local)'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      <div className="panel">
        <h2>Cost if run on a hosted API</h2>
        <p className="empty-state">
          Local inference has no per-token cost. These are the same token
          volumes priced against published hosted-model rates, for comparison.
        </p>
        <ul className="cost-list">
          {Object.entries(costs).map(([name, value]) => (
            <li key={name}>
              <span>{name}</span>
              <strong>{USD(value)}</strong>
            </li>
          ))}
        </ul>
      </div>

      <div className="panel">
        <h2>Benchmark suite</h2>
        <p className="empty-state">
          Runs a fixed golden set of 6 prompts (3 requirements, 3 diagrams)
          against <code>{model}</code> so prompt or model changes can be
          compared on the same inputs. This makes 6 real generations and takes
          several minutes.
        </p>
        <button type="button" onClick={onRunSuite} disabled={running}>
          {running ? 'Running suite…' : 'Run evaluation suite'}
        </button>
      </div>

      <div className="panel">
        <h2>Generation log ({records.length})</h2>
        {records.length === 0 ? (
          <p className="empty-state">Nothing recorded yet.</p>
        ) : (
          <div className="table-scroll">
            <table className="eval-table">
              <thead>
                <tr>
                  <th>Time</th>
                  <th>Task</th>
                  <th>Model</th>
                  <th>Source</th>
                  <th>Calls</th>
                  <th>In</th>
                  <th>Out</th>
                  <th>First pass</th>
                  <th>Success</th>
                  <th>Duration</th>
                </tr>
              </thead>
              <tbody>
                {ordered.map((r, i) => (
                  <tr key={i}>
                    <td>{new Date(r.timestamp).toLocaleTimeString()}</td>
                    <td>{r.task}</td>
                    <td>{r.model}</td>
                    <td>
                      <span className={`badge${r.source === 'suite' ? ' badge-accent' : ''}`}>
                        {r.source}
                      </span>
                    </td>
                    <td>{r.llm_calls}</td>
                    <td>{TOKENS(r.prompt_tokens)}</td>
                    <td>{TOKENS(r.completion_tokens)}</td>
                    <td>{PERCENT(r.first_pass_rate)}</td>
                    <td>{PERCENT(r.success_rate)}</td>
                    <td>{SECONDS(r.duration_ms)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </>
  )
}
