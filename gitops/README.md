# DevBoard on EKS — GitOps with ArgoCD, Helm & Gateway API

Deploy DevBoard (React + Go + Postgres) to a real EKS cluster, GitOps-style, and
add a self-hosted AI feature. No Terraform — just `eksctl` and Kubernetes.

You'll set up:
- **EKS** via `eksctl` (one YAML file)
- **Envoy Gateway** for a public URL (Gateway API → AWS NLB)
- **ArgoCD** deploying the app from this Git branch — **two ways**: raw manifests
  (`k8s/`) and a Helm chart (`helm/devboard/`)
- **AI Assistant** — an in-cluster model (Ollama) that summarises/answers about your tasks

## Architecture

```
Internet ─▶ Envoy Gateway (NLB) ─▶ frontend ─┬─ /api    ─▶ backend ─▶ postgres
                                              └─ /api/ai ─▶ ai-service ─▶ Ollama
```
The frontend proxies `/api` to the backend internally, so the Gateway only points at the frontend.

## Steps

| # | File | What |
|---|------|------|
| 1 | [01-prerequisites.md](01-prerequisites.md) | Install tools, configure AWS |
| 2 | [02-create-eks.md](02-create-eks.md) | Create the cluster |
| 3 | [03-gateway-api.md](03-gateway-api.md) | Install Envoy Gateway |
| 4 | [04-argocd.md](04-argocd.md) | Install ArgoCD |
| 5 | [05-deploy-without-helm.md](05-deploy-without-helm.md) | Deploy from raw manifests |
| 6 | [06-package-with-helm.md](06-package-with-helm.md) | Tour the Helm chart |
| 7 | [07-deploy-with-helm.md](07-deploy-with-helm.md) | Deploy from the chart |
| 8 | [08-cleanup.md](08-cleanup.md) | Tear it all down |
| 9 | [09-ai-feature.md](09-ai-feature.md) | Add the AI Assistant |
| 10 | [10-cicd.md](10-cicd.md) | CI/CD pipeline (GitHub Actions → ArgoCD) |

## Cost

EKS is not free: control plane + 3 × t3.medium + one NLB per Gateway + EBS ≈ a
few USD/day. **Do [08-cleanup.md](08-cleanup.md) when you're done.**

## Layout

```
gitops/eksctl/cluster.yaml   the cluster definition
gitops/gateway/              GatewayClass
gitops/ollama/               shared in-cluster model server
gitops/argocd/               ArgoCD install values + Applications
helm/devboard/               the Helm chart
k8s/                         raw manifests
ai-service/                  the AI microservice (Python/Flask)
```
