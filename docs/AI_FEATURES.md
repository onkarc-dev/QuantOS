# AI Features

AI features are optional and must fail safely when `OPENAI_API_KEY` is not configured. QuantOS must never promise profits and must keep paper/backtest risk warnings visible.

## AI Backtest Explainer

Implemented fallback explains why a strategy likely won/lost, drawdowns, turnover/cost warnings, suggested improvements, risk warnings, sample-size warnings, and overfitting warnings. When an AI key is unavailable, QuantOS returns deterministic heuristic explanations rather than pretending an AI call happened.

## Daily AI Quant Coach foundation

Dashboard card direction: today's strategy status, yesterday's paper summary, risk alerts, repeated mistakes, suggested next action, and an empty-state fallback. The data sources are existing jobs/live-paper/journal data plus strategy health scoring.

## Journal intelligence

Existing journal fields cover trade notes, rule/mistake tags, emotional state, manual override/discipline flags, and R impact. Strategy health scoring can detect repeated mistakes when journal entries are supplied; weekly summaries remain a closed-beta foundation item.
