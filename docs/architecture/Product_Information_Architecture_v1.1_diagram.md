# Product Information Architecture v1.1 — Diagrams

**Status:** Companion to `Product_Information_Architecture_v1.1.md`

## 1. All inputs converge on one Research Universe

```mermaid
flowchart TD
    Q[Free-form market/theme question]
    S[Selected seeded universe]
    M[Manually entered Starting Companies]
    C[Company Analysis<br/>Research market and competition]
    V[Saved Research Universe revision]
    A[Curator-authored corpus]

    SC[Starting Companies<br/>source-neutral input contract]
    RCE[RCE Suggestions]
    REVIEW[Research Universe Review<br/>one matcher, comparison, and disposition workflow]
    RU[Approved Research Universe<br/>one object and explicit version]
    ANALYZE[Analyze every constituent]
    OPP[Opportunities]

    Q --> RCE
    Q --> SC
    S --> SC
    M --> SC
    C --> SC
    C --> Q
    V --> SC
    A --> SC
    SC --> REVIEW
    RCE --> REVIEW
    REVIEW --> RU
    RU --> ANALYZE
    ANALYZE --> OPP

    classDef input fill:#e8f1ff,stroke:#3568a8,color:#10243e;
    classDef contract fill:#e8f7ed,stroke:#3c7a4c,color:#15351d;
    class Q,S,M,C,V,A input;
    class RU contract;
```

Source origin is provenance. It does not select a different review engine or Research Universe type.

## 2. Canonical candidate and membership lifecycle

```mermaid
flowchart LR
    START[Starting Companies]
    SUGGEST[RCE Suggestions]
    MATCH[Ticker-first identity matching<br/>exact name fallback]
    CAND[UniverseCandidate<br/>all source records retained]
    AGREEMENT{In both corpora?}
    AUTO[Included automatically]
    PENDING[Pending]
    USER{Explicit review action}
    INCLUDE[Included]
    REJECT[Rejected]
    DEFER[Deferred / remains pending]
    APPROVE[Approve Research Universe<br/>unresolved suggestions allowed]
    MEMBERS[Approved membership<br/>automatic agreements + explicit inclusions]
    HISTORY[Version history<br/>pending and rejected remain auditable]

    START --> MATCH
    SUGGEST --> MATCH
    MATCH --> CAND
    CAND --> AGREEMENT
    AGREEMENT -->|Yes| AUTO
    AGREEMENT -->|No| PENDING
    PENDING --> USER
    USER --> INCLUDE
    USER --> REJECT
    USER --> DEFER
    AUTO --> APPROVE
    INCLUDE --> APPROVE
    PENDING -. may remain unresolved .-> APPROVE
    REJECT -. retained .-> HISTORY
    DEFER -. retained .-> HISTORY
    PENDING -. retained .-> HISTORY
    APPROVE --> MEMBERS
    APPROVE --> HISTORY
```

## 3. Role overlays on one review capability

```mermaid
flowchart TB
    MODEL[Canonical Research Universe model]
    SERVICE[Shared Research Universe review service]
    RENDERER[Shared company-list renderer]

    GENERAL[General-user mode]
    CURATOR[Curator mode]

    GVIEW[Topic, Starting Companies, RCE Suggestions,<br/>include, reject, pending, Analyze Company,<br/>approved summary]
    CVIEW[Same core review + authored provenance,<br/>evaluation, publication, certification,<br/>privileged governance]

    MODEL --> SERVICE --> RENDERER
    RENDERER --> GENERAL --> GVIEW
    RENDERER --> CURATOR --> CVIEW

    classDef shared fill:#e8f7ed,stroke:#3c7a4c,color:#15351d;
    class MODEL,SERVICE,RENDERER shared;
```

Curator is a permission context, not a separate universe or CRUD implementation.

## 4. Company-to-market workflow

```mermaid
flowchart LR
    COMPANY[Company]
    ANALYSIS[Company Analysis]
    ASK{Research this company's<br/>market and competition?}
    CONTEXT[Editable starter question<br/>source company + optional peers]
    STARTING[Starting Companies<br/>company_analysis_anchor provenance]
    RCE[RCE Suggestions]
    REVIEW[Same Research Universe Review]
    RU[Approved Research Universe]

    COMPANY --> ANALYSIS --> ASK
    ASK -->|Yes| CONTEXT
    CONTEXT --> STARTING
    CONTEXT --> RCE
    STARTING --> REVIEW
    RCE --> REVIEW
    REVIEW --> RU
```

No parallel peer-analysis or universe-review engine is created.

## 5. Downstream non-filtering contract

```mermaid
flowchart LR
    RU[Approved Research Universe<br/>ID + version]
    HANDOFF[Handoff contract<br/>exact constituents + expected count + provenance refs]
    SAM[SAM / Company Analysis]
    OD[Opportunity Discovery]
    SRESULT[Result or explicit status<br/>for every constituent]
    ORESULT[Opportunity or explicit status<br/>for every constituent]

    RU --> HANDOFF
    HANDOFF --> SAM --> SRESULT
    HANDOFF --> OD --> ORESULT

    FILTER[Display filters]
    RANK[Rankings / recommendations]
    SRESULT --> FILTER
    ORESULT --> RANK
    FILTER -. never changes .-> RU
    RANK -. never changes .-> RU

    classDef contract fill:#e8f7ed,stroke:#3c7a4c,color:#15351d;
    class RU,HANDOFF contract;
```

Approving a Research Universe creates the contract only. It does not automatically launch SAM or Opportunity Discovery.
