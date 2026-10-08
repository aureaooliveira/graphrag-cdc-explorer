"""
legislation_parser.py

Parser estrutural de legislação federal brasileira para preparação de
corpus a ser indexado em sistemas de RAG (ex.: GraphRAG).

CONTEXTO E GENERALIZAÇÃO
-------------------------
A técnica legislativa de leis federais brasileiras é normatizada pela
Lei Complementar n.º 95/1998, que define a hierarquia de divisão dos
textos legais:

    Parte > Livro > Título > Capítulo > Seção > Subseção
    > Artigo > Parágrafo > Inciso > Alínea > Item

Como essa convenção é compartilhada pela maior parte da legislação
federal codificada (Código de Defesa do Consumidor, Código Civil,
Código Penal, CLT, CPC etc.), este parser foi escrito de forma
configurável (ver LEVELS abaixo) para ser reaproveitável além do CDC,
servindo como peça de um framework de preparação de corpus jurídico
para RAG no contexto legal brasileiro.

LIMITAÇÕES CONHECIDAS (documente-as caso use este script como parte de
um framework mais amplo):
  1. Nem toda lei usa todos os níveis hierárquicos (leis de assunto
     único costumam ter só Artigos, sem Título/Capítulo/Seção) — os
     campos correspondentes simplesmente ficam `None` nesses casos.
  2. O comportamento depende da qualidade do texto de entrada. Textos
     extraídos de PDF via OCR podem exigir limpeza adicional antes de
     passar por este parser.
  3. Textos de fontes diferentes do planalto.gov.br podem ter
     cabeçalhos/rodapés de página distintos dos tratados na lista
     BOILERPLATE_PATTERNS — ajuste-a conforme a fonte utilizada.

TRATAMENTO DE DISPOSITIVOS VETADOS/REVOGADOS
---------------------------------------------
Por padrão, todo o texto é preservado, inclusive artigos e dispositivos
(parágrafos, incisos, alíneas) vetados ou revogados — o registro do veto
ou da revogação também é informação jurídica (ex.: Art. 54-E, vetado na
Lei nº 14.181/2021). Cada artigo recebe:
  - `situacao`: "vigente", "vetado" ou "revogado", referente ao artigo
    como um todo (um artigo vigente pode ter parágrafos vetados);
  - `dispositivos_vetados_ou_revogados`: rótulos dos parágrafos/incisos/
    alíneas vetados ou revogados dentro do artigo (ex.: ["§ 1°", "IX"]).
Use --remover-vetados para descartar esses dispositivos do corpus.

ARTIGOS COM SUFIXO
------------------
Artigos acrescidos por leis posteriores (ex.: Art. 54-A, Art. 104-B)
recebem id e número próprios (ex.: "cdc_art_54-A"), assim como capítulos
acrescidos (ex.: Capítulo VI-A). O cabeçalho do artigo segue a LC 95/1998:
ordinal até o nono ("Art. 9º") e cardinal a partir do décimo ("Art. 10.").

USO
---
    python corpus/parser/legislation_parser.py corpus/raw/cdc_planalto.txt data/input/cdc.json \
        --lei-nome "Código de Defesa do Consumidor" \
        --lei-numero "Lei nº 8.078, de 11 de setembro de 1990" \
        --lei-sigla CDC [--remover-vetados]

Se nenhum argumento for passado, o script roda em modo de demonstração
com um texto de exemplo embutido (primeiros artigos do CDC), apenas
para validar a lógica do parser.
"""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass, field, asdict
from typing import Optional


