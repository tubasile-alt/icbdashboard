import { useCallback, useState } from 'react';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';
const WHATSAPP_NUMBER = '5516997963460';

export default function ReportButton() {
  const [open, setOpen] = useState(false);
  const [periodo, setPeriodo] = useState('trimestre');
  const [status, setStatus] = useState('idle');
  const [errorMsg, setErrorMsg] = useState('');

  const periodos = [
    { id: 'mes', label: 'Último Mês', sub: 'Mês mais recente com dados', icon: '📅' },
    { id: 'trimestre', label: 'Último Trimestre', sub: 'Últimos 3 meses acumulados', icon: '📊' },
  ];

  const handleGerar = useCallback(async () => {
    setStatus('loading');
    setErrorMsg('');
    try {
      const res = await fetch(`${API_URL}/dashboard/relatorio?periodo=${periodo}`);
      if (!res.ok) throw new Error(`Erro ${res.status}: ${res.statusText}`);

      const blob = await res.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `ICB_Relatorio_${periodo === 'mes' ? 'Mensal' : 'Trimestral'}.pdf`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      window.URL.revokeObjectURL(url);
      setStatus('done');
    } catch (err) {
      setStatus('error');
      setErrorMsg(err.message || 'Falha ao gerar PDF. Tente novamente.');
    }
  }, [periodo]);

  const handleWhatsApp = useCallback(() => {
    const per = periodos.find((p) => p.id === periodo);
    const texto = encodeURIComponent(
      `📊 *ICB Performance Dashboard*\nRelatório Executivo — ${per?.label}\n\nAcesse e faça o download em:\n${API_URL}/dashboard/relatorio?periodo=${periodo}\n\n_Gerado automaticamente · Uso interno · Confidencial_`,
    );
    window.open(`https://wa.me/${WHATSAPP_NUMBER}?text=${texto}`, '_blank');
  }, [periodo]);

  const reset = () => {
    setStatus('idle');
    setErrorMsg('');
  };

  return (
    <>
      <button
        onClick={() => {
          setOpen(true);
          reset();
        }}
        className="flex items-center gap-2 rounded-lg border border-indigo-500/40 bg-indigo-500/10 px-3 py-2 text-xs font-semibold text-indigo-300 transition-all duration-150 hover:border-indigo-400/60 hover:bg-indigo-500/20 whitespace-nowrap"
      >
        <span>⬇</span>
        <span>Relatório PDF</span>
      </button>

      {open && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center p-4"
          style={{ background: 'rgba(0,0,0,0.75)' }}
          onClick={(e) => e.target === e.currentTarget && setOpen(false)}
        >
          <div
            className="w-full max-w-md overflow-hidden rounded-2xl"
            style={{ background: '#111827', border: '1px solid rgba(255,255,255,0.1)' }}
          >
            <div
              className="flex items-center justify-between px-5 py-4"
              style={{ borderBottom: '1px solid rgba(255,255,255,0.07)', background: 'rgba(0,0,0,0.3)' }}
            >
              <div>
                <p className="text-sm font-bold text-white">Relatório Executivo PDF</p>
                <p className="mt-0.5 text-xs" style={{ color: 'rgba(255,255,255,0.35)' }}>
                  ICB Transplante Capilar · Para diretores
                </p>
              </div>
              <button
                onClick={() => setOpen(false)}
                className="flex h-7 w-7 items-center justify-center rounded-lg text-sm transition-colors hover:bg-white/10"
                style={{ color: 'rgba(255,255,255,0.4)' }}
              >
                ✕
              </button>
            </div>

            <div className="space-y-4 p-5">
              <div>
                <p className="mb-2 text-xs font-semibold uppercase tracking-widest" style={{ color: 'rgba(255,255,255,0.35)' }}>
                  Período do relatório
                </p>
                <div className="grid grid-cols-2 gap-2">
                  {periodos.map((op) => (
                    <button
                      key={op.id}
                      onClick={() => {
                        setPeriodo(op.id);
                        reset();
                      }}
                      className="rounded-xl p-3 text-left transition-all duration-150"
                      style={{
                        border: `1.5px solid ${periodo === op.id ? '#6366f1' : 'rgba(255,255,255,0.08)'}`,
                        background: periodo === op.id ? 'rgba(99,102,241,0.12)' : 'rgba(255,255,255,0.02)',
                      }}
                    >
                      <span className="text-base">{op.icon}</span>
                      <p className="mt-1 text-xs font-semibold" style={{ color: periodo === op.id ? '#a5b4fc' : 'rgba(255,255,255,0.7)' }}>
                        {op.label}
                      </p>
                      <p className="mt-0.5 text-xs" style={{ color: 'rgba(255,255,255,0.3)' }}>
                        {op.sub}
                      </p>
                    </button>
                  ))}
                </div>
              </div>

              <div className="space-y-1 rounded-xl p-3 text-xs" style={{ background: 'rgba(99,102,241,0.06)', border: '1px solid rgba(99,102,241,0.2)' }}>
                <p className="font-semibold" style={{ color: '#a5b4fc' }}>
                  Conteúdo incluído
                </p>
                {[
                  'KPIs consolidados da rede (Receita, EBITDA, LL)',
                  'Alertas e riscos do período',
                  'DRE gerencial em cascata',
                  'Ranking de unidades por Lucro Líquido',
                  'Indicadores operacionais',
                  'Notas e limitações dos dados',
                ].map((item) => (
                  <p key={item} style={{ color: 'rgba(255,255,255,0.5)' }}>
                    ✓ {item}
                  </p>
                ))}
              </div>

              {status === 'error' && (
                <div className="rounded-xl p-3 text-xs" style={{ background: 'rgba(239,68,68,0.1)', border: '1px solid rgba(239,68,68,0.3)' }}>
                  <p className="font-semibold text-red-400">Erro ao gerar PDF</p>
                  <p className="mt-1" style={{ color: 'rgba(255,255,255,0.5)' }}>
                    {errorMsg}
                  </p>
                  <button onClick={reset} className="mt-2 text-red-400 underline">
                    Tentar novamente
                  </button>
                </div>
              )}

              {status === 'done' && (
                <div className="rounded-xl p-3" style={{ background: 'rgba(16,185,129,0.1)', border: '1px solid rgba(16,185,129,0.3)' }}>
                  <p className="text-xs font-semibold text-emerald-400">✓ PDF gerado e baixado</p>
                  <p className="mt-1 text-xs" style={{ color: 'rgba(255,255,255,0.4)' }}>
                    Verifique sua pasta de downloads.
                  </p>
                </div>
              )}

              <div className="space-y-2 pt-1">
                <button
                  onClick={handleGerar}
                  disabled={status === 'loading'}
                  className="flex w-full items-center justify-center gap-2 rounded-xl py-3 text-sm font-bold text-white transition-all duration-200"
                  style={{
                    background: status === 'loading' ? 'rgba(99,102,241,0.4)' : 'linear-gradient(135deg, #6366f1, #3b82f6)',
                    cursor: status === 'loading' ? 'not-allowed' : 'pointer',
                  }}
                >
                  {status === 'loading' ? (
                    <>
                      <Spinner />
                      Gerando PDF...
                    </>
                  ) : (
                    <>
                      <span>⬇</span>
                      {status === 'done' ? 'Baixar novamente' : 'Gerar e Baixar PDF'}
                    </>
                  )}
                </button>

                <button
                  onClick={handleWhatsApp}
                  className="flex w-full items-center justify-center gap-2 rounded-xl py-3 text-sm font-semibold transition-all duration-150"
                  style={{ background: 'rgba(37,211,102,0.1)', border: '1px solid rgba(37,211,102,0.3)', color: '#4ade80' }}
                >
                  <WhatsAppIcon />
                  Enviar link por WhatsApp
                </button>
                <p className="text-center text-xs" style={{ color: 'rgba(255,255,255,0.2)' }}>
                  Envia o link de download para +55 16 99796-3460
                </p>
              </div>
            </div>
          </div>
        </div>
      )}
    </>
  );
}

