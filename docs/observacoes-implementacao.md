# Observações de implementação e defeitos encontrados

Este documento reúne os defeitos e comportamentos não documentados do GraphRAG 3.1.0
identificados durante o trabalho, as correções e contornos adotados e os problemas de
configuração, de preparação do corpus e de ambiente enfrentados no desenvolvimento. É
referenciado pela monografia (`docs/paper/`), que cita os itens pelo número da tabela
abaixo. O histórico completo, com datas e medições, está em
[`implementation-log.md`](implementation-log.md).

A configuração completa usada na indexação e nas consultas está em
[`data/settings.yaml`](../data/settings.yaml), e a análise de cada opção das buscas, em
[`notes/configuracao-buscas.md`](notes/configuracao-buscas.md).

## 1. Defeitos e comportamentos não documentados do GraphRAG 3.1.0

O uso do GraphRAG fora dos exemplos da documentação (em português, com taxonomia
própria, com modelos de raciocínio e chamado como biblioteca pelo backend) revelou os
problemas abaixo. Vários afetam silenciosamente o resultado das consultas e, portanto,
qualquer comparação entre modalidades.

| # | Problema | Efeito |
|---|---|---|
| 1 | O método `search()` da busca básica chama a geração em modo *streaming* sem aguardar a corrotina (`await` ausente). | O erro é capturado internamente e a busca básica **sempre devolve resposta vazia**, sem aviso, quando usada como biblioteca. A CLI não é afetada por usar outro método. O defeito persiste na versão 3.2.0. Sem correção, o *baseline* da comparação seria inválido. |
| 2 | O ajuste automático de *prompts* reutiliza a mesma lista de mensagens em todas as chamadas de geração de exemplos. | Cada chamada recebe os textos de todos os exemplos, e o modelo responde sempre sobre o último: todos os exemplos de extração saem do mesmo trecho. |
| 3 | O ajuste automático de *prompts* não aceita uma taxonomia definida pelo usuário. | Os tipos "descobertos" pelo modelo são gravados fixos no *prompt*, ignorando os `entity_types` da configuração; sem a descoberta, o *prompt* sai sem tipo algum. O comando exige ainda um modelo com identificador fixo (`default_completion_model`). |
| 4 | A leitura dos *prompts* de consulta resolve o caminho em relação ao diretório corrente e, se o arquivo não existir, usa o *prompt* padrão. | Um erro no nome ou no caminho do arquivo faz a consulta usar silenciosamente o *prompt* padrão em inglês. |
| 5 | A substituição de variáveis de ambiente é aplicada ao `settings.yaml` inteiro, incluindo comentários. | Um cifrão em um comentário ou uma referência comentada a uma variável inexistente impede o carregamento da configuração. |
| 6 | Apenas a DRIFT define temperatura nas consultas, com valor padrão 0, herança da versão 2. | Inconsistência entre modalidades; com modelos de raciocínio, que só aceitam temperatura 1, a DRIFT falha. |
| 7 | Na DRIFT, as proporções padrão das buscas locais somam 1 (0,9 + 0,1). | Não sobra espaço para entidades e relações; e, neste índice, nenhum relatório cabe nos 10% restantes. As buscas locais da DRIFT passam a usar apenas unidades de texto, ou seja, o grafo só é usado no primer. |
| 8 | Na DRIFT, as perguntas de acompanhamento de cada rodada são escolhidas por sorteio. | Fonte adicional de variação entre execuções; as notas das perguntas não influenciam a exploração. |
| 9 | Nas buscas local e básica, o contexto recuperado só é notificado aos *callbacks* depois da geração da resposta. | Não é possível exibir o contexto antes da resposta usando apenas a interface de *callbacks*. |
| 10 | As métricas de *tokens* das consultas são calculadas pela contagem do texto enviado e recebido. | Não incluem os *tokens* de raciocínio dos modelos de raciocínio e, portanto, subestimam o custo real. |
| 11 | A versão do LiteLLM utilizada não reconhece modelos lançados depois dela. | Parâmetros não suportados pelo modelo não são filtrados automaticamente e precisam ser definidos de forma compatível na configuração. |
| 12 | A busca básica converte os resultados da busca vetorial em um conjunto de identificadores e filtra a tabela de unidades de texto por ele. | Os trechos são enviados ao modelo na ordem do corpus, e não na ordem de similaridade; o modelo não sabe quais trechos são mais relevantes. |
| 13 | Na busca local, os relatórios de comunidade não são truncados e só entram se couberem na fração reservada a eles (15% de 12 mil *tokens*, por padrão). | Com relatórios maiores que essa fração, como os deste índice, nenhum relatório é incluído no contexto, sem aviso. |

## 2. Correção da busca básica (item 1)

O primeiro teste da busca básica pela aplicação web devolveu uma resposta vazia, sem
erro. A causa: `BasicSearch.search()` chama a geração do modelo em modo streaming sem o
`await` necessário e percorre o resultado como um iterador assíncrono; o erro é
capturado internamente e a busca devolve resposta vazia. A CLI não é afetada porque usa
`stream_search()`, que tem o `await`. O defeito também está na versão 3.2.0.