# =============================================================================
# Configuração dos níveis hierárquicos (do mais abrangente ao mais específico)
# =============================================================================
# Cada nível é definido por uma chave (usada nos metadados de saída) e um
# regex que reconhece a linha de abertura daquele nível. O grupo 1 captura o
# "número" do nível (numeral romano, em geral); o nome (ex.: "Dos Direitos
# do Consumidor") normalmente vem na linha seguinte, não na mesma linha —
# o parser trata isso via look-ahead.
LEVELS = [
    {"key": "parte", "pattern": re.compile(r"^\s*PARTE\s+(.+?)\s*$", re.IGNORECASE)},
    {"key": "livro", "pattern": re.compile(r"^\s*LIVRO\s+([IVXLCDM]+(?:\s*-\s*[A-Z])?)(?![A-Za-z])\s*(.*)$", re.IGNORECASE)},
    {"key": "titulo", "pattern": re.compile(r"^\s*T[ÍI]TULO\s+([IVXLCDM]+(?:\s*-\s*[A-Z])?)(?![A-Za-z])\s*(.*)$", re.IGNORECASE)},
    {"key": "capitulo", "pattern": re.compile(r"^\s*CAP[ÍI]TULO\s+([IVXLCDM]+(?:\s*-\s*[A-Z])?)(?![A-Za-z])\s*(.*)$", re.IGNORECASE)},
    {"key": "secao", "pattern": re.compile(r"^\s*SE[ÇC][ÃA]O\s+([IVXLCDM]+(?:\s*-\s*[A-Z])?)(?![A-Za-z])\s*(.*)$", re.IGNORECASE)},
    {"key": "subsecao", "pattern": re.compile(r"^\s*SUBSE[ÇC][ÃA]O\s+([IVXLCDM]+(?:\s*-\s*[A-Z])?)(?![A-Za-z])\s*(.*)$", re.IGNORECASE)},
]
LEVEL_KEYS = [lvl["key"] for lvl in LEVELS]
# Os números dos níveis podem ter sufixo de letra (ex.: "CAPÍTULO VI-A",
# acrescido pela Lei nº 14.181/2021). O (?![A-Za-z]) evita confundir o
# início de uma palavra com numeral romano.

# Marcadores de microestrutura (dentro de um artigo)
# Grupo 1: número; grupo 2: sufixo opcional ("A" em "Art. 54-A."); grupo 3: caput.
ARTIGO_RE = re.compile(r"^\s*Art\.\s*(\d+)\s*[°º]?\s*(?:[-–]\s*([A-Z])\b)?\s*\.?\s*(.*)$")
PARAGRAFO_UNICO_RE = re.compile(r"^\s*Par[áa]grafo\s+[úu]nico\.?\s*(.*)$", re.IGNORECASE)
PARAGRAFO_NUM_RE = re.compile(r"^\s*§\s*(\d+)[°º]?\.?\s*(.*)$")
INCISO_RE = re.compile(r"^\s*([IVXLCDM]+)\s*[-–—]\s*(.*)$")
ALINEA_RE = re.compile(r"^\s*([a-z])\)\s*(.*)$")

# Dispositivo (artigo, parágrafo, inciso ou alínea) cujo único conteúdo é
# "(Vetado)"/"(Revogado)", eventualmente seguido de nota de alteração, ex.:
#   "Art. 11. (Vetado)."   "§ 1° (Vetado)."   "IX - (Vetado);"
#   "I - (VETADO);      (Incluído pela Lei nº 14.181, de 2021)"
_ROTULO_DISPOSITIVO = (
    r"(?:Art\.\s*\d+\s*[°º]?\s*(?:[-–]\s*[A-Z])?\s*\.?"
    r"|§\s*\d+\s*[°º]?\.?"
    r"|Par[áa]grafo\s+[úu]nico\.?"
    r"|[IVXLCDM]+\s*[-–—]"
    r"|[a-z]\))"
)
DISPOSITIVO_SEM_CONTEUDO_RE = re.compile(
    r"^\s*(" + _ROTULO_DISPOSITIVO
    + r")\s*\((vetad[oa]|revogad[oa])\)\s*[.;,]?\s*(?:\([^)]*\)\s*)*$",
    re.IGNORECASE,
)

# Linhas de ruído comuns em exportações de texto do planalto.gov.br.
# Ajuste/estenda esta lista conforme a fonte do texto utilizada.
BOILERPLATE_PATTERNS = [
    re.compile(r"^\s*Presidência da República\s*$", re.IGNORECASE),
    re.compile(r"^\s*Casa Civil\s*$", re.IGNORECASE),
    re.compile(r"^\s*Subchefia para Assuntos Jurídicos\s*$", re.IGNORECASE),
    re.compile(r"^\s*Página\s+\d+\s*$", re.IGNORECASE),
]


