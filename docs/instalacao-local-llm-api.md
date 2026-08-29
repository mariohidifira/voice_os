# Instalação local com LLM via API externa

Este guia descreve os requisitos e o procedimento para executar o VoiceOS localmente para homologação e demonstração, mantendo a aplicação, o banco de dados e as filas na máquina local e usando provedores externos para LLM, reconhecimento de voz e síntese de voz.

> Neste documento, LLM significa *Large Language Model* (modelo de linguagem de grande porte).

## 1. Arquitetura da instalação

A instalação local executa em contêineres:

- aplicação web;
- API do VoiceOS;
- PostgreSQL;
- Redis;
- workers de tarefas e de voz;
- serviço mock usado pelo ambiente de desenvolvimento.

O processamento dos modelos é realizado por APIs externas. Portanto, não é necessária uma GPU local. A máquina precisa apenas executar os serviços do VoiceOS e ter acesso estável à internet.

## 2. Requisitos da máquina

- Windows 10 ou Windows 11 de 64 bits;
- virtualização habilitada no BIOS/UEFI;
- WSL 2 instalado e habilitado;
- Docker Desktop com Docker Compose;
- Git;
- PowerShell;
- navegador atualizado;
- acesso de saída à internet por HTTPS, porta 443;
- DNS e relógio do sistema funcionando corretamente;
- recomendação prática de pelo menos 16 GB de RAM;
- espaço em disco suficiente para imagens Docker, banco, Redis, logs e backups.

Quando todos os serviços são executados por Docker, não é necessário instalar Python ou Node.js diretamente no Windows.

## 3. Estrutura mantida na unidade G

Todo o material necessário para transportar o projeto deve permanecer em `G:\DEV\VOICE_OS`:

- código-fonte e documentação do repositório;
- arquivo local `.env`;
- dados do PostgreSQL em `.docker-data\postgres`;
- dados do Redis em `.docker-data\redis`;
- backups do PostgreSQL em `backups\postgres`.

O arquivo `.env`, os diretórios de dados e os backups contêm dados locais ou informações sensíveis e não devem ser enviados ao Git.

## 4. Configuração local obrigatória

Crie o `.env` a partir do modelo existente e preencha, no mínimo, as configurações locais:

```env
APP_ENV=dev
APP_BASE_URL=http://localhost:3000
AUTH_URL=http://localhost:3000
AUTH_TRUST_HOST=true
API_BASE_URL=http://localhost:8005
DATABASE_URL=postgresql+asyncpg://voiceos:voiceos@db:5432/voiceos
REDIS_URL=redis://redis:6379/0
AUTH_SECRET=<segredo-com-pelo-menos-32-caracteres>
INTERNAL_API_TOKEN=<outro-segredo-forte-e-diferente>
```

Gere valores exclusivos para `AUTH_SECRET` e `INTERNAL_API_TOKEN`. Não reutilize senhas pessoais nem publique esses valores.

## 5. LLM por API externa

### Provedor principal: Anthropic

```env
ANTHROPIC_API_KEY=<chave-do-projeto>
ANTHROPIC_POSTPROCESS_MODEL=claude-haiku-4-5
```

O runtime de voz usa como modelo principal padrão `claude-sonnet-4-6`. O modelo de pós-processamento pode ser configurado separadamente conforme o exemplo.

### OpenAI para fallback e embeddings

```env
OPENAI_API_KEY=<chave-do-projeto>
```

No projeto, essa chave pode ser usada para:

- LLM de fallback, com `gpt-4.1` como padrão;
- STT de fallback, com `whisper-1` como padrão;
- embeddings e recursos de RAG.

As contas dos provedores precisam ter acesso à API habilitado, saldo ou faturamento configurado e limites de consumo definidos. Para demonstração, use chaves restritas a um projeto exclusivo.

## 6. Recursos de voz completos

Para demonstrar conversação por voz, configure também:

```env
LIVEKIT_URL=wss://...
LIVEKIT_API_KEY=...
LIVEKIT_API_SECRET=...
DEEPGRAM_API_KEY=...
ELEVENLABS_API_KEY=...
ELEVENLABS_VOICE_ID=...
```

Fallbacks opcionais:

```env
OPENAI_API_KEY=...
CARTESIA_API_KEY=...
```

Responsabilidade de cada serviço:

- LiveKit: transporte WebRTC e áudio em tempo real;
- Deepgram: reconhecimento de fala (STT) principal;
- Anthropic: LLM principal;
- OpenAI: LLM e STT de fallback, além de embeddings;
- ElevenLabs: síntese de voz (TTS) principal;
- Cartesia: TTS de fallback.

