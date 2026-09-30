# 5LTEP-L3: kit de detecção de anomalias da Camada 3 do 5L-TEP

[English](README.md) · **Português**

**Detecção de anomalias por *ensemble* + LLM local como juiz (*LLM-as-a-Judge*) + revisão humana (*human-in-the-loop*) para portais de Dados Abertos Governamentais baseados em CKAN.**

[![Tests](https://github.com/lsp3cesarschool/5ltep-layer3/actions/workflows/tests.yml/badge.svg)](https://github.com/lsp3cesarschool/5ltep-layer3/actions/workflows/tests.yml)
[![Layer 3](https://github.com/lsp3cesarschool/5ltep-layer3/actions/workflows/layer3.yml/badge.svg)](https://github.com/lsp3cesarschool/5ltep-layer3/actions/workflows/layer3.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

📊 **Painel:** <https://lsp3cesarschool.github.io/5ltep-layer3/> (anomalias, rótulos do LLM, decisões do gestor, proveniência de cada resultado)
🧑‍⚖️ **Fila de revisão:** [issues `layer3` abertas](https://github.com/lsp3cesarschool/5ltep-layer3/issues?q=is%3Aissue+is%3Aopen+label%3Alayer3)
🧪 **Qual LLM julga, e por quê:** [5ltep-layer3-modeltest](https://github.com/lsp3cesarschool/5ltep-layer3-modeltest), o benchmark mensal de modelos
🔁 **Experimento de controle em outro portal:** [5ltep-layer3-aneel](https://github.com/lsp3cesarschool/5ltep-layer3-aneel) (ANEEL, mesmo código)

> **Situação: demonstração de pesquisa.** Este kit faz parte de um projeto de pesquisa de mestrado e é
> mantido pelo seu autor. Não é um serviço oficial do IBAMA (nem da ANEEL), e não pressupõe que algum
> órgão vá revisar seus resultados ou adotá-lo. O fluxo completo, incluindo a revisão humana, está
> funcionando e pronto para ser adotado. As issues de revisão abertas demonstram esse fluxo: não há
> gestor designado, e o autor deliberadamente não faz esse papel, pois rotular as saídas da própria
> ferramenta seria autoavaliação.

## Caso de uso em um parágrafo

Dado um conjunto de dados grande, por exemplo os autos de infração do IBAMA, imagine que queiramos
corrigir o que estiver incorreto, mas não sabemos por onde começar. Esta camada detecta os
**períodos** em que o volume ou os valores fogem do padrão (por exemplo, um mês com o triplo de autos
do normal) e usa inteligência artificial para verificar quais desses desvios têm explicação conhecida.
Mais autos num mês de estação seca, quando isso se repete todo ano, é **sazonal**; uma queda que
coincide com uma nova lei é **mudança de política**. O que sobra, e principalmente o que parece
**problema nos dados** (migração de sistema, represamento, rajada de registros sem identificador), vai
primeiro para as pessoas. Em vez de revisar registros ao acaso, a equipe começa pelos períodos que
nada explica, e as pessoas que farão as correções manuais são alocadas onde mais importam. A IA apenas
propõe; um gestor de dados confirma ou corrige toda decisão que leve a uma ação.

## Termos-chave

| Termo | Significado aqui |
|---|---|
| **Anomalia** | um mês de uma série mensal (ex.: número de autos, total das multas) que foge do padrão habitual, sinalizado por pelo menos 2 de 4 detectores estatísticos |
| **Mudança de nível** | uma mudança duradoura de patamar (não um pico de um mês), detectada por um teste de Page-Hinkley |
| **LLM-as-a-Judge** | um modelo de linguagem pequeno, executado localmente e sem custo, que lê cada anomalia com seu contexto e diz qual das quatro causas abaixo a explica melhor |
| **Gestor de dados** (*data steward*) | a pessoa que confirma ou corrige o rótulo do juiz (por uma issue do GitHub) antes de qualquer ação |

As quatro causas (categorias) entre as quais o juiz escolhe, e por que importam:

| Código | Categoria | Exemplo (IBAMA) | O que significa para a equipe |
|---|---|---|---|
| **PDC** | Mudança por política (*Policy-Driven Change*) | os autos mudam logo após um novo decreto ou uma troca de governo | explicada por um evento conhecido: documentar |
| **SP** | Padrão sazonal (*Seasonal Pattern*) | janeiro tem menos autos quase todo ano | comportamento esperado: nenhuma ação |
| **DQE** | Evento de qualidade de dados (*Data-Quality Event*) | um mês quase sem registros numa série ativa; uma rajada de registros sem identificador | um **problema nos dados**: sempre revisado por um gestor, primeiro na fila de correção |
| **GES** | Mudança genuína de fiscalização (*Genuine Enforcement Shift*) | um aumento gradual e duradouro, sem evento, sem sazonalidade e sem sinais nos dados | uma mudança real que ninguém explicou ainda: vale investigar |

## Visão geral

Este kit implementa a **Camada 3 (Detecção de Anomalias)** da Pirâmide de Engenharia da Confiança em
Cinco Camadas (5L-TEP) para garantia de qualidade de Dados Abertos Governamentais (Pinheiro et al.,
SOFTENG 2026). A Camada 3 observa o *comportamento dos dados ao longo do tempo*: quedas, saltos e
mudanças de nível inesperados em séries agregadas, que as verificações estruturais (Camada 1) e
semânticas (Camada 2) não conseguem antecipar.

Segue o protocolo em duas etapas do artigo do 5L-TEP:

1. **Monitoramento estatístico automatizado** sinaliza anomalias candidatas: um *ensemble* de quatro
   detectores vota em cada mês, e um teste de Page-Hinkley separa deriva sustentada de anomalias
   pontuais.
2. **Interpretação e revisão**: um LLM local ([Ollama](https://ollama.com); atualmente `qwen3:4b`,
   escolhido pelo [benchmark de modelos](https://github.com/lsp3cesarschool/5ltep-layer3-modeltest))
   lê cada candidata em contexto e propõe uma causa; anomalias que apontam para um problema de
   qualidade de dados, ou nas quais o LLM é inconsistente, vão para um **gestor de dados** como issues
   do GitHub. A decisão do gestor prevalece.

A primeira implantação monitora os **autos de infração** do IBAMA (mais de 700 mil registros desde
1977) em [dadosabertos.ibama.gov.br](https://dadosabertos.ibama.gov.br). Tudo o que é específico desse
conjunto de dados fica em um **perfil** declarativo, de modo que o mesmo código monitora outros
conjuntos, outros recortes dos dados e outros portais CKAN (ver
[Adaptação a outros conjuntos, recortes e portais](#adaptação-a-outros-conjuntos-recortes-e-portais)).

> **Escopo**: este repositório contém **apenas** a Camada 3. A Camada 4 (Observabilidade e
> Proveniência) é o [5ltep-layer4](https://github.com/lsp3cesarschool/5ltep-layer4); as Camadas 1, 2 e 5
> estão fora desta implementação. A Camada 3 expõe seu resultado nos campos que o registro de
> proveniência do 5L-TEP espera (`l3_pass`, `anomaly_flags`), prontos para as Camadas 4 e 5.

### Arquitetura

```
┌────────────────────────────────────────────────────────────┐
│  GitHub Actions: cron mensal  +  botão "Run workflow"      │
│  (runner de repositório público: 4 vCPU / 16 GB, sem cota) │
└─────────────────────────────┬──────────────────────────────┘
                              │ perfil (profiles/*.json)
                              ▼
┌────────────────────────────────────────────────────────────┐
│ ① Fonte       CKAN package_show → URL do recurso → baixar  │
│               SHA-256 do arquivo, metadados do portal      │
├────────────────────────────────────────────────────────────┤
│ ② Agregar     só as colunas necessárias (sem dado pessoal) │
│               filtros (recorte) → séries mensais           │
├────────────────────────────────────────────────────────────┤
│ ③ Detectar    Z-score · MAD · Isolation Forest · LSTM-ED   │
│   (etapa 1)   voto do ensemble ≥ 2 de 4  +  Page-Hinkley   │
├────────────────────────────────────────────────────────────┤
│ ④ Julgar      Ollama + modelo escolhido pelo benchmark,    │
│   (etapa 2)   3 execuções com semente, CoT, resposta JSON  │
│               → maioria + consistência                     │
├────────────────────────────────────────────────────────────┤
│ ⑤ Revisar     issues: rótulo steward:<CATEGORIA> + fechar  │
│   (HitL)      → results/<perfil>/reviews.json              │
├────────────────────────────────────────────────────────────┤
│ ⑥ Relatório   layer3_summary.json (l3_rate, l3_pass,       │
│               anomaly_flags) + dados do painel (Pages)     │
└─────────────────────────────┬──────────────────────────────┘
                              ▼
         Repositório Git: cada série, detecção, julgamento,
         revisão e resumo é versionado (histórico auditável)
```

## Etapa 1: detecção estatística

Cada série é analisada em escala logarítmica (contagens e totais de multas têm cauda pesada: uma única
multa pode passar de R$ 4 bilhões). O log é invariante à escala, então converter moedas antigas só
remove os degraus artificiais das reformas monetárias; zeros recebem um piso de metade do menor valor
positivo.

| Detector | O que pontua | Sinaliza quando | Referência |
|---|---|---|---|
| Z-score móvel | distância à média dos 12 meses anteriores | \|z\| > 3 | SOFTENG 2026 (k = 3, linha de base de 12 períodos) |
| MAD móvel | z-score modificado contra a mediana dos 12 meses anteriores | \|M\| > 3 | Iglewicz & Hoaglin (1993) |
| Isolation Forest | nível, primeira diferença, resíduo em relação à mediana móvel | 5% mais extremos (contaminação 0,05) | Liu et al. (2008) |
| LSTM codificador-decodificador | erro de reconstrução em janelas de 12 meses (64 unidades, *dropout* 0,2) | acima do percentil 99 | Malhotra et al. (2016) |
| ***Ensemble*** | votos dos quatro detectores | **≥ 2 de 4** | voto majoritário |
| Page-Hinkley | desvio acumulado do nível (bilateral) | δ = 0,5, λ = 12 (unidades de ruído) | Page (1954); SOFTENG 2026 |

Os alarmes de Page-Hinkley não votam: marcam **mudanças de nível sustentadas** (deriva), que o artigo
do 5L-TEP encaminha para uma revisão da estrutura dos dados, e não para correção. Estar perto de um
ponto de deriva faz parte da evidência dada ao LLM.

Toda aleatoriedade usa semente fixa (`RANDOM_SEED = 42`); duas execuções sobre a mesma série dão os
mesmos sinais.

## Etapa 2: LLM-as-a-Judge

Para cada mês sinalizado, o juiz recebe: a descrição da série, o valor contra a mediana de 12 meses, o
mesmo mês do calendário em cada um dos 10 anos anteriores e os anos em que ele também foi sinalizado
(evidência de sazonalidade), quais detectores dispararam, o resultado do Page-Hinkley, se a outra série
também foi sinalizada, uma tabela de ±12 meses com as duas séries, os registros excluídos (cancelados)
e sem identificador, e os eventos conhecidos em ±6 meses do
[calendário de eventos](profiles/events/brazil-environmental-enforcement.json) do perfil. Ele responde
em JSON restrito por um esquema (*structured outputs* do Ollama), com um raciocínio passo a passo, uma
categoria (ver [Termos-chave](#termos-chave)) e uma confiança.

| Código | Categoria (perfil IBAMA) | Revisão humana |
|---|---|---|
| `PDC` | Mudança por política: legislação, mandato, reestruturação, transição política | recomendada se inconsistente |
| `SP` | Padrão sazonal: um ciclo anual recorrente de fiscalização | recomendada se inconsistente |
| `DQE` | Evento de qualidade de dados: falha de registro, migração de sistema, represamento, correção retroativa | **sempre revisado** |
| `GES` | Mudança genuína de fiscalização: uma mudança real não explicada pelas anteriores | recomendada se inconsistente |

**Três execuções, sementes fixas, T = 0,7.** Com temperatura 0, as três execuções seriam idênticas por
construção e a "consistência" não mediria nada. Amostrar com sementes fixas (11, 22, 33) permite que as
execuções discordem, e cada execução continua reproduzível com o mesmo *digest* do modelo. Fica o
rótulo da maioria; a consistência do rótulo é *C = execuções que concordam com a maioria / 3*.

**Orçamento.** A inferência em CPU no runner do Actions é lenta, então cada execução julga no máximo
`MAX_JUDGMENTS` anomalias novas (as mais recentes primeiro) dentro de `MAX_JUDGE_MINUTES`, salvando
após cada uma. Um histórico longo é preenchido ao longo de algumas execuções; depois disso, a execução
mensal só vê os meses novos.

**Anomalias passadas não são julgadas de novo quando seus dados são os mesmos.** Cada julgamento guarda
uma impressão digital (SHA-256) dos dados que tornam o mês anômalo: esse mês e os 12 anteriores, em
todas as séries. Uma execução posterior pula a anomalia enquanto a impressão digital coincidir, mesmo
com a chegada de meses novos. Ela só é julgada de novo quando:

| Gatilho | Por quê | O que acontece com a revisão |
|---|---|---|
| seus dados mudaram (automático) | uma correção retroativa no portal alterou aquele mês ou sua linha de base de 12 meses | a issue existente recebe um comentário com o rótulo antigo e o novo |
| um gestor pede | *Actions → Layer 3 → Run workflow* com `rejudge` = `stale` (só o que um modelo ou versão de prompt anterior julgou) ou `all`; também o botão **Re-judge** do painel | idem |

Um novo modelo ou versão de prompt **não** rejulga o histórico por conta própria: cada julgamento
registra o modelo e a versão do prompt que o produziram (mostrados no painel), e o novo modelo julga as
anomalias novas. Em todos os casos, o julgamento anterior fica guardado no `history` da entrada, nunca
sobrescrito, e nenhuma issue é duplicada. Eventos adicionados ao calendário também não disparam novos
julgamentos.

**Qual modelo.** O modelo é escolhido por medição, não por impressão: o
[benchmark de modelos](https://github.com/lsp3cesarschool/5ltep-layer3-modeltest) roda todo mês no
runner gratuito, descobre modelos pequenos novos, testa-os no prompt de produção contra um gabarito
cujas respostas são conhecidas por construção, e publica qual modelo usar. Por padrão
(`LLM_MODEL=auto`), cada execução deste repositório lê essa decisão e julga com o modelo aprovado; o
benchmark só troca quando um candidato supera o modelo atual por uma margem cujo intervalo de confiança
pareado está acima de zero. Para manter um modelo fixo, defina a variável de repositório `LLM_MODEL`
com uma tag (e `LLM_THINK` para modelos com modo de raciocínio); o *Model check* mensal então abre uma
issue quando o benchmark recomendar outro. O primeiro benchmark (30/09/2026) levou a produção do
`gemma3:4b` (macro-F1 0,50 no gabarito) para o `qwen3:4b` sem raciocínio (0,81).

O LLM é uma ferramenta de apoio à decisão, não a verdade: cada prompt e cada raciocínio ficam
guardados, e a decisão do gestor substitui o rótulo do LLM onde houver uma.

## Revisão humana (*human-in-the-loop*)

Níveis de revisão:

- **Revisão obrigatória**: maioria do LLM `DQE` (ou nenhuma resposta válida). Nenhuma ação corretiva
  antes da decisão de um gestor.
- **Revisão recomendada**: consistência do rótulo *C* < 0,6 (as três execuções discordam entre si).
- **Revisão por mudança de nível**: o artigo do 5L-TEP encaminha deriva confirmada para uma revisão da
  estrutura dos dados, qualquer que seja o rótulo. Um salto permanente (ex.: os autos do IBAMA
  multiplicados por ~8 a partir de janeiro de 1996) pode ser uma troca de sistema de informação mesmo
  quando o modelo o chama de mudança genuína. Cada alarme de Page-Hinkley com meses sinalizados em
  volta vira **uma** issue listando esses meses e seus rótulos do LLM; o gestor decide a causa uma vez,
  e a decisão vale para todo mês do grupo que não tenha issue própria (a issue da anomalia sempre
  prevalece).

Os níveis de revisão são uma política aplicada aos julgamentos armazenados, então mudá-los nunca exige
chamar o LLM de novo. Quando uma mudança de política torna uma issue aberta desnecessária, ela é
fechada com o rótulo `superseded` e um link para a issue que a substitui (issues que um gestor já
começou a rotular são deixadas como estão).

Cada anomalia que precisa de revisão vira **uma issue do GitHub** (idempotente: novas execuções nunca a
duplicam) com a evidência, os três raciocínios e instruções. O gestor decide **aplicando um rótulo
`steward:<CATEGORIA>`, comentando a justificativa e fechando a issue**. O GitHub registra quem decidiu,
quando e por quê; o workflow [`reviews.yml`](.github/workflows/reviews.yml) copia a decisão para
`results/<perfil>/reviews.json` e atualiza o painel em minutos.

A concordância humano-LLM (`human_llm_agreement` no resumo), o tempo de revisão (da abertura ao
fechamento da issue) e as demais métricas de revisão são calculados a partir dessas decisões e
mostrados no painel. Estão vazios nesta demonstração e se preenchem assim que um gestor registrar
decisões, sem mudança de código.

## Escore da Camada 3 e saída para as Camadas 4-5

`results/<perfil>/layer3_summary.json` traz o resultado da Camada 3. Nos últimos 12 meses completos,
cada par (série, mês) **passa**, a menos que tenha sido sinalizado pelo *ensemble* e esteja ainda não
julgado, classificado `DQE` (pelo gestor, ou pelo LLM quando nenhum gestor decidiu) ou aguardando uma
revisão obrigatória:

- `l3_rate` = pares que passam / todos os pares: o termo *L3* da Pontuação Global de Qualidade
  *Qs = w₁L1 + w₂L2 + w₃L3 + w₄L4* (SOFTENG 2026, padrão *w₃ = 0,2*);
- `l3_pass` = nenhum par reprovado;
- `anomaly_flags` = os pares coluna–período sinalizados, com sua categoria e quem a decidiu.

`l3_pass` e `anomaly_flags` são os nomes de campo do registro mínimo de proveniência do artigo do
5L-TEP, então a Camada 4 pode ingeri-los sem alteração.

## Tratamento dos dados e privacidade

- O arquivo bruto é baixado para um diretório temporário e apagado no fim da etapa; **nunca é
  commitado**. O arquivo do IBAMA traz nomes de autuados e CPF/CNPJ; o kit só **lê** as colunas de que
  o perfil precisa (data, identificador, indicador de cancelamento, valor da multa), então dados
  pessoais nem chegam a ser carregados. Só agregados mensais são versionados.
- **Autos cancelados** são excluídos das séries e contados à parte (`excluded`).
- **Registros sem identificador** (6.806 no arquivo do IBAMA em set./2026) são mantidos e contados
  (`missing_key`); duplicatas verdadeiras de um identificador não vazio seriam descartadas (nenhuma
  encontrada).
- **O mês corrente nunca é analisado**: ainda está sendo preenchido e sempre pareceria uma queda.
- **Início esparso**: a análise começa no primeiro mês a partir do qual os 12 meses seguintes têm
  mediana de pelo menos 3 registros (1980-11 no IBAMA). Só o começo é aparado: meses calmos mais adiante
  são mantidos, o que importa para conjuntos de baixo volume.
- **Moeda**: o Brasil trocou de moeda cinco vezes antes do Real (julho de 1994). As reformas estão num
  arquivo editável à mão, [`profiles/monetary/brazil-currency.json`](profiles/monetary/brazil-currency.json)
  (data, moeda antiga e nova, divisor, fonte legal). Séries marcadas com `"convert_currency": true` têm
  cada valor convertido para Reais na sua própria data, o que remove os degraus artificiais de /1.000
  das reformas; os valores **não** são corrigidos pela inflação. As reformas também chegam ao juiz como
  eventos. Quando houver uma nova reforma, acrescente uma entrada nesse arquivo.

## Calendário de eventos: curado por pessoas, sugerido pelo LLM

O juiz só consegue relacionar uma anomalia a eventos que lhe são informados. Cada perfil tem um
calendário de eventos (ex.:
[`brazil-environmental-enforcement.json`](profiles/events/brazil-environmental-enforcement.json)), em
que cada evento tem um `status`:

| status | significado | enviado ao juiz |
|---|---|---|
| `verified` | verificado por um gestor, com fonte | sim |
| `suggested` | proposto pelo LLM, ainda não verificado | só se ancorado numa fonte citada, marcado *[unverified suggestion]* (opção de perfil `events_include_suggested`); sugestões feitas de memória pelo modelo, nunca, até serem verificadas |
| `rejected` | verificado e descartado | não (mantido para não ser sugerido de novo) |

**Preenchimento automático.** `python main.py suggest-events` olha os anos com anomalias e, para cada
um, busca a página da Wikipédia "*ano* no *país*" (opção de perfil `event_sources`; para o Brasil,
`pt.wikipedia.org/wiki/2019_no_Brasil` e assim por diante). O LLM seleciona os eventos que podem ter
afetado os registros e precisa **citar a frase** de onde cada um vem; sugestões cuja citação não é
encontrada na página são descartadas, o que filtra eventos inventados. Com `--offline`, o modelo
responde com seu próprio conhecimento; essas entradas são marcadas `origin: llm-memory` e nunca são
enviadas ao juiz antes de um gestor verificá-las. Não é uma precaução teórica: numa primeira execução
sem ancoragem, o Gemma 3 4B (o modelo em uso na época) propôs impeachments e decretos inexistentes, com
números inventados. Use o modo offline apenas como lista de pistas a conferir.

No GitHub, o botão **Suggest events** do painel abre o workflow
[`events.yml`](.github/workflows/events.yml), que roda o mesmo comando e abre um **pull request** com
as sugestões. O gestor revisa a diferença, define cada `status` como `verified` ou `rejected`, corrige
os rótulos se necessário e faz o *merge*.

## Princípios FAIR e replicabilidade

O kit foi desenhado para que seus *resultados* sejam FAIR (Wilkinson et al., 2016) e para que o
*método* possa ser reaplicado em outros lugares.

| Princípio | Como é atendido |
|---|---|
| **F** (localizável) | Repositório público com URL persistente, [`CITATION.cff`](CITATION.cff) (citação legível por máquina), tópicos descritivos; cada resultado tem um caminho estável `results/<perfil>/…` e um hash de commit Git. Arquivar uma versão no Zenodo acrescenta um DOI. |
| **A** (acessível) | Tudo pode ser obtido por HTTPS sem login: código, séries, detecções, julgamentos, revisões e resumos no repositório; o painel no GitHub Pages; a fonte pela API CKAN aberta do portal. |
| **I** (interoperável) | Só formatos abertos (CSV, JSON); datas ISO 8601; a fonte é acessada pela API de ações padrão do CKAN; o resumo usa os nomes de campo do registro de proveniência do 5L-TEP consumido pela Camada 4 (baseado no W3C PROV-DM); categorias e parâmetros são explícitos nos arquivos. |
| **R** (reutilizável) | Licença MIT; proveniência rica em cada resultado (abaixo); perfis declarativos tornam o método reutilizável em outros dados sem mudar código; testes e uma suíte de avaliação documentam o comportamento esperado. |

**O que cada execução registra** (`data/<perfil>/source_manifest.json`, `results/<perfil>/layer3_summary.json`, `run_log.jsonl`):

- o portal, o conjunto de dados e a URL do recurso, o `metadata_modified` do portal e o **SHA-256 do
  arquivo exato analisado**;
- o **SHA-256 do perfil** usado e as estatísticas de agregação (linhas lidas, filtradas, excluídas, sem
  identificador, datas inválidas);
- cada **parâmetro do método** (limiares, janelas, sementes, modelo, temperatura, versão do prompt);
- o **ambiente**: versões do Python e dos pacotes;
- para cada julgamento: o prompt completo, as três respostas com sementes e latências, o **digest do
  modelo** e a versão do Ollama;
- o commit Git, que data e torna evidente qualquer adulteração de tudo o que está acima.

**Reproduzir um resultado passado.** O arquivo do portal muda todo dia, então não pode ser baixado de
novo como era. Em vez disso, a série mensal de cada execução é versionada:

```bash
git checkout <commit-da-execução>
python main.py detect --from-series --profile ibama-autos-infracao   # mesmos sinais, sem download
python evaluation/judge_report.py --profile ibama-autos-infracao     # estatísticas do LLM a partir das respostas guardadas
```

A detecção é determinística sobre a mesma série. Rodar o juiz de novo exige o mesmo digest do modelo
(registrado) e dá as mesmas respostas para as mesmas sementes na mesma versão do Ollama; as respostas
guardadas tornam a classificação auditável mesmo sem rodá-la de novo. O SHA-256 permite que quem
guardou uma cópia do arquivo de origem prove que é o que foi analisado.

## Adaptação a outros conjuntos, recortes e portais

Tudo o que é específico de um conjunto de dados está num **perfil**: um arquivo JSON em
[`profiles/`](profiles/). O código nunca muda. As saídas ficam separadas por perfil (`data/<id>/`,
`results/<id>/`, `docs/data/<id>.json`), então vários perfis convivem lado a lado e o painel tem um
seletor.

### Referência do perfil

| Campo | Significado |
|---|---|
| `id`, `title`, `country` | identificador (nome do arquivo, pasta de saída, rótulo das issues), título legível, país do publicador |
| `scheduled` | `true`: incluído na execução mensal; `false`: só sob demanda |
| `source.portal_url`, `dataset_id`, `resource_name`, `resource_format` | o portal CKAN, o identificador do conjunto e o recurso (casado por nome e formato). A URL é consultada a cada execução, então arquivos movidos são seguidos. |
| `file.compression` (`zip`/`none`), `member_pattern`, `sep`, `encoding` | como ler o recurso (um zip de CSVs ou um CSV) |
| `columns.date`, `columns.key` | a data que coloca um registro num mês; o identificador do registro (opcional) |
| `exclude` | linhas removidas das séries mas contadas como contexto (ex.: autos cancelados) |
| `filters` | **o recorte dos dados**: uma lista de `{"column", "in" \| "not_in" \| "equals"}` |
| `period.start`, `period.end` | janela de tempo opcional (`AAAA-MM`) |
| `sparse_min_records` | a análise começa onde os 12 meses seguintes têm pelo menos esta mediana |
| `series` | as séries mensais: `{"name", "kind": "count"}` ou `{"name", "kind": "sum", "column", "number_format": "br" \| "plain", "convert_currency": true \| false}`, cada uma com uma `description` que o LLM lê |
| `domain`, `record_label` | um parágrafo descrevendo o publicador e os registros, para o LLM |
| `events_file` | o calendário de eventos (`{"month", "kind", "label", "source", "status"}`) |
| `events_include_suggested` | enviar ao juiz sugestões não verificadas do LLM (marcadas como tais) |
| `event_sources` | onde o `suggest-events` procura, ex.: `{"wikipedia": {"lang": "pt", "title": "{year} no Brasil"}}` |
| `monetary_file` | reformas monetárias, para `convert_currency` e como eventos |
| `categories` | a taxonomia entre a qual o LLM escolhe e com a qual o gestor rotula (`DQE` sempre vai para revisão) |

### 1. Outro recorte do mesmo conjunto

Copie o perfil, dê a ele um novo `id` e acrescente filtros e/ou um período. O repositório traz um
exemplo, [`ibama-autos-infracao-amazonia-legal.json`](profiles/ibama-autos-infracao-amazonia-legal.json),
que mantém só os nove estados da Amazônia Legal a partir de 1996:

```json
"filters": [{"column": "UF", "in": ["AC", "AM", "AP", "MA", "MT", "PA", "RO", "RR", "TO"]}],
"period": {"start": "1996-01", "end": null}
```

Outros recortes seguem o mesmo padrão: um tipo de infração (`TIPO_INFRACAO`), um bioma, um único
estado, só multas acima de um valor (uma série `sum` sobre um conjunto filtrado), e assim por diante.

### 2. Outro conjunto no mesmo portal

Aponte `source` para o conjunto e o recurso, mapeie `columns` e declare as `series` que fazem sentido
(ex.: itens apreendidos por mês para os *Termos de Apreensão*). Ajuste `domain`, `record_label` e, se as
causas forem outras, `categories` e o calendário de eventos.

### 3. Outro portal CKAN

Só mudam `source.portal_url` e os campos específicos do conjunto. Confira o perfil contra o portal real
antes da primeira execução: o comando valida o perfil, resolve e baixa o recurso, lê as colunas e
mostra a janela de análise:

```bash
python main.py check-profile profiles/my-portal-dataset.json
```

Um segundo portal roda como instância separada, montada pelo autor seguindo os mesmos passos que outro
órgão seguiria para adotar o kit (a própria ANEEL não está envolvida):
[**5ltep-layer3-aneel**](https://github.com/lsp3cesarschool/5ltep-layer3-aneel) monitora os autos de
infração da ANEEL, a agência reguladora do setor elétrico, em
[dadosabertos.aneel.gov.br](https://dadosabertos.aneel.gov.br). Ele difere do IBAMA em todas as
dimensões que um perfil cobre: um CSV simples em vez de um zip de arquivos anuais, outros nomes de
colunas, nenhum indicador de cancelamento, cerca de 1.600 registros desde 2018 em vez de 700 mil desde
1977, e um calendário de eventos muito menor, feito para ser ampliado com `suggest-events`. Essa
instância roda o mesmo código deste repositório; só o perfil, o calendário e o README são diferentes.
Rodá-la expôs duas suposições que valiam para o IBAMA mas não em geral (meses esparsos só no início de
uma série; um perfil padrão fixo no código); as duas foram corrigidas aqui, no código comum.

Portais que não são CKAN precisam de um pequeno adaptador de fonte em `src/ckan_source.py` (o resto do
pipeline só precisa de um arquivo em disco).

### Rodar sua própria instância (fork)

1. Faça um **fork** deste repositório.
2. Acrescente ou edite perfis em `profiles/`; marque `"scheduled": true` nos que a execução mensal deve
   cobrir.
3. **Comece com um histórico limpo:** apague `data/`, `results/` e `docs/data/` e faça o commit. Eles
   são recriados pela primeira execução.
4. No fork, habilite os workflows na aba **Actions** (o GitHub os desabilita em forks) e o GitHub Pages
   (*Settings → Pages → Deploy from a branch → `main` / `docs`*).
5. Mantenha o repositório **público**: repositórios públicos recebem o runner de 16 GB de que o LLM
   precisa, sem cota de minutos. (O runner de 7 GB de um repositório privado é apertado para um modelo
   de 4B.)
6. Rode *Actions → 5L-TEP Layer 3 Anomaly Detection → Run workflow* uma vez. Ele percorre todo o
   histórico em lotes de 25 julgamentos, cada lote iniciando o próximo, até não sobrar nada pendente.
7. Por padrão, o modelo segue o [benchmark de modelos](https://github.com/lsp3cesarschool/5ltep-layer3-modeltest)
   (`LLM_MODEL=auto`). Para fixar um, defina a variável de repositório `LLM_MODEL` com uma tag do
   Ollama (e `LLM_THINK=false` para modelos com modo de raciocínio). Os julgamentos anteriores são
   mantidos de qualquer forma; rode o workflow com `rejudge` = `stale` ou `all` se quiser o histórico
   julgado de novo.

Não acrescente perfis de outros portais às execuções agendadas *deste* repositório sem discutir antes:
seus resultados alimentam o estudo de caso do IBAMA.

## Início rápido (local)

```bash
git clone https://github.com/lsp3cesarschool/5ltep-layer3.git
cd 5ltep-layer3
pip install -r requirements.txt          # PyTorch só CPU

python main.py list-profiles
python main.py run --skip-llm            # baixar + detectar + relatório, sem LLM
pytest tests/ -v                          # sem rede, sem LLM
```

Com um Ollama local (`ollama serve` e `ollama pull qwen3:4b`):

```bash
python main.py judge --max-judgments 5
python main.py report
```

Depois abra `docs/index.html` por um servidor local (`python -m http.server -d docs`).

## Implantação no GitHub Actions

| Workflow | Quando | O quê |
|---|---|---|
| [`layer3.yml`](.github/workflows/layer3.yml) | dia 5 de cada mês, 06:00 UTC, e **manual** (*Run workflow*, com as entradas perfil, tamanho do lote, "continuar", "só detectores" e **`rejudge`**; botões do painel *Run Layer 3 now* e *Re-judge*) | resolver o modelo → detectar → julgar um lote → abrir issues → relatório → commit → próximo lote, até não sobrar nada pendente |
| [`reviews.yml`](.github/workflows/reviews.yml) | sempre que uma issue `layer3` é rotulada, fechada ou reaberta | sincronizar as decisões do gestor, atualizar o escore L3 e o painel |
| [`model-check.yml`](.github/workflows/model-check.yml) | dia 22 de cada mês, e manual | só quando `LLM_MODEL` está fixado: compara com a recomendação do benchmark de modelos; abre issue se uma troca for recomendada |
| [`events.yml`](.github/workflows/events.yml) | **manual** (botão do painel *Suggest events*), com as entradas perfil, online/offline e anos | sugestões do LLM para o calendário de eventos → pull request para revisão |
| [`tests.yml`](.github/workflows/tests.yml) | push / pull request | suíte de testes no Python 3.10–3.12 |

**Por que mensal?** A Camada 3 procura mudanças em séries mensais; rodar a cada seis horas, como o
monitor da Camada 4, só reanalisaria os mesmos meses. Um gestor prestes a tomar uma decisão de
publicação (Camada 5) dispara uma execução pelo botão **Run Layer 3 now** do painel, que abre a página
do workflow: a execução é autorizada pelo próprio login do gestor no GitHub, e nenhum token é embutido
na página pública.

**Lotes até terminar.** Um mês é tempo de sobra para julgar todas as anomalias, mas um único job é
limitado a seis horas. Cada execução julga então um lote (`max_judgments`, 25 por padrão, cerca de 45
minutos no runner de CPU), faz o commit, para o painel mostrar o progresso, e inicia o próximo lote
enquanto houver anomalias ou issues de revisão pendentes (até 60 lotes por cadeia). Os lotes depois do
primeiro reutilizam a série commitada pelo primeiro, então a cadeia inteira analisa os mesmos dados
mesmo se o portal for atualizado nesse meio-tempo. Depois do preenchimento inicial, uma cadeia mensal
costuma ter um único lote.

**Ollama no Actions.** O job instala o Ollama, restaura `~/.ollama/models` do `actions/cache` (o modelo
de 3,3 GB é baixado uma vez), inicia o servidor, espera a verificação de saúde e baixa o modelo. A
inferência é só em CPU.

**Alertas não custam nada e não precisam de servidor de e-mail** (como na Camada 4): no fim de uma
cadeia, se ainda houver revisões **obrigatórias** abertas, o último lote (que já commitou tudo) falha de
propósito, e o GitHub envia um e-mail ao mantenedor sobre a execução com falha. Revisões obrigatórias
abertas produzem assim um lembrete por execução mensal até um gestor decidi-las. Habilite
*Settings → Notifications → Actions* na sua conta.

## Avaliação

Os scripts em [`evaluation/`](evaluation/) reproduzem todos os números que este repositório informa; os
resultados ficam em `evaluation/results/`. Só são informados números produzidos por esses scripts.

- [`synthetic_injection.py`](evaluation/synthetic_injection.py): injeta anomalias com gabarito conhecido
  (pico, queda, lacuna de dois meses, mudança de nível) nas séries reais e mede recall, precisão e
  falsos alarmes induzidos por detector e para o *ensemble*, além do recall do Page-Hinkley em mudanças
  de nível.
- [`judge_report.py`](evaluation/judge_report.py): distribuição de categorias, consistência dos rótulos,
  respostas inválidas e latência do LLM-as-a-Judge, e concordância humano-LLM com matriz de confusão
  quando houver decisões de gestores.

## Estrutura do projeto

```
5ltep-layer3/
├── main.py                        # CLI do pipeline (detect, judge, issues, sync-reviews, report,
│                                  #   check-profile, suggest-events)
├── profiles/
│   ├── ibama-autos-infracao.json                 # autos de infração do IBAMA, Brasil (agendado)
│   ├── ibama-autos-infracao-amazonia-legal.json  # exemplo de recorte (sob demanda)
│   ├── events/                                   # calendários de eventos (verified / suggested / rejected)
│   └── monetary/brazil-currency.json             # reformas monetárias (editável à mão)
├── src/
│   ├── config.py                  # parâmetros do método (substituíveis por variáveis de ambiente)
│   ├── profile.py                 # carga e validação de perfis, caminhos de saída
│   ├── ckan_source.py             # busca e download do recurso CKAN (SHA-256)
│   ├── aggregate.py               # leitura mínima de colunas, recorte, séries mensais
│   ├── detectors.py               # Z-score, MAD, Isolation Forest, LSTM-ED, ensemble, Page-Hinkley
│   ├── judge.py                   # LLM-as-a-Judge (Ollama), voto majoritário, consistência, cache
│   ├── review.py                  # fila de revisão em issues do GitHub (HitL)
│   ├── events_suggest.py          # sugestões do LLM para o calendário, ancoradas na Wikipédia
│   ├── monetary.py                # conversão monetária e eventos de reforma
│   └── report.py                  # escore da Camada 3, resumo, dados do painel
├── docs/                          # painel no GitHub Pages (estático; data/ escrito pelo pipeline)
├── data/<perfil>/                 # séries mensais + manifesto da fonte (commitados pelo robô)
├── results/<perfil>/              # detecções, deriva, julgamentos, revisões, resumo, log de execução
├── evaluation/                    # scripts de avaliação reproduzíveis e resultados
├── tests/                         # testes unitários + de integração (sem rede, LLM simulado)
├── .github/workflows/             # layer3.yml, reviews.yml, events.yml, tests.yml
├── .github/actions/setup-ollama/  # passo comum: instalar Ollama, modelo em cache, iniciar, baixar
├── CITATION.cff
└── LICENSE
```

## Configuração

Os parâmetros do método ficam em [`src/config.py`](src/config.py); cada um pode ser substituído por uma
variável de ambiente de mesmo nome (os valores usados ficam registrados em cada resumo). Os mais
relevantes:

| Variável | Padrão | Descrição |
|---|---|---|
| `PROFILE` | `ibama-autos-infracao` | perfil usado quando `--profile` não é informado |
| `BASELINE_WINDOW` | `12` | linha de base móvel (meses) do Z-score e do MAD |
| `ZSCORE_K`, `MAD_K` | `3.0` | limiares |
| `IF_CONTAMINATION` | `0.05` | proporção de *outliers* do Isolation Forest |
| `LSTM_PERCENTILE` | `99.0` | limiar do LSTM-ED sobre os erros de reconstrução |
| `ENSEMBLE_MIN_VOTES` | `2` | votos necessários para sinalizar um mês |
| `PH_DELTA`, `PH_LAMBDA` | `0.5`, `12.0` | tolerância e limiar do Page-Hinkley (unidades de ruído) |
| `LLM_MODEL` | `auto` | `auto`: o modelo aprovado pelo [benchmark de modelos](https://github.com/lsp3cesarschool/5ltep-layer3-modeltest), lido no início de cada execução; uma tag (ex.: `qwen3:4b`) fixa o modelo (no Actions: variável de repositório) |
| `LLM_THINK` | *(vazio)* | `false` desliga o modo de raciocínio dos modelos que o têm; vazio: como o benchmark testou (auto) ou o padrão do modelo (fixado) |
| `FALLBACK_MODEL` | `qwen3:4b` | usado no modo auto se o benchmark não puder ser lido |
| `LLM_TEMPERATURE`, `LLM_SEEDS` | `0.7`, `11,22,33` | amostragem das três execuções |
| `MAX_JUDGMENTS`, `MAX_JUDGE_MINUTES` | `25`, `240` | orçamento de LLM por execução |
| `ADVISORY_CONSISTENCY` | `0.6` | abaixo disso, revisão recomendada |
| `MAX_NEW_ISSUES` | `15` | issues de revisão abertas por execução |
| `L3_WINDOW_MONTHS` | `12` | janela do escore da Camada 3 |

## Limitações

- Os rótulos do LLM são hipóteses para um gestor, não a verdade; a taxonomia e o calendário de eventos
  são curados e, por natureza, incompletos (acrescente eventos por pull request, com fonte).
- A detecção trabalha sobre agregados mensais: encontra mudanças de volume e valor, não erros em
  registros individuais (Camadas 1–2).
- Os detectores globais (Isolation Forest, LSTM-ED) são reajustados a cada execução, então o sinal de um
  mês passado pode mudar quando chegam meses novos; os detectores móveis não. Julgamentos de meses que
  deixam de ser sinalizados ficam no histórico, mas não são mais contados.
- Os totais de multas são nominais; nenhuma correção inflacionária é aplicada.
- A inferência em CPU leva dezenas de segundos por chamada no runner do Actions; o orçamento mantém as
  execuções dentro do limite do job.

## Referências acadêmicas

- Pinheiro, L. S., Silva, C. H. B., Aquino, V. B., Carvalho, T. M. C. S., Barros Filho, C. V. R., & Almeida, W. H. C. (2026). *Towards Trust Engineering in Open Data Systems: A Layered Conceptual Framework Integrating Quality Assurance and Governance Perspectives*. SOFTENG 2026, IARIA, pp. 21–28.
- Pinheiro, L. S. & Sérgio, A. T. (2026). *5LTEP-L4: An Open-Source CKAN Toolkit for Provenance-Enabled Observability of Open Government Data*. WFA, Anais Estendidos do WebMedia 2026 (no prelo). Código: [5ltep-layer4](https://github.com/lsp3cesarschool/5ltep-layer4).
- Chandola, V., Banerjee, A., & Kumar, V. (2009). Anomaly detection: A survey. *ACM Computing Surveys*, 41(3).
- Liu, F. T., Ting, K. M., & Zhou, Z.-H. (2008). Isolation Forest. *IEEE ICDM*.
- Malhotra, P., et al. (2016). LSTM-based Encoder-Decoder for Multi-sensor Anomaly Detection. *ICML Anomaly Detection Workshop*.
- Iglewicz, B., & Hoaglin, D. (1993). *How to Detect and Handle Outliers*. ASQC Quality Press.
- Page, E. S. (1954). Continuous inspection schemes. *Biometrika*, 41(1/2), 100–115.
- Zheng, L., et al. (2023). Judging LLM-as-a-Judge with MT-Bench and Chatbot Arena. *NeurIPS*.
- Wei, J., et al. (2022). Chain-of-Thought Prompting Elicits Reasoning in Large Language Models. *NeurIPS*.
- Wilkinson, M. D., et al. (2016). The FAIR Guiding Principles for scientific data management and stewardship. *Scientific Data*, 3, 160018.

## Licença

Código: MIT, ver [LICENSE](LICENSE). As séries mensais em `data/` são agregados derivados dos dados
abertos do IBAMA; ao reutilizá-las, cite o portal de dados abertos do IBAMA como fonte original.