@dataclass
class Artigo:
    id: str
    artigo_num: str
    lei_sigla: Optional[str] = None
    lei_nome: Optional[str] = None
    lei_numero: Optional[str] = None
    parte: Optional[str] = None
    livro_num: Optional[str] = None
    livro_nome: Optional[str] = None
    titulo_num: Optional[str] = None
    titulo_nome: Optional[str] = None
    capitulo_num: Optional[str] = None
    capitulo_nome: Optional[str] = None
    secao_num: Optional[str] = None
    secao_nome: Optional[str] = None
    subsecao_num: Optional[str] = None
    subsecao_nome: Optional[str] = None
    situacao: str = "vigente"  # "vigente" | "vetado" | "revogado" (artigo inteiro)
    dispositivos_vetados_ou_revogados: list[str] = field(default_factory=list)
    text: str = ""


def _numero_artigo(numero: str, sufixo: Optional[str]) -> str:
    """"54" + "A" -> "54-A"; "10" + None -> "10"."""
    return f"{numero}-{sufixo.upper()}" if sufixo else numero


def _cabecalho_artigo(numero: str, sufixo: Optional[str]) -> str:
    """Cabeçalho canônico conforme a LC 95/1998 (art. 10, I): numeração
    ordinal até o nono artigo e cardinal a partir do décimo.
    Ex.: "Art. 1º", "Art. 10.", "Art. 54-A."."""
    if sufixo is None and int(numero) <= 9:
        return f"Art. {numero}º"
    return f"Art. {_numero_artigo(numero, sufixo)}."


def _id_artigo(numero_completo: str, lei_sigla: Optional[str]) -> str:
    """Id estável e único: "cdc_art_54-A". O prefixo da sigla evita colisão
    quando várias leis são indexadas juntas."""
    prefixo = f"{lei_sigla.lower()}_" if lei_sigla else ""
    return f"{prefixo}art_{numero_completo}"


def _is_boilerplate(line: str) -> bool:
    return any(p.match(line) for p in BOILERPLATE_PATTERNS)


def _clean_lines(raw_text: str) -> list[str]:
    """Remove ruído comum de exportação e normaliza espaços em branco."""
    lines = raw_text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    cleaned = []
    for line in lines:
        stripped = line.strip()
        if not stripped:
            cleaned.append("")  # preserva linha em branco como separador
            continue
        if _is_boilerplate(stripped):
            continue
        cleaned.append(stripped)
    return cleaned


def _match_level(line: str) -> Optional[tuple[str, str, str]]:
    """Retorna (chave_do_nivel, numero, nome_na_mesma_linha_ou_vazio) se a
    linha abrir um novo nível hierárquico (Parte/Livro/Título/.../Subseção)."""
    for lvl in LEVELS:
        m = lvl["pattern"].match(line)
        if m:
            if lvl["key"] == "parte":
                # "PARTE GERAL" / "PARTE ESPECIAL" -> número e nome coincidem
                return lvl["key"], m.group(1), ""
            numero = re.sub(r"\s*-\s*", "-", m.group(1)).upper()
            nome_mesma_linha = m.group(2).strip() if m.lastindex and m.lastindex >= 2 else ""
            return lvl["key"], numero, nome_mesma_linha
    return None


