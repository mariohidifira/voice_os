# 10 — Billing

## Planos (seed inicial; valores em BRL na UI, cobrança via Stripe em BRL)

| code | preço/mês | minutos inclusos | excedente/min | agentes | chamadas simultâneas | recursos |
|---|---|---|---|---|---|---|
| `trial` | 0 | 60 (uma vez, 14 dias) | bloqueado | 1 | 2 | web apenas |
| `starter` | R$ 297 | 500 | R$ 0,79 | 2 | 5 | web + telefone |
| `pro` | R$ 897 | 2.000 | R$ 0,69 | 10 | 20 | + campanhas, API, webhooks, QA |
| `business` | R$ 2.497 | 7.000 | R$ 0,59 | ilimitado | 50 | + WhatsApp, white-label, SLA |
| `enterprise` | sob consulta | negociado | negociado | ilimitado | negociado | tudo + contrato |

Números de telefone: R$ 39/mês cada (repasse Twilio + margem), cobrado como item de assinatura por quantidade. SMS: R$ 0,25/msg como uso medido.

## Medição
- Unidade: segundo faturável arredondado para cima em minutos por chamada (`ceil(billable_seconds/60)`), onde `billable_seconds = ended_at - answered_at` (telefone) ou `ended_at - started_at` (web). WhatsApp: cada mensagem de áudio processada = 0,5 min; texto = 0,25 min (equivalência de custo).
- Ao `call.ended`, `worker` cria `usage_records`. Job horário agrega e envia `usage_record` ao Stripe (metered price do excedente) só para o que exceder `included_minutes` no período.
- `GET /v1/billing/usage` calcula em tempo real a partir de `usage_records`.

## Stripe
- Products/prices criados por script `make stripe-sync` a partir de `plans`.
- Assinatura = price fixo mensal + price metered (excedente) + price por quantidade (números).
- Checkout Session para upgrade; Customer Portal para cartão, cancelamento, faturas.
- Métodos: cartão e Pix (Pix só para pagamento avulso do ciclo; Stripe suporta em assinatura via `pix` com fatura enviada). Se Pix não pago em 3 dias → `past_due`.
- Webhooks tratados: `checkout.session.completed`, `customer.subscription.updated|deleted`, `invoice.paid`, `invoice.payment_failed`.

## Limites e suspensão
- Ao criar sessão/chamada, API verifica: plano ativo, chamadas simultâneas < limite, agentes ≤ limite. Excedeu → 402 `plan_limit` com detalhes.
- Trial esgotado (minutos ou 14 dias) → `tenants.status=trial` bloqueia novas chamadas; painel mostra upgrade.
- `invoice.payment_failed` → e-mail; após 7 dias em `past_due` → `suspended` (números permanecem 30 dias, depois liberados com aviso).
- Aviso de uso: webhook `usage.threshold` e e-mail em 80% e 100% dos minutos inclusos.

## Custo interno x margem
Dashboard admin mostra por tenant: minutos, custo real (`calls.cost` somado + LiveKit + Twilio) e receita. Alerta se margem bruta de um tenant < 40% no mês.
