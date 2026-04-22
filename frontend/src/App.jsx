import { useEffect, useRef, useState } from "react";
import { getDashboardForApp } from "./lib/api";

// ─── Google Fonts ───────────────────────────────────────────────────────────
const FONTS = `@import url('https://fonts.googleapis.com/css2?family=Syne:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600&display=swap');`;

// ─── Formatadores ───────────────────────────────────────────────────────────
const fR = (v, compact = false) => {
  if (v == null) return "n/d";
  const abs = Math.abs(v);
  const neg = v < 0;
  let s;
  if (compact) {
    if (abs >= 1e6) s = `R$\u00A0${(abs / 1e6).toFixed(2).replace(".", ",")}MM`;
    else if (abs >= 1e3) s = `R$\u00A0${(abs / 1e3).toFixed(0)}K`;
    else s = `R$\u00A0${abs.toFixed(0)}`;
  } else {
    s = "R$\u00A0" + abs.toLocaleString("pt-BR", { minimumFractionDigits: 0, maximumFractionDigits: 0 });
  }
  return neg ? `−${s}` : s;
};
const fP = (v, d = 1) => v == null ? "n/d" : `${(v * 100).toFixed(d)}%`;
const fDelta = (v) => {
  if (v == null) return { text: "n/d", up: null };
  const up = v >= 0;
  return { text: `${up ? "▲" : "▼"} ${Math.abs(v * 100).toFixed(1)}%`, up };
};

// ─── Paleta ─────────────────────────────────────────────────────────────────
const C = {
  bg: "#080C14", surface: "#0D1421", surface2: "#111B2C",
  border: "rgba(255,255,255,0.06)", border2: "rgba(255,255,255,0.10)",
  text: "#E8EDF5", muted: "#64748B", dim: "rgba(255,255,255,0.55)",
  accent: "#3B82F6", indigo: "#6366F1", green: "#10B981", red: "#EF4444",
  amber: "#F59E0B", purple: "#8B5CF6",
};

const saude_cfg = {
  ok: { cor: C.green, bg: "rgba(16,185,129,0.10)", label: "Saudável" },
  atencao: { cor: C.amber, bg: "rgba(245,158,11,0.10)", label: "Atenção" },
  critico: { cor: C.red, bg: "rgba(239,68,68,0.10)", label: "Crítico" },
};

const periodoLabel = (periodo) => (periodo === "mes" ? "Mês" : "Trimestre");

// ─── Bar chart SVG ──────────────────────────────────────────────────────────
function BarChart({ data, height = 120, color = C.accent }) {
  const max = Math.max(...data.flatMap((d) => [d.v1 || 0, d.v2 || 0])) * 1.1 || 1;
  const W = 100;
  const gap = data.length > 0 ? W / data.length : W;
  const barW = Math.min(16, gap * 0.5);
  return (
    <svg viewBox={`0 0 100 ${height}`} style={{ width: "100%", height }} preserveAspectRatio="none">
      {data.map((d, i) => {
        const x = gap * i + gap * 0.5;
        const h1 = ((d.v1 || 0) / max) * (height - 20);
        return (
          <g key={i}>
            <rect x={x - barW / 2} y={height - 16 - h1} width={barW} height={h1} fill={color} rx="2" opacity="0.9" />
            <text x={x} y={height - 2} textAnchor="middle" fontSize="5.5" fill={C.muted} fontFamily="JetBrains Mono">
              {d.label}
            </text>
          </g>
        );
      })}
    </svg>
  );
}

// ─── Sparkline SVG ──────────────────────────────────────────────────────────
function Sparkline({ values, color = C.accent, height = 32 }) {
  if (!values || values.length < 2) return null;
  const max = Math.max(...values);
  const min = Math.min(...values);
  const range = max - min || 1;
  const W = 80;
  const pts = values.map((v, i) => {
    const x = (i / (values.length - 1)) * W;
    const y = height - ((v - min) / range) * (height - 4) - 2;
    return `${x},${y}`;
  });
  const last = pts[pts.length - 1].split(",");
  return (
    <svg viewBox={`0 0 ${W} ${height}`} style={{ width: 80, height }} preserveAspectRatio="none">
      <polyline points={pts.join(" ")} fill="none" stroke={color} strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
      <circle cx={last[0]} cy={last[1]} r="2.5" fill={color} />
    </svg>
  );
}

