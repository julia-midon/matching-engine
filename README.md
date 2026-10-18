# Matching Engine

Matching engine simples para **um único ativo**, em memória, escrita em Python. Cruza ordens por **prioridade preço-tempo** e suporta ordens *limit*, *market* e *pegged*, além de cancelamento, alteração de ordens e visualização do livro.

O projeto não tem dependências de execução (apenas a biblioteca padrão) e exige **Python 3.12 ou superior**.

## Sumário

- [Como executar](#como-executar)
- [Comandos](#comandos)
- [Exemplos](#exemplos)
- [Decisões de design](#decisões-de-design)
- [Arquitetura](#arquitetura)
- [Estruturas de dados e complexidade](#estruturas-de-dados-e-complexidade)
- [Testes](#testes)
- [Limitações conhecidas](#limitações-conhecidas)
- [Uso de IA](#uso-de-ia)

## Como executar

Na raiz do repositório:

```bash
pip install -e .            # apenas para executar
pip install -e ".[dev]"     # inclui pytest, pytest-cov e ruff (para testes e lint)
```

Modo interativo (com prompt `>>>`):

```bash
python -m matching_engine
```

Modo arquivo (um comando por linha) ou entrada padrão:

```bash
python -m matching_engine caminho/do/script.txt
python -m matching_engine caminho/do/script.txt --echo   # repete cada comando como ">>> comando"
cat caminho/do/script.txt | python -m matching_engine --echo
```

A flag `--echo` reproduz o formato dos exemplos do enunciado (comando seguido da sua saída). Em scripts, linhas em branco e linhas iniciadas por `#` são ignoradas. Para sair do modo interativo, use `exit`, `quit` ou Ctrl+D. A pasta [`examples/`](examples/) traz um script para cada cenário do enunciado:

| Script | Cenário |
| --- | --- |
| `statement_cancel.txt` | Cancelamento de ordem |
| `statement_market.txt` | Ordens limit e market, com preenchimento por ordem de chegada |
| `statement_modify.txt` | Alteração de preço, com perda de prioridade na fila |
| `statement_peg.txt` | Ordem pegged acompanhando o melhor bid |

```bash
python -m matching_engine examples/statement_market.txt --echo
```

Cada script deve ser executado isoladamente, pois cada execução começa com um livro vazio e os identificadores reiniciam em `identificador_1`.

> Sem instalar o pacote, também é possível rodar com `PYTHONPATH=src python -m matching_engine`.

## Comandos

Os comandos não diferenciam maiúsculas de minúsculas.

| Comando | Descrição |
| --- | --- |
| `limit <buy\|sell> <price> <qty>` | Ordem limite. Executa o que cruzar; o saldo fica no livro. |
| `market <buy\|sell> <qty>` | Ordem a mercado. Executa contra a liquidez disponível; o saldo é descartado. |
| `peg <bid\|offer> <buy\|sell> <qty>` | Ordem pegged que acompanha o melhor bid (compra) ou offer (venda). |
| `cancel order <id>` | Remove uma ordem do livro. |
| `modify order <id> [price <price>] [qty <qty>]` | Altera preço, quantidade ou ambos. |
| `print book` | Exibe o livro. |
| `help` | Lista os comandos. |
| `exit` / `quit` | Encerra. |

### Formato das saídas

| Situação | Saída |
| --- | --- |
| Ordem limit ou pegged aceita | `Order created: <side> <qty> @ <price> <id>` (pegged: `@ peg <bid\|offer>`) |
| Execução | `Trade, price: <preço>, qty: <quantidade>` |
| Cancelamento | `Order cancelled` |
| Alteração | `Order modified` (seguido das execuções geradas, se houver) |
| Entrada inválida | `Error: <motivo>` (o estado do livro não é alterado) |

Preços aceitam apenas o formato `10` ou `9.99` (sem sinal, sem vírgula decimal, sem notação científica). Quantidades são inteiros positivos. Preços são impressos normalizados (`10.50` vira `10.5`).

## Exemplos

### Execução e prioridade de chegada (exemplo do enunciado)

```
>>> limit buy 10 100
Order created: buy 100 @ 10 identificador_1
>>> limit sell 20 100
Order created: sell 100 @ 20 identificador_2
>>> limit sell 20 200
Order created: sell 200 @ 20 identificador_3
>>> market buy 150
Trade, price: 20, qty: 150
>>> market buy 200
Trade, price: 20, qty: 150
>>> market sell 200
Trade, price: 10, qty: 100
```

O `market buy 150` consome as 100 unidades da primeira venda e 50 da segunda, respeitando a ordem de chegada. O `market buy 200` executa apenas 150, que é tudo o que restava; o saldo é descartado.

### Limit order que cruza o livro

```
>>> limit buy 10 100
Order created: buy 100 @ 10 identificador_1
>>> limit sell 9 150
Order created: sell 150 @ 9 identificador_2
Trade, price: 10, qty: 100
>>> print book
Ordens de Compra    | Ordens de Venda
--------------------|-----------------
                    | 50 @ 9
```

A execução ocorre ao preço da ordem que já estava no livro (10), e o saldo (50) passa a repousar no livro.

### Alteração com perda de prioridade

```
>>> limit buy 10 200
Order created: buy 200 @ 10 identificador_1
>>> limit buy 9.99 100
Order created: buy 100 @ 9.99 identificador_2
>>> modify order identificador_1 price 9.98
Order modified
>>> print book
Ordens de Compra    | Ordens de Venda
--------------------|-----------------
100 @ 9.99          |
200 @ 9.98          |
>>> cancel order identificador_1
Order cancelled
```

### Ordem pegged

```
>>> limit buy 10 200
>>> limit buy 9.99 100
>>> limit sell 10.5 100
>>> peg bid buy 150
Order created: buy 150 @ peg bid identificador_4
>>> print book
Ordens de Compra    | Ordens de Venda
--------------------|-----------------
200 @ 10            | 100 @ 10.5
150 @ 10            |
100 @ 9.99          |
>>> limit buy 10.1 300
Order created: buy 300 @ 10.1 identificador_5
>>> print book
Ordens de Compra    | Ordens de Venda
--------------------|-----------------
150 @ 10.1          | 100 @ 10.5
300 @ 10.1          |
200 @ 10            |
100 @ 9.99          |
```

(As linhas `Order created` dos três primeiros comandos foram omitidas por brevidade.) A pegged acompanha o novo melhor bid (10.1) e, por ter sido criada antes da ordem de 300, mantém prioridade sobre ela no nível, exatamente como no enunciado.

## Decisões de design

O enunciado deixa algumas escolhas em aberto. Estas são as adotadas e o porquê.

### Limit order que gera trade é executada

O enunciado permite ignorar ou executar. A engine **executa**: a ordem limit atua como agressora contra o lado oposto enquanto o preço cruzar, e o saldo restante repousa no livro. Ignorar a ordem descartaria interesse legítimo de negociação, e deixá-la repousar sem executar produziria um livro cruzado (bid maior ou igual ao offer), o que contradiz o objetivo de uma matching engine. O preço da execução é o da **ordem passiva** (a que já estava no livro), de modo que o agressor nunca paga mais (nem recebe menos) do que o limite informado.

### Prioridade preço-tempo

Melhor preço primeiro (maior para compra, menor para venda) e, dentro do mesmo preço, a ordem mais antiga primeiro. A "idade" vem de um **contador monotônico** (`seq`), e não do relógio do sistema, o que garante ordem total e determinística mesmo para ordens criadas no mesmo instante. O `seq` é separado do `id`: o `id` nunca muda, enquanto o `seq` é renovado quando a ordem perde prioridade (por isso `modify` não consome número de identificador).

### Trades agregados por nível de preço

Cada ordem agressora gera **um `Trade` por nível de preço consumido**, e não um por ordem passiva. É o que o exemplo do enunciado mostra: 100 unidades da primeira venda mais 50 da segunda, ambas a 20, saem como `Trade, price: 20, qty: 150`. Uma ordem que varre vários níveis gera uma linha por nível.

### Ordem a mercado

Executa contra a liquidez disponível e **o saldo não executado é descartado** (nunca repousa no livro). Por isso ela não recebe identificador público (internamente usa `market_<n>`). Sem liquidez nenhuma, não há saída, pois não houve trade.

### Identificadores

Ordens limit e pegged recebem `identificador_<n>`, em sequência. O identificador é atribuído mesmo que a limit seja totalmente executada ao entrar; nesse caso a ordem nunca chega a repousar, e um `cancel` posterior retorna erro de "order not found". A linha `Order created` é impressa sempre, para toda ordem limit ou pegged aceita.

### O livro só é impresso sob demanda

O livro não é exibido automaticamente após cada comando; ele aparece com `print book`. No exemplo da ordem pegged, o enunciado mostra o livro depois de cada comando, e isso foi interpretado como um `print book` entre eles. Se fosse desejada a impressão automática, a mudança seria localizada em `commands.py`.

### Cancelamento

Remove a ordem do livro. Cancelar um id inexistente ou de uma ordem já totalmente executada é um **erro explícito** (`Error: order not found: <id>`), e não um no-op silencioso.

### Alteração de ordem

`modify` altera o preço, a quantidade ou ambos. A sintaxe `modify order <id> [price <p>] [qty <q>]` foi definida por mim, pois o enunciado não a especifica. Alterar uma ordem inexistente ou já executada gera erro explícito. A quantidade refere-se ao **saldo restante** da ordem (após execuções parciais).

- Mesmo preço e quantidade menor ou igual: a ordem **mantém a posição** na fila (reduzir exposição não prejudica ninguém).
- Preço diferente ou quantidade maior: a ordem **perde prioridade** e vai para o fim da fila do nível de preço correspondente, como pede o enunciado.
- Se, após a alteração, a ordem passar a cruzar o livro, ela é executada como agressora e os trades são impressos logo após `Order modified`.
- Em ordens pegged só a quantidade pode ser alterada, pois o preço é derivado do livro.

### Ordens pegged

Uma ordem pegged acompanha o melhor preço do **seu próprio lado** do livro: `peg bid` é uma ordem de **compra** que segue o melhor bid, e `peg offer` é uma ordem de **venda** que segue o melhor offer.

- **Referência ignora outras pegged.** O melhor bid/offer de referência considera apenas ordens não-pegged. Isso evita referência circular (uma pegged seguindo outra pegged) e é o que produz o comportamento do exemplo do enunciado, em que a pegged se posiciona no melhor preço "real" do livro.
- **Reposicionamento mantém a prioridade original.** Quando o preço de referência muda, a pegged é movida para o novo nível preservando o `seq` de criação, pois o reposicionamento automático não é uma alteração feita pelo usuário. Por isso, no exemplo do enunciado, a pegged (criada antes) fica à frente da limit de 300 no nível 10.1. Já um aumento de quantidade feito pelo usuário faz a pegged perder prioridade, como em qualquer ordem.
- **Sem referência, a ordem fica inativa.** Se não houver ordem não-pegged no lado de referência, a pegged existe (pode ser cancelada ou alterada), mas fica fora do livro até surgir uma referência.
- **O reposicionamento ocorre ao fim de cada operação, nunca no meio de um matching.** Consequência: durante um único matching, uma pegged ainda pode ser executada ao preço em que estava posicionada, mesmo que a execução esgote as ordens que serviam de referência. Exemplo: com `200 @ 10` (limit), `150 @ 10` (pegged) e `100 @ 9.99`, uma `limit sell 10 250` consome as 200 e mais 50 da pegged a 10; só depois a pegged remanescente migra para 9.99. A pegged é tratada como parte do nível de preço enquanto o matching acontece.
- **Por que `peg bid` só aceita compra e `peg offer` só venda.** Uma venda pegged ao bid teria preço igual ao do melhor comprador e cruzaria o livro imediatamente, deixando de "acompanhar" preço para se tornar uma ordem agressora, o que foge do conceito descrito no enunciado. Com a restrição, reposicionar uma pegged nunca gera execução. Combinações cruzadas (como `peg offer buy`) são rejeitadas com uma mensagem clara. A sintaxe mantém o lado explícito (`peg bid buy`) para espelhar o enunciado.

### Preços com `Decimal`

Preços usam `decimal.Decimal`, nunca `float`, evitando erros de representação em comparações e níveis de preço (`9.99`, `10.1`). A entrada é validada de forma estrita por expressão regular e o tamanho da quantidade é limitado.

### Erros não alteram o estado

Entradas inválidas (sintaxe, números malformados, quantidade ou preço não positivos, ordem inexistente) viram uma linha `Error: ...`. A validação ocorre antes de qualquer mutação e antes de os contadores de sequência avançarem, então erros não deixam buracos nos identificadores nem alteram o livro.

## Arquitetura

O núcleo (`engine`, `book`) não faz I/O: a interface de texto fica em camadas separadas, o que permite testar a lógica sem simular terminal.

```
src/matching_engine/
├── models.py      # Order, Trade, enums (Side, OrderType, PegReference), erros e validação
├── ids.py         # Contador monotônico e geração de identificadores
├── book.py        # OrderBook: níveis de preço, filas por prioridade, índice por id
├── engine.py      # MatchingEngine: matching, cancelamento, alteração e pegged
├── commands.py    # CommandProcessor: texto -> operações da engine -> linhas de saída
├── formatting.py  # Formatação de preços, trades e do livro
├── cli.py         # Modo interativo e modo arquivo/stdin
└── __main__.py    # Ponto de entrada (python -m matching_engine)
```

## Estruturas de dados e complexidade

O `OrderBook` mantém, por lado:

- um `dict` de **nível de preço → `deque` de ordens**, ordenado por `seq` dentro do nível;
- uma **lista ordenada de preços** (mantida com `bisect.insort`), de onde se lê o melhor preço em O(1);
- um **índice `id → ordem`** para localizar ordens em O(1).

| Operação | Custo |
| --- | --- |
| Melhor preço / melhor ordem | O(1) |
| Localizar ordem por id | O(1) |
| Inserir ordem em nível existente | O(1) no caso comum (ordem mais nova) |
| Criar ou remover nível de preço | O(log n) para localizar + O(n) de deslocamento na lista |
| Remover ordem (cancelamento, alteração) | O(m), sendo m o tamanho da fila do nível |
| Matching | O(k) para k ordens passivas consumidas |

O reposicionamento de pegged só percorre as pegged quando algum preço de referência mudou ou há uma pegged recém-criada. No caso comum, o custo de uma operação não depende de quantas pegged existem. Já `best_anchor_price` varre os níveis a partir do topo até achar uma ordem não-pegged, então seu custo seria O(níveis) se muitos níveis do topo tivessem apenas pegged.

Como o enunciado dispensa preocupações de escala, priorizou-se clareza e corretude em vez de estruturas mais sofisticadas (por exemplo, listas encadeadas intrusivas para remoção em O(1)).

## Testes

Os testes ficam em [`tests/`](tests/) e podem ser executados com:

```bash
pip install -e ".[dev]"
pytest                              # roda toda a suíte
pytest --cov=matching_engine        # com relatório de cobertura
ruff check .                        # lint
```

## Limitações conhecidas

- **Pegged restritas ao próprio lado** (`peg bid` = compra, `peg offer` = venda), conforme justificado acima.
- **Midpoint peg e market peg** estão fora do escopo; só existem `peg bid` e `peg offer`.
- **Pegged inativas** (sem referência no livro) não aparecem em `print book`, embora existam e possam ser canceladas ou alteradas.
- **Ordem a mercado sem liquidez** não gera saída nem erro; o saldo não executado é descartado em silêncio.
- **Sem tipos de validade** (IOC, FOK, GTC, etc.), prevenção de auto-negociação, tamanho mínimo de lote ou *tick size*.
- **Sem persistência nem concorrência**: tudo fica em memória e a engine é de thread única.
- **Remoção de ordens é O(m)** no nível (ver tabela de complexidade).

## Uso de IA

Ferramentas de IA foram utilizadas como apoio ao desenvolvimento e à revisão. Todo o código do repositório foi revisado por mim e é de minha responsabilidade, incluindo decisões técnicas, comportamentos, limitações e testes.
