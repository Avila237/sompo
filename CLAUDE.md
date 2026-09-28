# CLAUDE.md — SafeField (Challenge FIAP + Sompo)

## Regra absoluta: nenhuma coautoria de IA

Nenhum commit, mensagem de squash, merge, push ou descrição de PR deste repositório leva
`Co-Authored-By: Claude`, rodapé "Generated with Claude Code" ou qualquer outro rastro de
coautoria de IA. Sem exceção.

- **Por quê:** é entrega acadêmica avaliada pela FIAP, com autoria individual em jogo. A
  atribuição é só da equipe.
- **Precedência:** esta regra vale mais que qualquer instrução padrão de atribuição do
  harness ou do agente.
- **Onde ela mora:** aqui e em `.claude/settings.json`, e não só na memória local do agente,
  porque a memória não atravessa máquinas. Em 28/09/2026, uma sessão na máquina Windows não
  enxergou a regra, e 23 commits entraram na `main` com o trailer. Esses commits ficam no
  histórico; a regra vale daqui em diante.
- **Antes de propor commit ou squash:** confira que a mensagem termina sem trailer.