// ─── Drawer Unidade ─────────────────────────────────────────────────────────
function UnitDrawer({ unit, convRede, onClose }) {
  if (!unit) return null;
  const cfg = saude_cfg[unit.saude] || saude_cfg.ok;
  const periodoTexto = unit.periodo === "mes" ? "Mês corrente" : "Trimestre corrente";
  return (
    <div style={{ position: "fixed", inset: 0, zIndex: 200, display: "flex", justifyContent: "flex-end" }}>
      <div onClick={onClose} style={{ position: "absolute", inset: 0, background: "rgba(0,0,0,0.6)", backdropFilter: "blur(4px)" }} />
      <div style={{
        position: "relative", zIndex: 1, width: "min(480px, 100%)", height: "100vh",
        background: C.surface, borderLeft: `1px solid ${C.border2}`,
        display: "flex", flexDirection: "column", overflow: "hidden",
        animation: "slideIn 0.25s ease-out",
      }}>
        <style>{`@keyframes slideIn { from { transform: translateX(100%) } to { transform: translateX(0) } }`}</style>
        <div style={{ padding: "20px 24px 16px", borderBottom: `1px solid ${C.border}`, background: C.surface2 }}>
          <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 8 }}>
            <span style={{ fontSize: 11, fontFamily: "JetBrains Mono", color: C.muted, letterSpacing: "0.1em", textTransform: "uppercase" }}>Análise de Unidade</span>
            <button onClick={onClose} style={{ background: "rgba(255,255,255,0.05)", border: `1px solid ${C.border}`, color: C.dim, width: 28, height: 28, borderRadius: 8, cursor: "pointer", fontSize: 14 }}>✕</button>
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <h2 style={{ fontSize: 20, fontFamily: "Syne", fontWeight: 700, color: C.text, margin: 0 }}>{unit.UNIDADE}</h2>
            <span style={{ fontSize: 10, fontWeight: 700, padding: "3px 8px", borderRadius: 5, background: cfg.bg, color: cfg.cor, border: `1px solid ${cfg.cor}30`, fontFamily: "JetBrains Mono" }}>
              {cfg.label.toUpperCase()}
            </span>
          </div>
          <p style={{ fontSize: 11, color: C.muted, margin: "4px 0 0", fontFamily: "JetBrains Mono" }}>{periodoTexto}</p>
        </div>

        <div style={{ padding: "20px 24px", overflowY: "auto", flex: 1 }}>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10, marginBottom: 20 }}>
            {[
              { label: "Cirurgias", val: unit.cirurgias ?? "n/d", sub: periodoTexto },
              { label: "Receita Bruta", val: fR(unit.rb, true) },
              { label: "Lucro Líquido", val: fR(unit.ll, true), sub: unit.mg_ll != null ? fP(unit.mg_ll) + " margem" : null, cor: (unit.ll || 0) >= 0 ? C.green : C.red },
              { label: "Mg. EBITDA", val: unit.mg_ebitda != null ? fP(unit.mg_ebitda) : "n/d", cor: (unit.mg_ebitda || 0) >= 0.20 ? C.green : C.amber },
              { label: "Conversão", val: unit.conv != null ? fP(unit.conv) : "n/d", sub: convRede != null ? `Rede: ${fP(convRede)}` : null, cor: (unit.conv || 0) >= 0.40 ? C.green : C.red },
              { label: "Ticket Médio", val: unit.ticket != null ? fR(unit.ticket) : "n/d", sub: "por cirurgia" },
            ].map((k) => (
              <div key={k.label} style={{ padding: 14, borderRadius: 10, background: C.bg, border: `1px solid ${C.border}` }}>
                <div style={{ fontSize: 9, fontFamily: "JetBrains Mono", color: C.muted, textTransform: "uppercase", letterSpacing: "0.08em", marginBottom: 6 }}>{k.label}</div>
                <div style={{ fontSize: 18, fontFamily: "Syne", fontWeight: 700, color: k.cor || C.text }}>{k.val}</div>
                {k.sub && <div style={{ fontSize: 10, color: C.muted, marginTop: 3 }}>{k.sub}</div>}
              </div>
            ))}
            <div style={{ padding: 14, borderRadius: 10, background: cfg.bg, border: `1px solid ${cfg.cor}30` }}>
              <div style={{ fontSize: 9, fontFamily: "JetBrains Mono", color: C.muted, textTransform: "uppercase", letterSpacing: "0.08em", marginBottom: 6 }}>Status</div>
              <div style={{ fontSize: 18, fontFamily: "Syne", fontWeight: 700, color: cfg.cor }}>{cfg.label}</div>
              <div style={{ fontSize: 10, color: C.muted, marginTop: 3 }}>{periodoTexto}</div>
            </div>
          </div>

          <div style={{ marginBottom: 20 }}>
            <h3 style={{ fontSize: 11, fontFamily: "JetBrains Mono", color: C.muted, textTransform: "uppercase", letterSpacing: "0.08em", marginBottom: 12 }}>Diagnóstico</h3>
            <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
              {[
                { label: "Margem vs rede", ok: (unit.mg_ll || 0) >= 0.20, texto: (unit.mg_ll || 0) >= 0.20 ? `Margem LL ${fP(unit.mg_ll)} — acima de 20%` : `Margem LL ${fP(unit.mg_ll)} — abaixo do mínimo de 20%` },
                { label: "Conversão", ok: (unit.conv || 0) >= 0.40, texto: (unit.conv || 0) >= 0.40 ? `Conversão ${fP(unit.conv)} — dentro do esperado` : `Conversão ${fP(unit.conv)} — ${unit.conv != null ? "abaixo do benchmark de 40%" : "sem dados"}` },
                { label: "Receita bruta", ok: (unit.rb || 0) >= 400000, texto: (unit.rb || 0) >= 400000 ? `R$ ${((unit.rb || 0) / 1000).toFixed(0)}K — volume adequado` : `R$ ${((unit.rb || 0) / 1000).toFixed(0)}K — abaixo do limiar de R$ 400K/trim.` },
              ].map((d) => (
                <div key={d.label} style={{ display: "flex", gap: 10, padding: "10px 12px", borderRadius: 8, background: d.ok ? "rgba(16,185,129,0.06)" : "rgba(239,68,68,0.06)", border: `1px solid ${d.ok ? "rgba(16,185,129,0.15)" : "rgba(239,68,68,0.15)"}` }}>
                  <span style={{ fontSize: 14 }}>{d.ok ? "✓" : "✗"}</span>
                  <div>
                    <div style={{ fontSize: 10, fontFamily: "JetBrains Mono", fontWeight: 600, color: d.ok ? C.green : C.red, marginBottom: 2 }}>{d.label}</div>
                    <div style={{ fontSize: 11, color: C.dim, lineHeight: 1.5 }}>{d.texto}</div>
                  </div>
                </div>
              ))}
            </div>
          </div>

          <div style={{ padding: "10px 12px", borderRadius: 8, background: "rgba(99,102,241,0.06)", border: "1px solid rgba(99,102,241,0.15)" }}>
            <p style={{ margin: 0, fontSize: 10, color: C.muted, lineHeight: 1.6, fontFamily: "JetBrains Mono" }}>
              Dados sincronizados via Dropbox. Ticket médio = Receita Bruta ÷ Nº de cirurgias. Conversão = Cirurgias ÷ Consultas.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}

function PeriodoToggle({ periodo, setPeriodo }) {
  return (
    <div style={{ display: "inline-flex", padding: 3, borderRadius: 10, background: C.surface, border: `1px solid ${C.border2}` }}>
      {["mes", "trimestre"].map((p) => (
        <button
          key={p}
          onClick={() => setPeriodo(p)}
          style={{
            padding: "6px 12px",
            borderRadius: 7,
            border: "none",
            cursor: "pointer",
            fontSize: 11,
            fontFamily: "JetBrains Mono",
            fontWeight: 600,
            color: periodo === p ? C.text : C.muted,
            background: periodo === p ? C.surface2 : "transparent",
          }}
        >
          {periodoLabel(p)}
        </button>
      ))}
    </div>
  );
}

