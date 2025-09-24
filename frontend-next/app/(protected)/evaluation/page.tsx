"use client";

import { useEffect, useMemo, useState } from "react";
import { fetchSummary, runValidation } from "../../../lib/api";

const DEFAULT_PERSONAS = [
  {
    id: "p_tokyo_student",
    gender: "F",
    age_band: "20s",
    region: "JP",
    background: "student",
    familiarity: "medium",
    summary: "都内女子大生。トレンド感度は高いがブランド知識は平均的。",
  },
  {
    id: "p_osaka_engineer",
    gender: "M",
    age_band: "30s",
    region: "JP",
    background: "engineer",
    familiarity: "high",
    summary: "大阪在住エンジニア。プロダクトの実用性を重視する既存顧客。",
  },
  {
    id: "p_tokyo_marketer",
    gender: "F",
    age_band: "30s",
    region: "JP",
    background: "marketing lead",
    familiarity: "high",
    summary: "ブランド担当マネージャー。ビジュアルと訴求の一貫性を重視。",
  },
  {
    id: "p_nagoya_parent",
    gender: "F",
    age_band: "40s",
    region: "JP",
    background: "working parent",
    familiarity: "medium",
    summary: "名古屋のワーキングマザー。家族視点での分かりやすさを評価。",
  },
  {
    id: "p_fukuoka_designer",
    gender: "M",
    age_band: "40s",
    region: "JP",
    background: "designer",
    familiarity: "low",
    summary: "福岡のフリーランスデザイナー。新鮮さと色使いに敏感。",
  },
  {
    id: "p_sendai_student",
    gender: "M",
    age_band: "20s",
    region: "JP",
    background: "graduate student",
    familiarity: "low",
    summary: "仙台の院生。ブランド初接触でメッセージの読みやすさ重視。",
  },
  {
    id: "p_hokkaido_retail",
    gender: "F",
    age_band: "50s",
    region: "JP",
    background: "retail manager",
    familiarity: "medium",
    summary: "北海道の小売店長。売場展開時の視認性と導線を評価。",
  },
  {
    id: "p_okinawa_creator",
    gender: "F",
    age_band: "30s",
    region: "JP",
    background: "content creator",
    familiarity: "high",
    summary: "沖縄の動画クリエイター。SNS 映えと共感性を重視。",
  },
  {
    id: "p_kansai_sales",
    gender: "M",
    age_band: "30s",
    region: "JP",
    background: "sales",
    familiarity: "medium",
    summary: "関西の営業担当。クライアント説明のしやすさを評価。",
  },
  {
    id: "p_tokyo_analyst",
    gender: "F",
    age_band: "40s",
    region: "JP",
    background: "data analyst",
    familiarity: "high",
    summary: "都内データアナリスト。指標が読み取りやすい設計を好む。",
  },
];

const PERSONA_FIELDS: Array<{ key: keyof (typeof DEFAULT_PERSONAS)[number]; label: string; readOnly?: boolean }> = [
  { key: "id", label: "ID", readOnly: true },
  { key: "gender", label: "性別" },
  { key: "age_band", label: "年代" },
  { key: "region", label: "地域" },
  { key: "background", label: "背景" },
  { key: "familiarity", label: "ブランド理解" },
  { key: "summary", label: "要約" },
];

