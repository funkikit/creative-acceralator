# API リファレンス（簡易）

主要エンドポイントの I/O とサンプルをまとめます。詳細なスキーマは OpenAPI（`/docs`）を参照してください。

ベース URL: `http://localhost:8000`

---

## POST /api/variations

目的: 基本プロンプトからバリエーション案を生成

Request JSON:

```json
{
  "base_prompt": "A modern, minimal poster for a summer music festival",
  "k": 8,
  "llm": "gemini"
}
```

Response JSON（例）:

```json
{
  "prompt_run_id": "pr_ab12cd34",
  "variations": [
    {
      "id": "v_1234abcd",
      "prompt": "<prompt text>",
      "trace": {
        "motif": "sun",
        "style": "minimal",
        "concept": "summer",
        "constraints": ["A4", "CMYK"],
        "palette": "yellow/blue"
      }
    }
  ]
}
```

---

## POST /api/images

目的: Variation ID から画像を生成し、`/static` のパスを返す

Request JSON:

```json
{ "variation_ids": ["v_1234abcd", "v_ef567890"] }
```

Response JSON（例）:

```json
{
  "images": [
    {
      "id": "img_a1b2c3d4",
      "variation_id": "v_1234abcd",
      "url": "/static/img_a1b2c3d4.png",
      "provider_meta": {"model": "gemini-nanobanana"}
    }
  ]
}
```

---

## POST /api/validate

目的: 画像に対し、ペルソナ複数でスコア評価を行う

Request JSON:

```json
{ "image_ids": ["img_a1b2c3d4"], "n_personas": 20, "llm": "openai" }
```

Response JSON（例）:

```json
{
  "evaluations": [
    {
      "persona_id": "p_f0123a",
      "image_id": "img_a1b2c3d4",
      "scores": {
        "Appeal": 0.82,
        "BrandFit": 0.75,
        "Originality": 0.7,
        "Clarity": 0.9,
        "CulturalSensitivity": 0.95,
        "overall": 0.82
      },
      "comment": "Fresh and easy to understand",
      "flags": []
    }
  ]
}
```

---

## GET /api/summary

目的: 評価結果の集計（全体/グループ/画像ランキング）

Query:

```
group_by=gender,age_band  # 0〜複数キー
```

Response JSON（例）:

```json
{
  "overall": {"mean_overall": 0.81, "n": 100},
  "by_group": [
    {"group": {"gender": "male"}, "n": 52, "mean_overall": 0.79},
    {"group": {"gender": "female"}, "n": 48, "mean_overall": 0.83}
  ],
  "ranking": [
    {"image_id": "img_a1b2c3d4", "overall": 0.85},
    {"image_id": "img_e5f6g7h8", "overall": 0.80}
  ]
}
```

---

## cURL 例

Variations:

```
curl -sS -X POST http://localhost:8000/api/variations \
  -H 'Content-Type: application/json' \
  -d '{"base_prompt":"A modern...","k":4,"llm":"gemini"}' | jq .
```

Images:

```
curl -sS -X POST http://localhost:8000/api/images \
  -H 'Content-Type: application/json' \
  -d '{"variation_ids":["v_1234abcd"]}' | jq .
```

Validate:

```
curl -sS -X POST http://localhost:8000/api/validate \
  -H 'Content-Type: application/json' \
  -d '{"image_ids":["img_a1b2c3d4"],"n_personas":10,"llm":"openai"}' | jq .
```

Summary:

```
curl -sS 'http://localhost:8000/api/summary?group_by=gender,age_band' | jq .
```