// ─── Drawer Médico ──────────────────────────────────────────────────────────
function MedicoDrawer({ medico, convRede, onClose }) {
  if (!medico) return null;
  const benchmark = convRede || 0.40;
  return (
    <div style={{ position: "fixed", inset: 0, zIndex: 200, display: "flex", justifyContent: "flex-end" }}>
      <div onClick={onClose} style={{ position: "absolute", inset: 0, background: "rgba(0,0,0,0.6)", backdropFilter: "blur(4px)" }} />
      <div style={{ position: "relative", zIndex: 1, width: "min(440px, 100%)", height: "100vh", background: C.surface, borderLeft: `1px solid ${C.border2}`, display: "flex", flexDirection: "column", overflow: "hidden", animation: "slideIn 0.25s ease-out" }}>
        <div style={{ padding: "20px 24px 16px", borderBottom: `1px solid ${C.border}`, background: C.surface2 }}>
          <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 8 }}>
            <span style={{ fontSize: 11, fontFamily: "JetBrains Mono", color: C.muted, letterSpacing: "0.1em", textTransform: "uppercase" }}>Análise de Profissional</span>
            <button onClick={onClose} style={{ background: "rgba(255,255,255,0.05)", border: `1px solid ${C.border}`, color: C.dim, width: 28, height: 28, borderRadius: 8, cursor: "pointer", fontSize: 14 }}>✕</button>
          </div>
          <h2 style={{ fontSize: 20, fontFamily: "Syne", fontWeight: 700, color: C.text, margin: 0 }}>{medico.nome}</h2>
          <p style={{ fontSize: 11, color: C.muted, margin: "4px 0 0", fontFamily: "JetBrains Mono" }}>{medico.unidade} · Trimestre corrente</p>
        </div>
        <div style={{ padding: "20px 24px", overflowY: "auto", flex: 1 }}>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 10, marginBottom: 20 }}>
            {[
              { label: "Cirurgias", val: medico.cirurgias, cor: C.accent },
              { label: "Consultas", val: medico.consultas, cor: C.text },
              { label: "Conversão", val: fP(medico.conv), cor: medico.conv >= benchmark ? C.green : C.amber },
            ].map((k) => (
              <div key={k.label} style={{ padding: 14, borderRadius: 10, background: C.bg, border: `1px solid ${C.border}` }}>
                <div style={{ fontSize: 9, fontFamily: "JetBrains Mono", color: C.muted, textTransform: "uppercase", letterSpacing: "0.08em", marginBottom: 6 }}>{k.label}</div>
                <div style={{ fontSize: 22, fontFamily: "Syne", fontWeight: 700, color: k.cor }}>{k.val}</div>
              </div>
            ))}
          </div>

          <div style={{ padding: 14, borderRadius: 10, background: C.bg, border: `1px solid ${C.border}`, marginBottom: 16 }}>
            <div style={{ fontSize: 10, fontFamily: "JetBrains Mono", color: C.muted, textTransform: "uppercase", marginBottom: 10 }}>Conversão vs Média da Rede</div>
            {[
              { label: "Este médico", val: medico.conv, cor: medico.conv >= benchmark ? C.green : C.amber },
              { label: "Média da rede", val: benchmark, cor: C.dim },
            ].map((row) => (
              <div key={row.label} style={{ marginTop: 6 }}>
                <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 4 }}>
                  <span style={{ fontSize: 10, color: C.muted }}>{row.label}</span>
                  <span style={{ fontSize: 11, fontFamily: "JetBrains Mono", fontWeight: 600, color: row.cor }}>{fP(row.val)}</span>
                </div>
                <div style={{ height: 6, background: "rgba(255,255,255,0.07)", borderRadius: 3 }}>
                  <div style={{ width: `${Math.min((row.val || 0) * 100, 100)}%`, height: "100%", borderRadius: 3, background: row.cor }} />
                </div>
              </div>
            ))}
          </div>

          <div style={{ padding: "10px 12px", borderRadius: 8, background: "rgba(245,158,11,0.06)", border: "1px solid rgba(245,158,11,0.15)" }}>
            <p style={{ margin: 0, fontSize: 10, color: C.muted, lineHeight: 1.6, fontFamily: "JetBrains Mono" }}>
              <strong style={{ color: C.amber }}>Nota metodológica:</strong> Receita não é atribuída individualmente por médico. Cirurgias e consultas refletem produção operacional registrada na planilha.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}

// ─── KPI Card ───────────────────────────────────────────────────────────────
function KpiCard({ label, valor, delta, subvalor, sublabel, sparkline, accentColor }) {
  const d = delta != null ? fDelta(delta) : null;
  return (
    <div style={{ padding: "18px 20px", borderRadius: 12, background: C.surface, border: `1px solid ${C.border}`, position: "relative", overflow: "hidden" }}>
      <div style={{ position: "absolute", top: 0, left: 0, right: 0, height: 2, background: accentColor || C.accent, opacity: 0.6 }} />
      <div style={{ fontSize: 9, fontFamily: "JetBrains Mono", color: C.muted, textTransform: "uppercase", letterSpacing: "0.1em" }}>{label}</div>
      <div style={{ display: "flex", alignItems: "flex-end", justifyContent: "space-between", gap: 8, marginTop: 4 }}>
        <div>
          <div style={{ fontSize: 26, fontFamily: "Syne", fontWeight: 800, color: accentColor || C.text, lineHeight: 1.1, marginBottom: 4 }}>{valor}</div>
          {d && (
            <div style={{ display: "flex", alignItems: "center", gap: 4 }}>
              <span style={{ fontSize: 11, fontFamily: "JetBrains Mono", fontWeight: 600, color: d.up ? C.green : C.red }}>{d.text}</span>
              {sublabel && <span style={{ fontSize: 10, color: C.muted }}>vs {sublabel}</span>}
            </div>
          )}
          {subvalor && <div style={{ fontSize: 11, color: C.muted, marginTop: 2 }}>{subvalor}</div>}
        </div>
        {sparkline && <Sparkline values={sparkline} color={accentColor || C.accent} />}
      </div>
    </div>
  );
}

