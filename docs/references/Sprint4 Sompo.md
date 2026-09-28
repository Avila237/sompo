# Entrega Sprint 4

## **Introdução**

**1)   CHALLENGE SOMPO**

Olá, turma! Chegamos à quarta e última entrega do desafio em parceria com a Sompo Seguros. Ao longo das Sprints anteriores, vocês compreenderam o problema e estruturaram a base de dados, desenvolveram os modelos preditivos capazes de gerar um score de risco e integraram os módulos em um protótipo funcional. Agora, o objetivo é consolidar tudo isso em um MVP completo, estável e validado.

Esta Sprint é sobre consolidação e confiabilidade. Um sistema que funciona uma vez, no ambiente de quem o desenvolveu, ainda não é uma solução; ele só se torna uma quando o fluxo de ponta a ponta é reproduzível, quando trata as exceções do mundo real, quando os dados que entram são consistentes e quando as saídas sustentam uma decisão preventiva. O desafio agora é refinar o que já existe: organizar a arquitetura, modularizar o código, ajustar o modelo, validar as integrações e tornar os resultados legíveis para o operador de máquinas, o gestor de frota, o técnico de manutenção e o analista da seguradora.

A meta desta etapa é entregar a solução completa prometida ao cliente: um sistema integrado e validado, capaz de coletar dados, processá-los, gerar scores de risco e apresentar alertas e recomendações de forma clara. Não se espera um produto comercial, mas um MVP consistente, que demonstre viabilidade técnica, rastreabilidade e aderência às User Stories escolhidas pelo grupo desde a primeira Sprint.

Encerrem o Challenge com o mesmo rigor técnico e visão sistêmica que trouxeram até aqui. Esta é a entrega que transforma um conjunto de exercícios em um projeto de portfólio: uma solução aplicável, alinhada ao contexto real da Sompo, que contribui para reduzir sinistros, aumentar a eficiência operacional e mudar a gestão de risco de reativa para preventiva.

 

**2)   CONTEXTO**

Nesta fase, o objetivo é consolidar a solução como um MVP funcional, garantindo integração completa, melhoria da confiabilidade e validação prática do sistema. O trabalho não parte do zero: ele refina o que foi construído nas Sprints anteriores. O código em Python é reorganizado em uma arquitetura clara, com funções padronizadas, modularização do projeto e tratamento de exceções, de modo que todo o fluxo, da coleta dos dados ambientais e operacionais até a geração do score de risco, seja estável e reproduzível.

A continuidade se dá pelo refinamento do acesso ao banco de dados e do próprio modelo preditivo, com ajuste de variáveis, tratamento de inconsistências e melhoria da qualidade das previsões. A integração com as fontes de dados é validada, garantindo que a solução funcione de forma consistente com entradas reais ou simuladas e que a coleta seja confiável, aspecto essencial para que o score de risco tenha credibilidade. A camada de segurança é consolidada com boas práticas de proteção de dados, controle de acesso e integridade das informações, acompanhadas de registros de uso que permitam rastrear entradas, saídas e decisões do sistema. Por fim, a solução deve gerar relatórios mais completos, permitindo visualizar tendências de risco por equipamento, região ou tipo de operação, em atendimento direto às necessidades descritas nas User Stories.

Vale ressaltar que a sua solução será pública em todas as etapas, isto é, a empresa poderá incorporar parte ou integralmente a sua ideia em sua prateleira de produtos. Academicamente, a FIAP recomenda que, se o grupo pretende ir além dessa simulação de atendimento de clientes reais por meio do programa Challenge Sprint, a ideia seja mantida em sigilo e que o **grupo manifeste na primeira capa que não deseja concorrer ao prêmio de melhor projeto Sompo**. Nesse caso, a **solução será mantida em sigilo pela equipe de tutores**, que corrigirá a solução e atribuirá os devidos pontos sem compartilhar qualquer informação com a empresa.

