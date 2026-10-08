"""
prompt_tune.py

Gera os prompts de indexação do GraphRAG (extração do grafo, resumo de
descrições e relatórios de comunidade) adaptados ao CDC.

Por que não usar o `graphrag prompt-tune` padrão?
  1. Ele não aceita uma taxonomia de entidades: ou "descobre" os tipos
     sozinho (e os grava fixos no extract_graph.txt, ignorando os
     `entity_types` do settings.yaml), ou gera um prompt sem tipos.
  2. Ele procura um modelo com o ID fixo "default_completion_model".
  3. Ele sorteia os trechos usados como exemplo (não reprodutível).

Este script executa as MESMAS etapas e funções do prompt-tune oficial
(graphrag.api.prompt_tune.generate_indexing_prompts, versão 3.1.0), com
estas diferenças:
  - usa a taxonomia definida em extract_graph.entity_types (settings.yaml);
  - acrescenta ao prompt de extração uma DEFINIÇÃO de cada tipo
    (ENTITY_TYPE_DEFINITIONS) e REGRAS DE NOMEAÇÃO (NAMING_RULES), que
    também orientam a geração dos exemplos;
  - fixa domínio e idioma;
  - usa artigos escolhidos (EXAMPLE_IDS / CONTEXT_IDS) em vez de sorteio.

Os chunks são montados exatamente como na indexação (mesmo chunker e
mesmo prepend_metadata). Os prompts são gravados em data/prompts e os
dados da geração (persona, papel, artigos usados...) em
data/prompts/prompt_tune_metadata.json, para documentação.

Uso (dentro do container graphrag):
    python /scripts/prompt_tune.py            # gera e grava os prompts
    python /scripts/prompt_tune.py --dry-run  # gera e só mostra
"""
from __future__ import annotations

import argparse
import asyncio
import dataclasses
import json
import os
from datetime import datetime, timezone
from importlib.metadata import version
from pathlib import Path

from graphrag.config.load_config import load_config
from graphrag.index.workflows.create_base_text_units import chunk_document
from graphrag.prompt_tune.generator.community_report_rating import (
    generate_community_report_rating,
)
from graphrag.prompt_tune.generator.community_report_summarization import (
    COMMUNITY_SUMMARIZATION_FILENAME,
    create_community_summarization_prompt,
)
from graphrag.prompt_tune.generator.community_reporter_role import (
    generate_community_reporter_role,
)
from graphrag.prompt_tune.generator.entity_relationship import (
    generate_entity_relationship_examples,
)
from graphrag.prompt_tune.generator.entity_summarization_prompt import (
    ENTITY_SUMMARIZATION_FILENAME,
    create_entity_summarization_prompt,
)
from graphrag.prompt_tune.generator.extract_graph_prompt import (
    EXTRACT_GRAPH_FILENAME,
    create_extract_graph_prompt,
)
from graphrag.prompt_tune.generator.persona import generate_persona
from graphrag.tokenizer.get_tokenizer import get_tokenizer
from graphrag_chunking.chunker_factory import create_chunker
from graphrag_input import create_input_reader
from graphrag_llm.completion import create_completion
from graphrag_storage import create_storage

ROOT = Path(os.environ.get("GRAPHRAG_ROOT", "/data"))

DOMAIN = (
    "legislação consumerista brasileira "
    "(Código de Defesa do Consumidor, Lei nº 8.078/1990)"
)
LANGUAGE = "português do Brasil"

