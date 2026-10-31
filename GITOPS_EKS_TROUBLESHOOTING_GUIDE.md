# Complete End-to-End EKS GitOps Setup & Troubleshooting Guide

This guide documents the complete setup process for running **DevBoard** on **Amazon EKS** using **ArgoCD**, **Helm**, and **Envoy Gateway (Gateway API)**, along with a deep-dive troubleshooting manual covering real-world production errors encountered and solved.

---

## Architecture Overview

```text
  GitHub Repository (Devboard_AI)
      │  (push to `gitops` branch)
      ▼
  ArgoCD Controller (watches `gitops` branch, k8s/ manifests)
      │  (syncs & self-heals)
      ▼
┌────────────────────────────────────────────────────────────────────────┐
│ Amazon EKS Cluster (devboard)                                          │
│                                                                        │
│   AWS Network Load Balancer (NLB)                                      │
│              │                                                         │
│              ▼                                                         │
│   Envoy Gateway (Gateway API: Gateway + HTTPRoute)                     │
│        │                               │                               │
│        ▼ (path: `/api/ai/*`)           ▼ (path: `/`)                   │
│   ai-service (Flask :3005)        frontend (React :4173)               │
│        │                               │                               │
│        │ (internal: `backend:8080`)    ▼ (internal `/api/*` proxy)     │
│        └─────────────────────────▶ backend (Go Gin :8080)              │
│                                        │                               │
│                                        ▼ (`postgres:5432`)             │
│                                   postgres (StatefulSet + EBS gp2 PVC) │
└────────────────────────────────────────────────────────────────────────┘
```

---

## Phase 1: EC2 Jumpbox / Controller Setup

### Step 1: Install AWS CLI v2
```bash
sudo apt-get update && sudo apt-get install -y unzip curl
curl -sL "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o awscliv2.zip
unzip -q awscliv2.zip && sudo ./aws/install
rm -rf awscliv2.zip aws

# Verify installation
aws --version
```

### Step 2: Configure AWS Credentials
```bash
aws configure
# AWS Access Key ID: <YOUR_ACCESS_KEY>
# AWS Secret Access Key: <YOUR_SECRET_KEY>
# Default region name: us-west-2
# Default output format: json
```

Verify identity via AWS STS:
```bash
aws sts get-caller-identity
```
Expected output:
```json
{
    "UserId": "AIDAX5PKORNXSYJ2JNA7V",
    "Account": "544341920623",
    "Arn": "arn:aws:iam::544341920623:user/anand-user"
}
```

### Step 3: Required IAM Policies
Ensure your IAM user or role has the following AWS policies attached:
- `AdministratorAccess` (or scoped equivalent)
- `AmazonEC2FullAccess`
- `AmazonS3FullAccess`
- `AmazonVPCFullAccess`
- `IAMFullAccess` (required by `eksctl` for OIDC role creation)

---

## Phase 2: Tooling Installation (eksctl, kubectl, helm)

### Step 1: Install `eksctl`
```bash
curl -sLO "https://github.com/eksctl-io/eksctl/releases/latest/download/eksctl_$(uname -s)_amd64.tar.gz"
tar -xzf eksctl_*.tar.gz && sudo mv eksctl /usr/local/bin
rm -f eksctl_*.tar.gz

eksctl version
```

### Step 2: Install `kubectl`
```bash
curl -sLO "https://dl.k8s.io/release/$(curl -sL https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl"
sudo install -m 0755 kubectl /usr/local/bin/kubectl
rm -f kubectl

kubectl version --client
```

### Step 3: Install `helm` (Helm 3)
```bash
curl -fsSL https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3 | bash

helm version
```

---

## Phase 3: EKS Cluster Provisioning

You can create the EKS cluster using either the CLI flag method or the declarative YAML method.

### Option A: Quick CLI Creation
```bash
eksctl create cluster \
  --name devboard \
  --version 1.34 \
  --region us-west-2 \
  --nodegroup-name standard-workers \
  --node-type t3.medium \
  --nodes 3 \
  --nodes-min 2 \
  --nodes-max 3 \
  --managed
```

### Option B: Declarative Cluster YAML (`eks-config/cluster.yml`)
Create `eks-config/cluster.yml`:
```yaml
apiVersion: eksctl.io/v1alpha5
kind: ClusterConfig

metadata:
  name: devboard
  region: us-west-2

iam:
  withOIDC: true

managedNodeGroups:
  - name: ng-default
    instanceType: t3.medium
    desiredCapacity: 3
    minSize: 2
    maxSize: 3
    volumeSize: 20
    ssh:
      enableSsm: true

addons:
  - name: vpc-cni
  - name: coredns
  - name: kube-proxy
  - name: aws-ebs-csi-driver
    wellKnownPolicies:
      ebsCSIController: true
  - name: metrics-server
```

Deploy the cluster:
```bash
eksctl create cluster -f eks-config/cluster.yml
```

Verify cluster nodes:
```bash
kubectl get nodes -o wide
```

---

## Phase 4: Modern Gateway API Setup (Envoy Gateway)

The Gateway API is the modern, expressive replacement for deprecated Ingress. It decouples the load balancer definition (`Gateway`) from traffic routing rules (`HTTPRoute`).

### Step 1: Install Envoy Gateway via Helm
```bash
helm install eg oci://docker.io/envoyproxy/gateway-helm \
  --version v1.2.1 \
  -n envoy-gateway-system \
  --create-namespace

# Wait for controller rollout
kubectl -n envoy-gateway-system rollout status deploy/envoy-gateway
```

### Step 2: Register GatewayClass
Ensure `gitops/gateway/gatewayclass.yaml` is applied:
```yaml
apiVersion: gateway.networking.k8s.io/v1
kind: GatewayClass
metadata:
  name: envoy
spec:
  controllerName: gateway.envoyproxy.io/gatewayclass-controller
```
```bash
kubectl apply -f gitops/gateway/gatewayclass.yaml
kubectl get gatewayclass
```

---

## Phase 5: ArgoCD Installation & Configuration

### Step 1: Add ArgoCD Helm Repository
```bash
helm repo add argo https://argoproj.github.io/argo-helm
helm repo update
```

### Step 2: Install ArgoCD with Plain HTTP Support
`gitops/argocd/install-values.yaml`:
```yaml
configs:
  params:
    server.insecure: true
```

Install the Helm chart:
```bash
helm install argocd argo/argo-cd \
  -n argocd \
  --create-namespace \
  -f gitops/argocd/install-values.yaml

kubectl -n argocd rollout status deploy/argocd-server
```

### Step 3: Run Resilient Background Port-Forward
To access the ArgoCD Web UI externally from your browser:
```bash
nohup kubectl -n argocd port-forward --address 0.0.0.0 svc/argocd-server 8080:80 > /tmp/argocd-port-forward.log 2>&1 &
```
> [!IMPORTANT]
> In your EC2 Security Group (e.g. `gitops-server`), add an **Inbound Rule**:
> - **Type**: Custom TCP
> - **Port**: `8080`
> - **Source**: `My IP` (or `0.0.0.0/0` for testing)

### Step 4: Retrieve Admin Password
```bash
kubectl -n argocd get secret argocd-initial-admin-secret \
  -o jsonpath='{.data.password}' | base64 -d ; echo
```
Open in browser: `http://<EC2_PUBLIC_IP>:8080`
- **Username**: `admin`
- **Password**: *(output from above)*

---

## Phase 6: ArgoCD Application Registration (GitOps)

Save the application definition to `gitops/argocd/application.yml`:
```yaml
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: devboard
  namespace: argocd
spec:
  project: default

  source:
    repoURL: https://github.com/anandkumarprajap/Devboard_AI.git
    targetRevision: gitops
    path: k8s

  destination:
    server: https://kubernetes.default.svc
    namespace: devboard

  # Prevent ArgoCD selfHeal from conflicting with HPA replica autoscaling
  ignoreDifferences:
    - group: apps
      kind: Deployment
      jsonPointers:
        - /spec/replicas

  syncPolicy:
    automated:
      prune: true
      selfHeal: true
    syncOptions:
      - CreateNamespace=true
```

Apply the application:
```bash
kubectl apply -f gitops/argocd/application.yml
```

---

## Phase 7: Comprehensive Troubleshooting Guide

This section documents the actual errors faced in production and how to fix them.

### 1. Error: `SyncError: Failed last sync attempt to []: Invalid operation request: no operation specified`

#### Symptom:
ArgoCD UI shows a red status condition:
```text
Application conditions:
SyncError
Failed last sync attempt to []: Invalid operation request: no operation specified
```

#### Root Cause:
In ArgoCD's controller (`controller/sync.go`), an operation was registered in the Application CR without an `operation.sync` payload:
- Calling `POST /api/v1/applications/<app>/sync` without passing a JSON body (`{"revision": "gitops"}`).
- Clicking sync in UI followed by an interrupted/canceled sync.
- The controller encounters `app.Operation.Sync == nil` and flags `OperationError`. Because `revision` is nil, it renders `Failed last sync attempt to []:`.

#### Resolution:
Clear the stuck operation and force a hard refresh:
```bash
# Clear stuck operation state
kubectl patch application devboard -n argocd --type=json -p '[{"op": "remove", "path": "/status/operationState"}]'
kubectl patch application devboard -n argocd --type=merge -p '{"operation": null}'

# Hard refresh the application
kubectl annotate application devboard -n argocd argocd.argoproj.io/refresh=hard --overwrite
```

To trigger sync via the REST API with an API token:
```bash
curl -k -X POST "http://localhost:8080/api/v1/applications/devboard/sync" \
  -H "Authorization: Bearer <ARGOCD_TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{
    "revision": "gitops",
    "prune": true,
    "strategy": {
      "apply": {
        "force": true
      }
    }
  }'
```

---

### 2. Error: `The Service "postgres" is invalid: spec.clusterIP: field is immutable`

#### Symptom:
ArgoCD fails to sync `postgres-service.yml` with:
```text
The Service "postgres" is invalid: spec.clusterIP: Invalid value: "": field is immutable
```

#### Root Cause:
1. `postgres` was initially created as a standard Service with an allocated ClusterIP (e.g. `10.100.63.248`).
2. The manifest was later edited to specify `clusterIP: None` (Headless Service).
3. Kubernetes does NOT allow converting an allocated `ClusterIP` to `None` (or vice-versa).
4. Postgres is a `StatefulSet` (`serviceName: postgres`), which **requires** a headless service for DNS records (`postgres-statefulset-0.postgres.devboard.svc.cluster.local`).

#### Resolution:
Delete the old service and let ArgoCD / kubectl recreate the headless service:
```bash
kubectl delete svc postgres -n devboard
kubectl apply -f k8s/postgres-service.yml
```

Ensure `k8s/postgres-service.yml` is headless:
```yaml
kind: Service
apiVersion: v1
metadata:
  name: postgres
  namespace: devboard
spec:
  clusterIP: None
  publishNotReadyAddresses: true
  selector:
    app: devboard-postgres
  ports:
  - protocol: TCP
    port: 5432
    targetPort: 5432
```

---

### 3. Error: Why `Replace=true` Breaks Deployments

#### Symptom:
Adding `syncOptions: [Replace=true]` in `Application` or `argocd.argoproj.io/sync-options: Replace=true` causes resources to enter `OutOfSync` or fail with `NotFound`.

#### Root Cause:
`Replace=true` forces ArgoCD to execute `kubectl replace` instead of `kubectl apply`:
- If a resource does not yet exist in the cluster, `kubectl replace` throws `NotFound`.
- `kubectl replace` cannot bypass immutable fields (e.g., `spec.clusterIP` on Service or `volumeClaimTemplates` on StatefulSets).

#### Resolution:
Remove `Replace=true` across all manifests and application specs:
```bash
kubectl patch application devboard -n argocd --type=merge -p '{"spec":{"syncPolicy":{"syncOptions":["CreateNamespace=true"]}}}'
```

---

### 4. Error: `CreateContainerConfigError: secret "devboard-secrets" not found`

#### Symptom:
Backend pod fails to start:
```text
pod/devboard-backend-deployment-xxx 0/1 CreateContainerConfigError
kubelet: spec.containers{devboard-backend}: Error: secret "devboard-secrets" not found
```

#### Root Cause:
The `devboard-secrets` secret was missing or deleted while the deployment was rolling out.

#### Resolution:
1. Apply the secret:
   ```bash
   kubectl apply -f k8s/secrets.yml
   ```
2. Restart the deployment so pods re-read the secret:
   ```bash
   kubectl rollout restart deployment devboard-backend-deployment -n devboard
   ```

---

### 5. Error: HPA `Degraded: unable to fetch metrics from resource metrics API`

#### Symptom:
ArgoCD marks the application as `Degraded` because `devboard-frontend-hpa` shows:
```text
the HPA was unable to compute the replica count: failed to get cpu utilization: unable to fetch metrics from resource metrics API (get pods.metrics.k8s.io)
```

#### Root Cause:
EKS does not install `metrics-server` out of the box.

#### Resolution:
Deploy the official Kubernetes metrics-server:
```bash
kubectl apply -f https://github.com/kubernetes-sigs/metrics-server/releases/latest/download/components.yaml
kubectl rollout status deploy/metrics-server -n kube-system
```

Verify HPA is now receiving metrics:
```bash
kubectl get hpa -n devboard
# NAME                    REFERENCE                                 TARGETS        MINPODS   MAXPODS   REPLICAS
# devboard-frontend-hpa   Deployment/devboard-frontend-deployment   cpu: 10%/60%   1         5         1
```

---

### 6. Error: Port-Forward Dropping or Refusing Remote Connections

#### Symptom:
`http://<EC2_IP>:8080` times out or actively refuses connection.

#### Root Cause:
1. Running `kubectl port-forward svc/argocd-server 8080:80` without `--address 0.0.0.0` binds only to `127.0.0.1` (localhost).
2. When the SSH session disconnects, foreground port-forward processes terminate.
3. EC2 Security Group lacks inbound rule for port 8080.

#### Resolution:
Run port-forward with `nohup` on `0.0.0.0`:
```bash
nohup kubectl -n argocd port-forward --address 0.0.0.0 svc/argocd-server 8080:80 > /tmp/argocd-port-forward.log 2>&1 &
```
Verify port is actively listening:
```bash
sudo ss -tlpn | grep 8080
# LISTEN 0 4096 0.0.0.0:8080 0.0.0.0:* users:(("kubectl",pid=...,fd=...))
```

---

## Phase 8: Verification & Health Check

Run these verification commands on the controller host:

```bash
# Check all devboard workloads
kubectl get pods,svc,statefulset,hpa -n devboard

# Check ArgoCD application status
kubectl get application devboard -n argocd

# Get the AWS NLB public endpoint
ADDR=$(kubectl -n devboard get gateway devboard-gateway -o jsonpath='{.status.addresses[0].value}')
echo "App Public URL: http://$ADDR/"

# Test HTTP response
curl -s -I "http://$ADDR/" | head -n 5

# Test Postgres seeded data through Backend API
curl -s "http://$ADDR/api/projects"
```

Expected API response:
```json
{
  "projects": [
    {
      "id": 1,
      "name": "DevBoard MVP",
      "description": "Ship the v1 task tracker",
      "owner_id": 1,
      "created_at": "2026-10-31T11:17:08Z"
    },
    {
      "id": 2,
      "name": "Marketing Site",
      "description": "Landing page + launch blog",
      "owner_id": 1,
      "created_at": "2026-10-31T11:17:08Z"
    }
  ]
}
```
All components are **Synced**, **Healthy**, and **Live**!
