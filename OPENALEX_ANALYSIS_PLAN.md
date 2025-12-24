# OpenAlex Topic t13232 Analysis Plan

This document outlines a resilient workflow to collect and analyze the ~18,000 works under OpenAlex topic `t13232` (Laser-Ablation Synthesis of Nanoparticles) to identify influential papers, authors, institutions, and their relationships.

## 1) Data Acquisition Strategy
- **Scoped pulls with pagination**: Fetch works via `https://api.openalex.org/works?filter=topics.id:t13232&per-page=200&page=N`. Limit each run to a defined page range to allow restarts.
- **Field selection**: Use `select=id,title,publication_year,authorships,primary_location,concepts,topics,cited_by_count,relevance_score,open_access` to keep payloads small while retaining analytic value.
- **Date slices**: Optional `from_publication_date`/`to_publication_date` filters let you prioritize recent years before backfilling older works.
- **mailto**: Append `mailto=you@example.com` to requests for better reliability and rate-limit consideration.

## 2) Reliability and Restartability
- **Checkpointed downloads**: Store each page as an individual JSONL or compressed JSON file (e.g., `data/raw/page-0001.json`). Maintain a manifest with pages fetched and record response `meta` totals.
- **Retry policy**: Implement exponential backoff (e.g., 3–5 retries, starting at 2s) on network errors or 5xx responses; resume from the last incomplete page using the manifest.
- **Integrity checks**: Validate that each saved page has `results` count <= `per-page` and that cumulative pages cover `meta.count`. Log discrepancies for reruns.

## 3) Data Normalization
- **Schema extraction**: Normalize each work into tabular records (e.g., Parquet/CSV) with keys:
  - Works: `work_id`, `title`, `year`, `venue_id`, `venue_name`, `is_oa`, `cited_by_count`.
  - Authorships: `work_id`, `author_id`, `author_name`, `institution_id`, `institution_name`, `position`.
  - Concepts/Topics: `work_id`, `concept_id`, `concept_level`, `topic_id`.
- **Deduping**: Use OpenAlex IDs as primary keys; drop records missing IDs or titles after logging.
- **Time enrichment**: Derive publication decade/year buckets for trend analyses.

## 4) Importance Signals
- **Papers**:
  - Sort by `cited_by_count` and optionally weight by recency (`cited_by_count / (1 + age_years)`).
  - Identify review/overview works via `type:review` or title heuristics.
  - Compute PageRank on the citation graph if you later fetch reference lists.
- **Authors/Institutions**:
  - Aggregate total works, total citations, and h-index-like metrics within the topic.
  - Track cross-institution collaborations via co-authorship edges.
- **Venues**:
  - Rank by publication volume and median citations for this topic.

## 5) Network Construction
- **Co-authorship graph**: nodes = authors, edges = shared works; edge weight = coauthored works count. Consider institution-level projection.
- **Citation graph**: optional; requires fetching `referenced_works` for each work. Build directed edges to compute centrality (PageRank, HITS).
- **Concept/topic co-occurrence**: from `concepts`/`topics` lists per work; useful for sub-area clustering.

## 6) Analysis & Visualization
- **Trend plots**: yearly publication volume, OA share, and median citations.
- **Top-k tables**: papers, authors, institutions, venues sorted by chosen importance signals.
- **Community detection**: apply Louvain/Leiden on co-authorship to find research communities.
- **Embeddings**: optional text embeddings from titles/abstracts to cluster works; store vectors separately to keep repo light.

## 7) Tooling Recommendations
- **Languages**: Python with `requests` or `httpx` for fetching; `pandas`/`polars` + `pyarrow` for processing.
- **Storage**: Write raw pages to disk; keep normalized tables in Parquet for efficient I/O; use SQLite for lightweight querying.
- **Automation**: Provide a CLI with subcommands: `fetch`, `normalize`, `analyze`, `report`. Each should be restartable and log progress.

## 8) Reproducibility & Documentation
- **Config file**: YAML/TOML for API parameters, output paths, and retry/backoff settings.
- **Logging**: Structured logs (JSON) with timestamps for fetch retries and progress.
- **Notebooks/Reports**: Document methodology and summarize key findings in notebooks or markdown reports once data are processed.

These steps aim to ensure you can collect the full topic dataset reliably, recover from transient failures, and derive influence metrics and networks with transparent, reproducible workflows.
