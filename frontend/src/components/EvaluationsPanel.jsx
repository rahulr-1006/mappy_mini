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
  judgeResult,
  judging,
  onJudge,
  headToHead,
  headToHeadRunning,
  onRunHeadToHead,
}) {
  const costs = summary?.estimated_hosted_cost_totals ?? {}
  const ordered = [...records].reverse()

  return (
    <>
      <div className="panel">
        <h2>Evaluation summary</h2>

        {summary?.generations === 0 ? (
          <p className="empty-state">
            No generations recorded yet. Generate requirements or a diagram,
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
            Same prompts, same rule checks, same metrics, run against local
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
        <div className="diagram-panel-heading">
          <h2>Semantic review</h2>
          <button type="button" className="link-button" onClick={onJudge} disabled={judging}>
            {judging ? 'Reviewing…' : 'Run semantic review'}
          </button>
        </div>
        <p className="empty-state">
          The rule engine is lexical. It checks how a requirement is written,
          not what it says. A second model scores the same requirements on
          criteria a regex cannot reach, so the gap between the two is
          measurable rather than assumed.
        </p>

        {judgeResult?.summary?.reviewed > 0 && (
          <>
            <div className="stat-grid">
              <div className="stat-card">
                <div className="stat-value">{judgeResult.summary.mean_score}</div>
                <div className="stat-label">Mean score</div>
                <div className="stat-hint">out of 5, across all criteria</div>
              </div>
              <div className="stat-card">
                <div className="stat-value">{judgeResult.summary.flagged.length}</div>
                <div className="stat-label">Flagged</div>
                <div className="stat-hint">scored below 3.5</div>
              </div>
              <div className="stat-card">
                <div className="stat-value">
                  {judgeResult.summary.passed_rules_but_judge_flagged}
                </div>
                <div className="stat-label">Rule-engine blind spots</div>
                <div className="stat-hint">passed the rules, failed review</div>
              </div>
            </div>

            <ul className="cost-list">
              {Object.entries(judgeResult.summary.criteria_means).map(([k, v]) => (
                <li key={k}>
                  <span>{k.replace(/_/g, ' ')}</span>
                  <strong>{v}</strong>
                </li>
              ))}
            </ul>

            <ul className="requirement-list" style={{ marginTop: 16 }}>
              {judgeResult.reviews.map((r) => (
                <li key={r.index} className="requirement-card">
                  <div className="requirement-header">
                    <span className={`badge${r.mean < 3.5 ? ' badge-warn' : ' badge-accent'}`}>
                      {r.mean} / 5
                    </span>
                    <span className="badge">{r.name}</span>
                  </div>
                  <p className="requirement-text">{r.comment}</p>
                </li>
              ))}
            </ul>
          </>
        )}
      </div>

      <div className="panel">
        <div className="diagram-panel-heading">
          <div>
            <h2>Head to head</h2>
            <p className="panel-subtitle">
              One prompt, one rulebook, every model in turn. The provider
              table above is assembled from whatever is in the log, which
              compares runs that were never controlled against each other.
              This runs them back to back so the numbers are comparable by
              construction.
            </p>
          </div>
          <button type="button" onClick={onRunHeadToHead} disabled={headToHeadRunning}>
            {headToHeadRunning ? 'Running…' : 'Run head to head'}
          </button>
        </div>

        {headToHead ? (
          <>
            <p className="status-line">
              Prompt: <code>{headToHead.prompt}</code>
            </p>
            <div className="table-scroll">
              <table className="eval-table">
                <thead>
                  <tr>
                    <th>Model</th>
                    <th>Requirements</th>
                    <th>First pass</th>
                    <th>Valid after repair</th>
                    <th>Calls</th>
                    <th>Latency</th>
                    <th>Cost</th>
                  </tr>
                </thead>
                <tbody>
                  {headToHead.rows.map((r) => (
                    <tr key={r.model}>
                      <td>
                        <span className={`badge${r.provider === 'ollama' ? '' : ' badge-accent'}`}>
                          {r.model}
                        </span>
                      </td>
                      <td>{r.items}</td>
                      <td>{PERCENT(r.first_pass_rate)}</td>
                      <td>{PERCENT(r.success_rate)}</td>
                      <td>{r.llm_calls}</td>
                      <td>{SECONDS(r.duration_ms)}</td>
                      <td>{r.actual_cost_usd ? `$${r.actual_cost_usd.toFixed(4)}` : 'free'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <p className="panel-subtitle">
              Read the first two columns together. Output volume and
              first-pass conformance differ sharply between models; what the
              repair loop buys is that both land in the same place.
            </p>
          </>
        ) : (
          <p className="empty-state">
            Not run yet. Makes one real generation per model, a few seconds
            on a hosted model, up to a minute locally.
          </p>
        )}
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
