---
type: "query"
date: "2026-08-28T00:11:28.323250+00:00"
question: "Qual e o estado final portatil do VoiceOS na unidade G?"
contributor: "graphify"
source_nodes: ["PostgreSQL Tenant Data Model", "RedisEventBus", "Local Docker Compose stack"]
---

# Q: Qual e o estado final portatil do VoiceOS na unidade G?

## Answer

Todo estado especifico do VoiceOS esta em G:\DEV\VOICE_OS: repositorio e .env, backup em backups/postgres, PostgreSQL ativo em .docker-data/postgres e Redis ativo em .docker-data/redis. Os bind mounts foram reiniciados e validados com Alembic 0010, 40 tabelas e 180 usage_records. Os dois volumes anonimos e os dois volumes nomeados antigos foram removidos apos confirmacao de que nenhum container os usava; docker volume ls ficou vazio. O aplicativo Docker Desktop pode permanecer no C. Para mover tambem imagens e cache globais, use Disk image location nas configuracoes do Docker Desktop e nunca desconecte G enquanto Docker estiver ativo.

## Source Nodes

- PostgreSQL Tenant Data Model
- RedisEventBus
- Local Docker Compose stack