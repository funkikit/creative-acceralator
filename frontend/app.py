from __future__ import annotations

import os
import uuid
from pathlib import Path
from textwrap import shorten
from typing import Any, Dict, List
import time

import pandas as pd

import streamlit as st

try:
    # When running from project root
    from frontend.api_client import ApiClient  # type: ignore
except ModuleNotFoundError:  # pragma: no cover - fallback for `streamlit run frontend/app.py`
    # When Streamlit sets the working dir to this folder
    from api_client import ApiClient  # type: ignore


_PERSONA_BASE_COLUMNS = [
    "id",
    "gender",
    "age_band",
    "region",
    "background",
    "familiarity",
    "summary",
]


_CUSTOM_VARIATION_COLUMNS = [
    "motif",
    "style",
    "concept",
    "palette",
    "target_audience",
    "brand_tone",
    "notes",
]


def _default_variable_rows() -> List[Dict[str, str]]:
    return [
        {"name": "motif", "values": ""},
        {"name": "style", "values": ""},
        {"name": "concept", "values": ""},
    ]


def _variables_to_rows(dynamic_variables: Dict[str, List[str]]) -> List[Dict[str, str]]:
    rows: List[Dict[str, str]] = []
    for name, values in (dynamic_variables or {}).items():
        joined = ", ".join(str(v) for v in values if v)
        rows.append({"name": str(name), "values": joined})
    return rows or _default_variable_rows()


def _rows_to_dynamic_variables(rows: List[Dict[str, str]]) -> Dict[str, List[str]]:
    dynamic: Dict[str, List[str]] = {}
    for row in rows or []:
        name = str(row.get("name", "")).strip()
        if not name:
            continue
        values_raw = row.get("values", "")
        if pd.isna(values_raw):
            values_raw = ""
        values = _split_candidates(str(values_raw))
        if values:
            dynamic[name] = values
    return dynamic


def _default_custom_rows() -> List[Dict[str, str]]:
    return []


def _rows_to_custom_variations(rows: List[Dict[str, str]]) -> List[Dict[str, str]]:
    custom: List[Dict[str, str]] = []
    known = {"motif", "style", "concept", "palette", "target_audience", "brand_tone"}
    for row in rows or []:
        if not any(str(row.get(col, "")).strip() for col in known):
            continue
        seed: Dict[str, str] = {}
        extras: Dict[str, str] = {}
        for key, value in row.items():
            if not value:
                continue
            if isinstance(value, float) and pd.isna(value):
                continue
            text = str(value).strip()
            if not text:
                continue
            if key in known:
                seed[key] = text
            else:
                extras[key] = text
        if extras:
            seed["extras"] = extras
        custom.append(seed)
    return custom


def _split_candidates(text: str) -> List[str]:
    if not text:
        return []
    raw = text.replace("\n", ",")
    return [seg.strip() for seg in raw.split(",") if seg.strip()]


def _parse_constraints(text: str) -> List[str]:
    return _split_candidates(text)


def _project_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _seed_csv_path() -> Path:
    return _project_root() / "app" / "data" / "personas_seed.csv"


def _normalize_gender(value: str) -> str:
    mapping = {"F": "Female", "M": "Male"}
    return mapping.get(value, str(value).title())


def _normalize_familiarity(value: str) -> str:
    mapping = {"high": "high", "medium": "medium", "low": "low"}
    v = str(value).strip().lower()
    return mapping.get(v, v)


def _compose_summary(row: Dict[str, Any]) -> str:
    gender = _normalize_gender(row.get("gender", ""))
    familiarity = _normalize_familiarity(row.get("familiarity", ""))
    region = str(row.get("region", "")).upper()
    background = str(row.get("background", ""))
    age_band = str(row.get("age_band", ""))
    bits = [part for part in [age_band, gender, background] if part]
    headline = " ".join(bits)
    tail = f"based in {region} with {familiarity} familiarity".strip()
    return f"{headline} {tail}".strip()


def _blank_persona() -> Dict[str, Any]:
    return {
        "id": f"p_{uuid.uuid4().hex[:6]}",
        "gender": "",
        "age_band": "",
        "region": "",
        "background": "",
        "familiarity": "",
        "summary": "",
    }


