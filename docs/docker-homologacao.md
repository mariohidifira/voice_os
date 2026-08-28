# Docker local: backup, restauração e nova instalação

Este documento registra o estado do ambiente local de homologação em 27/08/2026 e o procedimento para reproduzi-lo em outro computador.

## Localização na unidade removível

Todo estado específico do VoiceOS está sob `G:\DEV\VOICE_OS`:

- repositório e `.env`;
- backup em `backups/postgres/`;
- PostgreSQL ativo em `.docker-data/postgres/`;
- Redis ativo em `.docker-data/redis/`.

O aplicativo Docker Desktop pode permanecer no `C:`. Se também for necessário mover imagens, contêineres e cache globais, abra Docker Desktop → Settings → Resources → Advanced → Disk image location e escolha, por exemplo, `G:\DEV\VOICE_OS\.docker-desktop-data`. Esse ajuste é global para o Docker Desktop e deve ser feito pela interface suportada: <https://docs.docker.com/desktop/settings-and-maintenance/settings/>.

Não desconecte o `G:` enquanto Docker Desktop estiver usando dados armazenados nele.

## O que fica no Git

- Código-fonte, migrações Alembic, `docker-compose.yml`, Dockerfiles e seed idempotente.
- Definição dos sete serviços: `db`, `redis`, `api`, `web`, `agent-worker`, `worker` e `mock`.
- Definição dos bind mounts portáteis `.docker-data/postgres` e `.docker-data/redis`.
- Modelo das variáveis de ambiente em `.env.example`.

Não ficam no Git: `.env`, credenciais de provedores, `.docker-data/` e arquivos em `backups/`. Esses itens ficam fisicamente dentro de `G:\DEV\VOICE_OS`, mas são ignorados por conter dados locais ou confidenciais.

## Alterações realizadas no Docker local

1. O PostgreSQL 16 com pgvector foi exportado com `pg_dump` no formato customizado.
2. A cópia exportada foi validada com `pg_restore --list`.
3. PostgreSQL e Redis deixaram de usar volumes mantidos no disco virtual do Docker Desktop.
4. O backup foi restaurado em `G:\DEV\VOICE_OS\.docker-data\postgres` por meio de bind mount.
5. O Redis foi recriado em `G:\DEV\VOICE_OS\.docker-data\redis`; ele tinha zero chaves antes da migração.
6. Os dois serviços ficaram saudáveis após a migração.
7. `.pytest-tmp/` foi excluído do contexto de build para impedir falhas de permissão causadas por artefatos temporários de teste.
8. A imagem da API foi reconstruída e validada com a revisão Alembic `0010 (head)`.

Validação do PostgreSQL restaurado:

- 40 tabelas no schema `public`;
- `usage_records`: 180 registros;
- `agent_versions`: 90 registros;
- `agents`: 58 registros;
- `calls`: 50 registros;
- `secrets`: 27 registros;
- `memberships`: 22 registros;
- `users`: 1 registro.

Depois da validação do backup, da restauração e do teste de reinicialização, os dois volumes anônimos e os dois volumes nomeados antigos foram removidos. Não restou volume Docker do VoiceOS fora do `G:`.

## Backup atual

Arquivo local, deliberadamente ignorado pelo Git:

```text
backups/postgres/voiceos-homolog-20260827T205425.dump
```

- Tamanho: 128.317 bytes;
- Entradas TOC no arquivo: 224;
- SHA-256: `39AE2E5F5A135DFC2A07CA01DE008AFEE558362250D39EE658E7D08FD3B1D19F`.

O backup contém dados de homologação e registros da tabela `secrets`. Trate-o como confidencial, não o envie ao GitHub e armazene uma segunda cópia em mídia privada antes de formatar ou trocar o computador.

### Gerar um backup atualizado

```powershell
$stamp = Get-Date -Format 'yyyyMMddTHHmmss'
$destino = ".\backups\postgres\voiceos-homolog-$stamp.dump"
New-Item -ItemType Directory -Force .\backups\postgres | Out-Null
docker exec voice_os-db-1 pg_dump -U voiceos -d voiceos -Fc --no-owner --no-privileges -f /tmp/voiceos-export.dump
docker cp voice_os-db-1:/tmp/voiceos-export.dump $destino
docker cp $destino voice_os-db-1:/tmp/voiceos-verify.dump
docker exec voice_os-db-1 pg_restore --list /tmp/voiceos-verify.dump
docker exec voice_os-db-1 rm -f /tmp/voiceos-export.dump /tmp/voiceos-verify.dump
Get-FileHash -Algorithm SHA256 $destino
```