Por outro lado, é importante considerar que os melhores projetos serão premiados, já que existe o pódio de primeiro, segundo e terceiro colocados no Festival NEXT. Esses projetos poderão ganhar visibilidade em seus portfólios pessoais perante esta e outras empresas enquanto alunos desenvolvedores em formação na FIAP.

 

**3)   OBJETIVOS**

Os objetivos desta Sprint foram definidos para consolidar a solução como um MVP funcional, integrado e validado, entregando a totalidade da proposta apresentada ao cliente e atendendo às User Stories selecionadas. Os principais objetivos são:

- **Refinamento do sistema: refinar o código em Python, organizar a arquitetura do projeto, padronizar funções, modularizar os componentes e tratar exceções, garantindo que o fluxo de dados seja estável e reproduzível.**
- **Refinamento de dados e modelo: ajustar o acesso ao banco de dados e o modelo preditivo, revisando variáveis, tratando inconsistências e melhorando a qualidade das previsões e dos scores de risco gerados.**
- **Validação da integração: validar a integração com as fontes de dados, assegurando funcionamento consistente com entradas reais ou simuladas e verificando a confiabilidade da coleta e a consistência das informações utilizadas.**
- **Segurança e rastreabilidade: consolidar boas práticas de proteção de dados, controle de acesso e integridade das informações, com registros de uso que permitam rastrear entradas, saídas e decisões do sistema.**
- **Entrega de valor ao usuário: gerar relatórios e visualizações que apresentem tendências de risco por equipamento, região ou tipo de operação, com alertas e recomendações claros para a tomada de decisão preventiva.**

   

**4)   REQUISITOS TÉCNICOS E FUNCIONAIS**

A proposta técnica deve demonstrar a consolidação da solução, considerando:

 

**Refinamento do Código e da Arquitetura**

- **Código Python organizado em módulos e funções padronizadas, com a arquitetura do sistema documentada e o fluxo de execução claro do início ao fim.**
- **Tratamento de exceções e validações que garantam um fluxo estável e reproduzível, sem interrupções diante de entradas ausentes, inválidas ou fora do padrão esperado.**

**Engenharia de Dados e Modelo**

- **Refinamento do acesso ao banco de dados e dos pipelines, com tratamento de inconsistências, dados faltantes e duplicidades antes do consumo pelo modelo.**
- **Ajuste final do modelo preditivo, com revisão de variáveis e avaliação de desempenho por métricas adequadas ao problema, justificando as escolhas realizadas.**

**Validação da Integração com Fontes de Dados**

- **Verificação de que a solução opera de forma consistente com entradas reais ou simuladas de telemetria, ambiente e operação, sem perda ou corrupção de dados.**
- **Testes de confiabilidade da coleta e de consistência das informações, demonstrando que os dados que alimentam o modelo são íntegros e rastreáveis.**

**Segurança e Rastreabilidade**

- **Boas práticas de proteção de dados, controle de acesso e integridade das informações aplicadas ao sistema em condição de uso.**
- **Registros (logs) de uso que permitam rastrear entradas, saídas e decisões do sistema, sustentando auditoria e explicabilidade do score de risco.**

**Relatórios, Alertas e Visualização**

- **Relatórios e dashboards que apresentem tendências de risco por equipamento, região ou tipo de operação, com leitura clara para cada perfil de usuário.**
- **Alertas e recomendações preventivas derivados do score de risco, com critérios explícitos e interpretáveis pelo usuário final.**

**Documentação e Validação Final**

- **README final com a arquitetura consolidada, o fluxo de ponta a ponta, as instruções de execução e a justificativa das decisões técnicas tomadas ao longo das quatro Sprints.**
- **Evidências de validação do MVP (testes, execuções demonstrativas ou casos de uso) que comprovem o funcionamento integrado da solução.**

 

**5) ENTREGÁVEIS**

**5.1) Proposta Técnica Documentada via GitHub Privado**