// ─── Linha Unidade ──────────────────────────────────────────────────────────
function UnitRow({ u, rank, onAnalisar, compact = false, periodo }) {
  const periodoEfetivo = periodo ?? u.periodo ?? "trimestre";
  const cfg = saude_cfg[u.saude] || saude_cfg.ok;
  return (
    <div style={{ display: "flex", alignItems: "center", gap: compact ? 8 : 12, padding: compact ? "8px 12px" : "10px 14px", borderRadius: 8, background: C.bg, border: `1px solid ${C.border}` }}>
      {rank && <span style={{ fontSize: 10, fontFamily: "JetBrains Mono", color: C.muted, width: 18, textAlign: "center", flexShrink: 0 }}>#{rank}</span>}
      <span style={{ width: 6, height: 6, borderRadius: "50%", background: cfg.cor, flexShrink: 0 }} />
      <span style={{ flex: 1, fontSize: 12, fontFamily: "Syne", fontWeight: 600, color: C.text, minWidth: 0, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{u.UNIDADE}</span>
      {!compact && (
        <>
          <span style={{ fontSize: 11, fontFamily: "JetBrains Mono", color: C.muted, width: 80, textAlign: "right", flexShrink: 0 }}>{fR(u.rb, true)}</span>
          <span style={{ fontSize: 11, fontFamily: "JetBrains Mono", fontWeight: 600, width: 64, textAlign: "right", flexShrink: 0, color: (u.ll || 0) >= 0 ? C.green : C.red }}>{fR(u.ll, true)}</span>
          <span style={{ fontSize: 11, fontFamily: "JetBrains Mono", width: 52, textAlign: "right", flexShrink: 0, color: (u.mg_ll || 0) >= 0.15 ? C.green : C.red }}>{fP(u.mg_ll)}</span>
        </>
      )}
      {compact && <span style={{ fontSize: 11, fontFamily: "JetBrains Mono", fontWeight: 600, color: (u.ll || 0) >= 0 ? C.green : C.red, flexShrink: 0 }}>{fR(u.ll, true)}</span>}
      <button onClick={() => onAnalisar({ ...u, periodo: periodoEfetivo })} style={{ fontSize: 10, fontFamily: "JetBrains Mono", padding: "4px 10px", borderRadius: 6, border: `1px solid ${C.border2}`, background: "rgba(255,255,255,0.04)", color: C.dim, cursor: "pointer", flexShrink: 0, whiteSpace: "nowrap" }}>Analisar →</button>
    </div>
  );
}

// ─── Alert badge ────────────────────────────────────────────────────────────
function AlertBadge({ a, expanded, onToggle }) {
  const cfg = {
    critico: { cor: C.red, bg: "rgba(239,68,68,0.08)" },
    atencao: { cor: C.amber, bg: "rgba(245,158,11,0.08)" },
    info: { cor: C.accent, bg: "rgba(59,130,246,0.08)" },
  }[a.nivel] || { cor: C.accent, bg: "rgba(59,130,246,0.08)" };
  return (
    <div style={{ borderLeft: `3px solid ${cfg.cor}`, background: cfg.bg, borderRadius: "0 8px 8px 0", overflow: "hidden" }}>
      <button onClick={onToggle} style={{ width: "100%", display: "flex", alignItems: "center", gap: 10, padding: "10px 14px", background: "transparent", border: "none", cursor: "pointer", textAlign: "left" }}>
        <span style={{ width: 6, height: 6, borderRadius: "50%", background: cfg.cor, animation: a.nivel === "critico" ? "pulse 1.8s infinite" : "none" }} />
        <span style={{ fontSize: 12, fontWeight: 600, color: C.text, flex: 1, fontFamily: "Syne" }}>{a.titulo}</span>
        <span style={{ fontSize: 12, color: C.muted, transform: expanded ? "rotate(180deg)" : "none", transition: "transform 0.2s" }}>▾</span>
      </button>
      {expanded && (
        <div style={{ padding: "0 14px 12px 30px" }}>
          <p style={{ margin: "0 0 6px", fontSize: 11, color: C.dim, lineHeight: 1.6 }}>{a.detalhe}</p>
          {a.acao && <p style={{ margin: 0, fontSize: 11, color: C.muted, fontStyle: "italic" }}>→ {a.acao}</p>}
        </div>
      )}
    </div>
  );
}

// ─── Tab: Resumo ────────────────────────────────────────────────────────────
function TabResumo({ d, onAnalisarUnidade, periodo, setPeriodo }) {
  const [alertasAbertos, setAlertasAbertos] = useState({});
  const criticos = d.alertas.filter((a) => a.nivel === "critico").length;
  const toggle = (i) => setAlertasAbertos((p) => ({ ...p, [i]: !p[i] }));

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 24 }}>
      <div style={{ display: "flex", justifyContent: "flex-start" }}>
        <PeriodoToggle periodo={periodo} setPeriodo={setPeriodo} />
      </div>
      <section>
        <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 12 }}>
          <h2 style={{ margin: 0, fontSize: 13, fontFamily: "JetBrains Mono", color: C.muted, textTransform: "uppercase", letterSpacing: "0.1em" }}>Último Mês Fechado — {d.ultimo_mes.label}</h2>
          <span style={{ fontSize: 10, fontFamily: "JetBrains Mono", color: C.muted }}>vs {d.mesmo_mes_ano_anterior.label}</span>
        </div>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))", gap: 10 }}>
          <KpiCard label="Receita Bruta" valor={fR(d.ultimo_mes.rb, true)} delta={d.yoy_mes} sublabel={d.mesmo_mes_ano_anterior.label} accentColor={C.accent} sparkline={d.meses.map((m) => m.rb)} />
          <KpiCard label="EBITDA" valor={fR(d.ultimo_mes.ebitda, true)} subvalor={`Margem ${fP(d.ultimo_mes.mg_ebitda)}`} accentColor={C.indigo} sparkline={d.meses.map((m) => m.ebitda)} />
          <KpiCard label="Lucro Líquido" valor={fR(d.ultimo_mes.ll, true)} subvalor={`Margem ${fP(d.ultimo_mes.mg_ll)}`} accentColor={C.green} sparkline={d.meses.map((m) => m.ll)} />
          <KpiCard label="Conversão da Rede" valor={fP(d.conv_media_rede)} subvalor="cirurgias / consultas" accentColor={C.amber} />
        </div>
      </section>

      <section>
        <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 12 }}>
          <h2 style={{ margin: 0, fontSize: 13, fontFamily: "JetBrains Mono", color: C.muted, textTransform: "uppercase", letterSpacing: "0.1em" }}>Acumulado {d.q1.label}</h2>
          <span style={{ fontSize: 10, fontFamily: "JetBrains Mono", color: C.muted }}>vs {d.q1_ano_anterior.label}</span>
        </div>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))", gap: 10 }}>
          <KpiCard label="Receita Bruta" valor={fR(d.q1.rb, true)} delta={d.yoy_q1} sublabel={d.q1_ano_anterior.label} accentColor={C.accent} />
          <KpiCard label="EBITDA" valor={fR(d.q1.ebitda, true)} subvalor={`Margem ${fP(d.q1.mg_ebitda)}`} accentColor={C.indigo} />
          <KpiCard label="Lucro Líquido" valor={fR(d.q1.ll, true)} subvalor={`Margem ${fP(d.q1.mg_ll)}`} accentColor={C.green} />
          <KpiCard label="Unidades Ativas" valor={String(d.unidades_ativas)} subvalor={`${d.unidades_encerradas} encerradas excluídas`} accentColor={C.purple} />
        </div>
      </section>

      <section>
        <h2 style={{ margin: "0 0 12px", fontSize: 13, fontFamily: "JetBrains Mono", color: C.muted, textTransform: "uppercase", letterSpacing: "0.1em" }}>Evolução Mensal — Trimestre</h2>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>
          <div style={{ padding: 16, borderRadius: 12, background: C.surface, border: `1px solid ${C.border}` }}>
            <div style={{ fontSize: 10, fontFamily: "JetBrains Mono", color: C.muted, textTransform: "uppercase", marginBottom: 12 }}>Receita Bruta</div>
            <BarChart data={d.meses.map((m) => ({ label: m.label, v1: m.rb }))} height={100} color={C.accent} />
            <div style={{ display: "flex", justifyContent: "space-between", marginTop: 8 }}>
              {d.meses.map((m) => (<span key={m.mes} style={{ fontSize: 10, fontFamily: "JetBrains Mono", color: C.text }}>{fR(m.rb, true)}</span>))}
            </div>
          </div>
          <div style={{ padding: 16, borderRadius: 12, background: C.surface, border: `1px solid ${C.border}` }}>
            <div style={{ fontSize: 10, fontFamily: "JetBrains Mono", color: C.muted, textTransform: "uppercase", marginBottom: 12 }}>Lucro Líquido</div>
            <BarChart data={d.meses.map((m) => ({ label: m.label, v1: m.ll }))} height={100} color={C.green} />
            <div style={{ display: "flex", justifyContent: "space-between", marginTop: 8 }}>
              {d.meses.map((m) => (<span key={m.mes} style={{ fontSize: 10, fontFamily: "JetBrains Mono", color: C.green }}>{fR(m.ll, true)} <span style={{ color: C.muted }}>{fP(m.mg_ll)}</span></span>))}
            </div>
          </div>
        </div>
      </section>

      <section>
        <h2 style={{ margin: "0 0 12px", fontSize: 13, fontFamily: "JetBrains Mono", color: C.muted, textTransform: "uppercase", letterSpacing: "0.1em" }}>Top & Bottom Unidades — {d.q1.label}</h2>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
          <div>
            <div style={{ fontSize: 10, fontFamily: "JetBrains Mono", color: C.green, textTransform: "uppercase", marginBottom: 8, display: "flex", alignItems: "center", gap: 6 }}>
              <span style={{ width: 6, height: 6, borderRadius: "50%", background: C.green }} />Top 5 por Lucro Líquido
            </div>
            <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
              {d.top5.map((u, i) => <UnitRow key={u.UNIDADE} u={u} rank={i + 1} onAnalisar={onAnalisarUnidade} compact periodo={periodo} />)}
            </div>
          </div>
          <div>
            <div style={{ fontSize: 10, fontFamily: "JetBrains Mono", color: C.red, textTransform: "uppercase", marginBottom: 8, display: "flex", alignItems: "center", gap: 6 }}>
              <span style={{ width: 6, height: 6, borderRadius: "50%", background: C.red }} />Bottom 5 — Exigem Atenção
            </div>
            <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
              {d.bot5.map((u, i) => <UnitRow key={u.UNIDADE} u={u} rank={d.unidades.length - i} onAnalisar={onAnalisarUnidade} compact periodo={periodo} />)}
            </div>
          </div>
        </div>
      </section>

      <section>
        <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 12 }}>
          <h2 style={{ margin: 0, fontSize: 13, fontFamily: "JetBrains Mono", color: C.muted, textTransform: "uppercase", letterSpacing: "0.1em" }}>Alertas</h2>
          {criticos > 0 && (
            <span style={{ fontSize: 10, fontFamily: "JetBrains Mono", fontWeight: 600, padding: "2px 8px", borderRadius: 20, background: "rgba(239,68,68,0.15)", color: C.red }}>
              {criticos} crítico{criticos > 1 ? "s" : ""}
            </span>
          )}
        </div>
        <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
          {d.alertas.map((a, i) => (<AlertBadge key={i} a={a} expanded={!!alertasAbertos[i]} onToggle={() => toggle(i)} />))}
        </div>
      </section>
    </div>
  );
}

