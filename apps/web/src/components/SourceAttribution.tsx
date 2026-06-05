"use client";

// Renders the committed Sprint 4 attribution artifact (HypothesisSet) in the
// inspector. STRICT rule: every visible string is the artifact's own text,
// rendered verbatim — the UI adds labels/layout only, never interpretation.
//
// Honesty invariants enforced structurally here:
//  - an evidence item's temporal_caveat renders INSIDE that evidence element, so
//    it cannot be shown detached from (or without) the evidence it qualifies;
//  - a hypothesis's confidence_rationale is always visible (collapsed too), and
//    the tier badge shows "· CAPPED" whenever the artifact's own rationale says
//    CAPPED — the cap never collapses to a clean badge;
//  - headline_finding + confidence_cap + scoring_disclaimer are first-class.
import { useState } from "react";
import type { HypothesisSet, ScoreComponent, SourceHypothesis } from "@/lib/types";

export default function SourceAttribution({ data }: { data: HypothesisSet }) {
  const [expanded, setExpanded] = useState<Set<string>>(new Set());
  const toggle = (id: string) =>
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });

  return (
    <div className="panel attr">
      <div className="panel-h">
        <span className="tag">Source Attribution</span>
        <span className="line" />
      </div>

      {/* (c) first-class coverage-ceiling banner — verbatim headline_finding */}
      <div className="attr-headline">
        <div className="ch">Coverage Ceiling · Data-Gap Finding</div>
        <p>{data.headline_finding}</p>
        <p className="attr-cap">{data.confidence_cap}</p>
      </div>

      {/* (d) scoring disclaimer, first appearance — verbatim */}
      <div className="attr-disclaimer">{data.scoring_disclaimer}</div>

      {data.hypotheses.map((h) => (
        <HypothesisCard
          key={h.id}
          h={h}
          open={expanded.has(h.id)}
          onToggle={() => toggle(h.id)}
          scoringDisclaimer={data.scoring_disclaimer}
        />
      ))}
    </div>
  );
}

function tierClass(tier: string): string {
  return `attr-tier t-${tier}`;
}

function HypothesisCard({
  h,
  open,
  onToggle,
  scoringDisclaimer,
}: {
  h: SourceHypothesis;
  open: boolean;
  onToggle: () => void;
  scoringDisclaimer: string;
}) {
  // (b) the cap is derived from the artifact's OWN rationale text, not invented.
  const capped = h.confidence_rationale.includes("CAPPED");
  return (
    <div className={`attr-card ${open ? "open" : ""}`}>
      <button className="attr-card-head" onClick={onToggle} aria-expanded={open}>
        <span className="attr-rank">{h.id}</span>
        <span className="attr-desc">{h.candidate.descriptor}</span>
        <span className={tierClass(h.confidence_tier)}>
          {h.confidence_tier.toUpperCase()}
          {capped && <span className="attr-capped"> · CAPPED</span>}
        </span>
        <span className="attr-chevron">{open ? "▾" : "▸"}</span>
      </button>

      <p className="attr-claim">{h.claim}</p>
      {/* (b) rationale ALWAYS visible (incl. collapsed) — never hidden by a badge */}
      <p className="attr-rationale">{h.confidence_rationale}</p>

      {open && (
        <div className="attr-body">
          {h.candidate.ogim_id !== null && (
            <div className="attr-trace">
              Candidate · {h.candidate.ogim_name} (OGIM_ID {h.candidate.ogim_id}, layer{" "}
              <code>{h.candidate.ogim_layer}</code>)
            </div>
          )}

          <div className="attr-sub">Score components</div>
          <div className="attr-disclaimer small">{scoringDisclaimer}</div>
          {h.score_components.map((c) => (
            <Component key={c.name} c={c} />
          ))}

          <div className="attr-sub">Evidence</div>
          <ul className="attr-evidence">
            {h.evidence.map((e, i) => (
              <li key={i} className="attr-ev">
                <div className="attr-ev-kind">{e.kind}</div>
                <div className="attr-ev-stmt">{e.statement}</div>
                <div className="attr-ev-src">
                  ↳ <code>{e.source.dataset}</code> — {e.source.locator}
                </div>
                {/* (a) temporal_caveat is nested INSIDE the evidence item, so it
                    is inseparable from and cannot be shown without it */}
                {e.temporal_caveat && (
                  <div className="attr-caveat">
                    <span className="attr-caveat-tag">⚠ Temporal caveat</span>
                    {e.temporal_caveat}
                  </div>
                )}
              </li>
            ))}
          </ul>

          <div className="attr-sub">Assumptions</div>
          <ul className="attr-list">
            {h.assumptions.map((a, i) => (
              <li key={i}>{a}</li>
            ))}
          </ul>

          <div className="attr-sub">Counter-considerations</div>
          <ul className="attr-list">
            {h.counter_considerations.map((cc, i) => (
              <li key={i}>{cc}</li>
            ))}
          </ul>

          <div className="attr-sub">Falsification</div>
          <p className="attr-falsify">{h.falsification}</p>
        </div>
      )}
    </div>
  );
}

function Component({ c }: { c: ScoreComponent }) {
  return (
    <div className="attr-comp">
      <div className="attr-comp-top">
        <span className="k">{c.name}</span>
        <span className="v">
          {c.value.toFixed(2)} × {c.weight.toFixed(2)} = {c.contribution.toFixed(3)}
        </span>
      </div>
      <div className="attr-comp-track">
        <div className="attr-comp-fill" style={{ width: `${Math.round(c.value * 100)}%` }} />
      </div>
      <div className="attr-comp-rationale">{c.rationale}</div>
    </div>
  );
}