def parse_legislacao(
    raw_text: str,
    lei_sigla: Optional[str] = None,
    lei_nome: Optional[str] = None,
    lei_numero: Optional[str] = None,
    remover_vetados: bool = False,
) -> list[dict]:
    """Converte o texto bruto de uma lei federal brasileira em uma lista de
    dicionários, um por Artigo, com metadados de macroestrutura (Parte,
    Livro, Título, Capítulo, Seção, Subseção) e o texto completo do artigo
    (caput + parágrafos + incisos + alíneas) preservado em `text`.

    Por padrão todo o texto é mantido e a situação de veto/revogação fica
    registrada em `situacao` e `dispositivos_vetados_ou_revogados`. Se
    `remover_vetados` for True, artigos e dispositivos cujo único conteúdo
    é "(Vetado)"/"(Revogado)" são descartados.
    """
    lines = _clean_lines(raw_text)

    # Estado corrente da macroestrutura (num, nome) por nível
    current: dict[str, Optional[tuple[str, str]]] = {k: None for k in LEVEL_KEYS}

    artigos: list[Artigo] = []
    current_artigo: Optional[Artigo] = None
    buffer_lines: list[str] = []  # linhas do artigo atual sendo acumuladas

    def flush_artigo():
        nonlocal current_artigo, buffer_lines
        if current_artigo is not None:
            blocks = [b for b in _merge_blocks(buffer_lines) if b]
            m_artigo = DISPOSITIVO_SEM_CONTEUDO_RE.match(blocks[0]) if blocks else None
            if m_artigo:
                situacao = m_artigo.group(2).lower()
                current_artigo.situacao = "vetado" if situacao.startswith("vetad") else "revogado"
            sub_matches = [(b, DISPOSITIVO_SEM_CONTEUDO_RE.match(b)) for b in blocks[1:]]
            current_artigo.dispositivos_vetados_ou_revogados = [
                re.sub(r"\s*[-–—]$", "", m.group(1).strip()).rstrip(".").replace("°", "º")
                for _, m in sub_matches if m
            ]
            if remover_vetados and blocks:
                blocks = [blocks[0]] + [b for b, m in sub_matches if not m]
            current_artigo.text = "\n\n".join(blocks).strip()
            if not (remover_vetados and m_artigo):
                artigos.append(current_artigo)
        current_artigo = None
        buffer_lines = []

    i = 0
    n = len(lines)
    while i < n:
        line = lines[i]

        if not line:
            buffer_lines.append("")  # preserva separação de blocos
            i += 1
            continue

        level_match = _match_level(line)
        if level_match:
            flush_artigo()
            key, numero, nome_mesma_linha = level_match
            nome = nome_mesma_linha
            if not nome:
                # nome do nível normalmente está na próxima linha não-vazia
                j = i + 1
                while j < n and not lines[j]:
                    j += 1
                if j < n and not _match_level(lines[j]) and not ARTIGO_RE.match(lines[j]):
                    nome = lines[j]
                    i = j  # consome a linha do nome também
            current[key] = (numero, nome)
            # reseta todos os níveis abaixo do nível encontrado
            idx = LEVEL_KEYS.index(key)
            for lower_key in LEVEL_KEYS[idx + 1:]:
                current[lower_key] = None
            i += 1
            continue

        art_match = ARTIGO_RE.match(line)
        if art_match:
            flush_artigo()
            numero, sufixo, resto = art_match.group(1), art_match.group(2), art_match.group(3)
            numero_completo = _numero_artigo(numero, sufixo)
            current_artigo = Artigo(
                id=_id_artigo(numero_completo, lei_sigla),
                artigo_num=numero_completo,
                lei_sigla=lei_sigla,
                lei_nome=lei_nome,
                lei_numero=lei_numero,
                parte=current["parte"][1] if current["parte"] else None,
                livro_num=current["livro"][0] if current["livro"] else None,
                livro_nome=current["livro"][1] if current["livro"] else None,
                titulo_num=current["titulo"][0] if current["titulo"] else None,
                titulo_nome=current["titulo"][1] if current["titulo"] else None,
                capitulo_num=current["capitulo"][0] if current["capitulo"] else None,
                capitulo_nome=current["capitulo"][1] if current["capitulo"] else None,
                secao_num=current["secao"][0] if current["secao"] else None,
                secao_nome=current["secao"][1] if current["secao"] else None,
                subsecao_num=current["subsecao"][0] if current["subsecao"] else None,
                subsecao_nome=current["subsecao"][1] if current["subsecao"] else None,
            )
            buffer_lines = [f"{_cabecalho_artigo(numero, sufixo)} {resto}".strip()]
            i += 1
            continue

        # Linhas de microestrutura (parágrafo/inciso/alínea) ou continuação
        # de texto: tudo é preservado dentro do artigo corrente.
        if current_artigo is not None:
            buffer_lines.append(line)
        # Linhas fora de qualquer artigo (ex.: preâmbulo da lei) são
        # ignoradas propositalmente — ajuste aqui se quiser capturá-las.
        i += 1

    flush_artigo()

    vistos: dict[str, int] = {}
    for a in artigos:
        vistos[a.id] = vistos.get(a.id, 0) + 1
    duplicados = sorted(k for k, v in vistos.items() if v > 1)
    if duplicados:
        raise ValueError(
            "Ids de artigo duplicados (verifique o texto de entrada): "
            + ", ".join(duplicados)
        )
    return [asdict(a) for a in artigos]


