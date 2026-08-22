# Relatório da Fase 3 — Billing, API pública, qualidade e LGPD

Status: **em implementação**. A integração está pronta para Stripe test, mas as credenciais `STRIPE_SECRET_KEY` e `STRIPE_WEBHOOK_SECRET` permanecem **pendentes e não bloqueantes**; o ciclo externo só será aprovado após homologação.

## Billing implementado e validado localmente

- Catálogo dos cinco planos conforme o spec, em BRL, com minutos, excedente, agentes, concorrência e features.
- Migration `0007` para prices Stripe e índices de reconciliação; migration `0008` para itens de excedente/números e controle de `past_due`.
- Medição idempotente por chamada encerrada em `usage_records`, com arredondamento por chamada.
- Endpoints de plano, uso em tempo real, faturas, checkout e Customer Portal.
- Webhook Stripe com assinatura, checkout, subscription update/delete e invoice paid/failed.
- Job horário de excedente incremental, quantidade de números e suspensão após sete dias em `past_due`.
- Limites `402 plan_limit` para agentes, concorrência, feature telefone, trial de 14 dias e minutos.
- Script `make stripe-sync` para produtos e prices fixo, metered e quantidade de números.
- Painel Billing com plano, uso, excedente, upgrades, portal e faturas.

## Evidências atuais

- Testes determinísticos de billing/Stripe: aprovados.
- Reconciliação real em PostgreSQL de chamada → usage, assinatura e fatura: aprovada.
- Alembic local: `0008 (head)`.
- Stripe test real: **pendente de credenciais**.

## Próximos itens da Fase 3

- Avisos 80/100%, e-mail e webhook de saída.
- API pública/webhooks completos, analytics, exports, end-users e admin.
- QA em 100% das chamadas, dashboards/alertas e documentação LGPD.