# Definição de cada tipo de entidade da taxonomia. As chaves devem ser
# exatamente os tipos de extract_graph.entity_types no settings.yaml.
# Atenção: não use chaves (os caracteres de abrir/fechar chave) nestes textos,
# pois o GraphRAG formata o prompt com str.format na indexação.
ENTITY_TYPE_DEFINITIONS = {
    "consumidor": (
        "consumidor e equiparados (coletividade de pessoas, vítimas do evento, "
        "pessoas expostas às práticas comerciais), incluindo o consumidor superendividado"
    ),
    "fornecedor": (
        "quem fornece produtos ou serviços: fabricante, produtor, construtor, importador, "
        "comerciante, prestador de serviço, fornecedor de crédito, intermediário"
    ),
    "orgao_entidade": (
        "órgãos e entidades públicos ou privados que atuam na defesa do consumidor: Procon, "
        "Sistema Nacional de Defesa do Consumidor, Ministério Público, Defensoria Pública, "
        "União, Estados, Municípios, Poder Judiciário, associações de defesa do consumidor"
    ),
    "produto": (
        "bens objeto da relação de consumo: móveis ou imóveis, materiais ou imateriais, "
        "duráveis ou não duráveis, perigosos ou nocivos, peças de reposição"
    ),
    "servico": (
        "atividades fornecidas mediante remuneração, inclusive bancárias, financeiras, "
        "de crédito, securitárias e serviços públicos"
    ),
    "contrato": (
        "contratos de consumo e seus elementos: contrato de adesão, cláusulas contratuais, "
        "garantia legal e contratual, crédito, financiamento, compra e venda a prazo"
    ),
    "direito": (
        "direitos assegurados ao consumidor: direitos básicos, direito de arrependimento, "
        "direito à informação, à reparação de danos, à repactuação de dívidas"
    ),
    "obrigacao": (
        "deveres impostos ao fornecedor ou ao poder público: informar, reparar, sanar o vício, "
        "manter peças de reposição, cumprir a oferta"
    ),
    "pratica_abusiva": (
        "condutas vedadas ao fornecedor: práticas abusivas, publicidade enganosa ou abusiva, "
        "cobrança vexatória de dívidas, cláusulas abusivas"
    ),
    "instituto_juridico": (
        "princípios e conceitos jurídicos: princípios da Política Nacional das Relações de "
        "Consumo (vulnerabilidade, boa-fé, harmonização), relação de consumo, responsabilidade "
        "objetiva e solidária, fato e vício do produto ou serviço, decadência e prescrição, "
        "desconsideração da personalidade jurídica, inversão do ônus da prova, "
        "superendividamento, mínimo existencial"
    ),
    "sancao_administrativa": (
        "sanções aplicadas pela administração pública: multa, apreensão, inutilização, "
        "cassação de registro ou licença, interdição, intervenção, contrapropaganda"
    ),
    "infracao_penal": (
        "crimes contra as relações de consumo tipificados no código e suas penas"
    ),
    "instrumento_processual": (
        "meios de defesa do consumidor em juízo: ações coletivas, ação civil pública, defesa de "
        "interesses difusos, coletivos e individuais homogêneos, coisa julgada, liquidação e "
        "execução, conciliação e processo por superendividamento"
    ),
    "dispositivo_legal": (
        "artigos do CDC e de outras normas citadas no texto: Constituição Federal, Código Penal, "
        "Código de Processo Civil, outras leis"
    ),
}

# Regras de nomeação: evitam que a mesma entidade apareça com nomes diferentes
# (o GraphRAG funde entidades pelo nome exato) e que conceitos diferentes com o
# mesmo nome sejam fundidos.
NAMING_RULES = [
    "Escreva os nomes das entidades em MAIÚSCULAS, no singular, em português e sem artigo "
    "inicial (CONSUMIDOR, e não O CONSUMIDOR).",
    "Use os termos do próprio CDC, sem sinônimos (FORNECEDOR, e não EMPRESA; PRODUTO, e não MERCADORIA).",
    "Nomeie artigos do CDC como ART. 6º DO CDC, ART. 54-A DO CDC ou ART. 10 DO CDC "
    "(ordinal até o nono artigo, cardinal a partir do décimo). Use o artigo como unidade: "
    "parágrafos, incisos e alíneas vão na descrição, não no nome.",
    "Nomeie outras normas pelo nome usual ou pelo número com ano de quatro dígitos: "
    "CONSTITUIÇÃO FEDERAL, CÓDIGO PENAL, LEI Nº 7.347/1985.",
    "Prazos não são entidades: registre-os na descrição do direito, da obrigação ou do "
    "instituto a que se referem (por exemplo, a decadência em 30 ou 90 dias).",
    "Se o artigo estiver vetado ou revogado (situacao no cabeçalho do trecho), crie a "
    "entidade do dispositivo e registre o veto ou a revogação na descrição.",
]

