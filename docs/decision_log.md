# Decision Log

This file records short rationale for important project decisions. It is append-only history and does not override `docs/project_state.md`.

## 2026-06-12

Type: feat
Decision: Neutralize the system prompt and rewrite all tool descriptions to Anthropic-style 3-4 sentence "when to use" form; re-ground prompt examples to the corpus.
Reason: The prompt biased the model toward calling specific tools (식단 "먼저 호출"), polluting A1/A2/A3 mode comparison; old examples carried fabricated graduation numbers and a false weekend-shuttle claim.
Consequence: tool_policy carries only general principles; graduation example uses 컴퓨터인공지능학부 with no fabricated total credits; shuttle example states weekday-only operation; fetch_cafeteria_menu enum drops 제1학생회관 (food court, no per-day menu).
Links: `examples/cnu-campus/prompts/system.md`, `src/sutra/tools.py` (squash ba7b5ac)

Type: feat
Decision: Prune the calendar corpus to month-level documents only, removing 276 per-event chunks; rewrite the shuttle corpus and drop the geology-dept-sourced notice document.
Reason: Per-event calendar chunks (avg 42 chars) competed with month docs in BM25 and added retrieval noise; the shuttle campus-loop route was contaminated with the internal-loop stop list, and the notice doc misattributed shuttle facts to a 지질환경과학과 source.
Consequence: Index 371 → 94 docs (academic_calendar 50, notices 24, dining 12, graduation 5, shuttle 3). Shuttle now has 3 clean docs (summary + 2 route docs); the notice doc's unique facts (operating period, 2 buses) were absorbed into the summary with provenance labels.
Links: `examples/cnu-campus/scripts/build_calendar_index.py`, `build_shuttle_index.py` (squash 0089526)

Type: feat
Decision: Expand fetch_recent_notices to 5 boards with an optional board param, and implement keyword search as client-side title filtering (not server-side params).
Reason: Live notices are the core of the real-time grading goal; server-side board search parameters proved unreliable on both CMSes (plus board has only the global netpia widget; computer srSearch params return mixed results — verified live by the orchestrator).
Consequence: Boards = 학교 학사공지/새소식, 학부 학사공지/소식/사업단. Omitting board fetches all 5 in parallel and merges by date. keywords filters fetched titles (OR, partial match) with body excerpts for matches and a fan-out to the remaining 3 boards on zero hits.
Links: `src/sutra/tools.py`

Type: feat
Decision: Guard fetch_cafeteria_menu against out-of-range dates by comparing the requested-date menu body against today's; identical bodies are treated as the site's fake-fallback data and blocked.
Reason: The dining site returns today's content for future dates (verified: 6/12, 6/15, 6/16 menu bodies byte-identical), which surfaced as a hallucinated future menu in the tool_only experiment.
Consequence: Requests for non-today dates fetch twice and compare; identical → "신뢰 가능한 데이터 없음" evidence; different → real data. The fixed-week guard was rejected in favor of this always-compare approach (auto-handles Sunday site updates).
Links: `src/sutra/tools.py`

Type: decision
Decision: Adopt "Option A" — the router executes the forced tool even when RAG returns zero evidence; the empty-evidence early return now applies only to non-forced domains. Also remove the smalltalk prefilter and add internal-identifier leak prevention (Korean enum labels + display↔internal mapping + output sanitization).
Reason: The forced-tool branch sat below an empty-RAG early return inherited from the original RAG-first ask() design, so live-only questions could skip the live source the router selected; tool enum values (univ_academic 등) leaked into user answers.
Consequence: dining/notices forced tools fire regardless of RAG; classifier-routed mode is feature-complete and pending a final large experiment to decide grading-path adoption (router vs default). chatbot.sh n_ctx 4096 → 8192; submission requirements include rag/legacy/ui extras (kiwipiepy, bm25s; no torch).
Links: `src/sutra/service.py`, `src/sutra/tools.py`, `scripts/build_submission.py` (squash 7cf7d56)

Type: decision
Decision: Reject the predict_proba confidence gate for OOD routing.
Reason: Calibration probe showed in-scope max-proba (min 0.295) and OOD max-proba (max 0.978) fully overlap; no threshold rejects a majority of OOD without dropping in-scope questions.
Consequence: OOD handling falls back to RAG default behavior; no confidence gate added. (Smalltalk prefilter also removed as a heuristic.)
Links: `src/nlp_term/classify/predict.py` (unchanged; probe only)

## 2026-06-11

Type: feat
Decision: Rebuild dining corpus as per-day documents + an operating-info doc + 6 제1학생회관 food-court corner docs, removing all "운영안함" noise.
Reason: "운영안함" was 63% of slot lines and per-cafeteria-per-day docs broke week-range queries (top_k).
Consequence: 12 dining docs, week queries fit top_k, operating schedule auto-derived from data.
Links: `examples/cnu-campus/scripts/build_dining_index.py`, `src/sutra/dining_format.py`

## 2026-06-11

Type: feat
Decision: Share src/sutra/dining_format.py between the corpus build and the live fetch_cafeteria_menu tool.
Reason: the live tool previously returned raw site text (운영안함 noise, 조식/중식/석식) inconsistent with the cleaned corpus.
Consequence: live cafeteria fetch returns the same clean 아침/점심/저녁 format in real time; rowspan-safe HTML parsing prevents data loss.
Links: `src/sutra/tools.py`, `src/sutra/dining_format.py`

## 2026-06-11

Type: feat
Decision: Add search_knowledge_base tool and ask(mode="tool_only") so RAG competes with live tools on equal footing.
Reason: with RAG always pre-injected, the model called tools only ~0-17% of the time; an experiment is needed to test whether equal footing improves routing.
Consequence: experimental tool_only path added; default ask path unchanged.
Links: `src/sutra/service.py`, `src/sutra/tools.py`

