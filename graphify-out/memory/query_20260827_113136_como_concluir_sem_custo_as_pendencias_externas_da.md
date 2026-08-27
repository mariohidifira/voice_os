---
type: "query"
date: "2026-08-27T11:31:36.878725+00:00"
question: "Como concluir sem custo as pendencias externas da Phase 5?"
contributor: "graphify"
source_nodes: ["Phase 5 Hosted Asset Runbook", "External delivery verification", "hostedOutfile"]
---

# Q: Como concluir sem custo as pendencias externas da Phase 5?

## Answer

Usar um repositorio publico separado mariohidifira.github.io apenas para o bundle compilado voiceos.js e paginas de teste. GitHub Pages fornece HTTPS gratuito; executar Lighthouse nas paginas baseline e widget e rodar check_phase5_external_delivery.py contra o hostname github.io. Isso conclui o verificador atual sem expor o repositorio privado. Tratar github.io como hostname de staging, nao como dominio proprio; dominio personalizado literal exige um dominio ja possuido ou subdominio gratuito compativel.

## Source Nodes

- Phase 5 Hosted Asset Runbook
- External delivery verification
- hostedOutfile