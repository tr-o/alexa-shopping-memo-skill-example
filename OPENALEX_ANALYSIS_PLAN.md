# OpenAlex トピック t13232 分析ワークフロー（改訂版）

約 18,000 件の Works を対象に、重要論文・重要人物・重要機関とその関係を抽出するための実務手順を日本語で整理しました。ネットワークや途中中断への耐性を考慮し、再開可能な収集・処理フローを中心にまとめています。

## 0) 推奨フォルダ構成
```
project-root/
  config/config.yaml        # API パラメータ、出力パス、リトライ設定
  data/raw/                 # 取得したページごとの生 JSON
  data/normalized/          # Parquet/CSV 等に正規化したテーブル
  logs/fetch.log            # 構造化ログ（JSON）
  notebooks/                # 分析・可視化ノート
  scripts/cli.py            # fetch / normalize / analyze / report サブコマンド
```

## 1) データ取得（堅牢性重視）
- **範囲指定 & ページング**: `per-page=200` で `page=N` を順に取得。各ページを `data/raw/page-00001.jsonl` のように保存し、
  `manifest.csv` に `page, status, fetched_at, result_count` を追記。
- **フィールド絞り込み**: `select=id,title,publication_year,authorships,primary_location,concepts,topics,cited_by_count,relevance_score,open_access,referenced_works`
  を推奨（引用ネットワークを後で使えるよう `referenced_works` を入れておく）。
- **日付スライス**: 取得時間が厳しい場合、`from_publication_date=2018-01-01` などで最近分から優先的に取得し、後で過去分を追加。
- **メール付与**: `mailto=you@example.com` を常に付けてレート制限緩和を期待。
- **サンプル取得コマンド（再実行可能）**:
  ```bash
  python scripts/cli.py fetch --topic t13232 --start-page 1 --end-page 200 --per-page 200 --out data/raw \
    --select "id,title,publication_year,authorships,primary_location,concepts,topics,cited_by_count,relevance_score,open_access,referenced_works" \
    --mailto you@example.com
  ```

## 2) リトライ・再開設計
- **指数バックオフ**: 例) 3〜5 回、2s→4s→8s。5xx/タイムアウト時にリトライ。
- **部分失敗の検知**: 保存した JSON の `meta.page` と `results` 長さを検証し、欠落ページを manifest から再取得。
- **中断再開**: `manifest` で `status=done` 以外を自動再試行する CLI オプション (`--resume`) を用意。
- **接続遮断対策**: 各ページ保存後にフラッシュし、`SIGINT` で中断しても次回は続きから再開できるようにする。

## 3) 正規化（Parquet/CSV）
- **Works テーブル**: `work_id (OpenAlex ID)`, `title`, `year`, `venue_id`, `venue_name`, `is_oa`, `cited_by_count`, `relevance_score`。
- **Authorship テーブル**: `work_id`, `author_id`, `author_name`, `institution_id`, `institution_name`, `position`（著者順）。
- **Topic/Concept テーブル**: `work_id`, `topic_id`, `concept_id`, `concept_level`。
- **Referencing テーブル（任意）**: `citing_work_id`, `cited_work_id`（`referenced_works` から展開）。
- **欠損処理**: ID やタイトル欠落はログを残して除外。重複は OpenAlex ID をキーに drop。
- **時間特徴量**: `age_years = current_year - publication_year` などを追加。

## 4) 重要度の指標と算出
- **論文ランキング**: `cited_by_count`、`cited_by_count / (1 + age_years)` の両方を算出。レビュー論文は `type:review` でフィルタ。
- **著者・機関ランキング**: 作品数、総被引用、平均被引用、`h-index` 風メトリクスを topic 内で計算。所属機関別の集計も併記。
- **ジャーナル/会議**: `venue_id` ごとの件数と中央値被引用で並べ替え。
- **ネットワーク中心性**: 後述のグラフから PageRank / betweenness を算出し、ランキングに加える。

## 5) ネットワーク構築
- **共著グラフ**: ノード=著者、エッジ=共著数（重み）。Louvain/Leiden でコミュニティ検出。
- **引用グラフ**: `referenced_works` から有向グラフを作成。PageRank や HITS で影響力を算出。
- **概念共起**: 論文ごとの `concepts`/`topics` から共起回数をカウントし、クラスタリングの補助に。

## 6) 可視化・レポーティング
- 年次推移: 出版数、OA 比率、中央値被引用。
- トップ k テーブル: 論文/著者/機関/ジャーナルのランキング（指標は明記）。
- ネットワーク図: 共著グラフのコミュニティ色分け、引用グラフの上位ノード強調。
- ノート or HTML レポートで全手順とパラメータを記録。

## 7) CLI 実装の最小仕様（例）
- `fetch`: 上記のリトライ・再開・manifest 付きでページ取得。
- `normalize`: raw JSON をテーブル化し Parquet/CSV 出力、欠損や重複ログを出力。
- `analyze`: 指標計算、ランキング生成、グラフ作成。
- `report`: 可視化やサマリーテキストを notebook/HTML に書き出し。
- すべて `config/config.yaml` のデフォルトを持ち、CLI 引数で上書き可能。

## 8) 簡易フェッチ擬似コード（Python）
```python
import json, time, requests, pathlib

API = "https://api.openalex.org/works"

def fetch_page(page, per_page, topic, select, mailto, out_dir, retries=5):
    params = {
        "filter": f"topics.id:{topic}",
        "per-page": per_page,
        "page": page,
        "select": select,
        "mailto": mailto,
    }
    wait = 2
    for attempt in range(retries):
        try:
            r = requests.get(API, params=params, timeout=30)
            if r.status_code >= 500:
                raise RuntimeError(f"server error {r.status_code}")
            r.raise_for_status()
            data = r.json()
            path = pathlib.Path(out_dir) / f"page-{page:05d}.json"
            path.write_text(json.dumps(data, ensure_ascii=False))
            return data
        except Exception as e:
            if attempt + 1 == retries:
                raise
            time.sleep(wait)
            wait *= 2  # backoff
```

## 9) 実行順序の例
1. `config` を用意（API パラメータ、保存先、リトライ回数）。
2. `fetch` をページ範囲ごとに実行し、manifest で進捗を確認しながら欠落ページを再取得。
3. `normalize` で Parquet/CSV を作成。
4. `analyze` でランキング指標とグラフ中心性を計算。
5. `report` でグラフ可視化と上位リストをまとめる。

以上の流れで、長時間にわたる取得や接続エラーがあっても、途中から再開しながら安定してデータを集約・分析できます。
