from __future__ import annotations

from dataclasses import dataclass, asdict


@dataclass(frozen=True)
class AlertCatalogEntry:
    id: int
    categoria: str
    nivel: str
    titulo: str
    como_funciona: str
    dado_base: str
    threshold: str
    impacto: str
    implementacao: str
    ativo_no_sistema: bool

    def to_dict(self) -> dict:
        return asdict(self)


CATALOG: tuple[AlertCatalogEntry, ...] = (
    AlertCatalogEntry(
        id=1,
        categoria="sobrevivencia",
        nivel="critico",
        titulo="Receita abaixo do limiar de sobrevivência por 2+ meses",
        como_funciona="Detecta unidade com receita_operacional < R$60.000 por 2 competências consecutivas.",
        dado_base="FactUnidadeMensal.receita_operacional",
        threshold="< 60000 por 2 meses seguidos",
        impacto="Antecipa risco de fechamento da unidade.",
        implementacao="pendente",
        ativo_no_sistema=False,
    ),
    AlertCatalogEntry(
        id=2,
        categoria="sobrevivencia",
        nivel="critico",
        titulo="Queda de receita > 50% vs mesmo mês do ano anterior",
        como_funciona="Compara receita da competência com a mesma competência do ano anterior por unidade.",
        dado_base="FactUnidadeMensal.receita_operacional",
        threshold="YoY < -50%",
        impacto="Sinaliza deterioração grave de demanda/execução.",
        implementacao="pendente",
        ativo_no_sistema=False,
    ),
    AlertCatalogEntry(
        id=3,
        categoria="sobrevivencia",
        nivel="critico",
        titulo="Margem EBITDA negativa por 2+ meses consecutivos",
        como_funciona="Detecta unidade com EBITDA < 0 ou margem_ebitda < 0 por 2 competências seguidas.",
        dado_base="FactFinanceiroMensal (ebitda, margem_ebitda)",
        threshold="2 meses consecutivos negativos",
        impacto="Aumenta risco de continuidade e caixa.",
        implementacao="implementado",
        ativo_no_sistema=True,
    ),
    AlertCatalogEntry(
        id=4,
        categoria="operacional",
        nivel="atencao",
        titulo="Queda de conversão consulta → cirurgia > 10pp vs média histórica",
        como_funciona="Compara conversão da competência de referência com média dos 6 meses anteriores da própria unidade.",
        dado_base="FactUnidadeMensal (cirurgias, consultas_totais)",
        threshold="> 10 pontos percentuais de queda",
        impacto="Indica perda de eficiência comercial/clínica.",
        implementacao="pendente",
        ativo_no_sistema=False,
    ),
    AlertCatalogEntry(
        id=5,
        categoria="operacional",
        nivel="atencao",
        titulo="Cirurgias zeradas em mês que deveria ter dados",
        como_funciona="Sinaliza unidade com cirurgias=0 na última competência fechada, tendo histórico prévio de operação.",
        dado_base="FactUnidadeMensal.cirurgias",
        threshold="= 0 em mês fechado",
        impacto="Pode indicar paralisação operacional ou problema de captura.",
        implementacao="implementado",
        ativo_no_sistema=True,
    ),
    AlertCatalogEntry(
        id=6,
        categoria="operacional",
        nivel="atencao",
        titulo="Ticket médio abaixo de 90% da média da rede",
        como_funciona="Compara ticket da unidade com média de rede no período.",
        dado_base="FactUnidadeMensal (receita_operacional/cirurgias)",
        threshold="< 90% da média da rede",
        impacto="Indica possível ineficiência de mix/preço.",
        implementacao="pendente",
        ativo_no_sistema=False,
    ),
    AlertCatalogEntry(
        id=7,
        categoria="operacional",
        nivel="info",
        titulo="Alta volatilidade de receita",
        como_funciona="Calcula coeficiente de variação da receita dos últimos 12 meses por unidade.",
        dado_base="FactUnidadeMensal.receita_operacional",
        threshold="CV > 40%",
        impacto="Mostra previsibilidade baixa de performance.",
        implementacao="pendente",
        ativo_no_sistema=False,
    ),
    AlertCatalogEntry(
        id=8,
        categoria="operacional",
        nivel="info",
        titulo="Volume abaixo do esperado para o mês pela sazonalidade",
        como_funciona="Compara produção do mês com expectativa histórica do mesmo mês calendário.",
        dado_base="FactUnidadeMensal.cirurgias",
        threshold="< 70% do esperado",
        impacto="Sinaliza desvio relevante de demanda/produção.",
        implementacao="pendente",
        ativo_no_sistema=False,
    ),
    AlertCatalogEntry(
        id=9,
        categoria="fiscal",
        nivel="atencao",
        titulo="% NF emitida abaixo de 65%",
        como_funciona="Avalia percentual_nf na competência de referência.",
        dado_base="FactFiscalMensal.percentual_nf",
        threshold="< 65%",
        impacto="Aumenta exposição fiscal e risco de não conformidade.",
        implementacao="implementado",
        ativo_no_sistema=True,
    ),
    AlertCatalogEntry(
        id=10,
        categoria="fiscal",
        nivel="atencao",
        titulo="NF > 100% da receita no mês",
        como_funciona="Avalia percentual_nf acima de 100% na competência de referência.",
        dado_base="FactFiscalMensal.percentual_nf",
        threshold="> 100%",
        impacto="Pode indicar erro de base, competência ou integração fiscal.",
        implementacao="implementado",
        ativo_no_sistema=True,
    ),
    AlertCatalogEntry(
        id=11,
        categoria="tendencia",
        nivel="atencao",
        titulo="Tendência de queda de receita por 4+ meses",
        como_funciona="Aplica slope em janela de receita recente por unidade.",
        dado_base="FactUnidadeMensal.receita_operacional",
        threshold="slope negativo relevante em 6 meses",
        impacto="Antecipa deterioração gradual antes de ruptura.",
        implementacao="pendente",
        ativo_no_sistema=False,
    ),
    AlertCatalogEntry(
        id=12,
        categoria="tendencia",
        nivel="info",
        titulo="Crescimento YoY > 20% por 2+ meses",
        como_funciona="Detecta sequência de crescimento YoY acima de 20%.",
        dado_base="FactUnidadeMensal.receita_operacional",
        threshold="> 20% por 2 meses",
        impacto="Evidencia benchmark positivo de execução.",
        implementacao="pendente",
        ativo_no_sistema=False,
    ),
    AlertCatalogEntry(
        id=13,
        categoria="positivo",
        nivel="info",
        titulo="Unidade saiu do vermelho",
        como_funciona="Detecta transição recente de EBITDA/margem negativa para positiva.",
        dado_base="FactFinanceiroMensal (ebitda, margem_ebitda)",
        threshold="mês anterior negativo e mês atual positivo",
        impacto="Indica recuperação operacional/financeira.",
        implementacao="implementado",
        ativo_no_sistema=True,
    ),
)


def get_catalog() -> list[dict]:
    return [entry.to_dict() for entry in CATALOG]


def get_catalog_index() -> dict[int, AlertCatalogEntry]:
    return {entry.id: entry for entry in CATALOG}
