# qbcore-carros — processamento seguro dos veículos PLOKMJNB

Este repositório guarda **código de preparação**, não os carros.

## Estado
- Pipeline em desenvolvimento; **nenhum carro foi validado em FXServer**.
- Pacotes só podem ser gerados quando o repositório estiver **Private**, para impedir publicação acidental dos arquivos de terceiros.
- Fonte: https://github.com/PLOKMJNB/FiveM-Civ-Car-Pack (master)
- Primeiro lote: ACURA.

## Objetivo
Gerar um ZIP por fabricante com `[carros]/car_<marca>_001`, `fxmanifest.lua`, `data/` e `stream/`. A instalação é extrair os ZIPs para a pasta `resources` e usar `ensure [carros]` no `server.cfg`.

## Execução
1. Altere **Settings → General → Danger Zone → Change repository visibility** para **Private** e verifique as condições de uso/licença dos veículos antes de compartilhar.
2. No GitHub abra **Actions → PLOKMJNB - criar lote de carros → Run workflow**.
3. Escolha a marca, inicialmente `ACURA`.
4. Confira o relatório da execução e baixe o ZIP na área de **Releases** somente depois de a execução terminar com sucesso.
5. Teste individualmente no FXServer, com backup e sem ativar outros packs duplicados.

## O que este pipeline faz — e não faz
- Faz clone parcial dos diretórios necessários, evitando baixar os 5 GB de binários num único processo.
- Identifica spawns duplicados entre metadados da origem e elimina **pastas de veículo conflitantes** do lote segundo prioridade determinística.
- Não remove peça 3D que possa quebrar modelo/colisão; não cria LODs, não promete FPS adicional.
- Mantém arquivos binários do autor sem alterações; reduz o peso de instalação apenas ao excluir arquivos alheios ao funcionamento e ao selecionar carros válidos.
- Gera inventário, contagem, tamanhos e alertas de colisões entre nomes de arquivos stream.
- Cria recursos menores para isolar falhas de inicialização.

### Atenção
O registro no Github Actions de uma tarefa bem-sucedida **não significa** que o veículo está funcionando em FiveM. Testes no FXServer e com vários veículos simultâneos são obrigatórios. A documentação oficial dos tipos de `data_file` está em https://docs.fivem.net/docs/game-references/data-files/.
