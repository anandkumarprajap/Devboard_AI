# Step 8 — Clean up

EKS, NLBs, and EBS volumes all cost money. Order matters: the AWS **NLBs** (made
by Envoy from the Gateways) and **EBS volumes** (made by the CSI driver from the
PVCs) must be removed *while those controllers are still running* — `eksctl
delete cluster` won't clean them up for you.

```bash
# 1. Stop ArgoCD from managing the apps (so it can't re-create what we delete).
kubectl delete -f gitops/argocd/devboard-raw.yaml \
               -f gitops/argocd/devboard-helm.yaml \
               -f gitops/argocd/ollama.yaml

# 2. Delete the app namespaces. This removes the Gateways (Envoy then deletes the
#    NLBs) and the PVCs (the EBS CSI driver then deletes the EBS volumes).
kubectl delete namespace devboard devboard-helm ollama --ignore-not-found

# 3. Confirm the load balancers are gone BEFORE deleting the cluster.
kubectl -n envoy-gateway-system get svc     # no LoadBalancer services left
kubectl get gateway -A                       # empty

# 4. (optional) remove the platform pieces.
helm uninstall argocd -n argocd
helm uninstall eg -n envoy-gateway-system

# 5. Delete the cluster (~10-15 min).
eksctl delete cluster -f gitops/eksctl/cluster.yaml
```

Verify nothing is left billing you:
```bash
eksctl get cluster --region us-west-2        # devboard gone
```
Then glance at the AWS console (EC2 → Load Balancers, and Volumes) in `us-west-2`
for any stray `devboard` NLB or EBS volume — if steps 2-3 succeeded, there are none.