export default function EvaluationPage() {
  const [images, setImages] = useState<any[]>([]);
  const [selection, setSelection] = useState<Record<string, boolean>>({});
  const [personas, setPersonas] = useState(DEFAULT_PERSONAS);
  const [llm, setLlm] = useState<"gemini" | "openai">("openai");
  const [nPersonas, setNPersonas] = useState(20);
  const [evaluations, setEvaluations] = useState<any[]>([]);
  const [summary, setSummary] = useState<any | null>(null);
  const [status, setStatus] = useState<string>("");
  const [loading, setLoading] = useState<string | null>(null);

  useEffect(() => {
    if (typeof window === "undefined") return;
    try {
      const saved = window.localStorage.getItem("pca-images");
      if (saved) {
        const parsed = JSON.parse(saved);
        setImages(parsed);
        const initial: Record<string, boolean> = {};
        parsed.forEach((img: any) => {
          initial[img.id] = true;
        });
        setSelection(initial);
      }
    } catch (error) {
      console.warn("画像の読み込みに失敗しました", error);
    }
  }, []);

  const selectedImageIds = useMemo(
    () => Object.entries(selection).filter(([, v]) => v).map(([id]) => id),
    [selection]
  );

  const handlePersonaChange = (index: number, key: string, value: string) => {
    setPersonas((rows) => rows.map((row, i) => (i === index ? { ...row, [key]: value } : row)));
  };

  const handleAddPersona = () => {
    setPersonas((rows) => [
      ...rows,
      {
        id: `p_custom_${rows.length + 1}`,
        gender: "",
        age_band: "",
        region: "",
        background: "",
        familiarity: "",
        summary: "",
      },
    ]);
  };

  const handleRemovePersona = (index: number) => {
    setPersonas((rows) => rows.filter((_, i) => i !== index));
  };

  const handleValidate = async () => {
    setLoading("validate");
    setStatus("");
    try {
      if (!selectedImageIds.length) throw new Error("画像を選択してください");
      const personasPayload = personas
        .map((persona) =>
          Object.fromEntries(
            Object.entries(persona).filter(([, value]) => String(value).trim().length > 0)
          )
        )
        .filter((persona) => Object.keys(persona).length > 0);

      const response = await runValidation({
        image_ids: selectedImageIds,
        n_personas: nPersonas,
        llm,
        personas: personasPayload.length ? personasPayload : undefined,
      });
      setEvaluations(response.evaluations);
      setStatus(`評価結果: ${response.evaluations.length} 件`);
    } catch (err) {
      setStatus((err as Error).message);
    } finally {
      setLoading(null);
    }
  };

  const handleSummary = async () => {
    setLoading("summary");
    setStatus("");
    try {
      const response = await fetchSummary(["gender", "age_band", "region"]);
      setSummary(response);
      setStatus("サマリーを取得しました");
    } catch (err) {
      setStatus((err as Error).message);
    } finally {
      setLoading(null);
    }
  };

  return (
    <div className="space-y-8">
      <section className="rounded-3xl border border-white/10 bg-white/5 p-6 shadow-xl shadow-primary-500/10">
        <h2 className="text-lg font-semibold text-white">画像の選択</h2>
        {images.length === 0 ? (
          <p className="mt-4 text-sm text-slate-300">
            まだ画像がありません。まず「クリエイティブ」画面で画像を生成してください。
          </p>
        ) : (
          <div className="mt-4 grid gap-4 md:grid-cols-2 lg:grid-cols-3">
            {images.map((img) => (
              <label
                key={img.id}
                className="group cursor-pointer overflow-hidden rounded-3xl border border-white/10 bg-slate-900/60"
              >
                <img
                  src={img.absUrl ?? (img.url?.startsWith("http") ? img.url : `${process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000"}${img.url ?? ""}`)}
                  alt={img.id}
                  className="h-48 w-full object-cover transition group-hover:scale-105"
                />
                <div className="flex items-center justify-between p-4 text-xs text-slate-200">
                  <div>
                    <p className="font-semibold">{img.id}</p>
                    <p className="text-slate-400">Variation: {img.variation_id}</p>
                  </div>
                  <input
                    type="checkbox"
                    checked={!!selection[img.id]}
                    onChange={(e) =>
                      setSelection((prev) => ({ ...prev, [img.id]: e.target.checked }))
                    }
                    className="h-5 w-5 rounded border border-white/20 bg-slate-950"
                  />
                </div>
              </label>
            ))}
          </div>
        )}
      </section>

      <section className="rounded-3xl border border-white/10 bg-white/5 p-6 shadow-xl shadow-primary-500/10">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h2 className="text-lg font-semibold text-white">ペルソナ設定</h2>
            <p className="text-sm text-slate-300">フォールバック時でもコメントに人格を持たせるため、プロフィールを明示しておきましょう。</p>
          </div>
          <div className="flex items-center gap-3">
            <label className="text-sm font-medium text-slate-200">
              LLM
              <select
                value={llm}
                onChange={(e) => setLlm(e.target.value as "gemini" | "openai")}
                className="ml-2 rounded-full border border-white/10 bg-slate-900/60 px-3 py-2 text-sm text-white"
              >
                <option value="gemini">Gemini</option>
                <option value="openai">OpenAI</option>
              </select>
            </label>
            <label className="text-sm font-medium text-slate-200">
              評価人数
              <input
                type="number"
                min={10}
                max={100}
                value={nPersonas}
                onChange={(e) => setNPersonas(Number(e.target.value))}
                className="ml-2 w-24 rounded-full border border-white/10 bg-slate-900/60 px-3 py-2 text-sm text-white"
              />
            </label>
          </div>
        </div>
        <div className="mt-4 space-y-3">
          {personas.map((persona, index) => (
            <div
              key={persona.id}
              className="rounded-2xl border border-white/10 bg-slate-900/60 p-3"
            >
              <div className="flex flex-wrap items-end gap-3">
                {PERSONA_FIELDS.map(({ key, label, readOnly }) => (
                  <label key={key} className="flex flex-col text-[11px] font-medium text-slate-300">
                    <span className="mb-1 text-slate-400">{label}</span>
                    <input
                      value={persona[key] ?? ""}
                      onChange={(e) => handlePersonaChange(index, key, e.target.value)}
                      readOnly={readOnly}
                      className="min-w-[120px] rounded-xl border border-white/10 bg-slate-950 px-3 py-2 text-xs text-white focus:border-primary-400 focus:outline-none disabled:opacity-70"
                    />
                  </label>
                ))}
                <button
                  onClick={() => handleRemovePersona(index)}
                  className="ml-auto inline-flex items-center rounded-full border border-white/10 px-3 py-2 text-xs text-slate-200 hover:bg-white/10"
                >
                  削除
                </button>
              </div>
            </div>
          ))}
          <button
            onClick={handleAddPersona}
            className="w-full rounded-full border border-dashed border-white/20 py-2 text-sm text-slate-200 hover:border-primary-400 hover:text-white"
          >
            + ペルソナを追加
          </button>
        </div>
      </section>

      <div className="flex flex-wrap items-center gap-3">
        <button
          onClick={handleValidate}
          disabled={loading === "validate"}
          className="rounded-full bg-gradient-to-r from-primary-500 via-primary-400 to-primary-600 px-6 py-3 text-base font-semibold text-slate-950 shadow-lg shadow-primary-500/30 transition hover:brightness-110 disabled:cursor-not-allowed disabled:opacity-60"
        >
          {loading === "validate" ? "評価中..." : "エージェント評価を実行"}
        </button>
        <button
          onClick={handleSummary}
          disabled={loading === "summary"}
          className="rounded-full border border-white/10 px-5 py-3 text-sm text-slate-200 hover:bg-white/10"
        >
          {loading === "summary" ? "集計中..." : "サマリービューを更新"}
        </button>
        {status && <span className="text-sm text-slate-300">{status}</span>}
      </div>

      {evaluations.length > 0 && (
        <section className="rounded-3xl border border-white/10 bg-white/5 p-6 shadow-xl shadow-primary-500/10">
          <h2 className="text-lg font-semibold text-white">評価結果 (抜粋)</h2>
          <div className="mt-4 space-y-3">
            {evaluations.slice(0, 10).map((item) => (
              <div
                key={`${item.persona_id}-${item.image_id}`}
                className="rounded-2xl border border-white/10 bg-slate-900/60 p-4"
              >
                <div className="flex flex-wrap items-center justify-between gap-2 text-xs text-slate-300">
                  <span>Persona: {item.persona_id}</span>
                  <span>Image: {item.image_id}</span>
                  {item.metadata?.used_fallback && (
                    <span className="rounded-full bg-yellow-500/20 px-3 py-1 text-[10px] text-yellow-200">
                      ⚠︎ フォールバック
                    </span>
                  )}
                </div>
                <p className="mt-3 text-sm text-slate-100">{item.comment}</p>
                <div className="mt-3 grid grid-cols-3 gap-2 text-xs text-slate-300 md:grid-cols-6">
                  {Object.entries(item.scores).map(([key, value]) => (
                    <span key={key} className="rounded-2xl bg-slate-950/60 px-3 py-2">
                      <strong className="mr-2 text-slate-200">{key}</strong>
                      {Number(value).toFixed(2)}
                    </span>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </section>
      )}

      {summary && (
        <section className="rounded-3xl border border-white/10 bg-white/5 p-6 shadow-xl shadow-primary-500/10 space-y-4">
          <h2 className="text-lg font-semibold text-white">統計サマリー</h2>
          <div className="grid gap-4 md:grid-cols-3">
            <div className="rounded-2xl border border-white/10 bg-slate-900/60 p-4 text-sm text-slate-300">
              <p className="text-slate-400">平均スコア</p>
              <p className="mt-2 text-2xl font-semibold text-white">
                {summary.overall?.mean_overall?.toFixed?.(3) ?? "-"}
              </p>
              <p className="text-xs text-slate-400">N = {summary.overall?.n ?? 0}</p>
            </div>
            <div className="rounded-2xl border border-white/10 bg-slate-900/60 p-4 text-sm text-slate-300">
              <p className="text-slate-400">ランキング (トップ3)</p>
              <ol className="mt-2 space-y-1 text-xs">
                {(summary.ranking ?? []).slice(0, 3).map((row: any, idx: number) => (
                  <li key={row.image_id} className="flex items-center justify-between rounded-xl bg-white/5 px-3 py-2">
                    <span>
                      #{idx + 1} {row.image_id}
                    </span>
                    <span>{Number(row.overall).toFixed(3)}</span>
                  </li>
                ))}
              </ol>
            </div>
            <div className="rounded-2xl border border-white/10 bg-slate-900/60 p-4 text-sm text-slate-300">
              <p className="text-slate-400">属性別平均</p>
              <div className="mt-2 space-y-2 text-xs">
                {(summary.by_group ?? []).slice(0, 4).map((row: any, idx: number) => (
                  <div key={idx} className="rounded-xl bg-white/5 px-3 py-2">
                    <div>{JSON.stringify(row.group)}</div>
                    <div>平均 {Number(row.mean_overall).toFixed(3)} / N={row.n}</div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </section>
      )}
    </div>
  );
}
