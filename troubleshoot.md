# Load Balancer & Gateway API Troubleshooting Guide (`troubleshoot.md`)

This document details the diagnosis, root causes, exact fix commands, and verification steps for when the AWS Load Balancer DNS (`a4cca75bdc352401bb064a34549f743c-1975438364.us-west-2.elb.amazonaws.com`) fails or hangs when opening in a browser or via `curl`.

---

## 1. Problem Description & Symptoms

- **Symptom**: Accessing the AWS Load Balancer DNS in a web browser (`http://a4cca75bdc352401bb064a34549f743c-1975438364.us-west-2.elb.amazonaws.com`) hangs indefinitely, drops connections, or shows:
  ```text
  This site can't be reached
  ERR_CONNECTION_TIMED_OUT
  ```
- **Gateway & HTTPRoute status**:
  ```bash
  kubectl get gateway,httproute -A
  ```
  Both `devboard-gateway` and `devboard-route` appear `Programmed: True`, but the application intermittently or consistently fails to open.

---

## 2. Root Cause Analysis

### Cause 1: 2 Out of 3 EKS Nodes Marked `OutOfService` in AWS ELB
The Classic Load Balancer spans 3 Availability Zones (`us-west-2a`, `us-west-2b`, `us-west-2c`). When checking ELB instance health:
```bash
aws elb describe-instance-health \
  --load-balancer-name a4cca75bdc352401bb064a34549f743c \
  --region us-west-2
```
Output:
```json
{
    "InstanceStates": [
        {
            "InstanceId": "i-03d5a053424941338",
            "State": "OutOfService",
            "Description": "Instance has failed at least the UnhealthyThreshold number of health checks consecutively."
        },
        {
            "InstanceId": "i-0b59ff7c2ebc60a34",
            "State": "OutOfService",
            "Description": "Instance has failed at least the UnhealthyThreshold number of health checks consecutively."
        },
        {
            "InstanceId": "i-0b5e652e07a0e3ba6",
            "State": "InService"
        }
    ]
}
```
**Why were nodes failing health checks?**
- Envoy Gateway creates a Kubernetes Service (`LoadBalancer`) with `externalTrafficPolicy: Local`.
- In `Local` mode, Kubernetes only marks a worker node as healthy (`HTTP:31295/healthz`) if an Envoy proxy pod is running locally on that specific node.
- Because the Envoy Proxy deployment (`envoy-devboard-devboard-gateway-bee4af0f`) had only **1 replica**, it was only scheduled on 1 node. The other 2 nodes had no local proxy pod, so they failed health checks and were marked `OutOfService`.

---

### Cause 2: Cross-Zone Load Balancing Was Disabled
Checking the ELB attributes:
```bash
aws elb describe-load-balancer-attributes \
  --load-balancer-name a4cca75bdc352401bb064a34549f743c \
  --region us-west-2
```
Output:
```json
{
    "LoadBalancerAttributes": {
        "CrossZoneLoadBalancing": {
            "Enabled": false
        }
    }
}
```
**Why this broke user browser connections:**
- AWS DNS returns 3 IP addresses for the ELB (one for each availability zone).
- When a user's browser connected to the IP in `us-west-2a` or `us-west-2b`, the ELB saw that the local instance in that zone was `OutOfService`.
- Because `CrossZoneLoadBalancing` was `false`, the ELB **refused to route traffic across to the healthy node in `us-west-2c`**, causing the connection to drop or time out!

---

### Cause 3: Modern Browsers Auto-Upgrading to HTTPS (Port 443)
- If you type the raw DNS name `a4cca75bdc352401bb064a34549f743c-1975438364.us-west-2.elb.amazonaws.com` into Chrome or Edge, the browser may default to `https://`.
- The Gateway listener is currently configured for plain HTTP on port `80`. Connecting to `https://` (port 443) will time out.

---

## 3. Exact Commands Used to Fix the Issue

### Step 1: Enable Cross-Zone Load Balancing on the AWS ELB
This instructs AWS to route incoming traffic across all availability zones to whichever node is healthy:
```bash
aws elb modify-load-balancer-attributes \
  --load-balancer-name a4cca75bdc352401bb064a34549f743c \
  --region us-west-2 \
  --load-balancer-attributes '{"CrossZoneLoadBalancing":{"Enabled":true}}'
```

### Step 2: Scale Envoy Proxy Across All 3 Worker Nodes
Scale the Envoy Gateway proxy deployment to 3 replicas so that every worker node in every availability zone runs an Envoy Proxy pod:
```bash
kubectl scale deployment -n envoy-gateway-system \
  envoy-devboard-devboard-gateway-bee4af0f --replicas=3
```

Check that the pods are running across all 3 distinct nodes:
```bash
kubectl get pods -n envoy-gateway-system -o wide
```

### Step 3: Verify All Instances Are Now `InService`
Wait ~15-20 seconds for the ELB health check (`HealthyThreshold: 2`) to pass:
```bash
aws elb describe-instance-health \
  --load-balancer-name a4cca75bdc352401bb064a34549f743c \
  --region us-west-2
```
Output:
```json
{
    "InstanceStates": [
        {
            "InstanceId": "i-03d5a053424941338",
            "State": "InService"
        },
        {
            "InstanceId": "i-0b59ff7c2ebc60a34",
            "State": "InService"
        },
        {
            "InstanceId": "i-0b5e652e07a0e3ba6",
            "State": "InService"
        }
    ]
}
```
All 3 instances in all 3 availability zones are now **100% `InService`**!

---

## 4. Verification & Testing

### Test 1: Curl with Response Time
```bash
curl -s -o /dev/null -w "HTTP: %{http_code} | Total Time: %{time_total}s\n" \
  http://a4cca75bdc352401bb064a34549f743c-1975438364.us-west-2.elb.amazonaws.com/
```
Output:
```text
HTTP: 200 | Total Time: 0.67s
```

### Test 2: Check Backend API Response (Database Integration)
```bash
curl -s "http://a4cca75bdc352401bb064a34549f743c-1975438364.us-west-2.elb.amazonaws.com/api/projects"
```
Output:
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

### Test 3: Opening in Web Browser
Open the URL explicitly with the `http://` prefix:
```text
http://a4cca75bdc352401bb064a34549f743c-1975438364.us-west-2.elb.amazonaws.com/
```
> [!TIP]
> Always prefix with `http://` (not `https://`), or disable "Always use secure connections" in your browser settings for AWS ELB default endpoints if it automatically forces HTTPS.