Como o backend não deve modificar a biblioteca, a correção é um invólucro do modelo
entregue ao motor da busca básica (`app/backend/app/services/query_service.py`): quando
o motor pede uma geração em streaming, o invólucro devolve um iterador assíncrono que
primeiro aguarda a chamada e depois repassa os fragmentos. Prompt, trechos recuperados,
modelo e parâmetros continuam idênticos aos da CLI. Sem a correção, o baseline vetorial
"responderia" sempre vazio, o que invalidaria qualquer comparação com as modalidades
baseadas em grafo.

```python
class _AwaitedStreamModel:
    """Faz a chamada em streaming sem await devolver um iterador assíncrono."""
    def __init__(self, model):
        self._model = model

    def __getattr__(self, name):          # demais atributos: os do modelo original
        return getattr(self._model, name)

    def completion_async(self, **kwargs):
        if not kwargs.get("stream"):
            return self._model.completion_async(**kwargs)
        async def _stream():
            response = await self._model.completion_async(**kwargs)
            async for chunk in response:
                yield chunk
        return _stream()
```

## 3. Outros contornos no backend

- **Contexto antes da resposta (item 9):** o backend substitui, na instância do motor
  criada para cada consulta, o método que monta o contexto por uma versão que chama o
  original e emite o contexto e o prompt final antes da geração.
- **Prompts de consulta (item 4):** os caminhos são resolvidos a partir da pasta raiz do
  GraphRAG, e o backend falha com mensagem clara se um arquivo configurado não existir.
- **Temperatura (itens 6 e 11):** temperatura 1 explícita nos argumentos de chamada dos
  modelos e nos campos próprios da DRIFT.

## 4. Ajuste de prompts (itens 2 e 3)

O `scripts/prompt_tune.py` substitui o `graphrag prompt-tune`: usa a taxonomia da
configuração, gera cada exemplo de extração em uma conversa independente (corrige o
item 2), normaliza os exemplos (nomes em maiúsculas, tipos com erro de digitação como
`instrument_processual`) e alerta quando um exemplo não cita o próprio artigo.

## 5. Erros de configuração corrigidos antes da indexação

| Erro | Efeito | Correção |
|---|---|---|
| Caminho do banco vetorial com barra invertida (`output\lancedb`) | No contêiner Linux, criava uma pasta com a barra no nome | Barra normal |
| Nome inexistente para o prompt de redução da DRIFT | A DRIFT usaria silenciosamente o prompt padrão | Nome corrigido |
| Cifrão no padrão de nomes de arquivo de entrada | Erro de interpretação da configuração (item 5) | Linha removida (o padrão da biblioteca é o mesmo) |
| Blocos comentados de outros provedores com referências a chaves inexistentes | Falha no carregamento, mesmo comentados (item 5) | Blocos movidos para `config/model_providers.yaml` |
| Parâmetro `max_tokens` no teste dos modelos | Rejeitado pelos modelos, que aceitam apenas `max_completion_tokens` | Parâmetro removido do script de teste |

## 6. Preparação do corpus: problemas do parser

| Problema | Causa | Correção |
|---|---|---|
| Identificadores repetidos (arts. 54 e 54-A a 54-G; 42-A; 104-A a 104-C) | A expressão regular do artigo descartava o sufixo de letra | O número inclui o sufixo e o id inclui a sigla da lei (`cdc_art_54-A`); o parser falha se houver id repetido |
| Cabeçalhos como "Art. 11º" e "Art. 54º-C" | O cabeçalho era remontado sempre com ordinal | Regra da LC nº 95/1998: ordinal até o nono artigo, cardinal a partir do décimo |
| Capítulo VI-A lido como "VI", com nome "-A" | Os níveis da hierarquia não aceitavam sufixo | Níveis com sufixo de letra; nome lido da linha seguinte |
| Artigos inteiros marcados como vetados quando só um parágrafo o era (ex.: arts. 6º e 37) | Busca de "(Vetado)" em todo o texto do artigo | Campos `situacao` e `dispositivos_vetados_ou_revogados` |

## 7. Problemas de ambiente da aplicação

- **Página em branco:** o `package.json` pedia Tailwind CSS 4, mas o código foi escrito
  para a versão 3; o CSS falhava e derrubava a aplicação. Versão fixada em `^3.4.17`.
- **Dependências da máquina dentro da imagem:** sem `.dockerignore`, o `COPY . .`
  copiava a pasta `node_modules` local por cima da instalação limpa. Criados
  `.dockerignore` no frontend e no backend.
- **Recursão infinita na árvore da DRIFT:** o estado da DRIFT pode ter arestas repetidas
  e laços; a árvore passou a ignorá-los.
- **Cores das comunidades:** as cores vinham de um hash de `comm-<id>`; ids próximos
  davam matizes quase iguais. Agora as comunidades usam o ângulo áureo (≈ 137,5°) e os
  tipos uma paleta fixa (`app/frontend/src/lib/colors.ts`).
