"use client";

import { ChangeEvent, useEffect, useMemo, useRef, useState } from "react";
import {
  API_BASE,
  fetchVariationVariables,
  generateVariations,
  generateImages,
} from "../../../lib/api";
import clsx from "clsx";

function parseMultiLine(value: string): string[] {
  return value
    .split(/[,\n]/)
    .map((item) => item.trim())
    .filter(Boolean);
}

function toMultiLine(values: string[]): string {
  return values.join(", ");
}

export default function CreativePage() {
  const [goal, setGoal] = useState("ブランドのサマーキャンペーンを盛り上げたい");
  const [constraints, setConstraints] = useState("ロゴは右下\n背景は明るめ");
  const [llm, setLlm] = useState<"gemini" | "openai">("gemini");
  const [variableRows, setVariableRows] = useState<Array<{ name: string; values: string }>>([
    { name: "motif", values: "サマーアイコン, 波, パラソル" },
    { name: "style", values: "ポップ, ミニマル" },
    { name: "concept", values: "熱気, 爽快感" },
  ]);
  const [customRows, setCustomRows] = useState<Array<Record<string, string>>>([]);
  const [variations, setVariations] = useState<any[]>([]);
  const [selected, setSelected] = useState<Record<string, boolean>>({});
  const [images, setImages] = useState<any[]>([]);
  const [loading, setLoading] = useState<string | null>(null);
  const [message, setMessage] = useState<string>("");
  const [imageProgress, setImageProgress] = useState<{
    status: "idle" | "running" | "complete" | "error";
    total: number;
    completed: number;
    message?: string | null;
  }>({ status: "idle", total: 0, completed: 0, message: null });
  const [imageFailures, setImageFailures] = useState<string[]>([]);
  const [variationCount, setVariationCount] = useState<number>(8);
  const [referenceImage, setReferenceImage] = useState<
    | {
        dataUrl: string;
        mimeType: string;
        name: string;
        size: number;
      }
    | null
  >(null);

  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const MAX_REFERENCE_SIZE = 8 * 1024 * 1024; // 8MB

  const selectedIds = useMemo(
    () => Object.entries(selected).filter(([, v]) => v).map(([id]) => id),
    [selected]
  );

  const progressPercent =
    imageProgress.total > 0
      ? Math.min(100, Math.round((imageProgress.completed / imageProgress.total) * 100))
      : 0;

  useEffect(() => {
    if (typeof window === "undefined") return;
    try {
      window.localStorage.setItem("pca-variations", JSON.stringify(variations));
      window.localStorage.setItem("pca-variation-selection", JSON.stringify(selected));
    } catch (error) {
      console.warn("variations persist error", error);
    }
  }, [variations, selected]);

  useEffect(() => {
    if (typeof window === "undefined") return;
    try {
      window.localStorage.setItem("pca-images", JSON.stringify(images));
    } catch (error) {
      console.warn("images persist error", error);
    }
  }, [images]);

  const handleAutoVariables = async () => {
    setLoading("variables");
    setMessage("");
    try {
      const response = await fetchVariationVariables({
        goal,
        constraints: parseMultiLine(constraints),
        llm,
      });
      const rows = Object.entries(response.dynamic_variables).map(([name, values]) => ({
        name,
        values: toMultiLine(values),
      }));
      setVariableRows(rows.length ? rows : [{ name: "concept", values: goal }]);
      setConstraints(response.fixed_constraints.join("\n"));
      setMessage(
        response.used_fallback
          ? "⚠︎ LLM の応答が得られなかったためテンプレートを表示しています"
          : "変数候補を更新しました"
      );
    } catch (err) {
      setMessage((err as Error).message);
    } finally {
      setLoading(null);
    }
  };

  const handleAddVariableRow = () => {
    setVariableRows((rows) => [...rows, { name: "", values: "" }]);
  };

  const handleVariableChange = (index: number, key: "name" | "values", value: string) => {
    setVariableRows((rows) => rows.map((row, i) => (i === index ? { ...row, [key]: value } : row)));
  };

  const handleRemoveVariable = (index: number) => {
    setVariableRows((rows) => rows.filter((_, i) => i !== index));
  };

  const handleAddCustomRow = () => {
    setCustomRows((rows) => [...rows, { motif: "", style: "", concept: "" }]);
  };

  const handleCustomChange = (index: number, key: string, value: string) => {
    setCustomRows((rows) =>
      rows.map((row, i) => (i === index ? { ...row, [key]: value } : row))
    );
  };

  const handleRemoveCustom = (index: number) => {
    setCustomRows((rows) => rows.filter((_, i) => i !== index));
  };

  const handleReferenceImageChange = (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0] ?? null;
    if (!file) {
      setReferenceImage(null);
      return;
    }
    if (!file.type.startsWith("image/")) {
      setMessage("画像ファイルを選択してください");
      event.target.value = "";
      return;
    }
    if (file.size > MAX_REFERENCE_SIZE) {
      setMessage("画像サイズが大きすぎます (最大 8MB まで)");
      event.target.value = "";
      return;
    }

    const reader = new FileReader();
    reader.onload = () => {
      if (typeof reader.result === "string") {
        setReferenceImage({
          dataUrl: reader.result,
          mimeType: file.type,
          name: file.name,
          size: file.size,
        });
      }
    };
    reader.onerror = () => {
      setMessage("画像の読み込みに失敗しました");
      setReferenceImage(null);
    };
    reader.readAsDataURL(file);
  };

  const handleReferenceImageClear = () => {
    setReferenceImage(null);
    if (fileInputRef.current) {
      fileInputRef.current.value = "";
    }
  };

  const handleGenerateVariations = async () => {
    setLoading("variations");
    setMessage("");
    try {
      const dynamic: Record<string, string[]> = {};
      for (const row of variableRows) {
        if (!row.name.trim()) continue;
        const values = parseMultiLine(row.values);
        if (values.length) {
          dynamic[row.name.trim()] = values;
        }
      }
      const custom = customRows
        .map((row) => {
          const entries = Object.entries(row).filter(([, value]) => value?.trim());
          if (!entries.length) return null;
          const record: Record<string, string> = {};
          for (const [key, value] of entries) record[key] = value.trim();
          return record;
        })
        .filter(Boolean) as Array<Record<string, string>>;

      const response = await generateVariations({
        goal,
        constraints: parseMultiLine(constraints),
        dynamic_variables: dynamic,
        custom_variations: custom,
        k: variationCount,
        llm,
      });
      setVariations(response.variations);
      const initialSelected: Record<string, boolean> = {};
      response.variations.forEach((v) => {
        initialSelected[v.id] = true;
      });
      setSelected(initialSelected);
      setImages([]);
      setMessage(`バリエーションを ${response.variations.length} 件生成しました`);
    } catch (err) {
      setMessage((err as Error).message);
    } finally {
      setLoading(null);
    }
  };

  const handleGenerateImages = async () => {
    if (!selectedIds.length) {
      setMessage("少なくとも 1 件のバリエーションを選択してください");
      setImageProgress({ status: "idle", total: 0, completed: 0, message: null });
      setImageFailures([]);
      return;
    }

    setLoading("images");
    setMessage("");
    setImageFailures([]);

    try {
      let referencePayload: { data: string; mime_type: string } | undefined;
      if (referenceImage) {
        const dataUrl = referenceImage.dataUrl;
        const base64 = dataUrl.includes(",") ? dataUrl.split(",", 2)[1] : dataUrl;
        if (!base64) {
          throw new Error("参照画像の読み込みに失敗しました");
        }
        referencePayload = {
          data: base64,
          mime_type: referenceImage.mimeType,
        };
      }

      const total = selectedIds.length;
      setImages([]);
      setImageProgress({ status: "running", total, completed: 0, message: null });

      const collected: any[] = [];
      const failures: string[] = [];

      for (let index = 0; index < selectedIds.length; index += 1) {
        const variationId = selectedIds[index];
        try {
          const response = await generateImages([variationId], referencePayload ?? null);
          const mapped = response.images.map((img) => ({
            ...img,
            absUrl: img.url.startsWith("http") ? img.url : `${API_BASE}${img.url}`,
          }));
          collected.push(...mapped);
          setImages((prev) => [...prev, ...mapped]);
        } catch (err) {
          const errorMessage = err instanceof Error ? err.message : String(err);
          failures.push(`${variationId}: ${errorMessage}`);
        }

        const completed = index + 1;
        setImageProgress((prev) => ({
          status: "running",
          total: prev.total || total,
          completed,
          message: null,
        }));
      }

      const successCount = collected.length;
      const failureCount = failures.length;

      if (failureCount > 0 && successCount === 0) {
        setImageProgress({
          status: "error",
          total,
          completed: total,
          message: "すべての画像生成に失敗しました",
        });
        setMessage("画像生成に失敗しました。設定や API キーを確認して再試行してください。");
      } else {
        setImageProgress({
          status: "complete",
          total,
          completed: total,
          message: failureCount > 0 ? "一部の画像生成でエラーが発生しました" : null,
        });
        if (failureCount > 0) {
          setMessage(`${successCount} 件の画像を生成しました (失敗: ${failureCount} 件)`);
        } else {
          setMessage(`${successCount} 件の画像を生成しました`);
        }
      }

      setImageFailures(failures);
    } catch (err) {
      setImageProgress({ status: "error", total: 0, completed: 0, message: (err as Error).message });
      setMessage((err as Error).message);
    } finally {
      setLoading(null);
    }
  };

  return (
    <div className="space-y-8">
      <section className="space-y-6">
        <div className="rounded-3xl border border-white/10 bg-white/5 p-6 shadow-xl shadow-primary-500/10">
          <h2 className="text-lg font-semibold text-white">バリエーション設定</h2>
          <p className="mt-1 text-sm text-slate-300">実現したいことと守るべき条件を入力し、候補となる変数を定義します。</p>
          <div className="mt-6 space-y-4">
            <label className="block text-sm font-medium text-slate-200">
              実現したいこと
              <textarea
                value={goal}
                onChange={(e) => setGoal(e.target.value)}
                rows={3}
                className="mt-2 w-full rounded-2xl border border-white/10 bg-slate-900/60 px-4 py-3 text-white placeholder:text-slate-500 focus:border-primary-400 focus:outline-none focus:ring-2 focus:ring-primary-500/40"
              />
            </label>
            <label className="block text-sm font-medium text-slate-200">
              守ってほしいこと
              <textarea
                value={constraints}
                onChange={(e) => setConstraints(e.target.value)}
                rows={3}
                className="mt-2 w-full rounded-2xl border border-white/10 bg-slate-900/60 px-4 py-3 text-white placeholder:text-slate-500 focus:border-primary-400 focus:outline-none focus:ring-2 focus:ring-primary-500/40"
              />
            </label>
            <div className="flex flex-wrap items-center gap-3">
              <label className="text-sm font-medium text-slate-200">
                LLM
                <select
                  value={llm}
                  onChange={(e) => setLlm(e.target.value as "gemini" | "openai")}
                  className="ml-3 rounded-full border border-white/10 bg-slate-900/60 px-4 py-2 text-sm text-white"
                >
                  <option value="gemini">Gemini</option>
                  <option value="openai">OpenAI</option>
                </select>
              </label>
              <label className="text-sm font-medium text-slate-200">
                生成件数
                <input
                  type="number"
                  min={1}
                  max={20}
                  value={variationCount}
                  onChange={(e) => {
                    const nextValue = Number(e.target.value);
                    if (Number.isNaN(nextValue)) {
                      setVariationCount(1);
                      return;
                    }
                    setVariationCount(Math.min(20, Math.max(1, Math.floor(nextValue))));
                  }}
                  className="ml-3 w-24 rounded-full border border-white/10 bg-slate-900/60 px-4 py-2 text-sm text-white [appearance:textfield] focus:border-primary-400 focus:outline-none"
                />
              </label>
              <button
                onClick={handleAutoVariables}
                disabled={loading === "variables"}
                className="rounded-full bg-gradient-to-r from-primary-500 to-primary-300 px-5 py-2 text-sm font-semibold text-slate-950 shadow-lg shadow-primary-500/20 transition hover:brightness-110 disabled:cursor-not-allowed disabled:opacity-60"
              >
                {loading === "variables" ? "抽出中..." : "変数を自動抽出"}
              </button>
            </div>
          </div>
        </div>
        <div className="rounded-3xl border border-white/10 bg-white/5 p-6 shadow-xl shadow-primary-500/10 space-y-4">
          <h3 className="text-base font-semibold text-white">変数リスト</h3>
          <p className="text-sm text-slate-300">行を追加して変数名や候補を編集できます。</p>
          <div className="space-y-3 max-h-80 overflow-y-auto pr-1">
            {variableRows.map((row, index) => (
              <div key={index} className="rounded-2xl border border-white/10 bg-slate-900/60 p-3">
                <div className="flex items-center gap-2">
                  <input
                    value={row.name}
                    onChange={(e) => handleVariableChange(index, "name", e.target.value)}
                    placeholder="変数名 (例: motif)"
                    className="flex-1 rounded-xl border border-white/10 bg-slate-950 px-3 py-2 text-sm text-white focus:border-primary-400 focus:outline-none"
                  />
                  <button
                    onClick={() => handleRemoveVariable(index)}
                    className="rounded-xl bg-white/10 px-3 py-2 text-xs text-slate-200 hover:bg-white/20"
                  >
                    削除
                  </button>
                </div>
                <textarea
                  value={row.values}
                  onChange={(e) => handleVariableChange(index, "values", e.target.value)}
                  placeholder="候補 (カンマ区切り)"
                  rows={2}
                  className="mt-2 w-full rounded-2xl border border-white/10 bg-slate-950 px-3 py-2 text-sm text-white focus:border-primary-400 focus:outline-none"
                />
              </div>
            ))}
          </div>
          <button
            onClick={handleAddVariableRow}
            className="w-full rounded-full border border-dashed border-white/20 py-2 text-sm text-slate-200 hover:border-primary-400 hover:text-white"
          >
            + 変数を追加
          </button>
        </div>
      </section>

      <section className="rounded-3xl border border-white/10 bg-white/5 p-6 shadow-xl shadow-primary-500/10">
        <h3 className="text-base font-semibold text-white">ユーザー追加バリエーション</h3>
        <p className="text-sm text-slate-300">LLM 生成とは別に固定したいアイデアがあればここで記述してください。</p>
        <div className="mt-4 space-y-3">
          {customRows.map((row, index) => (
            <div key={index} className="grid gap-2 rounded-2xl border border-white/10 bg-slate-900/60 p-4 lg:grid-cols-6">
              {[
                "motif",
                "style",
                "concept",
                "palette",
                "target_audience",
                "brand_tone",
              ].map((key) => (
                <input
                  key={key}
                  value={row[key] ?? ""}
                  onChange={(e) => handleCustomChange(index, key, e.target.value)}
                  placeholder={key}
                  className="rounded-xl border border-white/10 bg-slate-950 px-3 py-2 text-sm text-white focus:border-primary-400 focus:outline-none"
                />
              ))}
              <div className="lg:col-span-6">
                <button
                  onClick={() => handleRemoveCustom(index)}
                  className="w-full rounded-xl border border-white/10 py-2 text-xs text-slate-300 hover:bg-white/10"
                >
                  削除
                </button>
              </div>
            </div>
          ))}
          <button
            onClick={handleAddCustomRow}
            className="w-full rounded-full border border-dashed border-white/20 py-2 text-sm text-slate-200 hover:border-primary-400 hover:text-white"
          >
            + カスタムバリエーションを追加
          </button>
        </div>
      </section>

      <div className="flex flex-wrap items-center gap-3">
        <button
          onClick={handleGenerateVariations}
          disabled={loading === "variations"}
          className="rounded-full bg-gradient-to-r from-primary-500 via-primary-400 to-primary-600 px-6 py-3 text-base font-semibold text-slate-950 shadow-lg shadow-primary-500/30 transition hover:brightness-110 disabled:cursor-not-allowed disabled:opacity-60"
        >
          {loading === "variations" ? "生成中..." : "バリエーションを生成"}
        </button>
        {message && <span className="text-sm text-slate-300">{message}</span>}
      </div>

      {variations.length > 0 && (
        <section className="space-y-6">
          <h2 className="text-lg font-semibold text-white">バリエーション候補</h2>
          <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
            {variations.map((variation) => {
              const trace = variation.trace ?? {};
              const isSelected = selected[variation.id];
              return (
                <article
                  key={variation.id}
                  className={clsx(
                    "flex h-full flex-col justify-between rounded-3xl border p-5 shadow-lg transition",
                    isSelected
                      ? "border-primary-500/60 bg-primary-500/10"
                      : "border-white/10 bg-slate-900/60 hover:border-primary-400/60"
                  )}
                >
                  <div className="space-y-3">
                    <div className="flex items-center justify-between">
                      <h3 className="text-sm font-semibold text-white">{trace.concept || "コンセプト未設定"}</h3>
                      <label className="inline-flex items-center gap-2 text-xs text-slate-200">
                        <input
                          type="checkbox"
                          checked={!!isSelected}
                          onChange={(e) =>
                            setSelected((prev) => ({ ...prev, [variation.id]: e.target.checked }))
                          }
                          className="h-4 w-4 rounded border border-white/20 bg-slate-950"
                        />
                        生成対象
                      </label>
                    </div>
                    <p className="rounded-2xl bg-slate-950/60 p-3 text-xs text-slate-300">
                      {variation.prompt}
                    </p>
                    <dl className="grid grid-cols-2 gap-2 text-xs text-slate-300">
                      {Object.entries(trace)
                        .filter(([key]) => key !== "constraints" && key !== "extras")
                        .map(([key, value]) => (
                          <div key={key}>
                            <dt className="uppercase tracking-wide text-slate-400">{key}</dt>
                            <dd className="text-white">{String(value ?? "-")}</dd>
                          </div>
                        ))}
                    </dl>
                    {Array.isArray(trace.constraints) && trace.constraints.length > 0 && (
                      <div className="text-xs text-slate-300">
                        <span className="uppercase tracking-wide text-slate-400">constraints</span>
                        <p>{trace.constraints.join(", ")}</p>
                      </div>
                    )}
                  </div>
                </article>
              );
            })}
          </div>
          <div className="flex items-center gap-3">
            <button
              onClick={handleGenerateImages}
              disabled={loading === "images"}
              className="rounded-full bg-gradient-to-r from-primary-400 via-primary-500 to-primary-600 px-6 py-3 text-base font-semibold text-slate-950 shadow-lg shadow-primary-500/30 transition hover:brightness-110 disabled:cursor-not-allowed disabled:opacity-60"
            >
              {loading === "images" ? "生成中..." : "選択したバリエーションから画像生成"}
            </button>
            <span className="text-sm text-slate-400">{selectedIds.length} 件が選択されています</span>
          </div>
          {imageProgress.status !== "idle" && imageProgress.total > 0 && (
            <div className="rounded-3xl border border-white/10 bg-slate-900/60 p-4 text-xs text-slate-200">
              <div className="flex items-center justify-between text-[11px] uppercase tracking-wide">
                <span className="font-semibold text-white">画像生成の進捗</span>
                <span className="text-slate-300">
                  {imageProgress.completed}/{imageProgress.total} ({progressPercent}%)
                </span>
              </div>
              <div className="mt-2 h-2 w-full rounded-full bg-white/10">
                <div
                  className={clsx(
                    "h-2 rounded-full transition-all",
                    imageProgress.status === "error"
                      ? "bg-red-400"
                      : imageProgress.status === "complete"
                        ? "bg-emerald-400"
                        : "bg-primary-400"
                  )}
                  style={{ width: `${progressPercent}%` }}
                />
              </div>
              {imageProgress.message && (
                <p className="mt-2 text-[11px] text-amber-200">{imageProgress.message}</p>
              )}
            </div>
          )}
          {imageFailures.length > 0 && (
            <div className="rounded-3xl border border-red-400/40 bg-red-500/10 p-4 text-[11px] text-red-100">
              <p className="font-semibold text-red-200">失敗したバリエーション</p>
              <ul className="mt-2 space-y-1">
                {imageFailures.map((failure, index) => (
                  <li key={`${failure}-${index}`} className="list-inside list-disc">
                    {failure}
                  </li>
                ))}
              </ul>
            </div>
          )}
          <div className="rounded-3xl border border-white/10 bg-slate-900/60 p-5 text-sm text-slate-200">
            <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
              <div>
                <h3 className="text-sm font-semibold text-white">参照画像 (任意)</h3>
                <p className="mt-1 text-xs text-slate-400">
                  Gemini の Image-to-Image に渡す画像を 1 枚アップロードできます。
                </p>
              </div>
              <div className="flex items-center gap-3">
                <input
                  ref={fileInputRef}
                  type="file"
                  accept="image/*"
                  onChange={handleReferenceImageChange}
                  className="block w-full cursor-pointer text-xs text-slate-200 file:mr-3 file:rounded-full file:border-0 file:bg-primary-500 file:px-4 file:py-2 file:text-xs file:font-semibold file:text-slate-950 hover:file:brightness-110 md:w-64"
                />
                {referenceImage && (
                  <button
                    onClick={handleReferenceImageClear}
                    className="rounded-full border border-white/20 px-3 py-1 text-xs text-slate-200 hover:border-primary-400 hover:text-white"
                  >
                    クリア
                  </button>
                )}
              </div>
            </div>
            {referenceImage && (
              <div className="mt-4 flex items-center gap-4">
                <div className="h-20 w-20 overflow-hidden rounded-2xl border border-white/10">
                  <img src={referenceImage.dataUrl} alt="reference preview" className="h-full w-full object-cover" />
                </div>
                <div className="text-xs text-slate-300">
                  <p>{referenceImage.name}</p>
                  <p>{(referenceImage.size / 1024).toFixed(1)} KB</p>
                </div>
              </div>
            )}
          </div>
        </section>
      )}

      {images.length > 0 && (
        <section className="space-y-4">
          <h2 className="text-lg font-semibold text-white">生成された画像</h2>
          <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
            {images.map((img) => (
              <div key={img.id} className="overflow-hidden rounded-3xl border border-white/10 bg-slate-900/60">
                <img src={img.absUrl ?? img.url} alt={img.id} className="h-56 w-full object-cover" />
                <div className="p-4 text-xs text-slate-300">
                  <p>ID: {img.id}</p>
                  <p>Variation: {img.variation_id}</p>
                </div>
              </div>
            ))}
          </div>
        </section>
      )}
    </div>
  );
}
