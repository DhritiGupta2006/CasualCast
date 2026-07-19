import { useState, useRef, useMemo, useCallback } from "react";
import { motion } from "framer-motion";
import * as XLSX from "xlsx";
import jsPDF from "jspdf";
import html2canvas from "html2canvas-pro";
import {
  ComposedChart,
  LineChart,
  AreaChart,
  Line,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
  ReferenceLine,
} from "recharts";
import Header from "@/components/Header";
import Footer from "@/components/Footer";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import IncrementalityBadge from "@/components/IncrementalityBadge";
import BudgetSimulator from "@/components/BudgetSimulator";
import {
  Upload,
  FileSpreadsheet,
  ClipboardPaste,
  Download,
  Sparkles,
  TrendingUp,
  AlertTriangle,
  CheckCircle2,
  RefreshCw,
  Printer,
  Loader2,
} from "lucide-react";
import {
  type ForecastData,
  type ForecastOutput,
  EXPECTED_FIELDS,
  MIN_HISTORY_DAYS,
  generateSampleData,
  guessMapping,
  unmappedHeaders,
  unitConversionNotes,
  normalizeRows,
  aggregateByDate,
  parseCSV,
  toCSV,
  downloadFile,
  fmtMoney,
  todayStamp,
} from "@/lib/forecast";
import { runForecast as apiRunForecast, adaptForecastResponse, getInsights, ApiError, type InsightsResponse } from "@/lib/api";

function StatCard({ label, value, sub }: { label: string; value: string; sub?: string; color?: string }) {
  return (
    <div className="rounded-xl border border-border bg-card p-5">
      <div className="text-xs uppercase tracking-wider mb-2 text-muted-foreground/70 font-mono-data">{label}</div>
      <div className="text-2xl font-semibold font-mono-data text-foreground">{value}</div>
      {sub && <div className="text-xs mt-1 text-muted-foreground">{sub}</div>}
    </div>
  );
}

function ChartTooltip({ active, payload, label }: any) {
  if (!active || !payload?.length) return null;
  return (
    <div className="rounded-lg border border-border bg-popover px-3 py-2 text-xs font-mono-data">
      <div className="mb-1 text-muted-foreground/70">{label}</div>
      {payload.map((p: any) => (
        <div key={p.dataKey} style={{ color: p.color }}>
          {p.name}: {fmtMoney(p.value)}
        </div>
      ))}
    </div>
  );
}