function Spinner() {
  return (
    <span
      className="inline-block h-4 w-4 rounded-full"
      style={{ border: '2px solid rgba(255,255,255,0.3)', borderTopColor: '#fff', animation: 'icb-spin 0.7s linear infinite' }}
    >
      <style>{'@keyframes icb-spin { to { transform: rotate(360deg) } }'}</style>
    </span>
  );
}

function WhatsAppIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
      <path d="M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.298-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.5-.669-.51-.173-.008-.371-.01-.57-.01-.198 0-.52.074-.792.372-.272.297-1.04 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.096 3.2 5.077 4.487.709.306 1.262.489 1.694.625.712.227 1.36.195 1.871.118.571-.085 1.758-.719 2.006-1.413.248-.694.248-1.289.173-1.413-.074-.124-.272-.198-.57-.347m-5.421 7.403h-.004a9.87 9.87 0 01-5.031-1.378l-.361-.214-3.741.982.998-3.648-.235-.374a9.86 9.86 0 01-1.51-5.26c.001-5.45 4.436-9.884 9.888-9.884 2.64 0 5.122 1.03 6.988 2.898a9.825 9.825 0 012.893 6.994c-.003 5.45-4.437 9.884-9.885 9.884m8.413-18.297A11.815 11.815 0 0012.05 0C5.495 0 .16 5.335.157 11.892c0 2.096.547 4.142 1.588 5.945L.057 24l6.305-1.654a11.882 11.882 0 005.683 1.448h.005c6.554 0 11.89-5.335 11.893-11.893a11.821 11.821 0 00-3.48-8.413z" />
    </svg>
  );
}