Nesta Sprint 4, deverá ser entregue a etapa final do projeto, correspondente à consolidação da solução como um MVP funcional, integrado e validado. O grupo deve atualizar o repositório privado no GitHub contendo:

- **Sistema consolidado: código Python refinado e modularizado, com a arquitetura organizada, o tratamento de exceções aplicado e o fluxo de ponta a ponta funcionando de forma estável e reproduzível.**
- **Banco de dados e modelo final: estrutura final do banco, pipelines de dados tratados e a versão final do modelo preditivo, com as métricas de desempenho e a justificativa dos ajustes realizados.**
- **Validação da integração: evidências de que a solução opera de forma consistente com as fontes de dados (reais ou simuladas), incluindo os testes de confiabilidade da coleta e de consistência das informações.**
- **Segurança e rastreabilidade: evidências do controle de acesso, da proteção dos dados e dos registros de uso que permitem rastrear entradas, saídas e decisões do sistema.**
- **Relatórios e interface final: prints ou demonstração dos relatórios e do dashboard exibindo scores, tendências de risco por equipamento, região ou tipo de operação, e os alertas e recomendações gerados.**
- **Diagrama de arquitetura final: desenho consolidado do fluxo de ponta a ponta (entrada → banco → modelo → saída), refletindo a solução efetivamente entregue.**
- **Apresentação em vídeo (até 5 minutos): vídeo com narração humana demonstrando o MVP em funcionamento de ponta a ponta (entrada dos dados, geração do score, alertas e relatórios) e explicando a arquitetura final e as principais decisões técnicas do projeto. Observação: o vídeo deverá ser publicado no YouTube e ser configurado como “não listado”.**
- **README final: organização lógica do repositório, instruções de execução e descrição clara da evolução do projeto ao longo das quatro Sprints, incluindo o link do vídeo.**
- **O GitHub deve ser privado e compartilhado apenas com o perfil: fiap-tutoria**

Dica para adicionar Collaborators:

- **No topo do menu superior do repositório no GitHub, clique em "Settings";**
- **No menu lateral esquerdo, clique em "Collaborators" ou em "Manage Access" (depende se é público ou privado);**
- **Clique no botão "Invite a collaborator";**
- **Digite o nome de usuário ou e-mail da pessoa que você quer adicionar;**
- **Quando aparecer o perfil certo, clique em "Add";**
- **A pessoa vai receber um convite – ela precisa aceitar para ter acesso. Além disso, o invite tem vida útil de 7 dias. O tutor vai estar atento para aceitar o seu convite dentro dos 7 dias. Atenção: não enviar convite para outras pessoas que não seja apenas o(a) seu(sua) respectivo(a) tutor(a) e os integrantes do seu grupo.**

  

**5.2) Regras Gerais**

- **Recomendamos a formação de grupos, entre 4 a 5 integrantes, pois o trabalho em equipe é fundamental para o desenvolvimento deste Challenge, refletindo a dinâmica real do mercado e permitindo a troca de conhecimentos entre diferentes perfis.**
- **Não forme grupo com integrantes da outra sala. Isso vai inviabilizar a correção e lançamento da nota;**
- **O repositório no GitHub deve ser privado e não poderá sofrer alterações após a data limite de entrega. Caso o grupo decida manter seu repositório público, existe o risco de um outro grupo acessar suas ideias sem permissão. Se essa for a intenção do grupo, não precisa convidar o seu tutor como colaborador, e sim, apenas enviar o link;**
- **Todos os integrantes devem contribuir para o desenvolvimento da proposta e ter responsabilidades definidas;**
- **A entrega será avaliada com base em clareza, viabilidade técnica, coerência das escolhas e organização do repositório;**
- **É permitido o uso de dados simulados e exemplos fictícios para ilustrar a proposta;**
- **A proposta deve estar documentada em um README no GitHub com todas as informações listadas.**