def _sanitize_persona_record(row: Dict[str, Any]) -> Dict[str, Any]:
    data = {}
    for key in _PERSONA_BASE_COLUMNS:
        value = row.get(key, "")
        data[key] = "" if value is None else str(value).strip()
    if not data["id"]:
        data["id"] = f"p_{uuid.uuid4().hex[:6]}"
    extras = {
        str(k): ("" if v is None else str(v))
        for k, v in row.items()
        if k not in _PERSONA_BASE_COLUMNS
    }
    if not data.get("summary"):
        data["summary"] = _compose_summary(data)
    data.update(extras)
    return data


def _add_column(records: List[Dict[str, Any]], column: str) -> List[Dict[str, Any]]:
    column = column.strip()
    if not column:
        return records
    updated: List[Dict[str, Any]] = []
    rows = records or [_blank_persona()]
    for row in rows:
        if column not in row:
            row = {**row, column: ""}
        updated.append(row)
    return updated


def _records_from_editor(df: pd.DataFrame) -> List[Dict[str, Any]]:
    if df is None:
        return []
    df = df.fillna("")
    records: List[Dict[str, Any]] = []
    for row in df.to_dict("records"):
        normalized = {str(k): ("" if v is None else str(v)) for k, v in row.items()}
        records.append(normalized)
    return records


def _row_has_minimum_data(row: Dict[str, Any]) -> bool:
    if not row:
        return False
    essential_keys = ["gender", "age_band", "region", "background"]
    return any(str(row.get(k, "")).strip() for k in essential_keys)