# Artigos usados como EXEMPLOS de extração (o GraphRAG usa no máximo 5),
# escolhidos para cobrir o maior número possível de tipos:
#   art. 6  -> direito, consumidor, produto, servico, instituto_juridico
#   art. 12 -> fornecedor, produto, obrigacao, instituto_juridico
#   art. 51 -> pratica_abusiva, contrato, consumidor, fornecedor
#   art. 56 -> sancao_administrativa, dispositivo_legal
#   art. 82 -> orgao_entidade, instrumento_processual, dispositivo_legal
# Os tipos sem exemplo (ex.: infracao_penal) são guiados pelas definições.
EXAMPLE_IDS = ["cdc_art_6", "cdc_art_12", "cdc_art_51", "cdc_art_56", "cdc_art_82"]

# Artigos usados como CONTEXTO para gerar o papel do relator de comunidades
# e os critérios de relevância (inclui os exemplos e outros temas do código).
CONTEXT_IDS = EXAMPLE_IDS + [
    "cdc_art_2",    # conceito de consumidor
    "cdc_art_4",    # princípios da Política Nacional
    "cdc_art_18",   # vício do produto
    "cdc_art_26",   # decadência
    "cdc_art_39",   # práticas abusivas
    "cdc_art_54-A", # superendividamento
    "cdc_art_54-E", # artigo vetado
    "cdc_art_66",   # infração penal
    "cdc_art_106",  # Sistema Nacional de Defesa do Consumidor
]


def guidance_text() -> str:
    """Bloco com definições dos tipos e regras de nomeação (em português)."""
    lines = ["-Definições dos tipos de entidade-"]
    lines += [f"- {k}: {v}." for k, v in ENTITY_TYPE_DEFINITIONS.items()]
    lines += ["", "-Regras de nomeação das entidades-"]
    lines += [f"{n}. {r}" for n, r in enumerate(NAMING_RULES, start=1)]
    return "\n".join(lines)


def inject_guidance(prompt: str, guidance: str) -> str:
    """Insere o bloco de orientações antes da seção de exemplos do prompt."""
    marker = "-Examples-"
    if marker not in prompt:
        raise SystemExit("Marcador -Examples- não encontrado no prompt gerado.")
    return prompt.replace(marker, guidance + "\n\n" + marker, 1)


async def load_chunks(config) -> dict[str, str]:
    """Monta {id_do_documento: texto_do_chunk} exatamente como na indexação."""
    emb_cfg = config.get_embedding_model_config(config.embed_text.embedding_model_id)
    tokenizer = get_tokenizer(model_config=emb_cfg)
    chunker = create_chunker(config.chunking, tokenizer.encode, tokenizer.decode)
    reader = create_input_reader(config.input, create_storage(config.input_storage))
    chunks: dict[str, str] = {}
    for doc in await reader.read_files():
        doc_dict = dataclasses.asdict(doc)
        parts = chunk_document(doc_dict, chunker, config.chunking.prepend_metadata)
        if len(parts) > 1:
            print(f"AVISO: {doc_dict['id']} gerou {len(parts)} chunks; usando o primeiro.")
        chunks[str(doc_dict["id"])] = parts[0]
    return chunks


