# Step 1 — Prerequisites

## Tools

| Tool | Purpose |
|------|---------|
| `awscli` | talk to AWS |
| `eksctl` | create/delete the cluster |
| `kubectl` | talk to the cluster |
| `helm` | install ArgoCD & render the chart |

macOS:
```bash
brew install awscli eksctl kubernetes-cli helm
```

Linux (amd64):
```bash
# eksctl
curl -sLO "https://github.com/eksctl-io/eksctl/releases/latest/download/eksctl_$(uname -s)_amd64.tar.gz"
tar -xzf eksctl_*.tar.gz && sudo mv eksctl /usr/local/bin

# awscli v2
curl -sL "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o awscliv2.zip
unzip -q awscliv2.zip && sudo ./aws/install

# kubectl
curl -sLO "https://dl.k8s.io/release/$(curl -sL https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl"
sudo install -m 0755 kubectl /usr/local/bin/kubectl

# helm
curl -fsSL https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3 | bash
```

> On ARM (Graviton EC2, ARM laptops), swap `amd64` → `arm64` in the eksctl and
> kubectl URLs and use `awscli-exe-linux-aarch64.zip`. The Helm script
> auto-detects the architecture.

## Configure AWS

You need an IAM user/role that can create EKS (EKS + CloudFormation + EC2 + IAM;
`AdministratorAccess` is simplest for learning).

```bash
aws configure          # region: us-west-2
aws sts get-caller-identity   # must succeed
```

All docs use **us-west-2**. To change it, edit both `aws configure` and
`gitops/eksctl/cluster.yaml`.

Next: [02-create-eks.md](02-create-eks.md)
