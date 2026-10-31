# Step 6 — Package with Helm

Raw manifests hard-code every value across many files. Helm packages the same app
as a chart with one [`values.yaml`](../helm/devboard/values.yaml) you tune per
environment. Chart: [`../helm/devboard/`](../helm/devboard/).

```
helm/devboard/
  Chart.yaml
  values.yaml            images, replicas, resources, DB creds, gateway, ai
  files/                 Postgres init SQL
  templates/
    _helpers.tpl
    configmap.yaml  secret.yaml
    postgres-*.yaml  backend-*.yaml  frontend-*.yaml  frontend-hpa.yaml
    ai-service-deployment.yaml  ai-service-service.yaml
    gateway.yaml  httproute.yaml  NOTES.txt
```

Two things worth knowing:
- The backend reads one `POSTGRES_URL`; `secret.yaml` builds it from
  `postgres.user/password/db` (one source of truth).
- `backend.serviceName` must stay `backend` — the frontend image proxies to
  `http://backend:8080`.

Render it locally (what ArgoCD does under the hood):
```bash
helm lint helm/devboard
helm template devboard helm/devboard | less
helm template devboard helm/devboard --set frontend.replicas=3 | grep replicas
```

Next: [07-deploy-with-helm.md](07-deploy-with-helm.md)
