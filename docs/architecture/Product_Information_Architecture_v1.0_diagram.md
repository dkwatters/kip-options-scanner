# Product Information Architecture v1.0 — Diagrams

**Status:** Companion to `Product_Information_Architecture_v1.0.md`
**Scope:** Conceptual diagrams; documentation only

## 1. User-facing workflow

```mermaid
flowchart TD
    H[Home<br/>What would you like to analyze today?]
    R[Recent Research]

    H -->|Industry, Market, or Theme| Q[Research Topic<br/>Enter a research question]
    Q --> A[Optional inputs<br/>Known companies and existing research]
    A --> S[Suggested Companies]
    S --> V[Review Companies<br/>Add, exclude, restore]
    V --> U[Research Universe<br/>User approved]
    U --> P[Analyze Companies<br/>Population Analysis]
    P --> O[Opportunities<br/>Rank and characterize all constituents]
    P --> D[Company Analysis<br/>Drill into one constituent]
    O --> D
    O --> N[Deeper research, watchlists,<br/>future portfolio workflows]
    D --> N

    H -->|Company| C[Company<br/>Enter ticker or company name]
    C --> D
    D --> X{Research this company's<br/>market and competition?}
    X -->|Yes: company becomes anchor| Q
    X -->|Not now| D

    H <--> R
    R -. Resume at last valid state .-> Q
    R -. Resume .-> U
    R -. Resume .-> P
    R -. Resume .-> D

    classDef intent fill:#e8f1ff,stroke:#3568a8,color:#10243e;
    classDef contract fill:#e8f7ed,stroke:#3c7a4c,color:#15351d;
    classDef decision fill:#fff4d6,stroke:#a87918,color:#4b3507;
    class H,Q,C intent;
    class U contract;
    class X decision;
```

The Company-to-market branch enters the same Research Topic and universe-construction workflow. It does not create a second candidate, company-analysis, or opportunity engine.

## 2. User workflow mapped to internal architecture

```mermaid
flowchart TB
    subgraph UX[User-facing workflow]
        direction LR
        UH[Home] --> UT[Research Topic]
        UT --> US[Suggested Companies]
        US --> UR[Review Companies]
        UR --> UU[Research Universe]
        UU --> UA[Analyze Companies]
        UA --> UO[Opportunities]
        UH --> UC[Company]
        UC --> UCA[Company Analysis]
        UCA -. Market and competition .-> UT
        UA --> UCA
    end

    subgraph INTERNAL[Internal capability map]
        direction LR
        AI[Authored benchmark inputs<br/>and seeded sets] --> RCE[RCE]
        RCE --> CC[Candidate corpus]
        CC --> BW[Benchmark OS /<br/>universe construction]
        AI --> BW
        BW --> BOR[Benchmark of Record semantics /<br/>approved universe definition + snapshot]
        BOR --> SAM[SAM]
        SAM --> OD[Opportunity Discovery]
        BOR --> OD
    end

    subgraph EVIDENCE[Evidence, governance, and operations]
        RR[(Research Repository)]
        CT[Curator Tools]
        DD[Developer Diagnostics]
        AD[Administration]
    end

    UT -. interpreted by .-> RCE
    US -. presented from .-> CC
    UR -. curated through .-> BW
    UU -. represented by .-> BOR
    UA -. population view .-> SAM
    UCA -. single-company view .-> SAM
    UO -. ranked and characterized by .-> OD

    SAM --> RR
    OD --> RR
    BOR --> RR
    BW -. governance .-> CT
    RCE -. evaluation metadata .-> DD
    SAM -. model diagnostics .-> DD
    OD -. model diagnostics .-> DD
    RR -. operational status .-> AD

    classDef ux fill:#e8f1ff,stroke:#3568a8,color:#10243e;
    classDef authority fill:#e8f7ed,stroke:#3c7a4c,color:#15351d;
    classDef restricted fill:#f2f2f2,stroke:#6b6b6b,color:#282828;
    class UH,UT,US,UR,UU,UA,UO,UC,UCA ux;
    class BOR authority;
    class CT,DD,AD restricted;
```

## 3. Progressive navigation by state

```mermaid
stateDiagram-v2
    [*] --> Home
    Home --> TopicEntered: Choose Industry, Market, or Theme
    Home --> CompanyActive: Choose Company and resolve identity
    Home --> Resumed: Open Recent Research

    TopicEntered --> CandidatesGenerated: Find companies
    CandidatesGenerated --> UniverseReview: Review companies
    UniverseReview --> UniverseEstablished: Approve membership
    UniverseEstablished --> PopulationRunning: Analyze companies
    PopulationRunning --> PopulationComplete: Results/status for every member
    PopulationComplete --> OpportunitiesAvailable: View opportunities
    PopulationComplete --> CompanyActive: Open constituent
    OpportunitiesAvailable --> CompanyActive: Open constituent

    CompanyActive --> TopicEntered: Research market and competition
    CompanyActive --> PopulationComplete: Return to parent population

    UniverseEstablished --> UniverseReview: Create explicit revision
    Resumed --> TopicEntered
    Resumed --> UniverseReview
    Resumed --> UniverseEstablished
    Resumed --> PopulationComplete
    Resumed --> CompanyActive

    TopicEntered --> Home: Home
    CandidatesGenerated --> Home: Home
    UniverseReview --> Home: Home
    UniverseEstablished --> Home: Home
    PopulationComplete --> Home: Home
    CompanyActive --> Home: Home
    OpportunitiesAvailable --> Home: Home
```

Navigation reveals only states that exist or actions that are currently valid. Home and Recent Research remain consistently reachable.

## 4. Research Universe membership contract

```mermaid
flowchart LR
    D[Suggested Companies] --> E[User dispositions<br/>include / exclude / restore]
    E --> A[Approved Research Universe<br/>authoritative membership]
    A --> S[SAM / Company Analysis]
    A --> O[Opportunity Discovery]

    S --> SL[Complete constituent ledger<br/>analysis or explicit status]
    O --> OL[Complete constituent ledger<br/>rank/opportunity or explicit status]

    SL --> VF[Temporary view filters]
    SL --> RK[Ranking and highlighting]
    OL --> VF
    OL --> RK

    VF -. does not change .-> A
    RK -. does not change .-> A
    A -->|Only explicit user revision| E

    classDef contract fill:#e8f7ed,stroke:#3c7a4c,color:#15351d;
    class A contract;
```

Membership is distinct from ranking, temporary display filtering, recommendation, and non-membership dispositions such as watch or dismiss. A revised membership set requires an explicit user edit and approval.