def _prepare_persona_payload(records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    payload: List[Dict[str, Any]] = []
    seen_ids = set()
    for row in records:
        cleaned = _sanitize_persona_record(row)
        if not _row_has_minimum_data(cleaned):
            continue
        original_id = cleaned["id"]
        while cleaned["id"] in seen_ids:
            cleaned["id"] = f"p_{uuid.uuid4().hex[:6]}"
            cleaned["summary"] = _compose_summary(cleaned)
        seen_ids.add(cleaned["id"])
        payload.append(cleaned)
        if cleaned["id"] != original_id:
            # reflect new id back to table on next render
            row["id"] = cleaned["id"]
            row["summary"] = cleaned["summary"]
    return payload


def _load_seed_personas(count: int = 5) -> List[Dict[str, Any]]:
    path = _seed_csv_path()
    if not path.exists():
        return [_blank_persona() for _ in range(count)]
    df = pd.read_csv(path).fillna("")
    if df.empty:
        return [_blank_persona() for _ in range(count)]
    sample_df = df.sample(n=min(count, len(df)), replace=len(df) < count, random_state=None)
    personas: List[Dict[str, Any]] = []
    for _, row in sample_df.iterrows():
        record = row.to_dict()
        personas.append(_sanitize_persona_record(record))
    return personas

def init_session() -> None:
    if "variations" not in st.session_state:
        st.session_state["variations"] = []
    if "images" not in st.session_state:
        st.session_state["images"] = []
    if "evaluations" not in st.session_state:
        st.session_state["evaluations"] = []
    if "variation_goal" not in st.session_state:
        st.session_state["variation_goal"] = "ブランドのサマーキャンペーンを盛り上げたい"
    if "variation_constraints_text" not in st.session_state:
        st.session_state["variation_constraints_text"] = ""
    if "variation_dynamic_rows" not in st.session_state:
        st.session_state["variation_dynamic_rows"] = _default_variable_rows()
    if "variation_custom_rows" not in st.session_state:
        st.session_state["variation_custom_rows"] = []
    if "persona_table" not in st.session_state:
        st.session_state["persona_table"] = _load_seed_personas()
    if "last_persona_upload" not in st.session_state:
        st.session_state["last_persona_upload"] = None
    if "use_persona_override" not in st.session_state:
        st.session_state["use_persona_override"] = False


def render_variations(client: ApiClient) -> None:
    st.header("1) Generate Variations")

    goal = st.text_area(
        "実現したいこと",
        value=st.session_state.get("variation_goal", "ブランドのサマーキャンペーンを盛り上げたい"),
        height=120,
        help="プロジェクトの狙い、届けたいメッセージなど。",
    )
    constraints_text = st.text_area(
        "守ってほしいこと",
        value=st.session_state.get("variation_constraints_text", ""),
        height=100,
        help="必ず守る条件を1行ずつ入力してください (例: ロゴは右下に配置)。",
    )

    col1, col2, col3 = st.columns([1, 1, 1])
    with col1:
        k = st.slider("自動生成するバリエーション数", min_value=1, max_value=20, value=8)
    with col2:
        llm = st.selectbox("LLM Provider", options=["gemini", "openai"], index=0, key="variation_llm")
    with col3:
        if st.button("候補となる変数を抽出", type="secondary"):
            if not goal.strip():
                st.error("実現したいことを入力してください。")
            else:
                try:
                    constraints_list = _parse_constraints(constraints_text)
                    res = client.fetch_variation_variables(goal=goal, constraints=constraints_list, llm=llm)
                    rows = _variables_to_rows(res.get("dynamic_variables", {}))
                    st.session_state["variation_dynamic_rows"] = rows
                    merged_constraints = res.get("fixed_constraints", constraints_list)
                    st.session_state["variation_constraints_text"] = "\n".join(merged_constraints)
                    if res.get("used_fallback"):
                        st.warning(
                            "LLMから候補を取得できなかったため、テンプレート値を表示しています。"
                            " APIキーやネットワーク設定を確認してください。",
                            icon="⚠️",
                        )
                    else:
                        st.success("変数候補を更新しました。編集してから生成してください。")
                except Exception as e:  # noqa: BLE001
                    st.error(f"変数の抽出に失敗しました: {e}")

    st.session_state["variation_goal"] = goal
    st.session_state["variation_constraints_text"] = constraints_text

    st.subheader("変数の編集")
    st.caption("列名=変数名、値=候補をカンマ区切りで入力できます。不要な行は削除、行追加で新しい変数も設定できます。")
    variable_rows = st.session_state.get("variation_dynamic_rows") or _default_variable_rows()
    variable_df = pd.DataFrame(variable_rows)
    edited_variables = st.data_editor(
        variable_df,
        column_config={"name": "変数名", "values": st.column_config.TextColumn("候補 (カンマ区切り)")},
        num_rows="dynamic",
        hide_index=True,
        key="variation_variable_editor",
        use_container_width=True,
    )
    st.session_state["variation_dynamic_rows"] = edited_variables.to_dict("records")

    st.subheader("固定条件")
    constraints_buffer = st.text_area(
        "全バリエーションに共通で反映する条件",
        value=st.session_state.get("variation_constraints_text", ""),
        height=100,
        key="variation_constraints_editor",
    )
    st.session_state["variation_constraints_text"] = constraints_buffer

    st.subheader("ユーザー追加バリエーション")
    st.caption("ここで追加した行は自動生成とは別にそのまま評価対象に含まれます。空行は無視されます。")
    custom_rows = st.session_state.get("variation_custom_rows", [])
    custom_df = pd.DataFrame(custom_rows)
    if custom_df.empty:
        custom_df = pd.DataFrame(columns=_CUSTOM_VARIATION_COLUMNS)
    edited_custom = st.data_editor(
        custom_df,
        num_rows="dynamic",
        hide_index=True,
        key="variation_custom_editor",
        use_container_width=True,
    )
    st.session_state["variation_custom_rows"] = edited_custom.to_dict("records")

    if st.button("Create Variations", type="primary"):
        dynamic_payload = _rows_to_dynamic_variables(st.session_state["variation_dynamic_rows"])
        constraints_list = _parse_constraints(st.session_state.get("variation_constraints_text", ""))
        custom_payload = _rows_to_custom_variations(st.session_state.get("variation_custom_rows", []))
        try:
            res = client.create_variations(
                goal=goal,
                dynamic_variables=dynamic_payload,
                constraints=constraints_list,
                k=k,
                llm=llm,
                custom_variations=custom_payload,
            )
            st.session_state["variations"] = res.get("variations", [])
            st.success(f"Generated {len(st.session_state['variations'])} variations")
        except Exception as e:  # noqa: BLE001
            st.error(f"Failed to create variations: {e}")

    if st.session_state.get("variations"):
        st.subheader("Variations")
        for v in st.session_state["variations"]:
            title = v["trace"].get("concept") or v["trace"].get("motif") or v["id"]
            with st.expander(f"{v['id']} | {title}"):
                st.code(v["prompt"], language="text")
                st.json(v["trace"])  # quick peek


def render_images(client: ApiClient) -> None:
    st.header("2) Generate Images")
    variations = st.session_state.get("variations", [])
    if not variations:
        st.info("Generate variations first.")
        return

    ids = [v["id"] for v in variations]
    selected = st.multiselect("Select variations", options=ids, default=ids)

    if st.button("Create Images"):
        try:
            res = client.create_images(variation_ids=selected)
            st.session_state["images"] = res.get("images", [])
            st.success(f"Created {len(st.session_state['images'])} images")
        except Exception as e:  # noqa: BLE001
            st.error(f"Failed to create images: {e}")

    if st.session_state["images"]:
        st.subheader("Images")
        cols = st.columns(3)
        for i, img in enumerate(st.session_state["images"]):
            url = client.abs_url(img["url"])  # backend serves /static
            with cols[i % 3]:
                st.image(
                    url,
                    caption=f"{img['id']} (v: {img['variation_id']})",
                    use_container_width=True,
                )


def render_validate(client: ApiClient) -> None:
    st.header("3) Validate With Personas")
    images = st.session_state.get("images", [])
    if not images:
        st.info("Create images first.")
        return

    ids = [i["id"] for i in images]
    selected = st.multiselect("Select images", options=ids, default=ids)
    col1, col2 = st.columns([1, 1])
    with col1:
        n_personas = st.slider("# of personas", min_value=10, max_value=100, value=20, step=5)
    with col2:
        llm = st.selectbox("LLM Provider", options=["openai", "gemini"], index=0)

    st.subheader("Persona設定")
    st.caption("CSVアップロードや手入力で評価に使うペルソナを編集できます。空の行は自動で除外されます。")
    persona_records = st.session_state.get("persona_table", [])

    uploaded = st.file_uploader("ペルソナCSVを追加", type=["csv"], key="persona_uploader")
    if uploaded is not None:
        file_signature = (uploaded.name, uploaded.size)
        if st.session_state.get("last_persona_upload") != file_signature:
            uploaded.seek(0)
            df_upload = pd.read_csv(uploaded).fillna("")
            new_rows = [_sanitize_persona_record(row) for row in df_upload.to_dict("records")]
            persona_records = persona_records + new_rows
            st.session_state["persona_table"] = persona_records
            st.session_state["last_persona_upload"] = file_signature
            st.success(f"アップロードから {len(new_rows)} 件のペルソナを追加しました。")

    col_add, _ = st.columns([1, 3])
    with col_add:
        new_col = st.text_input("列名を追加", key="persona_new_column")
        if st.button("列を追加", key="persona_add_column"):
            if new_col:
                persona_records = _add_column(persona_records, new_col)
                st.session_state["persona_table"] = persona_records
                st.session_state["persona_new_column"] = ""

    persona_df = pd.DataFrame(st.session_state.get("persona_table", []))
    if persona_df.empty:
        persona_df = pd.DataFrame(columns=_PERSONA_BASE_COLUMNS)

    edited_df = st.data_editor(
        persona_df,
        num_rows="dynamic",
        hide_index=True,
        use_container_width=True,
        key="persona_editor",
    )
    st.session_state["persona_table"] = _records_from_editor(edited_df)
    persona_records = st.session_state["persona_table"]
    personas_payload = _prepare_persona_payload(persona_records)
    st.session_state["persona_table"] = persona_records
    st.caption(
        f"現在 {len(personas_payload)} 件のペルソナが設定されています。\n"
        "チェックボックスを有効にすると、バックエンドのランダムサンプリングではなくこの一覧を使用します。"
    )

    st.session_state["use_persona_override"] = st.checkbox(
        "このペルソナ一覧を評価に使用する",
        value=st.session_state.get("use_persona_override", False),
    )
    use_override = st.session_state["use_persona_override"] and len(personas_payload) > 0
    if st.session_state["use_persona_override"] and not personas_payload:
        st.warning("ペルソナ一覧が空です。サンプリングが使用されます。")

    if st.button("Run Validation", type="primary"):
        try:
            res = client.validate(
                image_ids=selected,
                n_personas=n_personas,
                llm=llm,
                personas=personas_payload if use_override else None,
            )
            st.session_state["evaluations"] = res.get("evaluations", [])
            st.success(f"Collected {len(st.session_state['evaluations'])} evaluations")
        except Exception as e:  # noqa: BLE001
            st.error(f"Failed to validate: {e}")

    if st.session_state["evaluations"]:
        evals = st.session_state["evaluations"]

        persona_catalog = {}
        for item in evals:
            persona = item.get("persona") or {}
            if not persona:
                continue
            persona_id = persona.get("id") or item.get("persona_id")
            persona_catalog[persona_id] = {
                "persona_id": persona_id,
                "gender": persona.get("gender", ""),
                "age_band": persona.get("age_band", ""),
                "region": persona.get("region", ""),
                "background": persona.get("background", ""),
                "familiarity": persona.get("familiarity", ""),
                "summary": persona.get("summary", ""),
            }

        if persona_catalog:
            st.subheader("Persona Profiles")
            st.caption("Validation sampled the following personas. Review their configuration before interpreting scores.")
            st.dataframe(list(persona_catalog.values()), use_container_width=True)

        st.subheader("Sample Evaluations")
        sample = evals[: min(15, len(evals))]
        st.write(f"Showing {len(sample)} of {len(evals)}")
        table_rows = []
        for e in sample:
            scores = e.get("scores", {})
            metadata = e.get("metadata", {})
            table_rows.append(
                {
                    "persona_id": e.get("persona_id"),
                    "image_id": e.get("image_id"),
                    "Appeal": scores.get("Appeal"),
                    "BrandFit": scores.get("BrandFit"),
                    "Originality": scores.get("Originality"),
                    "Clarity": scores.get("Clarity"),
                    "CulturalSensitivity": scores.get("CulturalSensitivity"),
                    "overall": scores.get("overall"),
                    "comment": shorten(e.get("comment", ""), width=100, placeholder="…"),
                    "fallback": "⚠︎" if metadata.get("used_fallback") else "",
                }
            )

        st.dataframe(table_rows, use_container_width=True)

        if any(row.get("fallback") for row in table_rows):
            st.warning(
                "⚠︎ 一部の評価がフォールバックで生成されています。LLM provider と API キー設定を確認してください。",
                icon="⚠️",
            )


def render_summary(client: ApiClient) -> None:
    st.header("4) Summary")
    group_by = st.multiselect("Group by", options=["gender", "age_band", "region"], default=[])
    if st.button("Fetch Summary"):
        try:
            res = client.get_summary(group_by)
            st.session_state["summary"] = res
        except Exception as e:  # noqa: BLE001
            st.error(f"Failed to get summary: {e}")

    summary = st.session_state.get("summary")
    if summary:
        st.subheader("Overall")
        overall = summary.get("overall", {})
        st.metric(label="Mean Overall", value=f"{overall.get('mean_overall', 0):.3f}")
        st.write(f"N = {overall.get('n', 0)}")

        by_group = summary.get("by_group", [])
        if by_group:
            st.subheader("By Group")
            st.dataframe(by_group, use_container_width=True)

        ranking = summary.get("ranking", [])
        if ranking:
            st.subheader("Ranking")
            st.dataframe(ranking, use_container_width=True)


def main() -> None:
    st.set_page_config(page_title="Creative Gen & Validation", layout="wide")
    init_session()

    st.sidebar.title("Settings")
    default_base = os.getenv("API_BASE_URL", "http://localhost:8000")
    base_url = st.sidebar.text_input("API Base URL", value=default_base)
    client = ApiClient(base_url=base_url)

    if st.sidebar.button("Ping API"):
        t0 = time.perf_counter()
        try:
            res = client.ping()
            dt_ms = int((time.perf_counter() - t0) * 1000)
            st.sidebar.success(f"OK {dt_ms} ms: {res}")
        except Exception as e:  # noqa: BLE001
            st.sidebar.error(f"Failed: {e}")

    tabs = st.tabs(["Variations", "Images", "Validate", "Summary"])
    with tabs[0]:
        render_variations(client)
    with tabs[1]:
        render_images(client)
    with tabs[2]:
        render_validate(client)
    with tabs[3]:
        render_summary(client)


if __name__ == "__main__":
    main()