Considere o backup concluído somente se `pg_dump`, as duas cópias e `pg_restore --list` terminarem sem erro.

## Nova instalação com restauração do backup

Pré-requisitos: Git, Docker Desktop com Docker Compose e uma cópia privada do arquivo `.dump`.

No PowerShell:

```powershell
git clone <URL-DO-REPOSITORIO> voice_os
Set-Location voice_os
Copy-Item .env.example .env
```

Preencha o `.env`. Para uma demonstração somente com interface e mocks, mantenha as integrações externas sem uso. Para demonstrar voz ou canais reais, configure as credenciais descritas em `PROVIDER-SETUP-CHECKLIST.md`.

Suba primeiro somente a persistência:

```powershell
New-Item -ItemType Directory -Force .\.docker-data\postgres, .\.docker-data\redis | Out-Null
docker compose pull db redis
docker compose up -d db redis
docker compose ps db redis
```

Copie o backup para o novo repositório em `backups/postgres/` e valide o hash:

```powershell
Get-FileHash -Algorithm SHA256 .\backups\postgres\voiceos-homolog-20260827T205425.dump
```

Restaure o banco novo:

```powershell
docker cp .\backups\postgres\voiceos-homolog-20260827T205425.dump voice_os-db-1:/tmp/voiceos-restore.dump
docker exec voice_os-db-1 pg_restore -U voiceos -d voiceos --clean --if-exists --no-owner --no-privileges /tmp/voiceos-restore.dump
docker exec voice_os-db-1 rm -f /tmp/voiceos-restore.dump
```

A imagem da API precisa ser reconstruída antes do Alembic. Uma imagem antiga pode não conter as revisões que já existem no banco restaurado. Depois, aplique eventuais migrações criadas após o backup e construa os demais serviços:

```powershell
docker compose build api
docker compose run --rm api alembic -c apps/api/alembic.ini upgrade head
docker compose up -d --build api mock web worker agent-worker
docker compose ps
```

Verificações básicas:

```powershell
Invoke-WebRequest http://localhost:8005/health
Invoke-WebRequest http://localhost:3000
Invoke-WebRequest http://localhost:9000/health
```

Portas locais: painel `3000`, API `8005`, agente `8081`, mock `9000`, PostgreSQL `5432` e Redis `6379`.

As funções globais do PostgreSQL não fazem parte de um backup criado apenas com `pg_dump`. A migração `0011` recria de forma idempotente o papel `voiceos_app` e suas permissões após uma restauração em outro mecanismo PostgreSQL.

## Nova instalação sem o backup

Quando os dados históricos não forem necessários, crie o schema e os dados mínimos de demonstração a partir do Git:

```powershell
Copy-Item .env.example .env
docker compose up -d db redis
docker compose build api
docker compose run --rm api alembic -c apps/api/alembic.ini upgrade head
docker compose run --rm api python apps/api/scripts/seed.py
docker compose up -d --build api mock web worker agent-worker
```

O seed cria um tenant, proprietário, agente, base de conhecimento, ferramentas e chamadas demonstrativas. Ele não recria todo o histórico contido no backup.

## O que precisa ser refeito fora do Docker

- Criar o `.env` local e gerar novos segredos de autenticação.
- Reconfigurar credenciais e webhooks dos provedores externos usados na demonstração.
- Recriar projetos/recursos externos que não pertencem ao Compose, como LiveKit Cloud, AWS/S3/KMS, Twilio, Stripe, WhatsApp, Resend, Grafana Cloud e Sentry, quando forem necessários.
- Copiar o backup por um canal privado; ele não acompanha o clone do Git.
- Revalidar URLs de callback, domínios e portas da máquina nova.

## Cuidados

- Os diretórios ativos de PostgreSQL e Redis estão no próprio projeto, em `.docker-data/`.
- `docker compose down` e `docker compose down -v` não removem os diretórios bind-mounted, mas ainda faça backup antes de operações de manutenção.
- O rollback deve ser feito pelo arquivo em `backups/postgres/`; os volumes Docker antigos já foram removidos.
- Imagens e cache de build não são fonte de verdade: reconstrua-os sempre a partir do repositório.
- Nunca remova a unidade `G:` enquanto Docker Desktop ou qualquer contêiner VoiceOS estiver ativo. Execute `docker compose down` e encerre o Docker Desktop antes de ejetá-la.
- Para manter também imagens e cache no `G:`, use Docker Desktop → Settings → Resources → Advanced → Disk image location. Isso é opcional para a portabilidade do projeto, pois esses artefatos são reconstruíveis.
