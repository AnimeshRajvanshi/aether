"use client";

// Renders the committed Stage C factor-attribution artifact (FactorHypothesisSet)
// verbatim — the heat analogue of SourceAttribution. The UI adds layout only.
//
// Honesty invariants enforced structurally here:
//  - headline_finding (incl. against-prior findings), confidence_cap (the
//    MODERATE ceiling explainer), scoring_disclaimer and attribution_boundary
//    are first-class, always-visible blocks;
//  - each factor's ROLE is a visible chip; COUNTER-EVIDENCE factors (urban
//    fabric) get distinct styling so the data-against-the-prior reading cannot
//    be mistaken for a ranked contributor;
//  - every diagnostic renders with its factor (no-fabrication-for-factors made
//    visible: the numbers behind each claim are on screen);
//  - the cited external attribution (WWA/Zachariah) renders in a visually
//    distinct CITED-EXTERNAL block, clearly separated from computed factors.
import { useState } from "react";
import type { FactorHypothesis, FactorHypothesisSet } from "@/lib/types";

const ROLE_LABELS: Record<FactorHypothesis["role"], string> = {
  warming_contributor: "WARMING CONTRIBUTOR",
  severity_framing: "SEVERITY FRAMING",
  counter_evidence: "COUNTER-EVIDENCE",
};

export default function FactorAttribution({ data }: { data: FactorHypothesisSet }) {
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
        <span className="tag">Factor Attribution · Hypothesis Engine v2</span>
        <span className="line" />
      </div>

      {/* first-class headline: ranking-not-apportionment + against-prior findings */}
      <div className="attr-headline">
        <div className="ch">Ranked Contributing Factors · Headline Finding</div>
        <p>{data.headline_finding}</p>
        <p className="attr-cap">{data.confidence_cap}</p>
      </div>

      {/* attribution boundary: what this engine does NOT do */}
      <div className="attr-boundary">
        <div className="ch">Attribution Boundary</div>
        <p>{data.attribution_boundary}</p>
      </div>

      <div className="attr-disclaimer">{data.scoring_disclaimer}</div>

      {data.factors.map((f) => (
        <FactorCard key={f.id} f={f} open={expanded.has(f.id)} onToggle={() => toggle(f.id)} />
      ))}

      {/* CITED EXTERNAL — visually distinct from computed factors */}
      {data.external_published_attribution.length > 0 && (
        <div className="ext-attr">
          <div className="ch">
            Cited External Attribution · NOT computed by Aether · NOT in factor scores
          </div>
          {data.external_published_attribution.map((e, i) => (
            <div key={i} className="ext-attr-item">
              <p>{e.statement}</p>
              <p className="ext-attr-src">{e.source.dataset}</p>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function FactorCard({
  f,
  open,
  onToggle,
}: {
  f: FactorHypothesis;
  open: boolean;
  onToggle: () => void;
}) {
  const capped = f.confidence_rationale.includes("CAPPED");
  const isCounter = f.role === "counter_evidence";
  return (
    <div className={`hypo ${isCounter ? "counter-evidence" : ""}`}>
      <button className="hypo-head" onClick={onToggle}>
        <span className="hypo-rank">{f.id}</span>
        <span className="hypo-name">{f.factor_name}</span>
        <span className={`role-chip role-${f.role}`}>{ROLE_LABELS[f.role]}</span>
        <span className={`attr-tier t-${f.confidence_tier}`}>
          {f.confidence_tier.toUpperCase()}
          {capped ? " · CAPPED" : ""}
        </span>
        <span className="hypo-score">{f.score.toFixed(2)}</span>
        <span className="hypo-caret">{open ? "−" : "+"}</span>
      </button>

      <p className="hypo-claim">{f.claim}</p>
      {/* the rationale is always visible — the cap never collapses away */}
      <p className="hypo-rationale">{f.confidence_rationale}</p>

      {/* diagnostics are the no-fabrication bind: always rendered with the factor */}
      <div className="diag-list">
        {f.diagnostics.map((d) => (
          <div className="diag" key={d.name}>
            <span className="diag-name">{d.name}</span>
            <span className="diag-val">
              {d.value} <span className="u">{d.unit}</span>
            </span>
            <span className="diag-def">{d.definition}</span>
          </div>
        ))}
      </div>

      {open && (
        <div className="hypo-body">
          {f.score_components.length > 0 && (
            <>
              <div className="hypo-sub">Score components (documented heuristic)</div>
              {f.score_components.map((c) => (
                <div className="scomp" key={c.name}>
                  <span className="k">{c.name}</span>
                  <span className="v">
                    {c.value.toFixed(2)} × {c.weight.toFixed(1)}
                  </span>
                  <p>{c.rationale}</p>
                </div>
              ))}
            </>
          )}
          <div className="hypo-sub">Assumptions</div>
          <ul>
            {f.assumptions.map((a, i) => (
              <li key={i}>{a}</li>
            ))}
          </ul>
          <div className="hypo-sub">Counter-considerations</div>
          <ul>
            {f.counter_considerations.map((c, i) => (
              <li key={i}>{c}</li>
            ))}
          </ul>
          <div className="hypo-sub">Falsification</div>
          <p>{f.falsification}</p>
        </div>
      )}
    </div>
  );
}
