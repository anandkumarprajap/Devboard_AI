# Step 4 — Install ArgoCD

ArgoCD is the GitOps engine: point it at a repo + path and it keeps the cluster
matching Git.

```bash
helm repo add argo https://argoproj.github.io/argo-helm
helm repo update
helm install argocd argo/argo-cd -n argocd --create-namespace \
  -f gitops/argocd/install-values.yaml
kubectl -n argocd rollout status deploy/argocd-server
```
(`install-values.yaml` sets `server.insecure: true` so the port-forward below
works over plain HTTP. Add TLS for real use.)

## Log in

```bash
# initial admin password
kubectl -n argocd get secret argocd-initial-admin-secret \
  -o jsonpath='{.data.password}' | base64 -d ; echo

# UI
kubectl -n argocd port-forward svc/argocd-server 8080:80
```
Open http://localhost:8080 → user `admin` + that password.

We register apps by `kubectl apply`-ing `Application` manifests (that's GitOps),
not by clicking in the UI. That's the next step.

Next: [05-deploy-without-helm.md](05-deploy-without-helm.md)
