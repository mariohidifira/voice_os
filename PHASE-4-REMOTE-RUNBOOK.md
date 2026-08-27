# Phase 4 Remote Runbook

Status date: 2026-08-25

Objetivo: obter a primeira evidência remota do workflow `phase4-nightly-whatsapp` no GitHub Actions assim que o acesso ao repositório estiver normalizado.

## Estado atual

- o workflow local está pronto em `.github/workflows/phase4-nightly-whatsapp.yml`
- o fluxo local consolidado da Fase 4 já está verde em `reports/phase4-local-acceptance.json`
- neste executor atual, o acesso remoto ainda não está confiável:
  - `gh api user` retornou `401`
  - `gh api repos/mariohidifira/voice_os` retornou `404`
  - `git` para `origin` falhou com `SEC_E_NO_CREDENTIALS`

Conclusão: a próxima lacuna não é funcional no código da Fase 4; é acesso/autenticação ao repositório remoto e publicação das mudanças.

## Pré-requisitos para a primeira execução remota

- o repositório `mariohidifira/voice_os` precisa existir e ser acessível com as credenciais atuais
- as mudanças locais precisam estar publicadas no branch remoto desejado
- GitHub Actions precisa estar habilitado no repositório
- `gh` precisa responder com autenticação válida para REST/GraphQL

## Diagnóstico rápido

No Windows/PowerShell:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/check_phase4_remote_ready.ps1
```

Atalho root equivalente:

```powershell
npm --prefix G:\DEV\VOICE_OS run phase4:remote:ready
```

Em ambientes com GNU Make disponível:

```bash
make phase4-remote-ready
```

Bundle leve para atualizar readiness remoto + sumário consolidado:

```powershell
npm --prefix G:\DEV\VOICE_OS run phase4:evidence:bundle
```

Pacote material de handoff com ZIP + manifesto:

```powershell
npm --prefix G:\DEV\VOICE_OS run phase4:evidence:package
```

Verificação de integridade do pacote material:

```powershell
npm --prefix G:\DEV\VOICE_OS run phase4:evidence:verify
```

Esse script valida:

- URL da `origin`
- acesso REST do `gh` ao usuário autenticado
- acesso REST ao repositório configurado
- listagem de workflows

## Sequência recomendada

1. Confirmar acesso ao repositório:

```powershell
npm --prefix G:\DEV\VOICE_OS run phase4:remote:ready
```

2. Publicar o branch com as mudanças da Fase 4/5.

3. Confirmar que o workflow existe remotamente:

```powershell
gh workflow list --repo mariohidifira/voice_os
```

4. Disparar manualmente:

```powershell
gh workflow run phase4-nightly-whatsapp.yml --repo mariohidifira/voice_os
```

5. Acompanhar a execução:

```powershell
gh run list --repo mariohidifira/voice_os --workflow phase4-nightly-whatsapp.yml --limit 5
gh run watch --repo mariohidifira/voice_os <RUN_ID>
```

6. Baixar e guardar os artefatos:

- `reports/phase4-nightly-whatsapp.xml`
- `reports/phase4-local-acceptance.json`
- `apps/web/playwright-report`
- `apps/web/test-results`

## Critério para marcar essa frente como comprovada

Todos os itens abaixo precisam existir no estado remoto:

- workflow `phase4-nightly-whatsapp` visível no repositório
- ao menos uma execução manual ou agendada concluída com sucesso
- artefato `phase4-nightly-whatsapp` disponível para download
- JSON `reports/phase4-local-acceptance.json` presente no artefato

## Bloqueadores externos conhecidos

- acesso/autenticação inconsistente do `gh`
- `origin` HTTPS exigindo credenciais válidas no Windows
- possível inexistência, renomeação ou privacidade divergente do repositório `mariohidifira/voice_os`

## Próximo passo quando o acesso remoto voltar

Executar primeiro:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/check_phase4_remote_ready.ps1
```

Se tudo estiver verde, publicar e disparar o workflow.

## Artifact verification after download

After downloading and extracting the `phase4-nightly-whatsapp` artifact locally, run:

```powershell
python scripts/verify_phase4_remote_artifact.py <artifact_dir>
```

Expected output artifact:

- `reports/phase4-remote-artifact-verification.json`

This verification should end with:

- `passed: true`
- `reports/phase4-nightly-whatsapp.xml` present
- `reports/phase4-local-acceptance.json` present and reporting `passed: true`
- `reports/phase4-evidence-summary.json` present
- `apps/web/playwright-report` present
- `apps/web/test-results` present