## 2026-06-11

Type: decision
Decision: Hybrid BM25+embedding retrieval at 50/50 weight, no per-domain weighting.
Reason: experiments showed embeddings separate relevant/irrelevant better (AUC 0.889 vs BM25 0.769) and recover colloquial/dining queries, while BM25 wins on notices; per-domain weighting gave +0.0%p.
Consequence: hybrid confirmed at fixed 50/50; per-domain weighting rejected.
Links: `docs/sutra_architecture.md`

## 2026-06-11

Type: decision
Decision: Route RAG-vs-tool deterministically via the Task1 classifier, forcing the tool with tool_choice={"type":"function","function":{"name":...}} for dining and notices; calendar/graduation/shuttle use RAG.
Reason: free model tool-calling is unreliable (0-17%); the server honors named tool_choice forcing (verified) but ignores tool_choice="required".
Consequence: classifier-routed ask mode in progress; thinking-mode was rejected (no tool-call gain, 3.4x latency).
Links: `src/sutra/service.py`, `src/nlp_term/classify/predict.py`

## 2026-06-11

Type: feat
Decision: Chainlit UI gains trace logging (logs/chat_trace.jsonl), feedback actions (👍/👎/💬), source side-panel with score filter (keep docs >= 0.4*top1), streaming, and English interface labels.
Reason: debugging visibility, feedback collection, and answer readability.
Consequence: UI rewritten; logs/ gitignored.
Links: `src/sutra/ui.py`, `src/sutra/tracelog.py`

## 2026-06-09

Type: docs
Decision: Do not restart Task 2 from scratch; simplify the active path from the current codebase.
Reason: Existing source collection, parsing, Qwen runtime, and probe assets are useful; the main issue is policy-heavy front-end logic.
Supersedes: Tool-use and single-tool experiment directions as active runtime plans.
Links: `docs/task2_simplification_direction_2026_06_09.md`

## 2026-06-09

Type: docs
Decision: Use `project_state.md` plus `doc_index.md` as the future-session memory router.
Reason: Chat history and old plans are too large and can conflict; future sessions need a small current-truth entrypoint.
Supersedes: Reading old plan files as implicit current direction.
Links: `docs/project_state.md`, `docs/doc_index.md`

## 2026-06-09

Type: docs
Decision: Mark stale or conflicting plans as `Do Not Execute` until explicitly reactivated.
Reason: Several older plans contain checklist-style implementation instructions that conflict with the current simplification direction.
Supersedes: Treating all files under `docs/superpowers/plans/` as executable.
Links: `docs/doc_index.md`

## 2026-06-09

Type: refactor
Decision: Simplify the Task 2 active path so retrieved evidence is passed to Qwen unless no evidence exists.
Reason: Policy-heavy sufficiency, answer-kind, temporal, and validator gates were suppressing or replacing generated answers before Qwen could use the evidence.
Supersedes: Harness behavior that fail-closed on current-fact, wrong-domain, temporal mismatch, or validator warning cases.
Links: `docs/task2_simplification_direction_2026_06_09.md`, `src/nlp_term/chat/orchestrator.py`

## 2026-06-09

Type: refactor
Decision: Treat the Task 1 route label as a Task 2 retrieval ordering preference instead of a strict evidence filter.
Reason: A strict route filter can erase useful evidence when Task 1 misclassifies an otherwise answerable question.
Consequence: Sufficiently scoring evidence is kept across labels, route-matching evidence is sorted first, and selected evidence remains visible in trace.
Links: `docs/task2_simplification_direction_2026_06_09.md`, `src/nlp_term/chat/orchestrator.py`

## 2026-06-09

Type: refactor
Decision: Adopt the next Task 2 retrieval simplification plan: demote route preference, remove label hints from active scoring, make `min_top_score` diagnostic only, keep aliases as search text, and keep temporal handling in prompt context.
Reason: The current project goal is simple evidence delivery to Qwen. Prior probe runs and reviewer analysis showed that score gates and routing-like boosts can suppress useful evidence or make behavior harder to reason about without proven isolated gains.
Consequence: Future retrieval changes should be small ablations with probe checks, starting with removing score-based fail-closed behavior from evidence pack selection.
Links: `docs/task2_simplification_direction_2026_06_09.md`, `docs/project_state.md`

## 2026-06-09

Type: refactor
Decision: Use a fixed Task 2 evidence pack size of 8 and remove score-positive and temporal pack-size selection rules.
Reason: The project direction is to give Qwen enough clean evidence and let the prompt handle relevance. Prior checks showed routing-like gates and arbitrary score thresholds made behavior harder to reason about without a measured benefit.
Consequence: Retrieved evidence is sorted by diagnostic score and passed through up to the fixed pack size. Date mismatch handling moves to prompt instructions and Qwen generation behavior.
Links: `src/nlp_term/chat/orchestrator.py`, `src/nlp_term/chat/prompts.py`, `docs/task2_simplification_direction_2026_06_09.md`

## 2026-06-09

Type: fix
Decision: Centralize retrieval ordering in `rank_docs` and preserve that order in the Task 2 harness.
Reason: Re-sorting retrieved evidence by score inside the harness undid source-native latest-notice ordering and made the behavior harder to reason about.
Consequence: Bare latest-notice queries put posted date first, topic-specific latest-notice queries put textual relevance first, and the harness no longer performs a second score sort.
Links: `src/nlp_term/retrieve/rank.py`, `src/nlp_term/chat/orchestrator.py`