def _merge_blocks(lines: list[str]) -> list[str]:
    """Agrupa linhas em blocos lógicos (caput, cada parágrafo, cada inciso,
    cada alínea), unindo linhas de continuação (quebras de linha de
    formatação do PDF/txt original) dentro do mesmo bloco."""
    blocks: list[str] = []
    buffer = ""
    for line in lines:
        if line == "":
            if buffer:
                blocks.append(buffer)
                buffer = ""
            continue
        is_new_block = (
            PARAGRAFO_UNICO_RE.match(line)
            or PARAGRAFO_NUM_RE.match(line)
            or INCISO_RE.match(line)
            or ALINEA_RE.match(line)
            or ARTIGO_RE.match(line)
        )
        if is_new_block and buffer:
            blocks.append(buffer)
            buffer = line
        elif is_new_block:
            buffer = line
        else:
            buffer = f"{buffer} {line}".strip() if buffer else line
    if buffer:
        blocks.append(buffer)
    return blocks


# =============================================================================
# Modo demonstração / CLI
# =============================================================================
_SAMPLE_TEXT = """
TÍTULO I
Dos Direitos do Consumidor

CAPÍTULO I
Disposições Gerais

        Art. 1° Este código estabelece normas de proteção e defesa do
consumidor, de ordem pública e interesse social, nos termos dos arts. 5°,
inciso XXXII, 170, inciso V, da Constituição Federal e art. 48 de suas
Disposições Transitórias.

        Art. 2° Consumidor é toda pessoa física ou jurídica que adquire
ou utiliza produto ou serviço como destinatário final.

        Parágrafo único. Equipara-se a consumidor a coletividade de
pessoas, ainda que indetermináveis, que haja intervindo nas relações de
consumo.

CAPÍTULO III
Dos Direitos Básicos do Consumidor

        Art. 6º São direitos básicos do consumidor:

        I - a proteção da vida, saúde e segurança contra os riscos
provocados por práticas no fornecimento de produtos e serviços
considerados perigosos ou nocivos;

        II - a educação e divulgação sobre o consumo adequado dos
produtos e serviços, asseguradas a liberdade de escolha e a igualdade nas
contratações;

        III - a informação adequada e clara sobre os diferentes produtos
e serviços, com especificação correta de quantidade, características,
composição, qualidade, tributos incidentes e preço, bem como sobre os
riscos que apresentem;
"""


def main():
    parser = argparse.ArgumentParser(
        description="Parser estrutural de legislação federal brasileira para corpus RAG."
    )
    parser.add_argument("entrada", nargs="?", help="Caminho do .txt com o texto bruto da lei.")
    parser.add_argument("saida", nargs="?", help="Caminho do .json de saída.")
    parser.add_argument("--lei-sigla", default=None, help='Ex.: "CDC"')
    parser.add_argument("--lei-nome", default=None, help='Ex.: "Código de Defesa do Consumidor"')
    parser.add_argument("--lei-numero", default=None, help='Ex.: "Lei nº 8.078, de 11 de setembro de 1990"')
    parser.add_argument("--remover-vetados", action="store_true",
                        help="Descarta artigos e dispositivos cujo conteúdo é apenas (Vetado)/(Revogado).")
    args = parser.parse_args()

    if args.entrada and args.saida:
        with open(args.entrada, "r", encoding="utf-8") as f:
            raw_text = f.read()
        out_path = args.saida
    else:
        print("[modo demonstração] Nenhum arquivo de entrada/saída informado — "
              "usando texto de exemplo embutido.\n")
        raw_text = _SAMPLE_TEXT
        out_path = "saida_demo.json"
        args.lei_sigla = args.lei_sigla or "CDC"
        args.lei_nome = args.lei_nome or "Código de Defesa do Consumidor"
        args.lei_numero = args.lei_numero or "Lei nº 8.078, de 11 de setembro de 1990"

    resultado = parse_legislacao(
        raw_text,
        lei_sigla=args.lei_sigla,
        lei_nome=args.lei_nome,
        lei_numero=args.lei_numero,
        remover_vetados=args.remover_vetados,
    )

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(resultado, f, ensure_ascii=False, indent=2)

    print(f"{len(resultado)} artigo(s) extraído(s). Saída escrita em: {out_path}")
    for art in resultado:
        preview = art["text"][:80].replace("\n", " ")
        print(f"  - {art['id']}: [{art.get('titulo_nome')} / {art.get('capitulo_nome')}] {preview}...")


if __name__ == "__main__":
    main()