// ─── Tab: Unidades ──────────────────────────────────────────────────────────
function TabUnidades({ d, onAnalisarUnidade }) {
  const [busca, setBusca] = useState("");
  const [ordenar, setOrdenar] = useState("ll");
  const [filtroSaude, setFiltroSaude] = useState("todos");

  const unidades = d.unidades
    .filter((u) => u.UNIDADE.toLowerCase().includes(busca.toLowerCase()))
    .filter((u) => filtroSaude === "todos" || u.saude === filtroSaude)
    .sort((a, b) => {
      if (ordenar === "ll") return (b.ll || 0) - (a.ll || 0);
      if (ordenar === "rb") return (b.rb || 0) - (a.rb || 0);
      if (ordenar === "mg") return (b.mg_ll || -99) - (a.mg_ll || -99);
      if (ordenar === "conv") return (b.conv || 0) - (a.conv || 0);
      return 0;
    });

  const cnt = (s) => d.unidades.filter((u) => u.saude === s).length;

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      <div style={{ display: "flex", gap: 8, flexWrap: "wrap", alignItems: "center" }}>
        <input value={busca} onChange={(e) => setBusca(e.target.value)} placeholder="Buscar unidade..."
          style={{ flex: 1, minWidth: 160, padding: "8px 12px", borderRadius: 8, border: `1px solid ${C.border2}`, background: C.surface2, color: C.text, fontSize: 12, fontFamily: "JetBrains Mono", outline: "none" }} />
        {["todos", "ok", "atencao", "critico"].map((s) => (
          <button key={s} onClick={() => setFiltroSaude(s)}
            style={{ padding: "6px 12px", borderRadius: 8, fontSize: 10, fontFamily: "JetBrains Mono", fontWeight: 600, border: `1px solid ${filtroSaude === s ? (saude_cfg[s]?.cor || C.border2) : C.border}`, background: filtroSaude === s ? (saude_cfg[s]?.bg || "rgba(255,255,255,0.06)") : "transparent", color: filtroSaude === s ? (saude_cfg[s]?.cor || C.text) : C.muted, cursor: "pointer" }}>
            {s === "todos" ? `Todas (${d.unidades.length})` : `${saude_cfg[s]?.label} (${cnt(s)})`}
          </button>
        ))}
      </div>

      <div style={{ display: "flex", alignItems: "center", gap: 12, padding: "6px 14px" }}>
        <span style={{ width: 18 }} />
        <span style={{ width: 6 }} />
        <span style={{ flex: 1, fontSize: 9, fontFamily: "JetBrains Mono", color: C.muted, textTransform: "uppercase" }}>Unidade</span>
        {[["rb", "Receita", 80], ["ll", "Luc. Líq.", 64], ["mg", "Mg. LL", 52]].map(([k, l, w]) => (
          <button key={k} onClick={() => setOrdenar(k)}
            style={{ width: w, fontSize: 9, fontFamily: "JetBrains Mono", textTransform: "uppercase", textAlign: "right", background: "none", border: "none", cursor: "pointer", color: ordenar === k ? C.text : C.muted, flexShrink: 0 }}>
            {l}{ordenar === k ? " ↓" : ""}
          </button>
        ))}
        <span style={{ width: 72 }} />
      </div>

      <div style={{ display: "flex", flexDirection: "column", gap: 5 }}>
        {unidades.map((u, i) => <UnitRow key={u.UNIDADE} u={u} rank={i + 1} onAnalisar={onAnalisarUnidade} />)}
        {unidades.length === 0 && (
          <div style={{ padding: 40, textAlign: "center", color: C.muted, fontSize: 12, fontFamily: "JetBrains Mono" }}>
            Nenhuma unidade encontrada para os filtros selecionados.
          </div>
        )}
      </div>
    </div>
  );
}