async def main(dry_run: bool, max_tokens: int, min_examples: int) -> None:
    config = load_config(ROOT)
    entity_types = list(config.extract_graph.entity_types)
    if set(entity_types) != set(ENTITY_TYPE_DEFINITIONS):
        raise SystemExit(
            "A taxonomia do settings.yaml e ENTITY_TYPE_DEFINITIONS divergem.\n"
            f"  só no settings: {sorted(set(entity_types) - set(ENTITY_TYPE_DEFINITIONS))}\n"
            f"  só no script:   {sorted(set(ENTITY_TYPE_DEFINITIONS) - set(entity_types))}"
        )
    guidance = guidance_text()
    model_id = config.extract_graph.completion_model_id
    model_cfg = config.get_completion_model_config(model_id)
    llm = create_completion(model_cfg)

    chunks = await load_chunks(config)
    missing = [i for i in CONTEXT_IDS if i not in chunks]
    if missing:
        raise SystemExit(f"Artigos não encontrados no corpus: {missing}")
    example_docs = [chunks[i] for i in EXAMPLE_IDS]
    context_docs = [chunks[i] for i in CONTEXT_IDS]

    print(f"Modelo: {model_cfg.model_provider}/{model_cfg.model} ({model_id})")
    print(f"Taxonomia: {', '.join(entity_types)}")

    print("1/5 Gerando persona...")
    persona = await generate_persona(llm, DOMAIN)

    print("2/5 Gerando critérios de relevância dos relatórios...")
    rating = await generate_community_report_rating(
        llm, domain=DOMAIN, persona=persona, docs=context_docs
    )

    print("3/5 Gerando exemplos de extração com a taxonomia...")
    # As definições e regras entram como instrução de sistema, para que os
    # exemplos gerados já sigam a taxonomia e a nomeação esperadas.
    examples = await generate_entity_relationship_examples(
        llm,
        persona=persona + "\n\n" + guidance,
        entity_types=entity_types,
        docs=example_docs,
        language=LANGUAGE,
        json_mode=False,  # a indexação usa o formato com delimitadores
    )
    extract_prompt = create_extract_graph_prompt(
        entity_types=entity_types,
        docs=example_docs,
        examples=examples,
        language=LANGUAGE,
        json_mode=False,
        tokenizer=get_tokenizer(model_config=model_cfg),
        max_token_count=max_tokens,
        min_examples_required=min_examples,
    )
    extract_prompt = inject_guidance(extract_prompt, guidance)

    print("4/5 Gerando prompt de resumo de descrições...")
    summarize_prompt = create_entity_summarization_prompt(persona=persona, language=LANGUAGE)

    print("5/5 Gerando papel do relator e prompt de relatórios de comunidade...")
    role = await generate_community_reporter_role(
        llm, domain=DOMAIN, persona=persona, docs=context_docs
    )
    community_prompt = create_community_summarization_prompt(
        persona=persona, role=role, report_rating_description=rating, language=LANGUAGE
    )

    tokenizer = get_tokenizer(model_config=model_cfg)
    n_examples = extract_prompt.count("Example ")
    print(
        f"\nPrompt de extração: {tokenizer.num_tokens(extract_prompt)} tokens, "
        f"{n_examples} exemplo(s)."
    )

    metadata = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "graphrag_version": version("graphrag"),
        "model": f"{model_cfg.model_provider}/{model_cfg.model}",
        "domain": DOMAIN,
        "language": LANGUAGE,
        "entity_types": entity_types,
        "entity_type_definitions": ENTITY_TYPE_DEFINITIONS,
        "naming_rules": NAMING_RULES,
        "example_ids": EXAMPLE_IDS,
        "context_ids": CONTEXT_IDS,
        "max_tokens": max_tokens,
        "min_examples": min_examples,
        "examples_in_prompt": n_examples,
        "persona": persona,
        "community_reporter_role": role,
        "community_report_rating": rating,
    }

    if dry_run:
        print("\n--- extract_graph.txt ---\n" + extract_prompt)
        print("\n--- metadados ---\n" + json.dumps(metadata, ensure_ascii=False, indent=2))
        return

    out = ROOT / "prompts"
    out.mkdir(parents=True, exist_ok=True)
    (out / EXTRACT_GRAPH_FILENAME).write_text(extract_prompt, encoding="utf-8")
    (out / ENTITY_SUMMARIZATION_FILENAME).write_text(summarize_prompt, encoding="utf-8")
    (out / COMMUNITY_SUMMARIZATION_FILENAME).write_text(community_prompt, encoding="utf-8")
    (out / "prompt_tune_metadata.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"Prompts gravados em {out}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--dry-run", action="store_true", help="Não grava os arquivos.")
    parser.add_argument("--max-tokens", type=int, default=5000,
                        help="Limite de tokens do prompt de extração (padrão: 5000).")
    parser.add_argument("--min-examples", type=int, default=4,
                        help="Mínimo de exemplos no prompt de extração (padrão: 4).")
    a = parser.parse_args()
    asyncio.run(main(a.dry_run, a.max_tokens, a.min_examples))