## 7. Segurança e controle de custos

- mantenha todas as chaves somente no backend e no `.env` local;
- nunca envie chaves ao navegador, Git, imagens Docker ou logs;
- utilize chaves e projetos separados para homologação;
- aplique limites de gasto e alertas em cada provedor;
- conceda somente as permissões necessárias;
- revogue e substitua imediatamente qualquer chave exposta;
- acompanhe consumo e custos durante as demonstrações.

Mocks locais podem permitir uma demonstração sem custo de provedor, mas não representam uma chamada real a LLM, STT ou TTS. O uso das APIs externas normalmente gera cobrança conforme o consumo e as condições vigentes de cada fornecedor.

## 8. Inicialização em uma nova máquina usando os dados da unidade G

Instale o Docker Desktop e o Git na nova máquina, conecte a unidade como `G:` e execute:

```powershell
Set-Location G:\DEV\VOICE_OS
docker desktop start
docker compose up -d db redis
docker compose build api
docker compose run --rm api alembic -c apps/api/alembic.ini upgrade head
docker compose up -d --build api mock web worker agent-worker
docker compose ps
```

Se `.docker-data` estiver íntegro, o PostgreSQL e o Redis reutilizarão os dados armazenados na unidade G. Se os dados estiverem ausentes ou corrompidos, siga o procedimento de restauração descrito em `docs/docker-homologacao.md`.

### Inicialização segura pelo Windows Credential Manager

Para evitar segredos em texto puro no `.env`, instale o suporte ao keyring no Python do Windows:

```powershell
py -m pip install keyring
```

Confira somente a disponibilidade das credenciais, sem mostrar seus valores:

```powershell
Set-Location G:\DEV\VOICE_OS
py scripts\start_local_with_keyring.py --check
```

Inicie a pilha completa carregando as credenciais apenas no ambiente do processo do Docker Compose:

```powershell
py scripts\start_local_with_keyring.py --build
```

ValidaÃ§Ã£o somente de leitura das credenciais comerciais:

```powershell
py scripts\check_external_integrations.py
```

Esse comando consulta identidade na AWS, Twilio e Stripe e nÃ£o cria recursos, chamadas ou cobranÃ§as.

O inicializador aceita os nomes canônicos `VOICEOS.<VARIAVEL>` e os aliases legados já usados localmente. Os valores nunca são impressos nem gravados pelo script. Como ocorre com qualquer segredo fornecido a um contêiner por variável de ambiente, um administrador local do Docker ainda pode inspecionar o ambiente do contêiner.

## 9. Instalação limpa, sem reutilizar os dados existentes

Para criar um ambiente novo:

```powershell
Set-Location G:\DEV\VOICE_OS
Copy-Item .env.example .env
docker compose up -d db redis
docker compose build api
docker compose run --rm api alembic -c apps/api/alembic.ini upgrade head
docker compose run --rm api python apps/api/scripts/seed.py
docker compose up -d --build api mock web worker agent-worker
```

Antes de subir todos os serviços, edite o novo `.env` e inclua os segredos e as chaves dos provedores.

## 10. Validação da instalação

Verifique os serviços básicos:

```powershell
Invoke-WebRequest http://localhost:8005/health
Invoke-WebRequest http://localhost:8005/ready
Invoke-WebRequest http://localhost:3000
Invoke-WebRequest http://localhost:9000/health
```

Depois, valide o fluxo funcional:

- login no ambiente local;
- acesso ao tenant de demonstração;
- criação e publicação de um agente;
- chamada ao LLM principal;
- acionamento do fallback, quando aplicável;
- conexão WebRTC, STT e TTS, quando a voz estiver habilitada;
- registro de uso e custos das chamadas.

## 11. Encerramento antes de remover a unidade G

Sempre encerre os serviços antes de desconectar a unidade externa:

```powershell
Set-Location G:\DEV\VOICE_OS
docker compose down
docker desktop stop
```

Não remova a unidade enquanto o Docker Desktop ou algum contêiner estiver ativo, pois isso pode corromper o banco de dados ou o sistema de arquivos.

## 12. Documentos relacionados

- `.env.example`: modelo das variáveis de ambiente;
- `PROVIDER-SETUP-CHECKLIST.md`: checklist de configuração dos provedores;
- `docs/docker-homologacao.md`: backup, restauração, transporte e reprodução do ambiente Docker.