export default function Forecast() {
  const [rawData, setRawData] = useState<Record<string, string>[] | null>(null);
  const [headers, setHeaders] = useState<string[]>([]);
  const [mapping, setMapping] = useState<Record<string, string> | null>(null);
  const [showMappingEditor, setShowMappingEditor] = useState(false);
  const [ignoredColumns, setIgnoredColumns] = useState<string[]>([]);
  const [unitNotes, setUnitNotes] = useState<string[]>([]);
  const [aggregationNote, setAggregationNote] = useState<string>("");
  const [pasteText, setPasteText] = useState("");
  const [forecast, setForecast] = useState<ForecastOutput | null>(null);
  const [dailyRows, setDailyRows] = useState<ForecastData[]>([]);
  const [chartView, setChartView] = useState<"combined" | "forecast" | "bands">("combined");
  const [error, setError] = useState("");
  const [dragOver, setDragOver] = useState(false);
  const [fileName, setFileName] = useState("");
  const [isExporting, setIsExporting] = useState(false);
  const [isForecasting, setIsForecasting] = useState(false);
  const [insights, setInsights] = useState<InsightsResponse | null>(null);
  const [insightsError, setInsightsError] = useState("");
  const fileInputRef = useRef<HTMLInputElement>(null);
  const reportRef = useRef<HTMLDivElement>(null);
  const chartCaptureRef = useRef<HTMLDivElement>(null);

  const handleParsedRows = (rows: Record<string, string>[], hdrs: string[]) => {
    setHeaders(hdrs);
    setRawData(rows);
    const guess = guessMapping(hdrs, rows);
    const complete = ["date", "spend", "revenue"].every((f) => guess[f]);
    setMapping(guess);
    setIgnoredColumns(unmappedHeaders(hdrs, guess));
    setUnitNotes(unitConversionNotes(guess));
    setShowMappingEditor(false);
    setForecast(null);
    setDailyRows([]);
    setInsights(null);
    setInsightsError("");
    setAggregationNote("");
    if (!complete) {
      // Extremely rare — only when neither the header name nor the column's
      // actual values (dates / numbers) give any signal. Offer the editor
      // instead of hard-blocking, since the rest of the data may still be usable.
      setError(
        "Couldn't confidently auto-detect every required column. Double-check the fields below, or use the column editor to point them at the right ones."
      );
      setShowMappingEditor(true);
    } else {
      setError("");
    }
  };

  const parseCSVText = (text: string) => {
    const { headers: hdrs, rows } = parseCSV(text);
    if (!hdrs.length) {
      setError("Could not parse this data. Make sure the first row contains headers (date, spend, revenue, sessions).");
      return;
    }
    setFileName("");
    handleParsedRows(rows, hdrs);
  };

  const handleFile = (file: File) => {
    setError("");
    setFileName(file.name);
    const isExcel = /\.(xlsx|xls)$/i.test(file.name);
    if (isExcel) {
      const reader = new FileReader();
      reader.onload = (e) => {
        try {
          const wb = XLSX.read(e.target?.result, { type: "array" });
          const sheet = wb.Sheets[wb.SheetNames[0]];
          const json = XLSX.utils.sheet_to_json<Record<string, string>>(sheet, { defval: "" });
          if (!json.length) {
            setError("The spreadsheet appears to be empty.");
            return;
          }
          handleParsedRows(json, Object.keys(json[0]));
        } catch {
          setError("Couldn't read that Excel file. Try exporting it as CSV instead.");
        }
      };
      reader.readAsArrayBuffer(file);
    } else {
      const reader = new FileReader();
      reader.onload = (e) => parseCSVText((e.target?.result as string) || "");
      reader.readAsText(file);
    }
  };

  const onDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(false);
    const file = e.dataTransfer.files?.[0];
    if (file) handleFile(file);
  }, []);

  const loadSample = () => {
    setError("");
    const sample = generateSampleData();
    setHeaders(["date", "spend", "revenue", "sessions"]);
    setRawData(sample as unknown as Record<string, string>[]);
    setMapping({ date: "date", spend: "spend", revenue: "revenue", sessions: "sessions" });
    setIgnoredColumns([]);
    setUnitNotes([]);
    setShowMappingEditor(false);
    setAggregationNote("");
    setFileName("sample-data.csv");
    setForecast(null);
    setDailyRows([]);
    setInsights(null);
    setInsightsError("");
  };

  const downloadTemplate = () => {
    const template = generateSampleData().slice(0, 10);
    downloadFile(toCSV(template, ["date", "spend", "revenue", "sessions"]), "causalcast_template.csv");
  };

  const startOver = () => {
    setRawData(null);
    setForecast(null);
    setDailyRows([]);
    setInsights(null);
    setInsightsError("");
    setFileName("");
    setPasteText("");
    setError("");
    setShowMappingEditor(false);
    setIgnoredColumns([]);
    setUnitNotes([]);
    setAggregationNote("");
  };

  const runForecast = async () => {
    if (!rawData || !mapping) return;
    const normalized: ForecastData[] = normalizeRows(rawData, mapping);
    const { data: daily, wasAggregated, rawRowCount } = aggregateByDate(normalized);
    if (wasAggregated) {
      setAggregationNote(
        `${rawRowCount} rows shared duplicate dates (e.g. multiple campaigns per day) — combined into ${daily.length} daily totals.`
      );
    } else {
      setAggregationNote("");
    }
    if (daily.length < MIN_HISTORY_DAYS) {
      setError(
        `Need at least ${MIN_HISTORY_DAYS} days of valid data — found ${daily.length}. Add more history or check your column mapping.`
      );
      return;
    }
    setError("");
    setInsights(null);
    setInsightsError("");
    setIsForecasting(true);
    try {
      // The forecast itself is computed server-side by core.forecasting.engine
      // (via POST /api/forecast) — this page never runs the Monte Carlo
      // simulation itself, so live-demo and batch-pipeline numbers can never
      // diverge on the same input.
      const res = await apiRunForecast(daily);
      setForecast(adaptForecastResponse(res));
      setDailyRows(daily);
    } catch (err) {
      const detail = err instanceof ApiError ? err.detail : null;
      setError(
        typeof detail === "string"
          ? detail
          : err instanceof ApiError && err.status === 0
            ? String(err.message)
            : "Couldn't generate a forecast for this data. Check the backend is running and try again."
      );
      return;
    } finally {
      setIsForecasting(false);
    }

    // Insights (incrementality, template summary) are a separate, non-blocking
    // call — the forecast/chart above should still render even if this fails.
    getInsights(daily)
      .then(setInsights)
      .catch((err: unknown) => {
        const detail = err instanceof ApiError ? err.detail : null;
        setInsightsError(typeof detail === "string" ? detail : "Couldn't load incrementality insights for this data.");
      });
  };

  const exportCSV = () => {
    if (!forecast) return;
    const csv = toCSV(forecast.results, ["date", "p10", "p50", "p90"]);
    downloadFile(csv, `forecast_${todayStamp()}.csv`);
  };

  const wait = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));

  /** Captures just the chart container for a given view, waiting for the
   *  chart type swap + recharts entrance animation to finish first. */
  const captureChartView = async (view: typeof chartView) => {
    setChartView(view);
    await wait(900); // recharts remounts the chart on type change; let its animation settle
    if (!chartCaptureRef.current) return null;
    const canvas = await html2canvas(chartCaptureRef.current, {
      backgroundColor: getComputedStyle(document.documentElement).getPropertyValue("--card").trim() || "#11151F",
      scale: 2,
    });
    return { dataUrl: canvas.toDataURL("image/png"), width: canvas.width, height: canvas.height };
  };

  const exportPDF = async () => {
    if (!forecast) return;
    setIsExporting(true);
    setError("");
    const originalView = chartView;
    try {
      // Capture every chart view up front so the report includes all of them,
      // not just whichever one happened to be on screen. Sequential on purpose:
      // each capture swaps the on-screen chart type, so they can't run in parallel.
      const combinedImg = await captureChartView("combined");
      const forecastImg = await captureChartView("forecast");
      const bandsImg = await captureChartView("bands");
      setChartView(originalView);

      // ---- derived numbers for the written sections ----
      const hist = forecast.historical;
      const firstDate = hist[0]?.date;
      const lastDate = hist[hist.length - 1]?.date;
      const totalRevenue = hist.reduce((a, d) => a + d.revenue, 0);
      const totalSpend = hist.reduce((a, d) => a + d.spend, 0);
      const totalSessions = hist.reduce((a, d) => a + d.sessions, 0);
      const avgDailyRevenue = totalRevenue / hist.length;
      const avgDailySpend = totalSpend / hist.length;
      const roas = totalSpend > 0 ? totalRevenue / totalSpend : null;
      const sumP10 = forecast.results.reduce((a, r) => a + r.p10, 0);
      const sumP50 = forecast.results.reduce((a, r) => a + r.p50, 0);
      const sumP90 = forecast.results.reduce((a, r) => a + r.p90, 0);
      const { avgP10, avgP50, avgP90, confidenceRange, trendDirection, slope } = forecast.stats;

      // ---- recommendations (dynamic, based on this dataset) ----
      const recommendations: string[] = [];
      if (hist.length < 14) {
        recommendations.push(
          `Add at least ${14 - hist.length} more day(s) of history to unlock weekday-seasonality modeling, which only activates at 14+ days of data.`
        );
      }
      if (hist.length < 30) {
        recommendations.push(
          "Longer history generally tightens the confidence bands. Consider extending to 30+ days of daily data if it's available."
        );
      }
      if (confidenceRange > 50) {
        recommendations.push(
          `The uncertainty band is wide (±${confidenceRange}%). This usually reflects high day-to-day volatility in the historical data — check for outlier days (promos, outages) that may be skewing it.`
        );
      }
      if (trendDirection === "down") {
        recommendations.push(
          "Revenue trend is declining over the historical window. Review recent changes in spend allocation, creative fatigue, or seasonality before committing budget to the P50 case."
        );
      } else if (trendDirection === "up") {
        recommendations.push(
          "Revenue trend is climbing. Confirm this reflects a durable pattern rather than a short-term promo spike before scaling budget off the P90 case."
        );
      } else {
        recommendations.push(
          "Revenue trend is roughly flat. If growth is a goal, this forecast reflects business-as-usual — it won't capture the effect of planned spend increases or new initiatives."
        );
      }
      if (roas !== null && roas < 1) {
        recommendations.push(
          `Blended ROAS over this period is ${roas.toFixed(2)}x — spend exceeded revenue. Confirm this is expected (e.g. brand campaigns) before using this forecast for budget planning.`
        );
      }
      if (unitNotes.length) {
        recommendations.push(`Unit conversions were applied automatically: ${unitNotes.join(" ")} Double-check these against your source platform.`);
      }
      if (ignoredColumns.length) {
        recommendations.push(
          `${ignoredColumns.length} column(s) were present but not used in this forecast (${ignoredColumns.slice(0, 6).join(", ")}${ignoredColumns.length > 6 ? ", …" : ""}). Consider a breakdown by these dimensions for deeper analysis.`
        );
      }
      recommendations.push("Re-run this forecast as new data comes in — weekly is a good cadence — to keep the range current.");

      // ---- build the PDF ----
      const pdf = new jsPDF({ orientation: "portrait", unit: "pt", format: "a4" });
      const pageW = pdf.internal.pageSize.getWidth();
      const pageH = pdf.internal.pageSize.getHeight();
      const margin = 40;
      const contentW = pageW - margin * 2;
      const navy: [number, number, number] = [23, 27, 38];
      const gray: [number, number, number] = [110, 118, 132];
      const green: [number, number, number] = [37, 158, 111];
      let y = margin;

      const ensureSpace = (needed: number) => {
        if (y + needed > pageH - 50) {
          pdf.addPage();
          y = margin;
        }
      };

      const heading = (text: string) => {
        ensureSpace(28);
        pdf.setFont("helvetica", "bold");
        pdf.setFontSize(13);
        pdf.setTextColor(...navy);
        pdf.text(text, margin, y);
        y += 8;
        pdf.setDrawColor(...green);
        pdf.setLineWidth(1.2);
        pdf.line(margin, y, margin + 36, y);
        y += 16;
      };

      const paragraph = (text: string, size = 10, color: [number, number, number] = navy) => {
        pdf.setFont("helvetica", "normal");
        pdf.setFontSize(size);
        pdf.setTextColor(...color);
        const lines = pdf.splitTextToSize(text, contentW);
        ensureSpace(lines.length * (size * 1.4) + 4);
        pdf.text(lines, margin, y);
        y += lines.length * (size * 1.4) + 4;
      };

      const bulletList = (items: string[]) => {
        pdf.setFont("helvetica", "normal");
        pdf.setFontSize(10);
        items.forEach((item) => {
          const lines = pdf.splitTextToSize(item, contentW - 14);
          ensureSpace(lines.length * 14 + 6);
          pdf.setTextColor(...green);
          pdf.text("•", margin, y);
          pdf.setTextColor(...navy);
          pdf.text(lines, margin + 14, y);
          y += lines.length * 14 + 6;
        });
      };

      const kvRow = (label: string, value: string) => {
        ensureSpace(16);
        pdf.setFont("helvetica", "normal");
        pdf.setFontSize(10);
        pdf.setTextColor(...gray);
        pdf.text(label, margin, y);
        pdf.setFont("helvetica", "bold");
        pdf.setTextColor(...navy);
        pdf.text(value, margin + 180, y);
        y += 16;
      };

      const addImage = (capture: { dataUrl: string; width: number; height: number } | null, caption: string) => {
        if (!capture) return;
        const ratio = capture.width ? capture.height / capture.width : 0.5;
        const imgW = contentW;
        const imgH = imgW * ratio;
        ensureSpace(imgH + 24);
        pdf.setFont("helvetica", "bold");
        pdf.setFontSize(10.5);
        pdf.setTextColor(...navy);
        pdf.text(caption, margin, y);
        y += 10;
        pdf.addImage(capture.dataUrl, "PNG", margin, y, imgW, imgH);
        y += imgH + 20;
      };

      // Cover / title
      pdf.setFont("helvetica", "bold");
      pdf.setFontSize(19);
      pdf.setTextColor(...navy);
      pdf.text("CausalCast — Revenue Forecast Report", margin, y);
      y += 18;
      pdf.setDrawColor(...green);
      pdf.setLineWidth(2);
      pdf.line(margin, y, pageW - margin, y);
      y += 20;
      paragraph(
        `Generated ${todayStamp()} · ${fileName || "Pasted data"} · ${hist.length} days of history → ${forecast.results.length}-day forecast`,
        9.5,
        gray
      );
      y += 6;

      // Data summary
      heading("Data Summary");
      kvRow("Date range", `${firstDate} to ${lastDate} (${hist.length} days)`);
      kvRow("Total spend", fmtMoney(totalSpend));
      kvRow("Total revenue", fmtMoney(totalRevenue));
      kvRow("Avg daily spend", fmtMoney(avgDailySpend));
      kvRow("Avg daily revenue", fmtMoney(avgDailyRevenue));
      if (totalSessions > 0) kvRow("Total sessions", totalSessions.toLocaleString());
      if (roas !== null) kvRow("Blended ROAS", `${roas.toFixed(2)}x`);
      if (aggregationNote) kvRow("Aggregation", aggregationNote);
      y += 6;

      // Key findings
      heading("Key Findings");
      bulletList([
        `Trend is reading ${trendDirection === "up" ? "upward" : trendDirection === "down" ? "downward" : "roughly flat"} (${slope >= 0 ? "+" : ""}${slope.toFixed(1)}/day) based on the historical window provided.`,
        `Expected case (P50): ${fmtMoney(avgP50)}/day on average, ${fmtMoney(sumP50)} projected over the next ${forecast.results.length} days.`,
        `Downside case (P10): ${fmtMoney(avgP10)}/day on average, ${fmtMoney(sumP10)} over ${forecast.results.length} days — budget against this.`,
        `Upside case (P90): ${fmtMoney(avgP90)}/day on average, ${fmtMoney(sumP90)} over ${forecast.results.length} days — treat as a stretch outcome, not a plan.`,
        `Confidence range is ±${confidenceRange}% (P90–P10 spread relative to P50).`,
        "This forecast reflects historical patterns only — it does not account for planned spend changes, promotions, or external shocks.",
      ]);
      y += 4;

      // Charts
      heading("Forecast Charts");
      addImage(combinedImg, "Combined — Historical vs. Forecast");
      addImage(forecastImg, "Forecast Only — P10 / P50 / P90");
      addImage(bandsImg, "Confidence Bands");

      // Recommendations
      heading("Recommendations for Improvement");
      bulletList(recommendations);

      // Methodology footnote
      y += 4;
      paragraph(
        `Methodology: Monte Carlo simulation (${1000} iterations) over a ${forecast.results.length}-day horizon, combining a linear trend, weekday seasonality (when 14+ days of history are available), and noise drawn from historical residual volatility. This is a statistical projection, not a guarantee.`,
        8.5,
        gray
      );

      // Page numbers
      const pageCount = pdf.getNumberOfPages();
      for (let i = 1; i <= pageCount; i++) {
        pdf.setPage(i);
        pdf.setFont("helvetica", "normal");
        pdf.setFontSize(8.5);
        pdf.setTextColor(...gray);
        pdf.text(`Page ${i} of ${pageCount}`, pageW - margin - 60, pageH - 24);
        pdf.text("CausalCast", margin, pageH - 24);
      }

      pdf.save(`forecast_report_${todayStamp()}.pdf`);
    } catch (err) {
      console.error("PDF export failed:", err);
      setChartView(originalView);
      setError("PDF export failed. Try the CSV export or print the page instead.");
    } finally {
      setIsExporting(false);
    }
  };

  const combinedChartData = useMemo(() => {
    if (!forecast) return [];
    const hist = forecast.historical.map((d) => ({ date: d.date, historical: d.revenue }));
    const fut = forecast.results.map((r) => ({ date: r.date, p10: r.p10, p50: r.p50, p90: r.p90 }));
    return [...hist, ...fut];
  }, [forecast]);

  const hasData = !!rawData;

  return (
    <div className="min-h-screen bg-background">
      <Header />
      <div className="container max-w-5xl mx-auto py-12">
        <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.5 }} className="mb-10">
          <div className="text-xs uppercase tracking-wider mb-3 text-primary font-mono-data">Forecaster</div>
          <h1 className="text-3xl mb-3 text-foreground">Revenue forecaster</h1>
          <p className="text-sm max-w-xl text-muted-foreground">
            Upload at least {MIN_HISTORY_DAYS} days of daily spend and revenue history. Column mapping happens
            locally in your browser; the forecast itself is computed by the CausalCast backend so the numbers you
            see here always match a batch run of the same data.
          </p>
        </motion.div>

        {!hasData && (
          <div className="grid md:grid-cols-2 gap-5">
            <div
              onDragOver={(e) => {
                e.preventDefault();
                setDragOver(true);
              }}
              onDragLeave={() => setDragOver(false)}
              onDrop={onDrop}
              onClick={() => fileInputRef.current?.click()}
              className={`rounded-xl border-2 border-dashed p-10 flex flex-col items-center justify-center text-center cursor-pointer transition-colors bg-card ${
                dragOver ? "border-primary" : "border-border"
              }`}
            >
              <Upload size={26} className="text-primary mb-3" />
              <div className="text-sm font-medium mb-1 text-foreground">Drop a CSV or Excel file</div>
              <div className="text-xs text-muted-foreground/70">or click to browse · date, spend, revenue, sessions</div>
              <input
                ref={fileInputRef}
                type="file"
                accept=".csv,.xlsx,.xls"
                className="hidden"
                onChange={(e) => e.target.files?.[0] && handleFile(e.target.files[0])}
              />
            </div>

            <div className="rounded-xl border border-border bg-card p-6">
              <div className="flex items-center gap-2 mb-3">
                <ClipboardPaste size={16} className="text-primary" />
                <span className="text-sm font-medium text-foreground">Or paste CSV data</span>
              </div>
              <Textarea
                value={pasteText}
                onChange={(e) => setPasteText(e.target.value)}
                placeholder={"date,spend,revenue,sessions\n2026-06-01,900,4300,2100\n..."}
                rows={5}
                className="w-full text-xs mb-3 font-mono-data resize-none"
              />
              <Button
                onClick={() => pasteText.trim() && parseCSVText(pasteText)}
                disabled={!pasteText.trim()}
                className="w-full font-medium"
              >
                Parse pasted data
              </Button>
            </div>

            <div className="md:col-span-2 flex flex-wrap gap-3">
              <Button variant="outline" onClick={loadSample} className="gap-2">
                <Sparkles size={14} className="text-accent" /> Load sample data
              </Button>
              <Button variant="outline" onClick={downloadTemplate} className="gap-2">
                <FileSpreadsheet size={14} className="text-secondary" /> Download CSV template
              </Button>
            </div>
          </div>
        )}

        {error && (
          <div className="mt-5 rounded-lg border border-destructive/40 bg-destructive/10 px-4 py-3 flex items-start gap-2 text-sm text-destructive">
            <AlertTriangle size={16} className="shrink-0 mt-0.5" />
            {error}
          </div>
        )}

        {hasData && (
          <div className="mt-4">
            <div className="flex items-center justify-between flex-wrap gap-3 mb-6">
              <div className="text-sm flex items-center gap-2 text-muted-foreground">
                <CheckCircle2 size={15} className="text-primary" />
                {fileName || "Pasted data"} loaded · {rawData!.length} rows
              </div>
              <Button variant="outline" size="sm" onClick={startOver} className="gap-1.5">
                <RefreshCw size={12} /> Start over
              </Button>
            </div>

            {mapping && (
              <div className="rounded-xl border border-border bg-card p-5 mb-6">
                <div className="flex items-center justify-between flex-wrap gap-2 mb-1">
                  <div className="text-sm font-medium text-foreground flex items-center gap-2">
                    <CheckCircle2 size={15} className="text-primary" />
                    Columns detected automatically
                  </div>
                  <button
                    onClick={() => setShowMappingEditor((v) => !v)}
                    className="text-xs text-primary hover:underline"
                  >
                    {showMappingEditor ? "Hide" : "Adjust columns"}
                  </button>
                </div>
                <div className="text-xs text-muted-foreground/80 font-mono-data flex flex-wrap gap-x-4 gap-y-1 mt-2">
                  {EXPECTED_FIELDS.map((field) => (
                    <span key={field}>
                      {field}: <span className="text-foreground">{mapping[field] || "—"}</span>
                    </span>
                  ))}
                </div>
                {ignoredColumns.length > 0 && (
                  <div className="text-xs text-muted-foreground/60 mt-2">
                    Ignored columns (not needed for the forecast): {ignoredColumns.join(", ")}
                  </div>
                )}
                {unitNotes.map((note) => (
                  <div key={note} className="text-xs text-muted-foreground/60 mt-1">
                    {note}
                  </div>
                ))}

                {showMappingEditor && (
                  <div className="grid sm:grid-cols-2 gap-4 mt-4 pt-4 border-t border-border">
                    {EXPECTED_FIELDS.map((field) => (
                      <div key={field}>
                        <label className="text-xs uppercase tracking-wider block mb-1.5 text-muted-foreground/70 font-mono-data">
                          {field} {field !== "sessions" && <span className="text-destructive">*</span>}
                        </label>
                        <select
                          value={mapping[field] || ""}
                          onChange={(e) => {
                            const next = { ...mapping, [field]: e.target.value };
                            setMapping(next);
                            setIgnoredColumns(unmappedHeaders(headers, next));
                            setUnitNotes(unitConversionNotes(next));
                          }}
                          className="w-full text-sm rounded-md px-3 py-2 outline-none bg-input border border-border text-foreground"
                        >
                          <option value="">— none —</option>
                          {headers.map((h) => (
                            <option key={h} value={h}>
                              {h}
                            </option>
                          ))}
                        </select>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}

            {!forecast && (
              <Button
                onClick={runForecast}
                size="lg"
                disabled={!mapping?.date || !mapping?.spend || !mapping?.revenue || isForecasting}
                className="gap-2 mb-2 font-medium"
              >
                {isForecasting ? <Loader2 size={15} className="animate-spin" /> : <TrendingUp size={15} />}
                {isForecasting ? "Generating forecast…" : "Generate forecast"}
              </Button>
            )}
            {aggregationNote && !forecast && (
              <div className="text-xs text-muted-foreground/70 mb-6">{aggregationNote}</div>
            )}
            {aggregationNote && forecast && (
              <div className="text-xs text-muted-foreground/70 mb-4 -mt-4">{aggregationNote}</div>
            )}

            {forecast && (
              <div ref={reportRef}>
                <div className="grid sm:grid-cols-4 gap-4 mb-8">
                  <StatCard label="Downside · P10" value={fmtMoney(forecast.stats.avgP10)} sub="avg / day" />
                  <StatCard label="Expected · P50" value={fmtMoney(forecast.stats.avgP50)} sub="avg / day" />
                  <StatCard label="Upside · P90" value={fmtMoney(forecast.stats.avgP90)} sub="avg / day" />
                  <StatCard label="Confidence range" value={`±${forecast.stats.confidenceRange}%`} sub="P90–P10 spread" />
                </div>

                <div className="flex gap-2 mb-4">
                  {(
                    [
                      ["combined", "Combined"],
                      ["forecast", "Forecast only"],
                      ["bands", "Confidence bands"],
                    ] as const
                  ).map(([key, label]) => (
                    <button
                      key={key}
                      onClick={() => setChartView(key)}
                      className={`text-xs px-3.5 py-1.5 rounded-md border transition-colors ${
                        chartView === key
                          ? "border-primary text-primary bg-primary/10"
                          : "border-border text-muted-foreground"
                      }`}
                    >
                      {label}
                    </button>
                  ))}
                </div>

                <div ref={chartCaptureRef} className="rounded-xl border border-border bg-card p-4 mb-8">
                  <ResponsiveContainer width="100%" height={340}>
                    {chartView === "bands" ? (
                      <AreaChart data={forecast.results}>
                        <CartesianGrid stroke="var(--border)" strokeDasharray="3 3" />
                        <XAxis dataKey="date" tick={{ fill: "var(--muted-foreground)", fontSize: 10 }} tickLine={false} axisLine={{ stroke: "var(--border)" }} />
                        <YAxis
                          tick={{ fill: "var(--muted-foreground)", fontSize: 10 }}
                          tickLine={false}
                          axisLine={{ stroke: "var(--border)" }}
                          tickFormatter={(v) => `$${(v / 1000).toFixed(0)}k`}
                        />
                        <Tooltip content={<ChartTooltip />} />
                        <Area type="monotone" dataKey="p90" name="P90" stroke="var(--chart-3)" fill="var(--chart-3)" fillOpacity={0.08} />
                        <Area type="monotone" dataKey="p50" name="P50" stroke="var(--chart-1)" fill="var(--chart-1)" fillOpacity={0.18} />
                        <Area type="monotone" dataKey="p10" name="P10" stroke="var(--chart-2)" fill="var(--background)" fillOpacity={0.9} />
                      </AreaChart>
                    ) : chartView === "forecast" ? (
                      <LineChart data={forecast.results}>
                        <CartesianGrid stroke="var(--border)" strokeDasharray="3 3" />
                        <XAxis dataKey="date" tick={{ fill: "var(--muted-foreground)", fontSize: 10 }} tickLine={false} axisLine={{ stroke: "var(--border)" }} />
                        <YAxis
                          tick={{ fill: "var(--muted-foreground)", fontSize: 10 }}
                          tickLine={false}
                          axisLine={{ stroke: "var(--border)" }}
                          tickFormatter={(v) => `$${(v / 1000).toFixed(0)}k`}
                        />
                        <Tooltip content={<ChartTooltip />} />
                        <Legend wrapperStyle={{ fontSize: 11, color: "var(--muted-foreground)" }} />
                        <Line type="monotone" dataKey="p10" name="P10" stroke="var(--chart-2)" strokeWidth={1.5} dot={false} strokeDasharray="4 3" />
                        <Line type="monotone" dataKey="p50" name="P50" stroke="var(--chart-1)" strokeWidth={2.5} dot={false} />
                        <Line type="monotone" dataKey="p90" name="P90" stroke="var(--chart-3)" strokeWidth={1.5} dot={false} strokeDasharray="4 3" />
                      </LineChart>
                    ) : (
                      <ComposedChart data={combinedChartData}>
                        <CartesianGrid stroke="var(--border)" strokeDasharray="3 3" />
                        <XAxis dataKey="date" tick={{ fill: "var(--muted-foreground)", fontSize: 10 }} tickLine={false} axisLine={{ stroke: "var(--border)" }} />
                        <YAxis
                          tick={{ fill: "var(--muted-foreground)", fontSize: 10 }}
                          tickLine={false}
                          axisLine={{ stroke: "var(--border)" }}
                          tickFormatter={(v) => `$${(v / 1000).toFixed(0)}k`}
                        />
                        <Tooltip content={<ChartTooltip />} />
                        <Legend wrapperStyle={{ fontSize: 11, color: "var(--muted-foreground)" }} />
                        <ReferenceLine x={forecast.historical[forecast.historical.length - 1].date} stroke="var(--muted-foreground)" strokeDasharray="4 4" />
                        <Line type="monotone" dataKey="historical" name="Historical" stroke="var(--foreground)" strokeWidth={2} dot={false} connectNulls />
                        <Line type="monotone" dataKey="p50" name="Forecast (P50)" stroke="var(--chart-1)" strokeWidth={2.5} dot={false} connectNulls />
                        <Line type="monotone" dataKey="p10" name="P10" stroke="var(--chart-2)" strokeWidth={1} dot={false} strokeDasharray="3 3" connectNulls />
                        <Line type="monotone" dataKey="p90" name="P90" stroke="var(--chart-3)" strokeWidth={1} dot={false} strokeDasharray="3 3" connectNulls />
                      </ComposedChart>
                    )}
                  </ResponsiveContainer>
                </div>

                <div className="rounded-xl border border-border bg-card p-6 mb-8">
                  <div className="text-sm font-medium mb-3 text-foreground">Insights</div>
                  <ul className="text-sm space-y-2 text-muted-foreground">
                    <li>
                      • Trend is reading{" "}
                      <strong className="text-foreground">
                        {forecast.stats.trendDirection === "up"
                          ? "upward"
                          : forecast.stats.trendDirection === "down"
                          ? "downward"
                          : "roughly flat"}
                      </strong>{" "}
                      based on the historical window provided.
                    </li>
                    <li>
                      • The P90–P10 spread is <strong className="text-foreground">±{forecast.stats.confidenceRange}%</strong> of
                      the expected value — budget for the P10 case, treat P90 as a stretch outcome.
                    </li>
                    <li>
                      • This forecast reflects historical patterns only — it does not account for planned spend
                      changes, promotions, or external shocks.
                    </li>
                    {insights?.anomaly_count ? (
                      <li>
                        • <strong className="text-foreground">{insights.anomaly_count}</strong> anomalous day(s) were
                        detected in the input data and may be widening the confidence bands.
                      </li>
                    ) : null}
                  </ul>
                  {insights?.template_summary && (
                    <div className="text-xs text-muted-foreground/70 mt-4 pt-4 border-t border-border">
                      {insights.template_summary}
                    </div>
                  )}
                  {insights?.warnings && insights.warnings.length > 0 && (
                    <div className="text-xs text-muted-foreground/70 mt-3 space-y-1">
                      {insights.warnings.map((w, i) => (
                        <div key={i}>⚠ {w}</div>
                      ))}
                    </div>
                  )}
                  {insightsError && <div className="text-xs text-muted-foreground/60 mt-4 pt-4 border-t border-border">{insightsError}</div>}
                </div>

                <div className="grid md:grid-cols-2 gap-6 mb-8">
                  <IncrementalityBadge
                    incrementality={insights?.incrementality ?? null}
                    disclaimer={insights?.incrementality_disclaimer}
                  />
                  <div className="rounded-xl border border-border bg-card p-5 flex flex-col justify-center">
                    <div className="text-xs uppercase tracking-wider mb-2 text-muted-foreground/70 font-mono-data">
                      Channels seen
                    </div>
                    <div className="text-sm text-foreground">
                      {insights?.channel_groups?.length ? insights.channel_groups.join(", ") : "No channel column provided"}
                    </div>
                  </div>
                </div>

                {dailyRows.length > 0 && <BudgetSimulator rows={dailyRows} className="mb-8" />}
              </div>
            )}

            {forecast && (
              <div className="flex flex-wrap gap-3">
                <Button onClick={exportCSV} className="gap-2 font-medium">
                  <Download size={14} /> Export as CSV
                </Button>
                <Button onClick={exportPDF} variant="outline" disabled={isExporting} className="gap-2">
                  {isExporting ? <Loader2 size={14} className="animate-spin" /> : <Printer size={14} />}
                  {isExporting ? "Building PDF…" : "Export as PDF"}
                </Button>
              </div>
            )}
          </div>
        )}
      </div>
      <Footer />
    </div>
  );
}
