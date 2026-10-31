# Step 2 — Create the EKS cluster

The whole cluster is defined in [eksctl/cluster.yaml](eksctl/cluster.yaml):
`us-west-2`, 3 × t3.medium nodes, OIDC, and add-ons (incl. `aws-ebs-csi-driver`
for Postgres storage and `metrics-server` for the HPA).

```bash
eksctl create cluster -f gitops/eksctl/cluster.yaml     # ~15-20 min
```

eksctl points `kubectl` at the new cluster automatically. Verify:

```bash
kubectl get nodes                 # 3 Ready
kubectl get storageclass          # gp2 present
kubectl -n kube-system get pods | grep -E 'ebs-csi|metrics-server'
```

## Make gp2 the default StorageClass

EKS does **not** mark `gp2` as default, and Postgres' PVC relies on a default —
without this it stays `Pending`.

```bash
kubectl patch storageclass gp2 \
  -p '{"metadata":{"annotations":{"storageclass.kubernetes.io/is-default-class":"true"}}}'
kubectl get storageclass          # now shows "gp2 (default)"
```

Next: [03-gateway-api.md](03-gateway-api.md)