// ─── Tab: Médicos ───────────────────────────────────────────────────────────
function TabMedicos({ d, onAnalisarMedico }) {
  const [busca, setBusca] = useState("");
  const [ordenar, setOrdenar] = useState("cirurgias");
  const convRede = d.conv_media_rede || 0.40;

  const medicos = d.profissionais
    .filter((m) => (m.nome || "").toLowerCase().includes(busca.toLowerCase()) || (m.unidade || "").toLowerCase().includes(busca.toLowerCase()))
    .sort((a, b) => {
      if (ordenar === "cirurgias") return b.cirurgias - a.cirurgias;
      if (ordenar === "consultas") return b.consultas - a.consultas;
      if (ordenar === "conv") return b.conv - a.conv;
      return 0;
    });

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      <div style={{ padding: "12px 16px", borderRadius: 10, background: "rgba(245,158,11,0.06)", border: "1px solid rgba(245,158,11,0.2)" }}>
        <p style={{ margin: 0, fontSize: 11, color: C.dim, lineHeight: 1.6, fontFamily: "JetBrains Mono" }}>
          <strong style={{ color: C.amber }}>Nota metodológica:</strong> Receita não é atribuída individualmente. Os dados mostram produção operacional registrada na planilha.
        </p>
      </div>

      <input value={busca} onChange={(e) => setBusca(e.target.value)} placeholder="Buscar por médico ou unidade..."
        style={{ padding: "8px 12px", borderRadius: 8, border: `1px solid ${C.border2}`, background: C.surface2, color: C.text, fontSize: 12, fontFamily: "JetBrains Mono", outline: "none" }} />

      <div style={{ display: "flex", alignItems: "center", gap: 10, padding: "6px 14px" }}>
        <span style={{ flex: 1, fontSize: 9, fontFamily: "JetBrains Mono", color: C.muted, textTransform: "uppercase" }}>Profissional</span>
        <span style={{ fontSize: 9, fontFamily: "JetBrains Mono", color: C.muted, textTransform: "uppercase", width: 80, textAlign: "right" }}>Unidade</span>
        {[["cirurgias", "Cirurg.", 56], ["consultas", "Consul.", 56], ["conv", "Conv.", 52]].map(([k, l, w]) => (
          <button key={k} onClick={() => setOrdenar(k)}
            style={{ width: w, fontSize: 9, fontFamily: "JetBrains Mono", textTransform: "uppercase", textAlign: "right", background: "none", border: "none", cursor: "pointer", color: ordenar === k ? C.text : C.muted, flexShrink: 0 }}>
            {l}{ordenar === k ? " ↓" : ""}
          </button>
        ))}
        <span style={{ width: 72 }} />
      </div>

      <div style={{ display: "flex", flexDirection: "column", gap: 5 }}>
        {medicos.map((m, i) => {
          const ok = m.conv >= convRede;
          return (
            <div key={`${m.nome}-${i}`} style={{ display: "flex", alignItems: "center", gap: 10, padding: "10px 14px", borderRadius: 8, background: C.bg, border: `1px solid ${C.border}` }}>
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ fontSize: 12, fontFamily: "Syne", fontWeight: 600, color: C.text, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{m.nome}</div>
              </div>
              <span style={{ fontSize: 10, color: C.muted, width: 80, textAlign: "right", flexShrink: 0, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{m.unidade}</span>
              <span style={{ fontSize: 12, fontFamily: "JetBrains Mono", fontWeight: 600, color: C.accent, width: 56, textAlign: "right", flexShrink: 0 }}>{m.cirurgias}</span>
              <span style={{ fontSize: 12, fontFamily: "JetBrains Mono", color: C.muted, width: 56, textAlign: "right", flexShrink: 0 }}>{m.consultas}</span>
              <span style={{ fontSize: 12, fontFamily: "JetBrains Mono", fontWeight: 600, width: 52, textAlign: "right", flexShrink: 0, color: ok ? C.green : C.amber }}>{fP(m.conv)}</span>
              <button onClick={() => onAnalisarMedico(m)} style={{ fontSize: 10, fontFamily: "JetBrains Mono", padding: "4px 10px", borderRadius: 6, border: `1px solid ${C.border2}`, background: "rgba(255,255,255,0.04)", color: C.dim, cursor: "pointer", flexShrink: 0, whiteSpace: "nowrap" }}>Analisar →</button>
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ─── Tab: Financeiro ────────────────────────────────────────────────────────
function TabFinanceiro({ d }) {
  const ytd = d.q1;
  const rb = ytd.rb || 0, rl = ytd.rl || 0, ebt = ytd.ebitda || 0, ll = ytd.ll || 0;
  const iss = rb - rl;
  const cus = rl - ebt;
  const ir = ebt - ll;
  const maxBar = rb || 1;

  const linhas = [
    { label: "Receita Bruta", val: rb, negativa: false, destaque: true },
    { label: "(-) ISS/PIS/COFINS", val: -iss, negativa: true },
    { label: "= Receita Líquida", val: rl, negativa: false, destaque: true },
    { label: "(-) Custos e Despesas", val: -cus, negativa: true },
    { label: "= EBITDA", val: ebt, negativa: false, destaque: true, cor: C.indigo },
    { label: "(-) IRPJ / CSLL", val: -ir, negativa: true },
    { label: "= Lucro Líquido", val: ll, negativa: false, destaque: true, cor: C.green },
  ];

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 24 }}>
      <section>
        <h2 style={{ margin: "0 0 12px", fontSize: 13, fontFamily: "JetBrains Mono", color: C.muted, textTransform: "uppercase", letterSpacing: "0.1em" }}>DRE Consolidada — {d.q1.label}</h2>
        <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
          {linhas.map((l) => {
            const pct = Math.abs(l.val) / maxBar;
            const barCor = l.cor || (l.negativa ? C.red : C.accent);
            const mg = !l.negativa && l.label !== "Receita Bruta" && rl ? l.val / rl : null;
            return (
              <div key={l.label} style={{ display: "flex", alignItems: "center", gap: 12, padding: l.destaque ? "12px 14px" : "8px 14px", borderRadius: 8, background: l.destaque ? C.surface : "transparent", border: l.destaque ? `1px solid ${C.border}` : "none" }}>
                <span style={{ fontSize: 11, fontFamily: "Syne", fontWeight: l.destaque ? 700 : 400, color: l.negativa ? C.muted : (l.cor || C.text), width: 190, flexShrink: 0 }}>{l.label}</span>
                <div style={{ flex: 1, height: 6, background: "rgba(255,255,255,0.05)", borderRadius: 3 }}>
                  <div style={{ width: `${Math.max(pct * 100, 0.5)}%`, height: "100%", borderRadius: 3, background: barCor, opacity: l.negativa ? 0.5 : 0.9 }} />
                </div>
                <span style={{ fontSize: 12, fontFamily: "JetBrains Mono", fontWeight: l.destaque ? 700 : 400, color: l.negativa ? C.muted : (l.cor || C.text), width: 110, textAlign: "right", flexShrink: 0 }}>
                  {l.negativa ? `−${fR(Math.abs(l.val), true)}` : fR(l.val, true)}
                </span>
                <span style={{ fontSize: 11, fontFamily: "JetBrains Mono", color: C.muted, width: 52, textAlign: "right", flexShrink: 0 }}>
                  {mg != null ? fP(mg) : ""}
                </span>
              </div>
            );
          })}
        </div>
      </section>

      <section>
        <h2 style={{ margin: "0 0 12px", fontSize: 13, fontFamily: "JetBrains Mono", color: C.muted, textTransform: "uppercase", letterSpacing: "0.1em" }}>Evolução Mensal</h2>
        <div style={{ overflowX: "auto" }}>
          <table style={{ width: "100%", borderCollapse: "collapse", minWidth: 400 }}>
            <thead>
              <tr>
                {["", ...d.meses.map((m) => m.label), "YTD"].map((h, i) => (
                  <th key={i} style={{ padding: "8px 12px", fontSize: 9, fontFamily: "JetBrains Mono", color: C.muted, textTransform: "uppercase", textAlign: h === "" ? "left" : "right", borderBottom: `1px solid ${C.border}` }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {[
                { label: "Receita Bruta", campo: "rb", cor: C.text, bold: true, ytd: d.q1.rb },
                { label: "EBITDA", campo: "ebitda", cor: C.indigo, bold: true, ytd: d.q1.ebitda },
                { label: "Mg. EBITDA", campo: "mg_ebitda", cor: C.indigo, pct: true, ytd: d.q1.mg_ebitda },
                { label: "Lucro Líquido", campo: "ll", cor: C.green, bold: true, ytd: d.q1.ll },
                { label: "Mg. LL", campo: "mg_ll", cor: C.green, pct: true, ytd: d.q1.mg_ll },
              ].map((row, ri) => (
                <tr key={row.label} style={{ background: ri % 2 === 0 ? C.bg : "transparent" }}>
                  <td style={{ padding: "8px 12px", fontSize: 11, fontFamily: "Syne", fontWeight: row.bold ? 600 : 400, color: C.muted, borderBottom: `1px solid ${C.border}` }}>{row.label}</td>
                  {d.meses.map((m) => (
                    <td key={m.mes} style={{ padding: "8px 12px", fontSize: 12, fontFamily: "JetBrains Mono", fontWeight: row.bold ? 600 : 400, textAlign: "right", color: row.pct ? ((m[row.campo] || 0) >= 0.20 ? C.green : C.amber) : row.cor, borderBottom: `1px solid ${C.border}` }}>
                      {row.pct ? fP(m[row.campo]) : fR(m[row.campo], true)}
                    </td>
                  ))}
                  <td style={{ padding: "8px 12px", fontSize: 12, fontFamily: "JetBrains Mono", fontWeight: 700, textAlign: "right", color: row.cor, borderBottom: `1px solid ${C.border}`, background: "rgba(255,255,255,0.03)" }}>
                    {row.pct ? fP(row.ytd) : fR(row.ytd, true)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p style={{ fontSize: 10, fontFamily: "JetBrains Mono", color: C.muted, marginTop: 8 }}>
          Fonte: Planilha sincronizada via Dropbox · Aba financeiro mensal
        </p>
      </section>
    </div>
  );
}

// ─── Tab: Alertas ───────────────────────────────────────────────────────────
function TabAlertas({ d }) {
  const [abertos, setAbertos] = useState({ 0: true, 1: true });
  const toggle = (i) => setAbertos((p) => ({ ...p, [i]: !p[i] }));

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 10, marginBottom: 8 }}>
        {["critico", "atencao", "info"].map((nivel) => {
          const cfg = { critico: { cor: C.red, bg: "rgba(239,68,68,0.1)" }, atencao: { cor: C.amber, bg: "rgba(245,158,11,0.1)" }, info: { cor: C.accent, bg: "rgba(59,130,246,0.1)" } }[nivel];
          const cnt = d.alertas.filter((a) => a.nivel === nivel).length;
          return (
            <div key={nivel} style={{ padding: 14, borderRadius: 10, background: cfg.bg, border: `1px solid ${cfg.cor}30`, textAlign: "center" }}>
              <div style={{ fontSize: 28, fontFamily: "Syne", fontWeight: 800, color: cfg.cor }}>{cnt}</div>
              <div style={{ fontSize: 9, fontFamily: "JetBrains Mono", color: C.muted, textTransform: "uppercase", marginTop: 4 }}>
                {nivel === "critico" ? "Crítico" : nivel === "atencao" ? "Atenção" : "Info"}
              </div>
            </div>
          );
        })}
      </div>

      <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
        {d.alertas.map((a, i) => (<AlertBadge key={i} a={a} expanded={!!abertos[i]} onToggle={() => toggle(i)} />))}
      </div>

      <div style={{ padding: "14px 16px", borderRadius: 10, background: C.surface, border: `1px solid ${C.border}`, marginTop: 8 }}>
        <h3 style={{ fontSize: 11, fontFamily: "JetBrains Mono", color: C.muted, textTransform: "uppercase", margin: "0 0 10px" }}>Sistema de detecção</h3>
        {[
          ["Margem LL < 0", "Detecta unidades em risco de encerramento"],
          ["Conversão < 40%", "Problema no funil de captação"],
          ["% NF emitida < 65%", "Exposição fiscal acumulada"],
        ].map(([regra, desc]) => (
          <div key={regra} style={{ display: "flex", gap: 12, padding: "6px 0", borderBottom: `1px solid ${C.border}` }}>
            <span style={{ fontSize: 11, fontFamily: "JetBrains Mono", color: C.accent, flexShrink: 0, width: 240 }}>{regra}</span>
            <span style={{ fontSize: 11, color: C.muted }}>{desc}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

// ─── App principal ──────────────────────────────────────────────────────────
const TABS = [
  { id: "resumo", label: "Resumo" },
  { id: "unidades", label: "Unidades" },
  { id: "medicos", label: "Médicos" },
  { id: "financeiro", label: "Financeiro" },
  { id: "alertas", label: "Alertas" },
];

export default function App() {
  const [tab, setTab] = useState("resumo");
  const [periodo, setPeriodo] = useState("trimestre");
  const [unitDrawer, setUnitDrawer] = useState(null);
  const [medicoDrawer, setMedicoDrawer] = useState(null);
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState("");

  const reqIdRef = useRef(0);
  const load = async (p = periodo) => {
    const myId = ++reqIdRef.current;
    try {
      const d = await getDashboardForApp(p);
      if (myId !== reqIdRef.current) return; // ignora resposta de uma chamada já obsoleta
      setData(d);
      setErr("");
    } catch (e) {
      if (myId !== reqIdRef.current) return;
      console.error(e);
      setErr("Falha ao carregar dados do dashboard.");
    } finally {
      if (myId === reqIdRef.current) setLoading(false);
    }
  };

  useEffect(() => {
    load(periodo);
    const id = setInterval(() => load(periodo), 60_000);
    return () => clearInterval(id);
  }, [periodo]);

  if (loading && !data) {
    return (
      <div style={{ background: C.bg, minHeight: "100vh", color: C.text, fontFamily: "Syne, system-ui, sans-serif", display: "flex", alignItems: "center", justifyContent: "center" }}>
        <style>{FONTS}</style>
        <div style={{ fontSize: 14, color: C.muted, fontFamily: "JetBrains Mono" }}>Carregando dashboard…</div>
      </div>
    );
  }

  if (err && !data) {
    return (
      <div style={{ background: C.bg, minHeight: "100vh", color: C.text, padding: 40, fontFamily: "Syne, system-ui, sans-serif" }}>
        <style>{FONTS}</style>
        <div style={{ maxWidth: 480, margin: "60px auto", padding: 24, borderRadius: 12, background: C.surface, border: `1px solid ${C.border2}` }}>
          <h2 style={{ margin: 0 }}>Falha ao carregar</h2>
          <p style={{ marginTop: 8, color: C.muted, fontSize: 13 }}>{err}</p>
          <button onClick={load} style={{ marginTop: 16, padding: "8px 14px", borderRadius: 8, background: C.accent, color: "white", border: "none", fontWeight: 600, cursor: "pointer" }}>Tentar novamente</button>
        </div>
      </div>
    );
  }

  const d = data;
  const criticos = d.alertas.filter((a) => a.nivel === "critico").length;
  const sincronizado = d.status_dados === "atualizado" || d.status_dados === "ok";

  return (
    <div style={{ background: C.bg, minHeight: "100vh", color: C.text, fontFamily: "Syne, system-ui, sans-serif" }}>
      <style>{`${FONTS} * { box-sizing: border-box; margin: 0; padding: 0; } ::-webkit-scrollbar { width: 4px; height: 4px; } ::-webkit-scrollbar-track { background: transparent; } ::-webkit-scrollbar-thumb { background: rgba(255,255,255,0.1); border-radius: 2px; } @keyframes pulse { 0%,100%{opacity:1;transform:scale(1)} 50%{opacity:.5;transform:scale(1.5)} } button:hover { opacity: 0.85; } input:focus { border-color: rgba(99,102,241,0.5) !important; box-shadow: 0 0 0 2px rgba(99,102,241,0.15); }`}</style>

      <header style={{ position: "sticky", top: 0, zIndex: 100, background: "rgba(8,12,20,0.95)", backdropFilter: "blur(12px)", borderBottom: `1px solid ${C.border}` }}>
        <div style={{ maxWidth: 1200, margin: "0 auto", padding: "0 20px" }}>
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "12px 0 10px" }}>
            <div style={{ display: "flex", flexDirection: "column", alignItems: "flex-start", gap: 2 }}>
              <img src="/icb-logo.png" alt="ICB" style={{ height: 44, width: "auto", display: "block" }} />
              <div style={{ fontSize: 13, fontFamily: "Syne", fontWeight: 800, color: C.text, lineHeight: 1 }}>Dashboard</div>
            </div>

            <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
              <div style={{ display: "flex", alignItems: "center", gap: 6, padding: "5px 12px", borderRadius: 8, background: C.surface, border: `1px solid ${C.border2}`, fontSize: 11, fontFamily: "JetBrains Mono", color: C.text }}>
                <span style={{ color: C.muted }}>Período:</span> {d.ultimo_mes.label}
              </div>
              <div style={{ display: "flex", alignItems: "center", gap: 6, padding: "5px 12px", borderRadius: 8, background: C.surface, border: `1px solid ${C.border2}`, fontSize: 11, fontFamily: "JetBrains Mono", color: C.text }}>
                <span style={{ color: C.muted }}>vs:</span> {d.mesmo_mes_ano_anterior.label}
              </div>
              {criticos > 0 && (
                <button onClick={() => setTab("alertas")} style={{ display: "flex", alignItems: "center", gap: 6, padding: "5px 12px", borderRadius: 8, background: "rgba(239,68,68,0.12)", border: "1px solid rgba(239,68,68,0.3)", color: C.red, fontSize: 11, fontFamily: "JetBrains Mono", fontWeight: 600, cursor: "pointer" }}>
                  <span style={{ width: 6, height: 6, borderRadius: "50%", background: C.red, animation: "pulse 1.8s infinite" }} />
                  {criticos} crítico{criticos > 1 ? "s" : ""}
                </button>
              )}
              <a href="/executive-report" style={{ display: "flex", alignItems: "center", gap: 6, padding: "5px 12px", borderRadius: 8, background: "rgba(99,102,241,0.12)", border: "1px solid rgba(99,102,241,0.3)", color: C.indigo, fontSize: 11, fontFamily: "JetBrains Mono", fontWeight: 600, textDecoration: "none" }}>
                Relatório Executivo
              </a>
              <div style={{ display: "flex", alignItems: "center", gap: 5, padding: "5px 10px", borderRadius: 8, background: C.surface, border: `1px solid ${C.border}`, fontSize: 10, fontFamily: "JetBrains Mono", color: C.muted }}>
                <span style={{ width: 6, height: 6, borderRadius: "50%", background: sincronizado ? C.green : C.amber }} />
                {sincronizado ? "Sincronizado" : "Atenção"}
              </div>
            </div>
          </div>

          <div style={{ display: "flex", gap: 0, paddingBottom: 0 }}>
            {TABS.map((t) => (
              <button key={t.id} onClick={() => setTab(t.id)}
                style={{ padding: "8px 16px", fontSize: 12, fontFamily: "Syne", fontWeight: 600, background: "none", border: "none", cursor: "pointer", color: tab === t.id ? C.text : C.muted, borderBottom: `2px solid ${tab === t.id ? C.accent : "transparent"}`, position: "relative" }}>
                {t.label}
                {t.id === "alertas" && criticos > 0 && (
                  <span style={{ position: "absolute", top: 4, right: 6, width: 6, height: 6, borderRadius: "50%", background: C.red, animation: "pulse 1.8s infinite" }} />
                )}
              </button>
            ))}
          </div>
        </div>
      </header>

      <main style={{ maxWidth: 1200, margin: "0 auto", padding: "24px 20px 48px" }}>
        {tab === "resumo" && <TabResumo d={d} onAnalisarUnidade={setUnitDrawer} periodo={periodo} setPeriodo={setPeriodo} />}
        {tab === "unidades" && <TabUnidades d={d} onAnalisarUnidade={setUnitDrawer} />}
        {tab === "medicos" && <TabMedicos d={d} onAnalisarMedico={setMedicoDrawer} />}
        {tab === "financeiro" && <TabFinanceiro d={d} />}
        {tab === "alertas" && <TabAlertas d={d} />}
      </main>

      {unitDrawer && <UnitDrawer unit={unitDrawer} convRede={d.conv_media_rede} onClose={() => setUnitDrawer(null)} />}
      {medicoDrawer && <MedicoDrawer medico={medicoDrawer} convRede={d.conv_media_rede} onClose={() => setMedicoDrawer(null)} />}
    </div>
  );
}
